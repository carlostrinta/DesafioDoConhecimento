"""
Lista lateral do editor de perguntas (Etapa E2).

Componentes Tk clássicos (não Canvas) para integração com a janela modal do
editor. Inclui busca por texto, filtro por categoria, reordenação por
arrastar-e-soltar ou botões ↑/↓, seleção única e ações de CRUD.

A lista não guarda regra de negócio: todas as operações são delegadas aos
callbacks informados pelo editor, que por sua vez usam `BancoEditavel`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from editor_modelo import BancoEditavel, PerguntaEditavel
from ui_componentes import Cor

COR_SELECIONADA = "#1B2A54"


class ListaPerguntasEditor(tk.Frame):
    """
    Painel lateral esquerdo do editor.

    Callbacks:
    - ao_selecionar(pergunta: PerguntaEditavel | None) -> None
    - ao_novo() -> None
    - ao_duplicar(pergunta: PerguntaEditavel) -> None
    - ao_excluir(pergunta: PerguntaEditavel) -> bool
    - ao_mover(indice_origem: int, indice_destino: int) -> None
    """

    def __init__(
        self,
        master,
        banco: BancoEditavel,
        *,
        ao_selecionar: Callable[[Optional[PerguntaEditavel]], None],
        ao_novo: Callable[[], None],
        ao_duplicar: Callable[[PerguntaEditavel], None],
        ao_excluir: Callable[[PerguntaEditavel], bool],
        ao_mover: Callable[[int, int], None],
        largura: int = 380,
    ):
        super().__init__(master, bg=Cor.FUNDO, width=largura)
        self.banco = banco
        self.ao_selecionar = ao_selecionar
        self.ao_novo = ao_novo
        self.ao_duplicar = ao_duplicar
        self.ao_excluir = ao_excluir
        self.ao_mover = ao_mover
        self.largura = largura

        self._indices_filtrados: list[int] = []
        self._item_selecionado: Optional[int] = None
        self._drag_origem: Optional[int] = None
        self._suspender_filtros = False
        self._cards: list[tk.Frame] = []

        self._construir_ui()
        self.atualizar_lista()

    # ──────────────────────────────────────────────────────────
    # Construção
    # ──────────────────────────────────────────────────────────
    def _construir_ui(self):
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        # 1. Cabeçalho
        cabecalho = tk.Frame(self, bg=Cor.PAINEL, padx=12, pady=10)
        cabecalho.grid(row=0, column=0, sticky="ew")
        cabecalho.columnconfigure(0, weight=1)

        tk.Label(
            cabecalho,
            text="📝  PERGUNTAS",
            font=("Segoe UI", 12, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.PAINEL,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        self.lbl_contador = tk.Label(
            cabecalho,
            text="0 perguntas",
            font=("Segoe UI", 9),
            fg=Cor.SUAVE,
            bg=Cor.PAINEL,
            anchor="e",
        )
        self.lbl_contador.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        # 2. Barra de busca
        busca_frame = tk.Frame(self, bg=Cor.FUNDO, padx=12)
        busca_frame.grid(row=1, column=0, sticky="ew", pady=(8, 4))
        busca_frame.columnconfigure(0, weight=1)

        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", self._ao_mudar_filtro)
        self.entry_busca = tk.Entry(
            busca_frame,
            textvariable=self.var_busca,
            font=("Segoe UI", 10),
            bg=Cor.PAINEL,
            fg=Cor.TEXTO,
            insertbackground=Cor.TEXTO,
            relief="flat",
            highlightthickness=1,
            highlightbackground=Cor.BORDA,
            highlightcolor=Cor.A,
        )
        self.entry_busca.grid(row=0, column=0, sticky="ew", ipady=6, padx=(0, 8))
        self.entry_busca.bind("<Escape>", self._limpar_busca)

        tk.Label(
            busca_frame,
            text="🔍",
            font=("Segoe UI Emoji", 12),
            fg=Cor.SUAVE,
            bg=Cor.FUNDO,
        ).grid(row=0, column=1)

        # 3. Filtro por categoria
        cat_frame = tk.Frame(self, bg=Cor.FUNDO, padx=12)
        cat_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        cat_frame.columnconfigure(1, weight=1)

        tk.Label(
            cat_frame,
            text="Categoria:",
            font=("Segoe UI", 9),
            fg=Cor.SUAVE,
            bg=Cor.FUNDO,
        ).grid(row=0, column=0, padx=(0, 8))

        self.var_categoria = tk.StringVar(value="")
        self.var_categoria.trace_add("write", self._ao_mudar_filtro)
        self.combo_categoria = ttk.Combobox(
            cat_frame,
            textvariable=self.var_categoria,
            values=[],
            state="readonly",
            font=("Segoe UI", 9),
        )
        self.combo_categoria.grid(row=0, column=1, sticky="ew")
        self.combo_categoria.bind("<<ComboboxSelected>>", self._ao_mudar_filtro)
        self.combo_categoria.bind("<Escape>", self._limpar_categoria)

        # 4. Lista (Canvas + Scrollbar)
        lista_frame = tk.Frame(self, bg=Cor.FUNDO, padx=8)
        lista_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        lista_frame.columnconfigure(0, weight=1)
        lista_frame.rowconfigure(0, weight=1)

        self.canvas_lista = tk.Canvas(
            lista_frame,
            bg=Cor.FUNDO,
            highlightthickness=1,
            highlightbackground=Cor.BORDA,
            bd=0,
        )
        self.scrollbar = ttk.Scrollbar(
            lista_frame, orient="vertical", command=self.canvas_lista.yview
        )
        self.canvas_lista.configure(yscrollcommand=self.scrollbar.set)

        self.canvas_lista.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.container_itens = tk.Frame(self.canvas_lista, bg=Cor.FUNDO)
        self.janela_canvas = self.canvas_lista.create_window(
            (0, 0), window=self.container_itens, anchor="nw"
        )

        self.container_itens.bind("<Configure>", self._ao_configurar_container)
        self.canvas_lista.bind("<Configure>", self._ao_configurar_canvas)
        self.canvas_lista.bind("<MouseWheel>", self.rolar)
        self.canvas_lista.bind("<Button-4>", self.rolar)
        self.canvas_lista.bind("<Button-5>", self.rolar)

        # 5. Botões de ação (rodapé)
        botoes_frame = tk.Frame(self, bg=Cor.PAINEL, padx=12, pady=10)
        botoes_frame.grid(row=4, column=0, sticky="ew")
        for i in range(3):
            botoes_frame.columnconfigure(i, weight=1)

        estilo_btn = {
            "font": ("Segoe UI", 9, "bold"),
            "fg": Cor.TEXTO,
            "activeforeground": Cor.TEXTO,
            "relief": "flat",
            "bd": 0,
            "padx": 10,
            "pady": 6,
            "cursor": "hand2",
        }

        self.btn_novo = tk.Button(
            botoes_frame,
            text="➕ Novo",
            bg=Cor.A,
            activebackground="#5CB7FF",
            command=self._cb_novo,
            **estilo_btn,
        )
        self.btn_novo.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.btn_duplicar = tk.Button(
            botoes_frame,
            text="📋 Duplicar",
            bg="#555599",
            activebackground="#7777BB",
            command=self._cb_duplicar,
            state="disabled",
            **estilo_btn,
        )
        self.btn_duplicar.grid(row=0, column=1, sticky="ew", padx=4)

        self.btn_excluir = tk.Button(
            botoes_frame,
            text="🗑 Excluir",
            bg="#AA3333",
            activebackground="#CC5555",
            command=self._cb_excluir,
            state="disabled",
            **estilo_btn,
        )
        self.btn_excluir.grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def _ao_configurar_container(self, event=None):
        self.canvas_lista.configure(scrollregion=self.canvas_lista.bbox("all"))

    def _ao_configurar_canvas(self, event):
        self.canvas_lista.itemconfig(self.janela_canvas, width=event.width)

    def rolar(self, event):
        """Rola a lista; também pode ser chamada pelo editor."""
        if getattr(event, "delta", 0):
            passo = -1 if event.delta > 0 else 1
        elif getattr(event, "num", None) == 4:
            passo = -1
        else:
            passo = 1
        self.canvas_lista.yview_scroll(passo, "units")
        return "break"

    def limpar_bindings(self):
        """Compatibilidade: a versão atual não usa `bind_all`."""

    # ──────────────────────────────────────────────────────────
    # Atualização da lista
    # ──────────────────────────────────────────────────────────
    def atualizar_lista(self, preservar_selecao: bool = True):
        """Recalcula filtros e reconstrói os cards."""
        selecionado_antes = self._item_selecionado
        self._atualizar_categorias()
        self._indices_filtrados = self.banco.indices_filtrados(
            texto=self.var_busca.get(),
            categoria=self.var_categoria.get() or None,
        )

        if not preservar_selecao:
            self._item_selecionado = None
        elif (
            selecionado_antes is not None
            and selecionado_antes not in self._indices_filtrados
        ):
            self._item_selecionado = None

        self._renderizar_itens()
        self._atualizar_botoes_acao()

        if not preservar_selecao and selecionado_antes is not None:
            self.ao_selecionar(None)
        elif (
            preservar_selecao
            and selecionado_antes is not None
            and self._item_selecionado is None
        ):
            self.ao_selecionar(None)

    def _atualizar_categorias(self):
        categorias = self.banco.categorias()
        self.combo_categoria["values"] = [""] + categorias
        if self.var_categoria.get() and self.var_categoria.get() not in categorias:
            self._suspender_filtros = True
            try:
                self.var_categoria.set("")
            finally:
                self._suspender_filtros = False

    def _renderizar_itens(self):
        for widget in self.container_itens.winfo_children():
            widget.destroy()
        self._cards = []

        if not self._indices_filtrados:
            vazio = tk.Label(
                self.container_itens,
                text="Nenhuma pergunta encontrada.",
                font=("Segoe UI", 9),
                fg=Cor.SUAVE,
                bg=Cor.FUNDO,
                pady=20,
            )
            vazio.pack(fill="x")
            self._cards.append(vazio)

        for pos_lista, idx_banco in enumerate(self._indices_filtrados):
            pergunta = self.banco.perguntas[idx_banco]
            self._criar_card(pos_lista, idx_banco, pergunta)

        total = len(self.banco.perguntas)
        filtrados = len(self._indices_filtrados)
        if filtrados == total:
            texto = f"{total} pergunta" if total == 1 else f"{total} perguntas"
        else:
            texto = f"{filtrados} de {total} perguntas"
        self.lbl_contador.config(text=texto)
        self._ao_configurar_container()

    def _criar_card(self, pos_lista: int, idx_banco: int, pergunta: PerguntaEditavel):
        selecionado = self._item_selecionado == idx_banco
        cor_bg = COR_SELECIONADA if selecionado else Cor.PAINEL
        cor_borda = Cor.A if selecionado else Cor.BORDA
        esp_borda = 2 if selecionado else 1

        card = tk.Frame(
            self.container_itens,
            bg=cor_bg,
            highlightthickness=esp_borda,
            highlightbackground=cor_borda,
            padx=10,
            pady=8,
            cursor="hand2",
        )
        card.pack(fill="x", pady=2)
        card.idx_banco = idx_banco
        card.pos_lista = pos_lista
        card._widgets_bg = []
        card._lbl_num = None
        card._lbl_texto = None
        self._cards.append(card)

        col_principal = tk.Frame(card, bg=cor_bg)
        col_principal.pack(side="left", fill="both", expand=True)
        card._widgets_bg.append(col_principal)

        lbl_num = tk.Label(
            col_principal,
            text=f"{pos_lista + 1}.",
            font=("Segoe UI", 9, "bold"),
            fg=Cor.A if selecionado else Cor.APOIO,
            bg=cor_bg,
            anchor="w",
        )
        lbl_num.pack(anchor="w")
        card._widgets_bg.append(lbl_num)
        card._lbl_num = lbl_num

        texto = pergunta.texto.strip()
        if len(texto) > 80:
            texto = texto[:77] + "…"
        lbl_texto = tk.Label(
            col_principal,
            text=texto or "(sem enunciado)",
            font=("Segoe UI", 9),
            fg=Cor.TEXTO,
            bg=cor_bg,
            anchor="w",
            justify="left",
        )
        lbl_texto.pack(anchor="w", pady=(2, 0))
        card._widgets_bg.append(lbl_texto)
        card._lbl_texto = lbl_texto

        info_frame = tk.Frame(col_principal, bg=cor_bg)
        info_frame.pack(anchor="w", pady=(4, 0))
        card._widgets_bg.append(info_frame)

        if pergunta.categoria:
            lbl_cat = tk.Label(
                info_frame,
                text=f"🏷 {pergunta.categoria}",
                font=("Segoe UI", 8),
                fg=Cor.APOIO,
                bg=cor_bg,
            )
            lbl_cat.pack(side="left")
            card._widgets_bg.append(lbl_cat)

        n_alts = len(pergunta.alternativas)
        cor_alts = Cor.CERTO if 2 <= n_alts <= 4 else Cor.AVISO
        lbl_alts = tk.Label(
            info_frame,
            text=f"  {n_alts} alt.",
            font=("Segoe UI", 8),
            fg=cor_alts,
            bg=cor_bg,
        )
        lbl_alts.pack(side="left")
        card._widgets_bg.append(lbl_alts)

        # Botões de mover ficam à direita e não participam do arrasto.
        botoes_mover = tk.Frame(card, bg=cor_bg)
        botoes_mover.pack(side="right", padx=(8, 0))
        card._widgets_bg.append(botoes_mover)

        btn_cima = tk.Button(
            botoes_mover,
            text="▲",
            font=("Segoe UI", 8, "bold"),
            bg=Cor.PAINEL if pos_lista == 0 else Cor.BORDA,
            fg=Cor.APAGADO if pos_lista == 0 else Cor.SUAVE,
            activebackground=Cor.A,
            activeforeground=Cor.FUNDO,
            relief="flat",
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2" if pos_lista > 0 else "",
            command=lambda p=pos_lista: self._mover_item(p, -1),
            state="normal" if pos_lista > 0 else "disabled",
        )
        btn_cima.pack(pady=1)

        btn_baixo = tk.Button(
            botoes_mover,
            text="▼",
            font=("Segoe UI", 8, "bold"),
            bg=(
                Cor.PAINEL
                if pos_lista == len(self._indices_filtrados) - 1
                else Cor.BORDA
            ),
            fg=(
                Cor.APAGADO
                if pos_lista == len(self._indices_filtrados) - 1
                else Cor.SUAVE
            ),
            activebackground=Cor.A,
            activeforeground=Cor.FUNDO,
            relief="flat",
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2" if pos_lista < len(self._indices_filtrados) - 1 else "",
            command=lambda p=pos_lista: self._mover_item(p, 1),
            state=(
                "normal"
                if pos_lista < len(self._indices_filtrados) - 1
                else "disabled"
            ),
        )
        btn_baixo.pack(pady=1)

        # Clique seleciona e inicia um possível arrasto.
        def _pressionar(event, p=pos_lista):
            self._selecionar_por_posicao(p)
            self._drag_origem = p
            return "break"

        card.bind("<Button-1>", _pressionar)
        card.bind("<B1-Motion>", self._arrastar)
        card.bind("<ButtonRelease-1>", self._soltar_drag)

        for filho in (col_principal, lbl_num, lbl_texto, info_frame):
            filho.bind("<Button-1>", _pressionar)
            filho.bind("<B1-Motion>", self._arrastar)
            filho.bind("<ButtonRelease-1>", self._soltar_drag)

    # ──────────────────────────────────────────────────────────
    # Seleção e aparência
    # ──────────────────────────────────────────────────────────
    def _atualizar_visual_selecao(self):
        for card in self._cards:
            if not hasattr(card, "idx_banco"):
                continue
            selecionado = card.idx_banco == self._item_selecionado
            cor_bg = COR_SELECIONADA if selecionado else Cor.PAINEL
            for widget in getattr(card, "_widgets_bg", []):
                try:
                    widget.configure(bg=cor_bg)
                except tk.TclError:
                    pass
            try:
                card.configure(
                    bg=cor_bg,
                    highlightbackground=Cor.A if selecionado else Cor.BORDA,
                    highlightthickness=2 if selecionado else 1,
                )
            except tk.TclError:
                pass
            if card._lbl_num is not None:
                card._lbl_num.configure(fg=Cor.A if selecionado else Cor.APOIO)

    def _selecionar_por_posicao(self, pos_lista: int):
        if not (0 <= pos_lista < len(self._indices_filtrados)):
            return
        idx_banco = self._indices_filtrados[pos_lista]
        if self._item_selecionado == idx_banco:
            return
        self._item_selecionado = idx_banco
        self._atualizar_visual_selecao()
        self._atualizar_botoes_acao()
        self.ao_selecionar(self.banco.perguntas[idx_banco])

    def _atualizar_botoes_acao(self):
        tem_selecao = self._item_selecionado is not None
        self.btn_duplicar.config(state="normal" if tem_selecao else "disabled")
        self.btn_excluir.config(state="normal" if tem_selecao else "disabled")

    def indice_selecionado(self) -> Optional[int]:
        return self._item_selecionado

    def limpar_selecao(self):
        if self._item_selecionado is None:
            return
        self._item_selecionado = None
        self._atualizar_visual_selecao()
        self._atualizar_botoes_acao()
        self.ao_selecionar(None)

    # ──────────────────────────────────────────────────────────
    # Filtros
    # ──────────────────────────────────────────────────────────
    def _ao_mudar_filtro(self, *_):
        if self._suspender_filtros:
            return
        self.atualizar_lista(preservar_selecao=True)

    def _aplicar_filtros(self):
        self.atualizar_lista(preservar_selecao=True)

    def _limpar_busca(self, event=None):
        self.var_busca.set("")
        return "break"

    def _limpar_categoria(self, event=None):
        self.var_categoria.set("")
        self._aplicar_filtros()
        return "break"

    def focus_busca(self):
        """Coloca o foco na busca (chamado ao abrir o editor)."""
        try:
            self.entry_busca.focus_set()
            self.entry_busca.selection_range(0, "end")
        except tk.TclError:
            pass

    # ──────────────────────────────────────────────────────────
    # Ações (callbacks)
    # ──────────────────────────────────────────────────────────
    def _cb_novo(self):
        self.ao_novo()

    def _cb_duplicar(self):
        if self._item_selecionado is not None:
            self.ao_duplicar(self.banco.perguntas[self._item_selecionado])

    def _cb_excluir(self):
        if self._item_selecionado is not None:
            self.ao_excluir(self.banco.perguntas[self._item_selecionado])

    # ──────────────────────────────────────────────────────────
    # Reordenação
    # ──────────────────────────────────────────────────────────
    def _mover_item(self, pos_lista: int, delta: int):
        if not (0 <= pos_lista < len(self._indices_filtrados)):
            return
        nova_pos = pos_lista + delta
        if not (0 <= nova_pos < len(self._indices_filtrados)):
            return
        idx_origem = self._indices_filtrados[pos_lista]
        idx_destino = self._indices_filtrados[nova_pos]
        self.ao_mover(idx_origem, idx_destino)

    def mover_selecionado(self, delta: int):
        """Move a pergunta selecionada dentro da lista filtrada."""
        if self._item_selecionado is None:
            return
        try:
            pos = self._indices_filtrados.index(self._item_selecionado)
        except ValueError:
            return
        self._mover_item(pos, delta)

    def selecionar_relativo(self, delta: int):
        """Seleciona a pergunta anterior/próxima na lista filtrada."""
        if not self._indices_filtrados:
            return
        if self._item_selecionado in self._indices_filtrados:
            nova_pos = self._indices_filtrados.index(self._item_selecionado) + delta
        else:
            nova_pos = 0 if delta > 0 else len(self._indices_filtrados) - 1
        nova_pos = max(0, min(len(self._indices_filtrados) - 1, nova_pos))
        self._selecionar_por_posicao(nova_pos)
        self._scroll_para_posicao(nova_pos)

    def _arrastar(self, event):
        if self._drag_origem is None:
            return
        try:
            y = event.y_root - self.canvas_lista.winfo_rooty()
            altura = self.canvas_lista.winfo_height()
        except tk.TclError:
            return
        if y < 32:
            self.canvas_lista.yview_scroll(-1, "units")
        elif y > altura - 32:
            self.canvas_lista.yview_scroll(1, "units")

    def _soltar_drag(self, event):
        origem = self._drag_origem
        self._drag_origem = None
        if origem is None or not (0 <= origem < len(self._indices_filtrados)):
            return
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return
        while widget is not None and widget is not self:
            if hasattr(widget, "pos_lista") and hasattr(widget, "idx_banco"):
                destino = widget.pos_lista
                if destino != origem:
                    idx_origem = self._indices_filtrados[origem]
                    idx_destino = self._indices_filtrados[destino]
                    self.ao_mover(idx_origem, idx_destino)
                return
            widget = getattr(widget, "master", None)

    # ──────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────
    def selecionar_indice_banco(self, idx_banco: int):
        """Seleciona pelo índice no banco, limpando filtros se necessário."""
        if not (0 <= idx_banco < len(self.banco.perguntas)):
            return
        if idx_banco not in self._indices_filtrados:
            self._suspender_filtros = True
            try:
                self.var_busca.set("")
                self.var_categoria.set("")
            finally:
                self._suspender_filtros = False
            self._atualizar_categorias()
            self._indices_filtrados = list(range(len(self.banco.perguntas)))
            self._renderizar_itens()
            self._atualizar_botoes_acao()

        try:
            pos = self._indices_filtrados.index(idx_banco)
        except ValueError:
            return
        self._selecionar_por_posicao(pos)
        self._scroll_para_posicao(pos)

    def selecionar_por_id(self, id_interno: str):
        for i, pergunta in enumerate(self.banco.perguntas):
            if getattr(pergunta, "id_interno", None) == id_interno:
                self.selecionar_indice_banco(i)
                return

    def _scroll_para_posicao(self, pos_lista: int):
        if not (0 <= pos_lista < len(self._cards)):
            return
        card = self._cards[pos_lista]
        if not hasattr(card, "winfo_y"):
            return
        self.update_idletasks()
        try:
            altura_container = max(1, self.container_itens.winfo_height())
            topo = card.winfo_y()
        except tk.TclError:
            return
        self.canvas_lista.yview_moveto(max(0, topo - 60) / altura_container)

    def on_banco_alterado(self):
        """Chamado quando o banco muda externamente (undo/redo, carregar)."""
        self.atualizar_lista(preservar_selecao=True)
