"""Testes do ponto de entrada (Etapa 3.7)."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

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


def _tk_disponivel():
    try:
        import tkinter as tk

        root = tk.Tk()
        root.destroy()
        return True
    except Exception:
        return False


def test_main_abre_a_janela_e_sai_limpo():
    """Roda `python main.py` de verdade; a janela fecha sozinha após 1 s."""
    if not _tk_disponivel():
        pytest.skip("Tk indisponível (ambiente headless)")

    env = os.environ.copy()
    env["DESAFIO_AUTO_FECHAR"] = "1"

    processo = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(RAIZ),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.5)
        assert processo.poll() is None, (
            "main.py saiu antes de abrir a janela "
            "(montagem não executou ou falhou na inicialização)"
        )
        saida, erro = processo.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        processo.kill()
        saida, erro = processo.communicate()
        pytest.fail(f"main.py não fechou com DESAFIO_AUTO_FECHAR:\n{saida}\n{erro}")

    assert processo.returncode == 0, f"stdout={saida}\nstderr={erro}"
    assert "Traceback" not in erro, erro
