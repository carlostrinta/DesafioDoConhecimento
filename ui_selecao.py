"""
Janela modal de escolha do banco de perguntas (tema).

Extraída de desafio.py na Etapa 3.6. Só apresentação: lista os bancos
disponíveis, permite escolher/procurar um .json e devolve a escolha pelo
callback `ao_confirmar`. Nenhuma regra de jogo mora aqui.

Usa widgets Tk clássicos (não é um componente Canvas), por isso vive em
ui_selecao.py e não em ui_componentes.py.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from perguntas import inspecionar_arquivo_perguntas, listar_arquivos_perguntas
from recursos import caminho_recurso, obter_diretorio_base
from ui_componentes import Cor, obter_icone_tema


class ModalSelecaoPerguntas(tk.Toplevel):
    """
    Janela modal para escolha do arquivo de perguntas (tema / tecnologia) na inicialização
    ou durante a execução do jogo.
    """
    def __init__(
        self,
        parent,
        lista_arquivos,
        arquivo_atual=None,
        ao_confirmar=None,
        permitir_cancelar=True,
        inicial=False,
        diretorio=None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.lista_arquivos = list(lista_arquivos)
        self.arquivo_selecionado = arquivo_atual
        self.ao_confirmar = ao_confirmar
        self.permitir_cancelar = permitir_cancelar
        self.inicial = inicial
        self.diretorio = diretorio or obter_diretorio_base()

        self.title("Duelo de Conhecimento — Escolha de Tema")
        self.configure(bg=Cor.FUNDO)
        self.resizable(False, False)

        ico_path = caminho_recurso("desafio.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        if not self.arquivo_selecionado and self.lista_arquivos:
            self.arquivo_selecionado = self.lista_arquivos[0]

        self.cards_widgets = []
        self._construir_ui()
        self._centralizar(700, 540)

        self.bind("<Return>", lambda e: self._confirmar())
        self.bind("<KP_Enter>", lambda e: self._confirmar())
        self.bind("<Up>", lambda e: self._mover_selecao(-1))
        self.bind("<Down>", lambda e: self._mover_selecao(1))
        if self.permitir_cancelar:
            self.bind("<Escape>", lambda e: self._cancelar())

        self.grab_set()
        self.focus_force()

    def _centralizar(self, w, h):
        self.update_idletasks()
        try:
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            if pw > 100 and ph > 100:
                x = px + (pw - w) // 2
                y = py + (ph - h) // 2
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = (sw - w) // 2
                y = (sh - h) // 2
        except Exception:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _construir_ui(self):
        # 1. Topo / Cabeçalho
        topo = tk.Frame(self, bg=Cor.PAINEL, padx=24, pady=16)
        topo.pack(side="top", fill="x")

        tk.Label(
            topo,
            text="🎯  ESCOLHA A TECNOLOGIA OU TEMA",
            font=("Segoe UI", 15, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.PAINEL,
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            topo,
            text="Selecione o arquivo de perguntas (.json) para iniciar o duelo:",
            font=("Segoe UI", 10),
            fg=Cor.SUAVE,
            bg=Cor.PAINEL,
            anchor="w"
        ).pack(fill="x", pady=(4, 0))

        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        # 2. Área Central com Canvas e Scrollbar
        meio = tk.Frame(self, bg=Cor.FUNDO, padx=16, pady=14)
        meio.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(meio, bg=Cor.FUNDO, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(meio, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.container_cards = tk.Frame(self.canvas, bg=Cor.FUNDO)
        self.janela_canvas = self.canvas.create_window((0, 0), window=self.container_cards, anchor="nw")

        self.container_cards.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.janela_canvas, width=e.width)
        )

        def _rolar(event):
            if event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                self.canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                self.canvas.yview_scroll(1, "units")

        self.canvas.bind_all("<MouseWheel>", _rolar)

        self._reconstruir_cards()

        # 3. Rodapé com Botões de Ação
        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        rodape = tk.Frame(self, bg=Cor.PAINEL, padx=20, pady=14)
        rodape.pack(side="bottom", fill="x")

        btn_procurar = tk.Button(
            rodape,
            text="📁 Procurar outro (.json)...",
            font=("Segoe UI", 9, "bold"),
            bg="#182244",
            fg=Cor.TEXTO,
            activebackground="#253568",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._procurar_arquivo
        )
        btn_procurar.pack(side="left", padx=(0, 8))

        btn_atualizar = tk.Button(
            rodape,
            text="🔄 Atualizar",
            font=("Segoe UI", 9),
            bg="#182244",
            fg=Cor.SUAVE,
            activebackground="#253568",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._atualizar_lista
        )
        btn_atualizar.pack(side="left")

        btn_iniciar = tk.Button(
            rodape,
            text="▶  Iniciar Desafio",
            font=("Segoe UI", 11, "bold"),
            bg=Cor.A,
            fg=Cor.FUNDO,
            activebackground="#5CB7FF",
            activeforeground=Cor.FUNDO,
            relief="flat",
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._confirmar
        )
        btn_iniciar.pack(side="right", padx=(8, 0))

        if self.permitir_cancelar:
            btn_cancelar = tk.Button(
                rodape,
                text="Cancelar",
                font=("Segoe UI", 9),
                bg="#231A26",
                fg=Cor.ERRO,
                activebackground="#3D1D28",
                activeforeground="#FF8599",
                relief="flat",
                bd=0,
                padx=14,
                pady=8,
                cursor="hand2",
                command=self._cancelar
            )
            btn_cancelar.pack(side="right")

    def _reconstruir_cards(self):
        for w in self.container_cards.winfo_children():
            w.destroy()
        self.cards_widgets = []

        if not self.lista_arquivos:
            vazio = tk.Frame(self.container_cards, bg=Cor.PAINEL, padx=20, pady=24, highlightthickness=1, highlightbackground=Cor.BORDA)
            vazio.pack(fill="x", pady=10)
            tk.Label(
                vazio,
                text="⚠️  Nenhum arquivo de perguntas (.json) válido encontrado.",
                font=("Segoe UI", 11, "bold"),
                fg=Cor.AVISO,
                bg=Cor.PAINEL
            ).pack(anchor="w")
            tk.Label(
                vazio,
                text="Coloque arquivos .json na pasta de perguntas configurada (ex: eletrotecnica.json, radiologia.json)\nou use o botão 'Procurar outro (.json)...' abaixo.",
                font=("Segoe UI", 9),
                fg=Cor.SUAVE,
                bg=Cor.PAINEL,
                justify="left"
            ).pack(anchor="w", pady=(6, 0))
            return

        for idx, info in enumerate(self.lista_arquivos):
            selecionado = (
                self.arquivo_selecionado is not None and
                self.arquivo_selecionado.get("caminho") == info["caminho"]
            )

            cor_bg = "#1B2A54" if selecionado else Cor.PAINEL
            cor_borda = Cor.A if selecionado else Cor.BORDA
            esp_borda = 2 if selecionado else 1

            card = tk.Frame(
                self.container_cards,
                bg=cor_bg,
                highlightthickness=esp_borda,
                highlightbackground=cor_borda,
                padx=16,
                pady=10,
                cursor="hand2"
            )
            card.pack(fill="x", pady=4)

            icone = obter_icone_tema(info["titulo"], info["arquivo"])
            lbl_ico = tk.Label(
                card,
                text=icone,
                font=("Segoe UI Emoji", 20),
                fg=Cor.TEXTO,
                bg=cor_bg
            )
            lbl_ico.pack(side="left", padx=(0, 14))

            col = tk.Frame(card, bg=cor_bg)
            col.pack(side="left", fill="both", expand=True)

            lbl_tit = tk.Label(
                col,
                text=info["titulo"],
                font=("Segoe UI", 12, "bold"),
                fg=Cor.TEXTO,
                bg=cor_bg,
                anchor="w"
            )
            lbl_tit.pack(fill="x")

            sub_txt = f"{info['total']} perguntas  •  {info['arquivo']}"
            lbl_sub = tk.Label(
                col,
                text=sub_txt,
                font=("Segoe UI", 9),
                fg=Cor.SUAVE,
                bg=cor_bg,
                anchor="w"
            )
            lbl_sub.pack(fill="x")

            if info.get("categorias"):
                cats = ", ".join(info["categorias"][:3])
                if len(info["categorias"]) > 3:
                    cats += f" (+{len(info['categorias']) - 3})"
                lbl_cat = tk.Label(
                    col,
                    text="Tags: " + cats,
                    font=("Segoe UI", 8),
                    fg=Cor.APOIO,
                    bg=cor_bg,
                    anchor="w"
                )
                lbl_cat.pack(fill="x", pady=(2, 0))
            else:
                lbl_cat = None

            badge_txt = "●  SELECIONADO" if selecionado else "○  Escolher"
            badge_cor = Cor.A if selecionado else Cor.APAGADO
            lbl_badge = tk.Label(
                card,
                text=badge_txt,
                font=("Segoe UI", 9, "bold" if selecionado else "normal"),
                fg=badge_cor,
                bg=cor_bg
            )
            lbl_badge.pack(side="right", padx=(10, 0))

            card_info = {
                "idx": idx,
                "info": info,
                "card": card,
                "lbl_ico": lbl_ico,
                "col": col,
                "lbl_tit": lbl_tit,
                "lbl_sub": lbl_sub,
                "lbl_cat": lbl_cat,
                "lbl_badge": lbl_badge,
            }
            self.cards_widgets.append(card_info)

            def criar_cb_click(i):
                return lambda e: self._selecionar_indice(i)

            def criar_cb_dblclick(i):
                return lambda e: (self._selecionar_indice(i), self._confirmar())

            todos_widgets = [card, lbl_ico, col, lbl_tit, lbl_sub, lbl_badge]
            if lbl_cat:
                todos_widgets.append(lbl_cat)

            for w in todos_widgets:
                w.bind("<Button-1>", criar_cb_click(idx))
                w.bind("<Double-Button-1>", criar_cb_dblclick(idx))

    def _selecionar_indice(self, idx):
        if not (0 <= idx < len(self.lista_arquivos)):
            return
        self.arquivo_selecionado = self.lista_arquivos[idx]

        for item in self.cards_widgets:
            i = item["idx"]
            sel = (i == idx)
            cor_bg = "#1B2A54" if sel else Cor.PAINEL
            cor_borda = Cor.A if sel else Cor.BORDA
            esp = 2 if sel else 1

            item["card"].configure(bg=cor_bg, highlightbackground=cor_borda, highlightthickness=esp)
            item["lbl_ico"].configure(bg=cor_bg)
            item["col"].configure(bg=cor_bg)
            item["lbl_tit"].configure(bg=cor_bg)
            item["lbl_sub"].configure(bg=cor_bg)
            if item["lbl_cat"]:
                item["lbl_cat"].configure(bg=cor_bg)

            item["lbl_badge"].configure(
                bg=cor_bg,
                text="●  SELECIONADO" if sel else "○  Escolher",
                fg=Cor.A if sel else Cor.APAGADO,
                font=("Segoe UI", 9, "bold" if sel else "normal")
            )

    def _mover_selecao(self, delta):
        if not self.lista_arquivos:
            return
        atual_idx = 0
        if self.arquivo_selecionado:
            for i, it in enumerate(self.lista_arquivos):
                if it["caminho"] == self.arquivo_selecionado["caminho"]:
                    atual_idx = i
                    break
        novo_idx = max(0, min(len(self.lista_arquivos) - 1, atual_idx + delta))
        self._selecionar_indice(novo_idx)

    def _procurar_arquivo(self):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar arquivo de perguntas JSON",
            filetypes=[("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")]
        )
        if not caminho:
            return
        info = inspecionar_arquivo_perguntas(caminho)
        if not info:
            messagebox.showerror(
                "Arquivo Inválido",
                "O arquivo selecionado não contém um formato de perguntas válido.\n\n"
                "O JSON deve conter uma lista com os campos 'pergunta', 'alternativas' (2 a 4) e 'correta'.",
                parent=self
            )
            return

        encontrado_idx = None
        for i, item in enumerate(self.lista_arquivos):
            if os.path.abspath(item["caminho"]) == os.path.abspath(info["caminho"]):
                encontrado_idx = i
                break

        if encontrado_idx is None:
            self.lista_arquivos.append(info)
            self.arquivo_selecionado = info
            self._reconstruir_cards()
            self._selecionar_indice(len(self.lista_arquivos) - 1)
        else:
            self._selecionar_indice(encontrado_idx)

    def _atualizar_lista(self):
        self.lista_arquivos = listar_arquivos_perguntas(self.diretorio)
        self._reconstruir_cards()
        if self.lista_arquivos:
            self._selecionar_indice(0)

    def _limpar_mousewheel(self):
        try:
            self.canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass

    def _confirmar(self):
        if not self.arquivo_selecionado:
            messagebox.showwarning("Seleção", "Por favor, selecione um arquivo de perguntas.", parent=self)
            return
        self._limpar_mousewheel()
        escolhido = self.arquivo_selecionado
        cb = self.ao_confirmar
        self.destroy()
        if cb:
            cb(escolhido)

    def _cancelar(self):
        self._limpar_mousewheel()
        self.destroy()

    def _ao_fechar(self):
        self._limpar_mousewheel()
        if self.inicial:
            # Modal inicial: fechar a janela = sair do app
            if messagebox.askyesno("Sair", "Deseja fechar o Duelo de Conhecimento?", parent=self):
                self.parent.destroy()
        else:
            # Modal durante o jogo: apenas fecha o modal
            self.destroy()


class ModalContinuarPartida(tk.Toplevel):
    """
    Modal inicial da Etapa 4.3: continuar a partida salva ou começar outra.

    Só apresentação. A escolha volta pelo callback `ao_escolher(bool)`:
    True = Continuar, False = Nova partida.
    """

    def __init__(self, parent, resumo, ao_escolher):
        super().__init__(parent)
        self.parent = parent
        self.resumo = str(resumo or "")
        self.ao_escolher = ao_escolher
        self._respondido = False

        self.title("Duelo de Conhecimento — Partida salva")
        self.configure(bg=Cor.FUNDO)
        self.resizable(False, False)

        ico_path = caminho_recurso("desafio.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: self._escolher(False))
        self._construir_ui()
        self._centralizar(560, 360)

        self.bind("<Return>", lambda e: self._escolher(True))
        self.bind("<KP_Enter>", lambda e: self._escolher(True))
        self.bind("<Escape>", lambda e: self._escolher(False))
        self.grab_set()
        self.focus_force()

    def _construir_ui(self):
        topo = tk.Frame(self, bg=Cor.PAINEL, padx=24, pady=16)
        topo.pack(side="top", fill="x")
        tk.Label(
            topo,
            text="Continuar partida salva?",
            font=("Segoe UI", 16, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.PAINEL,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            topo,
            text="Encontramos uma partida interrompida.",
            font=("Segoe UI", 10),
            fg=Cor.SUAVE,
            bg=Cor.PAINEL,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        corpo = tk.Frame(self, bg=Cor.FUNDO, padx=28, pady=22)
        corpo.pack(fill="both", expand=True)
        tk.Label(
            corpo,
            text=self.resumo,
            font=("Segoe UI", 11),
            fg=Cor.TEXTO,
            bg=Cor.FUNDO,
            justify="left",
            anchor="w",
        ).pack(fill="x", anchor="w")

        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        rodape = tk.Frame(self, bg=Cor.PAINEL, padx=20, pady=14)
        rodape.pack(side="bottom", fill="x")

        btn_nova = tk.Button(
            rodape,
            text="Nova partida",
            font=("Segoe UI", 10, "bold"),
            bg="#231A26",
            fg=Cor.ERRO,
            activebackground="#3D1D28",
            activeforeground="#FF8599",
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            cursor="hand2",
            command=lambda: self._escolher(False),
        )
        btn_nova.pack(side="left")

        btn_continuar = tk.Button(
            rodape,
            text="Continuar",
            font=("Segoe UI", 11, "bold"),
            bg=Cor.A,
            fg=Cor.FUNDO,
            activebackground="#5CB7FF",
            activeforeground=Cor.FUNDO,
            relief="flat",
            bd=0,
            padx=24,
            pady=9,
            cursor="hand2",
            command=lambda: self._escolher(True),
        )
        btn_continuar.pack(side="right")
        btn_continuar.focus_set()

    def _centralizar(self, largura, altura):
        self.update_idletasks()
        try:
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            if pw > 100 and ph > 100:
                x = px + (pw - largura) // 2
                y = py + (ph - altura) // 2
            else:
                x = (self.winfo_screenwidth() - largura) // 2
                y = (self.winfo_screenheight() - altura) // 2
        except Exception:
            x = (self.winfo_screenwidth() - largura) // 2
            y = (self.winfo_screenheight() - altura) // 2
        self.geometry(f"{largura}x{altura}+{max(0, x)}+{max(0, y)}")

    def _escolher(self, continuar):
        if self._respondido:
            return
        self._respondido = True
        callback = self.ao_escolher
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        if callback:
            callback(bool(continuar))
