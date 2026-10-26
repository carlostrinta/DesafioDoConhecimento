"""
Ponto de entrada do Duelo de Conhecimento.

Aqui fica só a montagem: janela raiz, aplicação e loop do Tk. A lógica
(`jogo.py`), a interface (`desafio.py`, `ui_componentes.py`, `ui_selecao.py`),
a serial e o áudio vivem nos módulos próprios.
"""

import tkinter as tk

from desafio import DueloDeConhecimento


def main():
    root = tk.Tk()
    app = DueloDeConhecimento(root)
    root.mainloop()
    return app


if __name__ == "__main__":
    main()
