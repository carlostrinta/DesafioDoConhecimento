"""
Regressão de Tk real da contagem de largada (Etapa 4.6).

O bug original só aparecia no caminho completo: confirmar o tema, carregar a
primeira pergunta e desenhar o overlay (`_mostrar_contagem`). Os testes de
regra usavam `object.__new__`/Canvas isolado e não passavam por esse caminho.

Aqui a `DueloDeConhecimento` é montada de verdade, com Tk real, mas com
serial, áudio, trava e persistência falsos. O relógio do `Jogo` é injetável;
os `after()` do Tk são drenados com `update()`. Em ambiente headless o teste
é pulado.
"""

import json
from types import SimpleNamespace

import pytest

import desafio
import ui_componentes
from apoio_tk import criar_raiz_tk
from jogo import FASE_AGUARDANDO, FASE_CONTAGEM, Jogo
from ui_selecao import ModalSelecaoPerguntas


class Relogio:
    def __init__(self, agora=100.0):
        self.agora = agora

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


class TravaFalsa:
    def adquirir(self):
        return None

    def liberar(self):
        return None


class SerialFalsa:
    def __init__(self, fila, log=None):
        self.fila = fila

    def iniciar(self):
        return None

    def enviar(self, comando):
        return None

    def parar(self):
        return None


class SomFalso:
    disponivel = True
    ativo = True

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, nome):
        return lambda *args, **kwargs: None


class SalvadorFalso:
    def __init__(self, *args, **kwargs):
        pass

    def pedir(self):
        return None

    def pedir_imediato(self):
        return None

    def executar_agora(self):
        return None


