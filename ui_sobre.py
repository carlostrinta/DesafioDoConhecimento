"""
Tela "Sobre" do Desafio do Conhecimento (F1).

A janela é posicionada e dimensionada dentro da área central da aplicação
para não cobrir a barra de topo, os cartões de placar nem o overlay da
contagem. Os metadados vêm exclusivamente de `versao.py`.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser

from ui_componentes import Cor
from versao import AUTOR, LICENCA, NOME, URL, VERSAO


class TelaSobre(tk.Toplevel):
    """Janela modal com nome, versão, autor, link e licença."""

    def __init__(self, parent, ao_fechar=None):
        super().__init__(parent)
        self.parent = parent
        self.ao_fechar = ao_fechar
        self._fechada = False

        self.title(f"Sobre — {NOME}")
        self.configure(bg=Cor.FUNDO)
        self.resizable(False, False)

        try:
            self.transient(parent)
        except tk.TclError:
            pass

        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self._construir_ui()
        self._posicionar()
        self.bind("<Escape>", lambda e: self.fechar())
        self.bind("<F1>", lambda e: self.fechar())
        self.bind("<Return>", lambda e: self.fechar())
        self.bind("<KP_Enter>", lambda e: self.fechar())

        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()

    def _construir_ui(self):
        topo = tk.Frame(self, bg=Cor.PAINEL, padx=28, pady=18)
        topo.pack(side="top", fill="x")

        tk.Label(
            topo,
            text=NOME,
            font=("Segoe UI", 19, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.PAINEL,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            topo,
            text=f"Versão {VERSAO}",
            font=("Segoe UI", 10),
            fg=Cor.SUAVE,
            bg=Cor.PAINEL,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        corpo = tk.Frame(self, bg=Cor.FUNDO, padx=28, pady=18)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)

        self._linha(corpo, 0, "Autor", AUTOR)
        self._linha(corpo, 1, "Licença do código", LICENCA)
        self._linha(corpo, 2, "Perguntas", "CC BY 4.0 — Carlos Santos")
        self._linha(corpo, 3, "Projeto", URL, link=True)

        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        rodape = tk.Frame(self, bg=Cor.PAINEL, padx=20, pady=12)
        rodape.pack(side="bottom", fill="x")

        tk.Label(
            rodape,
            text="F1 ou Esc para fechar",
            font=("Segoe UI", 8),
            fg=Cor.APAGADO,
            bg=Cor.PAINEL,
            anchor="w",
        ).pack(side="left")

        tk.Button(
            rodape,
            text="Fechar",
            font=("Segoe UI", 9, "bold"),
            bg=Cor.A,
            fg=Cor.FUNDO,
            activebackground="#5CB7FF",
            activeforeground=Cor.FUNDO,
            relief="flat",
            bd=0,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self.fechar,
        ).pack(side="right")

    def _linha(self, master, linha, rotulo, valor, link=False):
        tk.Label(
            master,
            text=rotulo,
            font=("Segoe UI", 9, "bold"),
            fg=Cor.SUAVE,
            bg=Cor.FUNDO,
            anchor="w",
        ).grid(row=linha, column=0, sticky="w", padx=(0, 16), pady=5)

        label = tk.Label(
            master,
            text=valor,
            font=("Segoe UI", 10),
            fg=Cor.A if link else Cor.TEXTO,
            bg=Cor.FUNDO,
            anchor="w",
            justify="left",
            cursor="hand2" if link else "",
        )
        label.grid(row=linha, column=1, sticky="w", pady=5)
        if link:
            label.bind("<Button-1>", lambda e: webbrowser.open(URL))
        return label

    def _posicionar(self):
        self.update_idletasks()
        try:
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
        except tk.TclError:
            pw = ph = 0
            px = py = 0

        if pw < 400 or ph < 300:
            pw, ph, px, py = 1280, 800, 0, 0

        largura = max(420, min(680, int(pw * 0.52)))
        altura = max(280, min(420, int(ph * 0.58)))
        x = px + (pw - largura) // 2
        y = py + (ph - altura) // 2
        self.geometry(f"{largura}x{altura}+{max(0, x)}+{max(0, y)}")

    def fechar(self):
        if self._fechada:
            return
        self._fechada = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        callback = self.ao_fechar
        self.destroy()
        if callback:
            callback()
