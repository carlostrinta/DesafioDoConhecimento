"""
Janela modal do Editor de Perguntas (Etapa E2).

Integra a lista lateral (`ui_editor_lista`), o formulário
(`ui_editor_form`) e o modelo puro (`editor_modelo.BancoEditavel`).

Responsabilidades desta camada:
- atalhos F3/Esc, Ctrl+S, Ctrl+Z e Ctrl+Y;
- debounce das edições para não criar um undo por tecla;
- salvamento seguro, “Salvar como cópia” e confirmações;
- bloqueio de abertura durante uma rodada (verificado pelo chamador);
- devolver o banco (e o caminho) ao fechar, para o jogo recarregar.

Nenhuma regra de validação ou de gravação é reimplementada aqui: tudo passa
por `perguntas.validar_*`, `BancoEditavel` e as funções de `editor_modelo`.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

import editor_modelo as em
from editor_modelo import BancoEditavel, PerguntaEditavel
from ui_componentes import Cor
from ui_editor_form import FormularioPergunta
from ui_editor_lista import ListaPerguntasEditor

INTERVALO_DEBOUNCE_MS = 400


class EditorPerguntas(tk.Toplevel):
    """Janela modal do editor de perguntas."""

    def __init__(
        self,
        parent,
        banco_atual: Optional[BancoEditavel] = None,
        *,
        ao_fechar: Optional[Callable[[Optional[BancoEditavel]], None]] = None,
        estado_path: Optional[str] = None,
        diretorio_base: Optional[str] = None,
        diretorio_aplicacao: Optional[str] = None,
        pasta_config: Optional[str] = None,
        rodando_partida: bool = False,
        banco_em_uso_caminho: Optional[str] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.ao_fechar = ao_fechar
        self.estado_path = estado_path
        self.diretorio_base = diretorio_base
        self.diretorio_aplicacao = diretorio_aplicacao
        self.pasta_config = pasta_config
        self.rodando_partida = rodando_partida
        self.banco_em_uso_caminho = banco_em_uso_caminho

        self.banco: BancoEditavel = banco_atual or em.criar_banco_novo()
        self._pendente: Optional[tuple[int, dict[str, object]]] = None
        self._job_pendente: Optional[str] = None
        self._mensagem_status = ""
        self._fechando = False
        self._fechado = False
        self._ultimo_caminho_salvo = self.banco.caminho_origem or ""

        self.title("Editor de Perguntas — Desafio do Conhecimento")
        self.configure(bg=Cor.FUNDO)
        self.resizable(True, True)
        self.minsize(880, 560)
        self._dimensionar_inicial()

        try:
            from recursos import caminho_recurso

            ico = caminho_recurso("desafio.ico")
            if os.path.exists(ico):
                self.iconbitmap(ico)
        except Exception:
            pass

        try:
            self.transient(parent)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._confirmar_fechar)

        self._construir_ui()
        self._configurar_atalhos()
        self._centralizar()

        if self.banco.perguntas:
            self.lista.selecionar_indice_banco(0)
        self.lista.focus_busca()

        try:
            self.grab_set()
        except tk.TclError:
            pass
        try:
            self.focus_force()
        except tk.TclError:
            pass

        self._atualizar_status()

    # ──────────────────────────────────────────────────────────
    # Construção da interface
    # ──────────────────────────────────────────────────────────
    def _construir_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Topo: título e nome do banco.
        topo = tk.Frame(self, bg=Cor.PAINEL, padx=16, pady=10)
        topo.grid(row=0, column=0, sticky="ew")
        topo.columnconfigure(0, weight=1)

        tk.Label(
            topo,
            text="Editor de Perguntas",
            font=("Segoe UI", 14, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.PAINEL,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        self.lbl_banco = tk.Label(
            topo,
            text=self._nome_banco(),
            font=("Segoe UI", 9),
            fg=Cor.SUAVE,
            bg=Cor.PAINEL,
            anchor="w",
        )
        self.lbl_banco.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.lbl_aviso_leitura = tk.Label(
            topo,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg=Cor.AVISO,
            bg=Cor.PAINEL,
            anchor="e",
        )
        self.lbl_aviso_leitura.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self._atualizar_aviso_leitura()

        # Corpo: lista + formulário.
        self.painel = tk.Frame(self, bg=Cor.FUNDO)
        self.painel.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.painel.rowconfigure(0, weight=1)
        self.painel.columnconfigure(0, weight=0)
        self.painel.columnconfigure(1, weight=1)

        self.lista = ListaPerguntasEditor(
            self.painel,
            self.banco,
            ao_selecionar=self._ao_selecionar,
            ao_novo=self._ao_novo,
            ao_duplicar=self._ao_duplicar,
            ao_excluir=self._ao_excluir,
            ao_mover=self._ao_mover,
            largura=360,
        )
        self.lista.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        separador = tk.Frame(self.painel, bg=Cor.BORDA, width=2)
        separador.grid(row=0, column=1, sticky="nsw", padx=(0, 6))

        self.formulario = FormularioPergunta(
            self.painel,
            self.banco,
            ao_alterar=self._ao_alterar_campo,
            ao_salvar=self.salvar,
            ao_desfazer=self.desfazer,
            ao_refazer=self.refazer,
        )
        self.formulario.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # Status.
        self.lbl_status = tk.Label(
            self,
            text="",
            font=("Segoe UI", 9),
            fg=Cor.SUAVE,
            bg=Cor.FUNDO,
            anchor="w",
            padx=12,
        )
        self.lbl_status.grid(row=2, column=0, sticky="ew")

        # Rodapé: histórico à esquerda; gravação/fechamento à direita.
        rodape = tk.Frame(self, bg=Cor.PAINEL, padx=12, pady=10)
        rodape.grid(row=3, column=0, sticky="ew")
        rodape.columnconfigure(2, weight=1)

        self.btn_desfazer = tk.Button(
            rodape,
            text="↶ Desfazer",
            command=self.desfazer,
            **self._estilo_botao("#333355", "#555577"),
        )
        self.btn_desfazer.grid(row=0, column=0, padx=(0, 4))

        self.btn_refazer = tk.Button(
            rodape,
            text="↷ Refazer",
            command=self.refazer,
            **self._estilo_botao("#333355", "#555577"),
        )
        self.btn_refazer.grid(row=0, column=1, padx=(0, 4))

        acoes = tk.Frame(rodape, bg=Cor.PAINEL)
        acoes.grid(row=0, column=3, sticky="e")

        self.btn_salvar_como = tk.Button(
            acoes,
            text="💾 Salvar como cópia…",
            command=self.salvar_como_copia,
            **self._estilo_botao("#444488", "#6666AA"),
        )
        self.btn_salvar_como.pack(side="left", padx=4)

        self.btn_salvar = tk.Button(
            acoes,
            text="✓ Salvar (Ctrl+S)",
            command=self.salvar,
            **self._estilo_botao(Cor.A, "#5CB7FF"),
        )
        self.btn_salvar.pack(side="left", padx=4)

        self.btn_fechar = tk.Button(
            acoes,
            text="Fechar (Esc)",
            command=self._confirmar_fechar,
            **self._estilo_botao("#333355", "#555577"),
        )
        self.btn_fechar.pack(side="left", padx=(4, 0))

        self.bind("<Configure>", self._ao_redimensionar)

    @staticmethod
    def _estilo_botao(bg: str, activebackground: str) -> dict:
        return {
            "font": ("Segoe UI", 9, "bold"),
            "fg": Cor.TEXTO,
            "activeforeground": Cor.TEXTO,
            "bg": bg,
            "activebackground": activebackground,
            "relief": "flat",
            "bd": 0,
            "padx": 14,
            "pady": 7,
            "cursor": "hand2",
        }

    def _dimensionar_inicial(self):
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        largura = max(880, min(1280, largura_tela - 80))
        altura = max(560, min(800, altura_tela - 100))
        self.geometry(f"{largura}x{altura}")

    def _centralizar(self):
        self.update_idletasks()
        largura = max(880, self.winfo_width())
        altura = max(560, self.winfo_height())
        try:
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            if pw > 100 and ph > 100:
                x = px + (pw - largura) // 2
                y = py + (ph - altura) // 2
            else:
                raise ValueError
        except (tk.TclError, ValueError):
            x = (self.winfo_screenwidth() - largura) // 2
            y = (self.winfo_screenheight() - altura) // 2
        self.geometry(f"{largura}x{altura}+{max(0, x)}+{max(0, y)}")

    def _ao_redimensionar(self, event):
        if event.widget is not self:
            return
        largura = event.width
        if largura >= 1200:
            alvo = 360
        elif largura >= 1000:
            alvo = 320
        else:
            alvo = 250
        if alvo != self.lista.largura:
            self.lista.largura = alvo
            try:
                self.lista.configure(width=alvo)
            except tk.TclError:
                pass

    def _configurar_atalhos(self):
        self.bind("<F3>", lambda e: self._confirmar_fechar())
        self.bind("<Escape>", lambda e: self._confirmar_fechar())
        self.bind("<Control-s>", lambda e: self.salvar())
        self.bind("<Control-S>", lambda e: self.salvar())
        self.bind("<Control-n>", lambda e: self._ao_novo())
        self.bind("<Control-N>", lambda e: self._ao_novo())
        self.bind("<Control-d>", self._atalho_duplicar)
        self.bind("<Control-D>", self._atalho_duplicar)
        self.bind("<Control-f>", lambda e: self.lista.focus_busca())
        self.bind("<Control-F>", lambda e: self.lista.focus_busca())
        self.bind("<Control-z>", lambda e: self.desfazer())
        self.bind("<Control-Z>", lambda e: self.desfazer())
        self.bind("<Control-y>", lambda e: self.refazer())
        self.bind("<Control-Y>", lambda e: self.refazer())
        self.bind("<Control-Shift-Z>", lambda e: self.refazer())
        self.bind("<Control-Shift-z>", lambda e: self.refazer())
        self.bind("<Alt-Up>", lambda e: self.lista.mover_selecionado(-1))
        self.bind("<Alt-Down>", lambda e: self.lista.mover_selecionado(1))
        self.bind("<Up>", self._atalho_setas)
        self.bind("<Down>", self._atalho_setas)
        self.bind("<Return>", self._atalho_enter)
        self.bind("<KP_Enter>", self._atalho_enter)
        self.bind("<Delete>", self._atalho_excluir)
        self.bind("<MouseWheel>", self._ao_rolar)
        self.bind("<Button-4>", self._ao_rolar)
        self.bind("<Button-5>", self._ao_rolar)

    def _duplicar_selecionada(self):
        indice = self.lista.indice_selecionado()
        if indice is not None and 0 <= indice < len(self.banco.perguntas):
            self._ao_duplicar(self.banco.perguntas[indice])

    def _atalho_duplicar(self, event):
        widget = getattr(event, "widget", None)
        if isinstance(widget, (tk.Entry, tk.Text, ttk.Combobox)):
            return None
        self._duplicar_selecionada()
        return "break"

    def _atalho_setas(self, event):
        if not self._descende_de(getattr(event, "widget", None), self.lista):
            return None
        delta = -1 if event.keysym == "Up" else 1
        self.lista.selecionar_relativo(delta)
        return "break"

    def _atalho_enter(self, event):
        if not self._descende_de(getattr(event, "widget", None), self.lista):
            return None
        self.formulario.focar_primeiro_campo()
        return "break"

    def _atalho_excluir(self, event):
        widget = getattr(event, "widget", None)
        if not self._descende_de(widget, self.lista):
            return None
        if isinstance(widget, (tk.Entry, tk.Text, ttk.Combobox)):
            return None
        self.lista._cb_excluir()
        return "break"

    def _ao_rolar(self, event):
        widget = getattr(event, "widget", None)
        if self._descende_de(widget, self.lista):
            return self.lista.rolar(event)
        return self.formulario.rolar(event)

    @staticmethod
    def _descende_de(widget, ancestor) -> bool:
        while widget is not None:
            if widget is ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    # ──────────────────────────────────────────────────────────
    # Estado visual
    # ──────────────────────────────────────────────────────────
    def _nome_banco(self) -> str:
        if self.banco.caminho_origem:
            return os.path.basename(self.banco.caminho_origem)
        return "Banco novo (ainda não salvo)"

    def _atualizar_aviso_leitura(self):
        if self.banco.somente_leitura:
            self.lbl_aviso_leitura.config(text="⚠ SOMENTE LEITURA")
        else:
            self.lbl_aviso_leitura.config(text="")

    def _texto_status(self) -> str:
        partes: list[str] = []
        if self._mensagem_status:
            partes.append(self._mensagem_status)
        if self.banco.somente_leitura:
            partes.append("somente leitura — use Salvar como cópia")
        elif self._pendente is not None:
            partes.append("editando…")
        elif self.banco.alterado:
            partes.append("alterações não salvas")
        else:
            partes.append("salvo")
        return f"{self._nome_banco()} — " + " · ".join(partes)

    def _atualizar_status(self):
        self.lbl_status.config(text=self._texto_status())
        self.lbl_banco.config(text=self._nome_banco())
        self._atualizar_aviso_leitura()
        try:
            self.btn_desfazer.config(
                state="normal" if self.banco.pode_desfazer else "disabled"
            )
            self.btn_refazer.config(
                state="normal" if self.banco.pode_refazer else "disabled"
            )
            erros_form = (
                self.formulario.erros_bloqueantes()
                if self.formulario.pergunta is not None
                else ([] if self.banco.perguntas else ["sem perguntas"])
            )
            self.btn_salvar.config(
                state="disabled" if erros_form else "normal"
            )
        except tk.TclError:
            pass
        titulo = "Editor de Perguntas — Desafio do Conhecimento"
        if self.banco.alterado or self._tem_alteracoes_pendentes():
            titulo = "* " + titulo
        self.title(titulo)

    def _tem_alteracoes_pendentes(self) -> bool:
        """True enquanto há edição digitada e ainda não aplicada ao banco."""
        pendente = self._pendente
        return bool(pendente and pendente[1])

    # ──────────────────────────────────────────────────────────
    # Debounce das edições
    # ──────────────────────────────────────────────────────────
    def _cancelar_job_pendente(self):
        if self._job_pendente is not None:
            try:
                self.after_cancel(self._job_pendente)
            except tk.TclError:
                pass
            self._job_pendente = None

    def _indice_pergunta(self, pergunta: PerguntaEditavel) -> Optional[int]:
        alvo = getattr(pergunta, "id_interno", None)
        for i, atual in enumerate(self.banco.perguntas):
            if atual is pergunta:
                return i
            if alvo and getattr(atual, "id_interno", None) == alvo:
                return i
        return None

    def _ao_alterar_campo(self, campo: str, valor):
        if self.formulario.pergunta is None:
            return
        indice = self._indice_pergunta(self.formulario.pergunta)
        if indice is None:
            return

        if self._pendente is None or self._pendente[0] != indice:
            self._aplicar_pendente()
            self._pendente = (indice, {})
        self._pendente[1][campo] = valor
        self._cancelar_job_pendente()
        self._job_pendente = self.after(
            INTERVALO_DEBOUNCE_MS, self._aplicar_pendente
        )
        self._mensagem_status = ""
        self._atualizar_status()

    def _aplicar_pendente(self):
        self._cancelar_job_pendente()
        pendente = self._pendente
        self._pendente = None
        if pendente is None:
            return
        indice, campos = pendente
        if not campos or not (0 <= indice < len(self.banco.perguntas)):
            return
        try:
            self.banco.editar(indice, **campos)
        except (IndexError, ValueError):
            return
        self._mensagem_status = ""
        self.lista.atualizar_lista(preservar_selecao=True)
        self.formulario.atualizar_categorias()
        self._atualizar_status()

    def _descartar_pendente(self):
        self._cancelar_job_pendente()
        self._pendente = None

    # ──────────────────────────────────────────────────────────
    # Callbacks da lista
    # ──────────────────────────────────────────────────────────
    def _ao_selecionar(self, pergunta: Optional[PerguntaEditavel]):
        if self._pendente is not None:
            self._aplicar_pendente()
        self.formulario.carregar(pergunta)
        self._atualizar_status()

    def _categoria_padrao(self) -> str:
        categorias = self.banco.categorias()
        return categorias[0] if categorias else "Geral"

    def _ao_novo(self):
        self._aplicar_pendente()
        nova = self.banco.adicionar(
            texto="Nova pergunta",
            alternativas=["Alternativa 1", "Alternativa 2"],
            correta=0,
            categoria=self._categoria_padrao(),
        )
        self._mensagem_status = "Nova pergunta criada."
        self.lista.atualizar_lista(preservar_selecao=False)
        self.lista.selecionar_por_id(nova.id_interno)
        self.formulario.focar_primeiro_campo()
        self._atualizar_status()

    def _ao_duplicar(self, pergunta: PerguntaEditavel):
        self._aplicar_pendente()
        indice = self._indice_pergunta(pergunta)
        if indice is None:
            return
        copia = self.banco.duplicar(indice)
        self._mensagem_status = "Pergunta duplicada."
        self.lista.atualizar_lista(preservar_selecao=False)
        self.lista.selecionar_por_id(copia.id_interno)
        self._atualizar_status()

    def _ao_excluir(self, pergunta: PerguntaEditavel) -> bool:
        self._aplicar_pendente()
        indice = self._indice_pergunta(pergunta)
        if indice is None:
            return False

        texto = (pergunta.texto or "").strip()
        resumo = texto[:100] + ("…" if len(texto) > 100 else "")
        if not messagebox.askyesno(
            "Excluir pergunta",
            f"Excluir a pergunta:\n\n{resumo}\n\n"
            "A exclusão pode ser desfeita com Ctrl+Z.",
            parent=self,
            icon="warning",
        ):
            return False

        vizinha = None
        if indice + 1 < len(self.banco.perguntas):
            vizinha = self.banco.perguntas[indice + 1]
        elif indice > 0:
            vizinha = self.banco.perguntas[indice - 1]

        self.banco.excluir(indice)
        self._mensagem_status = "Pergunta excluída."
        self.lista.atualizar_lista(preservar_selecao=False)
        if vizinha is not None:
            self.lista.selecionar_por_id(vizinha.id_interno)
        self._atualizar_status()
        return True

    def _ao_mover(self, indice_origem: int, indice_destino: int):
        self._aplicar_pendente()
        if not (0 <= indice_origem < len(self.banco.perguntas)):
            return
        if not (0 <= indice_destino < len(self.banco.perguntas)):
            return
        id_movida = self.banco.perguntas[indice_origem].id_interno
        self.banco.mover(indice_origem, indice_destino)
        self._mensagem_status = "Ordem alterada."
        self.lista.atualizar_lista(preservar_selecao=False)
        self.lista.selecionar_por_id(id_movida)
        self._atualizar_status()

    # ──────────────────────────────────────────────────────────
    # Undo / redo
    # ──────────────────────────────────────────────────────────
    def _sincronizar_apos_historico(self):
        self._mensagem_status = ""
        self.lista.atualizar_lista(preservar_selecao=True)
        indice = self.lista.indice_selecionado()
        if indice is not None and 0 <= indice < len(self.banco.perguntas):
            self.formulario.carregar(self.banco.perguntas[indice])
        elif not self.banco.perguntas:
            self.formulario.limpar()
        self.formulario.atualizar_categorias()
        self._atualizar_status()

    def desfazer(self):
        self._aplicar_pendente()
        if self.banco.desfazer():
            self._sincronizar_apos_historico()

    def refazer(self):
        self._aplicar_pendente()
        if self.banco.refazer():
            self._sincronizar_apos_historico()

    # ──────────────────────────────────────────────────────────
    # Salvamento
    # ──────────────────────────────────────────────────────────
    def _preparar_para_salvar(self) -> bool:
        self._aplicar_pendente()
        if self.formulario.pergunta is not None:
            erros = self.formulario.erros_bloqueantes()
            if erros:
                self._avisar_erros(erros)
                return False
            indice = self._indice_pergunta(self.formulario.pergunta)
            if indice is not None:
                self.banco.editar(indice, **self.formulario.obter_dados_salvos())

        erros_banco = self.banco.erros_bloqueantes()
        if erros_banco:
            self._avisar_erros(erros_banco)
            return False
        return True

    def _avisar_erros(self, erros):
        self._mensagem_status = (
            f"{len(erros)} erro(s) impedem o salvamento."
        )
        self._atualizar_status()
        linhas = [str(erro) for erro in erros[:8]]
        if len(erros) > 8:
            linhas.append(f"… e mais {len(erros) - 8} erro(s).")
        messagebox.showwarning(
            "Corrija antes de salvar",
            "Não foi possível salvar:\n\n" + "\n".join(linhas),
            parent=self,
        )

    def salvar(self) -> bool:
        if not self._preparar_para_salvar():
            return False

        if self.banco.somente_leitura or not self.banco.caminho_origem:
            return self.salvar_como_copia()

        resultado = em.salvar_banco(
            self.banco,
            self.banco.caminho_origem,
            formato="envelope",
            permitir_sobrescrever=False,
            confirmar_invalidacao=False,
            validar=True,
            estado_path=self.estado_path,
            diretorio_base=self.diretorio_base,
            diretorio_aplicacao=self.diretorio_aplicacao,
        )
        return self._processar_resultado(resultado, salvar_como=False)

    def salvar_como_copia(self) -> bool:
        if not self._preparar_para_salvar():
            return False

        resultado = em.salvar_como_copia(
            self.banco,
            nome=None,
            pasta_config=self.pasta_config,
            diretorio_aplicacao=self.diretorio_aplicacao,
            permitir_sobrescrever=False,
            confirmar_invalidacao=False,
            validar=True,
            estado_path=self.estado_path,
            diretorio_base=self.diretorio_base,
        )
        return self._processar_resultado(resultado, salvar_como=True)

    def _retentar_salvamento(
        self,
        resultado: em.ResultadoSalvamento,
        *,
        salvar_como: bool,
        sobrescrever: bool,
        invalidar: bool,
    ) -> bool:
        if salvar_como:
            novo = em.salvar_como_copia(
                self.banco,
                nome=None,
                pasta_config=self.pasta_config,
                diretorio_aplicacao=self.diretorio_aplicacao,
                permitir_sobrescrever=sobrescrever,
                confirmar_invalidacao=invalidar,
                validar=True,
                estado_path=self.estado_path,
                diretorio_base=self.diretorio_base,
            )
        else:
            destino = resultado.caminho or self.banco.caminho_origem
            novo = em.salvar_banco(
                self.banco,
                destino,
                formato="envelope",
                permitir_sobrescrever=sobrescrever,
                confirmar_invalidacao=invalidar,
                validar=True,
                estado_path=self.estado_path,
                diretorio_base=self.diretorio_base,
                diretorio_aplicacao=self.diretorio_aplicacao,
            )
        return self._processar_resultado(
            novo, salvar_como=salvar_como, permitir_reconfirmar=False
        )

    def _processar_resultado(
        self,
        resultado: em.ResultadoSalvamento,
        *,
        salvar_como: bool,
        permitir_reconfirmar: bool = True,
    ) -> bool:
        if resultado.ok:
            self._ultimo_caminho_salvo = resultado.caminho
            self._mensagem_status = (
                f"Salvo em {os.path.basename(resultado.caminho)}."
            )
            self.lista.atualizar_lista(preservar_selecao=True)
            self.formulario.atualizar_categorias()
            self._atualizar_status()
            if resultado.estado_invalidado:
                messagebox.showinfo(
                    "Partida salva invalidada",
                    "A partida salva foi renomeada para:\n"
                    f"{os.path.basename(resultado.estado_invalidado)}",
                    parent=self,
                )
            return True

        if resultado.partida_salva_afetada and permitir_reconfirmar:
            self._mensagem_status = "A partida salva seria invalidada."
            self._atualizar_status()
            if messagebox.askyesno(
                "Partida salva",
                "Existe uma partida salva que usa este banco.\n\n"
                "Salvar agora vai invalidar essa partida (ela será "
                "renomeada, não apagada). Deseja continuar?",
                parent=self,
                icon="warning",
            ):
                return self._retentar_salvamento(
                    resultado,
                    salvar_como=salvar_como,
                    sobrescrever=False,
                    invalidar=True,
                )
            self._mensagem_status = "Salvamento cancelado."
            self._atualizar_status()
            return False

        if resultado.somente_leitura:
            self._mensagem_status = "O banco é somente leitura."
            self._atualizar_status()
            if salvar_como or not permitir_reconfirmar:
                messagebox.showerror(
                    "Não foi possível salvar",
                    resultado.erro or "O destino é somente leitura.",
                    parent=self,
                )
                return False
            if messagebox.askyesno(
                "Banco somente leitura",
                f"{resultado.erro or 'Este banco é somente leitura.'}\n\n"
                "Deseja salvar uma cópia em outro local?",
                parent=self,
                icon="warning",
            ):
                return self.salvar_como_copia()
            self._mensagem_status = "Salvamento cancelado."
            self._atualizar_status()
            return False

        if resultado.conflito:
            self._mensagem_status = "Salvamento precisa de confirmação."
            self._atualizar_status()
            if not permitir_reconfirmar:
                messagebox.showerror(
                    "Não foi possível salvar",
                    resultado.erro or "O destino não pôde ser gravado.",
                    parent=self,
                )
                return False
            if messagebox.askyesno(
                "Confirmar gravação",
                f"{resultado.erro}\n\nDeseja continuar?",
                parent=self,
                icon="warning",
            ):
                return self._retentar_salvamento(
                    resultado,
                    salvar_como=salvar_como,
                    sobrescrever=True,
                    invalidar=False,
                )
            self._mensagem_status = "Salvamento cancelado."
            self._atualizar_status()
            return False

        self._mensagem_status = "Falha ao salvar."
        self._atualizar_status()
        messagebox.showerror(
            "Não foi possível salvar",
            resultado.erro or "Erro desconhecido ao gravar o banco.",
            parent=self,
        )
        return False

    # ──────────────────────────────────────────────────────────
    # Fechamento
    # ──────────────────────────────────────────────────────────
    def _confirmar_fechar(self):
        if self._fechando or self._fechado:
            return
        self._aplicar_pendente()

        if self.banco.alterado:
            resposta = messagebox.askyesnocancel(
                "Alterações não salvas",
                "Há alterações não salvas. Deseja salvar antes de fechar?",
                parent=self,
                icon="warning",
            )
            if resposta is None:
                return
            if resposta:
                if not self.salvar():
                    return
        self._fechar()

    def _fechar(self):
        if self._fechado:
            return
        self._fechando = True
        self._fechado = True
        self._descartar_pendente()
        try:
            self.grab_release()
        except tk.TclError:
            pass
        callback = self.ao_fechar
        try:
            self.destroy()
        except tk.TclError:
            pass
        if callback is not None:
            callback(self.banco)

    def destroy(self):
        self._descartar_pendente()
        try:
            self.grab_release()
        except tk.TclError:
            pass
        super().destroy()


def abrir_editor(
    parent,
    banco_atual: Optional[BancoEditavel] = None,
    *,
    ao_fechar: Optional[Callable[[Optional[BancoEditavel]], None]] = None,
    estado_path: Optional[str] = None,
    diretorio_base: Optional[str] = None,
    diretorio_aplicacao: Optional[str] = None,
    pasta_config: Optional[str] = None,
    rodando_partida: bool = False,
    banco_em_uso_caminho: Optional[str] = None,
) -> EditorPerguntas:
    """Abre o editor e devolve a instância (não bloqueia o chamador)."""
    return EditorPerguntas(
        parent,
        banco_atual=banco_atual,
        ao_fechar=ao_fechar,
        estado_path=estado_path,
        diretorio_base=diretorio_base,
        diretorio_aplicacao=diretorio_aplicacao,
        pasta_config=pasta_config,
        rodando_partida=rodando_partida,
        banco_em_uso_caminho=banco_em_uso_caminho,
    )