def _banco(tmp_path):
    caminho = tmp_path / "banco.json"
    caminho.write_text(
        json.dumps(
            [
                {
                    "pergunta": f"Pergunta {i}?",
                    "alternativas": ["Certa", "Errada"],
                    "correta": 0,
                    "categoria": "Teste",
                    "explicacao": f"Explicação {i}.",
                }
                for i in range(1, 5)
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return caminho


@pytest.fixture(scope="module")
def raiz_tk():
    import tkinter as tk

    try:
        root = criar_raiz_tk()
    except tk.TclError as e:
        pytest.skip(f"Tk indisponível: {e}")

    def reportar(tipo, valor, tb):
        raise valor

    root.report_callback_exception = reportar
    yield root
    root.destroy()


@pytest.fixture
def montar_app(tmp_path, monkeypatch, raiz_tk):
    import tkinter as tk

    # Isola tudo que a DueloDeConhecimento toca fora da UI.
    monkeypatch.setattr(desafio.persistencia, "TravaInstancia", TravaFalsa)
    monkeypatch.setattr(
        desafio.persistencia,
        "carregar",
        lambda *a, **k: SimpleNamespace(partida=None, motivo=""),
    )
    monkeypatch.setattr(
        desafio.persistencia, "AgendadorSalvamento", SalvadorFalso
    )
    monkeypatch.setattr(desafio, "ComunicacaoSerial", SerialFalsa)
    monkeypatch.setattr(desafio, "Som", SomFalso)
    monkeypatch.setattr(desafio, "CONFIG", SimpleNamespace(avisos=()))
    monkeypatch.setattr(desafio, "PASTA_PERGUNTAS", str(tmp_path))
    monkeypatch.setattr(desafio, "ARQUIVO_PERGUNTAS", "banco.json")
    # O fluxo inicial abriria o modal de tema; o teste o abre e confirma.
    monkeypatch.setattr(
        desafio.DueloDeConhecimento, "_iniciar_fluxo_inicial", lambda self: None
    )

    banco = _banco(tmp_path)
    escala_original = ui_componentes.ESCALA
    familias_originais = dict(ui_componentes.FAMILIAS)
    criados = []

    def montar(contagem=3, mostrar_pergunta=False):
        # Uma raiz só para o módulo: o Tk do Python 3.12 fica instável ao
        # criar/destruir vários `Tk` no mesmo processo. Cada teste ganha um
        # Toplevel novo, que é destruído no teardown.
        root = tk.Toplevel(raiz_tk)
        # Evita "zoomed" no teste.
        root.state = lambda *a: None

        ui_componentes.definir_escala(1.0)
        app = desafio.DueloDeConhecimento(root)
        relogio = Relogio()
        app.jogo = Jogo(
            [],
            num_equipes=2,
            tempo_pergunta=30,
            tempo_resposta=15,
            clock=relogio,
            contagem_largada=contagem,
            mostrar_pergunta_na_contagem=mostrar_pergunta,
        )
        criados.append((app, root))
        root.update()
        return app, root, relogio

    yield montar, banco

    for app, root in criados:
        app.rodando = False
        try:
            for job in root.tk.call("after", "info"):
                try:
                    root.after_cancel(job)
                except Exception:
                    pass
        except Exception:
            pass
        for atributo in (
            "_job_timer",
            "_job_aviso",
            "_job_escala",
            "_job_contagem_visual",
        ):
            job = getattr(app, atributo, None)
            if job:
                try:
                    root.after_cancel(job)
                except Exception:
                    pass
        try:
            root.update_idletasks()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    ui_componentes.definir_escala(escala_original)
    ui_componentes.FAMILIAS.clear()
    ui_componentes.FAMILIAS.update(familias_originais)


def _escolher_tema(app, root, banco):
    """Percorre o modal real: escolher tema -> primeira pergunta."""
    app.abrir_seletor_tema(inicial=True)
    root.update()
    modal = next(
        w for w in root.winfo_children()
        if isinstance(w, ModalSelecaoPerguntas)
    )
    modal.arquivo_selecionado = {
        "caminho": str(banco),
        "titulo": "Teste",
    }
    modal._confirmar()
    root.update()


def _textos_do_overlay(app):
    overlay = app.overlay_contagem
    return [
        overlay.itemcget(item, "text")
        for item in overlay.find_all()
        if overlay.type(item) == "text"
    ]


def _fonte_do_numero(app, valor):
    overlay = app.overlay_contagem
    item = next(
        i for i in overlay.find_all()
        if overlay.type(i) == "text"
        and overlay.itemcget(i, "text") == valor
    )
    return int(overlay.itemcget(item, "font").rsplit(" ", 2)[-2])


def _avancar(app, root, relogio, segundos):
    relogio.avancar(segundos)
    app._cancelar_job_timer()
    # Passa pelo after() do Tk, em vez de chamar _tick direto: o update()
    # processa o callback como no loop real.
    root.after(0, app._tick)
    root.update()


def _confirmar_contagem(app, root, relogio):
    assert app.fase == FASE_CONTAGEM
    assert app.overlay_contagem.winfo_ismapped()
    assert app.jogo.timer_ativo is False

    _avancar(app, root, relogio, app.jogo.contagem_largada)

    assert app.fase == FASE_AGUARDANDO
    assert app.jogo.timer_ativo is True
    assert app.overlay_contagem.winfo_ismapped()
    assert "JÁ!" in _textos_do_overlay(app)
    assert app._job_contagem_visual is not None

    # O job de 500 ms esconde o "JÁ!" e redesenha a pergunta.
    app._ocultar_contagem()
    root.update()
    assert not app.overlay_contagem.winfo_ismapped()
    assert app.cartao_pergunta.winfo_ismapped()


def test_fluxo_real_3_2_1_ja_chega_em_aguardando(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=3)

    _escolher_tema(app, root, banco)

    assert app.fase == FASE_CONTAGEM
    assert app.overlay_contagem.winfo_ismapped()
    assert "3" in _textos_do_overlay(app)
    # Padrão: pergunta oculta durante a contagem.
    assert not app.cartao_pergunta.winfo_ismapped()

    _avancar(app, root, relogio, 1)
    assert "2" in _textos_do_overlay(app)
    _avancar(app, root, relogio, 1)
    assert "1" in _textos_do_overlay(app)

    _confirmar_contagem(app, root, relogio)


def test_contagem_zero_nao_mostra_overlay(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=0)

    _escolher_tema(app, root, banco)

    assert app.fase == FASE_AGUARDANDO
    assert app.jogo.contagem_ativa is False
    assert app.jogo.timer_ativo is True
    assert not app.overlay_contagem.winfo_ismapped()
    assert app.cartao_pergunta.winfo_ismapped()


def test_contagem_de_um_segundo(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=1)

    _escolher_tema(app, root, banco)
    assert "1" in _textos_do_overlay(app)

    _confirmar_contagem(app, root, relogio)


def test_contagem_de_dez_segundos(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=10)

    _escolher_tema(app, root, banco)
    assert "10" in _textos_do_overlay(app)

    _avancar(app, root, relogio, 1)
    assert "9" in _textos_do_overlay(app)
    _avancar(app, root, relogio, 8)
    assert "1" in _textos_do_overlay(app)

    _confirmar_contagem(app, root, relogio)


def test_mostrar_pergunta_na_contagem(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=3, mostrar_pergunta=True)

    _escolher_tema(app, root, banco)

    assert app.fase == FASE_CONTAGEM
    assert app.overlay_contagem.winfo_ismapped()
    assert app.cartao_pergunta.winfo_ismapped()
    assert app.cartoes_alt[0].winfo_ismapped()
    assert app.cartoes_alt[1].winfo_ismapped()
    # O overlay é o widget do topo no palco (tkraise, não tag_raise).
    assert app.overlay_contagem.master.winfo_children()[-1] is app.overlay_contagem

    _confirmar_contagem(app, root, relogio)


def test_redimensionamento_no_meio_da_contagem(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=3)

    _escolher_tema(app, root, banco)
    fonte_antes = _fonte_do_numero(app, "3")

    root.geometry("900x600")
    root.update()
    app._aplicar_escala()
    root.update()

    assert app.fase == FASE_CONTAGEM
    assert app.overlay_contagem.winfo_ismapped()
    assert "3" in _textos_do_overlay(app)
    assert app.overlay_contagem.winfo_width() > 0
    fonte_depois = _fonte_do_numero(app, "3")
    assert fonte_depois <= fonte_antes
    assert fonte_depois >= 7

    _avancar(app, root, relogio, 1)
    assert "2" in _textos_do_overlay(app)

    _confirmar_contagem(app, root, relogio)
