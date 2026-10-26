"""Testes do ponto de entrada (Etapa 3.7)."""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_importar_main_nao_abre_janela():
    codigo = (
        "import tkinter, main; "
        "assert callable(main.main); "
        "assert tkinter._default_root is None"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=str(RAIZ),
    )
    assert saida.returncode == 0, saida.stderr


def test_main_monta_e_inicia_o_loop(monkeypatch):
    import main

    chamadas = {}

    class RootFalsa:
        def mainloop(self):
            chamadas["loop"] = True

    class AppFalsa:
        def __init__(self, root):
            chamadas["root"] = root

    monkeypatch.setattr(main.tk, "Tk", lambda: RootFalsa())
    monkeypatch.setattr(main, "DueloDeConhecimento", AppFalsa)

    main.main()

    assert isinstance(chamadas["root"], RootFalsa)
    assert chamadas["loop"] is True


def test_desafio_nao_monta_a_aplicacao():
    fonte = (RAIZ / "desafio.py").read_text(encoding="utf-8")
    assert 'if __name__ == "__main__"' not in fonte
