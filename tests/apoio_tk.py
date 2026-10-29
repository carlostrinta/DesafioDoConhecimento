"""Criação de raiz Tk real para os testes.

No Python 3.12 do `uv` no Windows, a criação de uma segunda raiz no mesmo
processo falha intermitentemente depois que a primeira foi destruída. O Tcl
reporta `invalid command name "tcl_findLibrary"` ou não consegue ler
`ttk/entry.tcl`, embora os arquivos existam. É uma falha de inicialização do
interpretador, não do aplicativo.

Para não transformar isso em skip silencioso, a criação é repetida algumas
vezes. Se todas falharem, o último `TclError` é propagado; o teste decide se
pula (ambiente realmente headless) e mostra a mensagem original.
"""

from __future__ import annotations

import time
import tkinter as tk


def criar_raiz_tk(tentativas: int = 6, retirar: bool = True) -> tk.Tk:
    ultimo = None
    for tentativa in range(tentativas):
        root = None
        try:
            root = tk.Tk()
            if retirar:
                root.withdraw()
            return root
        except tk.TclError as e:
            ultimo = e
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass
            if tentativa + 1 < tentativas:
                time.sleep(0.05 * (tentativa + 1))
    raise ultimo
