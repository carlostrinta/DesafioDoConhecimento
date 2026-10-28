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


def test_desafio_executado_diretamente_orienta_o_entrypoint():
    """`python desafio.py` não monta nada: avisa e sai com erro."""
    saida = subprocess.run(
        [sys.executable, "desafio.py"],
        capture_output=True,
        text=True,
        cwd=str(RAIZ),
        timeout=30,
    )

    assert saida.returncode == 1, saida.stderr
    assert "Use: python main.py" in saida.stdout
    assert "Traceback" not in saida.stderr
