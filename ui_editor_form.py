"""
Formulário de edição de pergunta (Etapa E2).

Widget Tk clássico com validação inline por campo, conectado ao
`editor_modelo.PerguntaEditavel` e a `perguntas.validar_pergunta`.

O formulário não grava nada: cada alteração é notificada ao editor, que
decide quando aplicar no modelo (com debounce) e quando empilhar undo.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from editor_modelo import PerguntaEditavel
from perguntas import (
    ErroCampo,
    SEVERIDADE_AVISO,
    SEVERIDADE_ERRO,
    validar_pergunta,
)
from ui_componentes import Cor


class FormularioPergunta(tk.Frame):
    """
    Formulário de edição de uma pergunta.

    Callbacks:
    - ao_alterar(campo: str, valor) -> None
    - ao_salvar() -> None  (opcional; o editor também trata Ctrl+S)
    """

    def __init__(
        self,
        master,
        banco,
        *,
        ao_alterar: Callable[[str, object], None],
        ao_salvar: Optional[Callable[[], None]] = None,
        ao_desfazer: Optional[Callable[[], None]] = None,
        ao_refazer: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, bg=Cor.FUNDO)
        self.banco = banco
        self.ao_alterar = ao_alterar
        self.ao_salvar = ao_salvar
        self.ao_desfazer = ao_desfazer
        self.ao_refazer = ao_refazer

        self.pergunta: Optional[PerguntaEditavel] = None
        self._widgets_campos: dict[str, dict] = {}
        self._labels_erro: dict[str, tk.Label] = {}
        self._entry_alts: list[tk.Entry] = []
        self._rb_alts: list[tk.Radiobutton] = []
        self._var_categoria = tk.StringVar()
        self._vars_alternativas: list[tk.StringVar] = []
        self._var_correta = tk.IntVar(value=-1)

        self._construir_ui()
        self.limpar()

    # ──────────────────────────────────────────────────────────
    # Construção
    # ──────────────────────────────────────────────────────────
    def _construir_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg=Cor.FUNDO, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.container = tk.Frame(self.canvas, bg=Cor.FUNDO, padx=16, pady=12)
        self.janela_canvas = self.canvas.create_window(
            (0, 0), window=self.container, anchor="nw"
        )
        self.container.bind("<Configure>", self._ao_configurar_container)
        self.canvas.bind("<Configure>", self._ao_configurar_canvas)
        self.canvas.bind("<MouseWheel>", self.rolar)
        self.canvas.bind("<Button-4>", self.rolar)
        self.canvas.bind("<Button-5>", self.rolar)

        self._criar_campo_texto(
            "pergunta",
            "Enunciado da pergunta *",
            altura=4,
            obrigatorio=True,
        )
        self._criar_campo_alternativas()
        self._criar_campo_categoria()
        self._criar_campo_texto(
            "explicacao",
            "Explicação (opcional)",
            altura=3,
            obrigatorio=False,
        )

        dica = tk.Label(
            self.container,
            text="Dica: Ctrl+S salva, Ctrl+Z desfaz e Ctrl+Y refaz.",
            font=("Segoe UI", 8),
            fg=Cor.SUAVE,
            bg=Cor.FUNDO,
            anchor="w",
        )
        dica.pack(fill="x", pady=(2, 8))

    def _ao_configurar_container(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _ao_configurar_canvas(self, event):
        self.canvas.itemconfig(self.janela_canvas, width=event.width)

    def _criar_campo_texto(
        self, nome: str, rotulo: str, altura: int, obrigatorio: bool
    ):
        frame = tk.Frame(self.container, bg=Cor.FUNDO)
        frame.pack(fill="x", pady=(0, 12))
        frame.columnconfigure(0, weight=1)

        tk.Label(
            frame,
            text=rotulo,
            font=("Segoe UI", 9, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.FUNDO,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        texto = tk.Text(
            frame,
            font=("Segoe UI", 10),
            bg=Cor.PAINEL,
            fg=Cor.TEXTO,
            insertbackground=Cor.TEXTO,
            relief="flat",
            highlightthickness=1,
            highlightbackground=Cor.BORDA,
            highlightcolor=Cor.A,
            height=altura,
            wrap="word",
            padx=8,
            pady=6,
        )
        texto.grid(row=1, column=0, sticky="ew")
        texto.bind("<KeyRelease>", lambda e, n=nome: self._ao_digitar(n))
        texto.bind("<Control-a>", self._selecionar_tudo)
        texto.bind("<Control-A>", self._selecionar_tudo)
        texto.bind("<Control-z>", self._atalho_desfazer)
        texto.bind("<Control-Z>", self._atalho_desfazer)
        texto.bind("<Control-y>", self._atalho_refazer)
        texto.bind("<Control-Y>", self._atalho_refazer)

        lbl_erro = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 8),
            fg=Cor.ERRO,
            bg=Cor.FUNDO,
            anchor="w",
            justify="left",
        )
        lbl_erro.grid(row=2, column=0, sticky="ew", pady=(2, 0))

        self._widgets_campos[nome] = {
            "widget": texto,
            "tipo": "text",
            "obrigatorio": obrigatorio,
        }
        self._labels_erro[nome] = lbl_erro

    def _criar_campo_alternativas(self):
        frame = tk.Frame(self.container, bg=Cor.FUNDO)
        frame.pack(fill="x", pady=(0, 12))
        frame.columnconfigure(1, weight=1)

        tk.Label(
            frame,
            text="Alternativas (2 a 4) *",
            font=("Segoe UI", 9, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.FUNDO,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        tk.Label(
            frame,
            text="Marque o botão à esquerda da alternativa correta.",
            font=("Segoe UI", 8),
            fg=Cor.SUAVE,
            bg=Cor.FUNDO,
            anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        self._vars_alternativas = []
        self._entry_alts = []
        self._rb_alts = []

        for i in range(4):
            linha = i + 2
            rb = tk.Radiobutton(
                frame,
                variable=self._var_correta,
                value=i,
                bg=Cor.FUNDO,
                activebackground=Cor.FUNDO,
                selectcolor=Cor.A,
                highlightthickness=0,
                bd=0,
                cursor="hand2",
                command=lambda: self._ao_digitar("correta"),
            )
            rb.grid(row=linha, column=0, sticky="w", padx=(0, 8), pady=2)

            entry = tk.Entry(
                frame,
                font=("Segoe UI", 10),
                bg=Cor.PAINEL,
                fg=Cor.TEXTO,
                insertbackground=Cor.TEXTO,
                relief="flat",
                highlightthickness=1,
                highlightbackground=Cor.BORDA,
                highlightcolor=Cor.A,
            )
            entry.grid(row=linha, column=1, sticky="ew", pady=2, ipady=4)
            entry.bind(
                "<KeyRelease>",
                lambda e, n="alternativas": self._ao_digitar(n),
            )
            entry.bind("<Control-a>", self._selecionar_tudo)
            entry.bind("<Control-A>", self._selecionar_tudo)

            var = tk.StringVar()
            entry.config(textvariable=var)
            self._vars_alternativas.append(var)
            self._entry_alts.append(entry)
            self._rb_alts.append(rb)

        self.lbl_erro_alternativas = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 8),
            fg=Cor.ERRO,
            bg=Cor.FUNDO,
            anchor="w",
            justify="left",
        )
        self.lbl_erro_alternativas.grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(2, 0)
        )

        self.lbl_erro_correta = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 8),
            fg=Cor.ERRO,
            bg=Cor.FUNDO,
            anchor="w",
            justify="left",
        )
        self.lbl_erro_correta.grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(1, 0)
        )

        self._widgets_campos["alternativas"] = {
            "widget": frame,
            "tipo": "list",
            "obrigatorio": True,
        }
        self._widgets_campos["correta"] = {
            "widget": None,
            "tipo": "radio",
            "obrigatorio": True,
        }
        self._labels_erro["alternativas"] = self.lbl_erro_alternativas
        self._labels_erro["correta"] = self.lbl_erro_correta

    def _criar_campo_categoria(self):
        frame = tk.Frame(self.container, bg=Cor.FUNDO)
        frame.pack(fill="x", pady=(0, 12))
        frame.columnconfigure(0, weight=1)

        tk.Label(
            frame,
            text="Categoria *",
            font=("Segoe UI", 9, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.FUNDO,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.combo_categoria = ttk.Combobox(
            frame,
            textvariable=self._var_categoria,
            values=self.banco.categorias(),
            font=("Segoe UI", 10),
            state="normal",
        )
        self.combo_categoria.grid(row=1, column=0, sticky="ew", ipady=4)
        self.combo_categoria.bind(
            "<<ComboboxSelected>>", lambda e: self._ao_digitar("categoria")
        )
        self.combo_categoria.bind(
            "<KeyRelease>", lambda e: self._ao_digitar("categoria")
        )
        self.combo_categoria.bind(
            "<FocusOut>", lambda e: self._ao_digitar("categoria")
        )

        lbl_erro = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 8),
            fg=Cor.ERRO,
            bg=Cor.FUNDO,
            anchor="w",
            justify="left",
        )
        lbl_erro.grid(row=2, column=0, sticky="ew", pady=(2, 0))

        self._widgets_campos["categoria"] = {
            "widget": self.combo_categoria,
            "tipo": "combo",
            "obrigatorio": True,
        }
        self._labels_erro["categoria"] = lbl_erro

    def _selecionar_tudo(self, event):
        widget = event.widget
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
        elif isinstance(widget, tk.Entry):
            widget.select_range(0, "end")
            widget.icursor("end")
        return "break"

    def _atalho_desfazer(self, event=None):
        if self.ao_desfazer is not None:
            self.ao_desfazer()
        return "break"

    def _atalho_refazer(self, event=None):
        if self.ao_refazer is not None:
            self.ao_refazer()
        return "break"

    def rolar(self, event):
        if getattr(event, "delta", 0):
            passo = -1 if event.delta > 0 else 1
        elif getattr(event, "num", None) == 4:
            passo = -1
        else:
            passo = 1
        self.canvas.yview_scroll(passo, "units")
        return "break"

    def limpar_bindings(self):
        """Compatibilidade: a versão atual não usa `bind_all`."""

    def focar_primeiro_campo(self):
        try:
            self._widgets_campos["pergunta"]["widget"].focus_set()
        except tk.TclError:
            pass

    # ──────────────────────────────────────────────────────────
    # Carregar / limpar
    # ──────────────────────────────────────────────────────────
    def carregar(self, pergunta: Optional[PerguntaEditavel]):
        self.pergunta = pergunta
        if pergunta is None:
            self.limpar()
            return

        self._set_texto("pergunta", pergunta.texto)

        alts = list(pergunta.alternativas)
        for i, var in enumerate(self._vars_alternativas):
            var.set(alts[i] if i < len(alts) else "")

        try:
            correta = int(pergunta.correta) if pergunta.correta is not None else -1
        except (TypeError, ValueError):
            correta = -1
        self._var_correta.set(correta)

        self._var_categoria.set(pergunta.categoria)
        self.combo_categoria["values"] = self.banco.categorias()
        self._set_texto("explicacao", pergunta.explicacao)
        self.validar_tempo_real()

    def limpar(self):
        self.pergunta = None
        self._set_texto("pergunta", "")
        for var in self._vars_alternativas:
            var.set("")
        self._var_correta.set(-1)
        self._var_categoria.set("")
        self._set_texto("explicacao", "")
        self.combo_categoria["values"] = self.banco.categorias()
        self.limpar_erros()

    def _set_texto(self, nome: str, valor: str):
        widget = self._widgets_campos[nome]["widget"]
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", valor if isinstance(valor, str) else "")

    def _get_texto(self, nome: str) -> str:
        widget = self._widgets_campos[nome]["widget"]
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c")
        return ""

    # ──────────────────────────────────────────────────────────
    # Alteração / validação
    # ──────────────────────────────────────────────────────────
    def _ao_digitar(self, campo: str):
        if self.pergunta is None:
            return
        self.validar_tempo_real()
        self._notificar_alteracao(campo)

    def _alternativas_atuais(self) -> list[str]:
        alts = [var.get() for var in self._vars_alternativas]
        while len(alts) > 2 and not alts[-1].strip():
            alts.pop()
        return alts

    def _notificar_alteracao(self, campo: str):
        if self.pergunta is None:
            return

        if campo == "pergunta":
            valor: object = self._get_texto("pergunta")
        elif campo == "alternativas":
            valor = self._alternativas_atuais()
        elif campo == "correta":
            valor = self._var_correta.get()
        elif campo == "categoria":
            valor = self._var_categoria.get()
        elif campo == "explicacao":
            valor = self._get_texto("explicacao")
        else:
            return

        self.ao_alterar(campo, valor)

    def _coletar_dados_para_validacao(self) -> dict:
        return {
            "pergunta": self._get_texto("pergunta"),
            "alternativas": self._alternativas_atuais(),
            "correta": self._var_correta.get(),
            "categoria": self._var_categoria.get(),
            "explicacao": self._get_texto("explicacao"),
        }

    def validar_tempo_real(self) -> list[ErroCampo]:
        if self.pergunta is None:
            self.limpar_erros()
            return []
        erros = validar_pergunta(self._coletar_dados_para_validacao())
        self._mostrar_erros(erros)
        return erros

    def _campo_do_erro(self, erro: ErroCampo) -> str:
        if erro.campo.startswith("alternativas"):
            return "alternativas"
        return erro.campo

    def _mostrar_erros(self, erros: list[ErroCampo]):
        self.limpar_erros()
        por_campo: dict[str, list[ErroCampo]] = {}
        for erro in erros:
            por_campo.setdefault(self._campo_do_erro(erro), []).append(erro)

        for campo, lista in por_campo.items():
            label = self._labels_erro.get(campo)
            if label is None:
                continue
            bloqueantes = [e for e in lista if e.severidade == SEVERIDADE_ERRO]
            avisos = [e for e in lista if e.severidade == SEVERIDADE_AVISO]
            mensagens = [f"❌ {e.mensagem}" for e in bloqueantes]
            mensagens += [f"⚠ {e.mensagem}" for e in avisos]
            label.config(
                text="\n".join(mensagens),
                fg=Cor.ERRO if bloqueantes else Cor.AVISO,
            )

        # Destaca as alternativas com erro individual.
        indices_com_erro = {
            e.alternativa
            for e in erros
            if e.alternativa is not None and e.severidade == SEVERIDADE_ERRO
        }
        for i, entry in enumerate(self._entry_alts):
            cor = Cor.ERRO if i in indices_com_erro else Cor.BORDA
            try:
                entry.configure(
                    highlightbackground=cor,
                    highlightcolor=cor,
                )
            except tk.TclError:
                pass

    def limpar_erros(self):
        for label in set(self._labels_erro.values()):
            label.config(text="", fg=Cor.ERRO)
        for entry in self._entry_alts:
            try:
                entry.configure(
                    highlightbackground=Cor.BORDA,
                    highlightcolor=Cor.A,
                )
            except tk.TclError:
                pass

    def tem_erros_bloqueantes(self) -> bool:
        return any(
            e.severidade == SEVERIDADE_ERRO for e in self.validar_tempo_real()
        )

    def erros_bloqueantes(self) -> list[ErroCampo]:
        return [
            e
            for e in self.validar_tempo_real()
            if e.severidade == SEVERIDADE_ERRO
        ]

    def obter_dados_salvos(self) -> dict:
        """Dados atuais do formulário, no formato aceito por `BancoEditavel`."""
        return {
            "texto": self._get_texto("pergunta"),
            "alternativas": self._alternativas_atuais(),
            "correta": self._var_correta.get(),
            "categoria": self._var_categoria.get(),
            "explicacao": self._get_texto("explicacao"),
        }

    def atualizar_categorias(self):
        if hasattr(self, "combo_categoria"):
            self.combo_categoria["values"] = self.banco.categorias()
