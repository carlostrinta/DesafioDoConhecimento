"""Testes do ponto de entrada (Etapa 3.7 + regressão da 3.6/3.7)."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


class LoggerFalso:
    def info(self, *args, **kwargs):
        pass


def _sem_log(monkeypatch, modulo):
    """Isola a montagem do log real (e do `logging.shutdown` global)."""
    monkeypatch.setattr(
        modulo.logging_conf, "configurar", lambda debug=False: LoggerFalso()
    )
    monkeypatch.setattr(modulo.logging_conf, "instalar_excepthook", lambda: None)
    monkeypatch.setattr(
        modulo.logging_conf, "tratar_excecao_tk", lambda *a, **k: None
    )
    monkeypatch.setattr(modulo.logging, "shutdown", lambda: None)


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


def test_iniciar_monta_a_raiz_e_roda_o_loop(monkeypatch):
    import main

    chamadas = {}

    class RootFalsa:
        def mainloop(self):
            chamadas["loop"] = True

    class AppFalsa:
        def __init__(self, root):
            chamadas["root"] = root

    _sem_log(monkeypatch, main)
    monkeypatch.setattr(main.tk, "Tk", lambda: RootFalsa())

    main.iniciar(AppFalsa)

    assert isinstance(chamadas["root"], RootFalsa)
    assert chamadas["loop"] is True
    assert callable(chamadas["root"].report_callback_exception)


def test_iniciar_instala_captura_de_callback_tk(monkeypatch):
    import main

    chamadas = {}
    criadas = []

    class RootFalsa:
        def mainloop(self):
            pass

    class AppFalsa:
        def __init__(self, root):
            pass

    _sem_log(monkeypatch, main)
    monkeypatch.setattr(
        main.logging_conf,
        "tratar_excecao_tk",
        lambda *a, parent=None: chamadas.update(args=a, parent=parent),
    )

    def criar_root():
        root = RootFalsa()
        criadas.append(root)
        return root

    monkeypatch.setattr(main.tk, "Tk", criar_root)

    main.iniciar(AppFalsa)

    root = criadas[0]
    erro = ValueError("falha em callback")
    root.report_callback_exception(ValueError, erro, None)

    assert chamadas["parent"] is root
    assert chamadas["args"] == (ValueError, erro, None)


def test_main_usa_o_app_do_desafio(monkeypatch):
    import desafio
    import main

    chamadas = {}

    class RootFalsa:
        def mainloop(self):
            chamadas["loop"] = True

    class AppFalsa:
        def __init__(self, root):
            chamadas["root"] = root

    _sem_log(monkeypatch, main)
    monkeypatch.setattr(desafio, "DueloDeConhecimento", AppFalsa)
    monkeypatch.setattr(main.tk, "Tk", lambda: RootFalsa())

    main.main([])

    assert isinstance(chamadas["root"], RootFalsa)
    assert chamadas["loop"] is True


def test_main_aceita_debug(monkeypatch):
    import main

    chamadas = {}
    monkeypatch.setattr(
        main,
        "iniciar",
        lambda app_cls, debug=False: chamadas.update(debug=debug, app=app_cls),
    )

    main.main(["--debug"])

    assert chamadas["debug"] is True


def test_auto_fechar_agenda_o_fechamento(monkeypatch):
    import main

    chamadas = {}

    class RootFalsa:
        def after(self, ms, callback):
            chamadas["ms"] = ms
            callback()

        def mainloop(self):
            pass

    class AppFalsa:
        def __init__(self, root):
            pass

        def fechar(self):
            chamadas["fechou"] = True

    _sem_log(monkeypatch, main)
    monkeypatch.setattr(main.tk, "Tk", lambda: RootFalsa())
    monkeypatch.setenv("DESAFIO_AUTO_FECHAR", "1")

    main.iniciar(AppFalsa)

    assert chamadas == {"ms": 1000, "fechou": True}


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
