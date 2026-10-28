"""
Ponto de entrada do Duelo de Conhecimento.

Aqui fica só a montagem: janela raiz, aplicação e loop do Tk. A lógica
(`jogo.py`), a interface (`desafio.py`, `ui_componentes.py`, `ui_selecao.py`),
a serial e o áudio vivem nos módulos próprios.

`DESAFIO_AUTO_FECHAR=1` agenda `fechar()` após 1 s; é o gancho usado pelo
teste de regressão que executa este arquivo como subprocesso.
"""

import os
import tkinter as tk

from desafio import DueloDeConhecimento


def main():
    root = tk.Tk()
    app = DueloDeConhecimento(root)
    if os.environ.get("DESAFIO_AUTO_FECHAR"):
        root.after(1000, app.fechar)
    root.mainloop()
    return app


if __name__ == "__main__":
    main()
