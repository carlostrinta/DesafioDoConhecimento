"""
Regressão de Tk real da Etapa 5: placar dinâmico e teclado de 2 a 4 equipes.

Os testes montam a `DueloDeConhecimento` de verdade, com serial, áudio,
trava e persistência falsos. Em ambiente sem display são pulados.
"""

import json
from types import SimpleNamespace

import pytest

import desafio
import ui_componentes
from apoio_tk import criar_raiz_tk
from jogo import (
    FASE_AGUARDANDO,
    FASE_CONTAGEM,
    FASE_REVELADA,
    FASE_RESPONDENDO,
    Jogo,
)
from ui_selecao import ModalSelecaoPerguntas


_INICIAR_FLUXO_ORIGINAL = desafio.DueloDeConhecimento._iniciar_fluxo_inicial


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
                for i in range(1, 7)
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

    monkeypatch.setattr(desafio.persistencia, "TravaInstancia", TravaFalsa)
    monkeypatch.setattr(
        desafio.persistencia,
        "carregar",
        lambda *a, **k: SimpleNamespace(partida=None, motivo=""),
    )
    monkeypatch.setattr(desafio.persistencia, "AgendadorSalvamento", SalvadorFalso)
    monkeypatch.setattr(desafio, "ComunicacaoSerial", SerialFalsa)
    monkeypatch.setattr(desafio, "Som", SomFalso)
    monkeypatch.setattr(desafio, "CONFIG", SimpleNamespace(avisos=()))
    monkeypatch.setattr(desafio, "PASTA_PERGUNTAS", str(tmp_path))
    monkeypatch.setattr(desafio, "ARQUIVO_PERGUNTAS", "banco.json")
    monkeypatch.setattr(
        desafio.DueloDeConhecimento, "_iniciar_fluxo_inicial", lambda self: None
    )

    banco = _banco(tmp_path)
    escala_original = ui_componentes.ESCALA
    familias_originais = dict(ui_componentes.FAMILIAS)
    criados = []

    def montar(
        contagem=0, num_equipes=2, tamanho=None, relogio_protocolo=None
    ):
        monkeypatch.setattr(desafio, "NUM_EQUIPES", num_equipes)
        root = tk.Toplevel(raiz_tk)
        root.state = lambda *a: None

        ui_componentes.definir_escala(1.0)
        app = desafio.DueloDeConhecimento(root, clock=relogio_protocolo)
        relogio = Relogio()
        app.jogo = Jogo(
            [],
            num_equipes=num_equipes,
            tempo_pergunta=30,
            tempo_resposta=15,
            clock=relogio,
            contagem_largada=contagem,
        )
        app.render()
        criados.append((app, root))
        if tamanho:
            root.geometry(f"{tamanho[0]}x{tamanho[1]}")
        root.update()
        if tamanho:
            app._aplicar_escala()
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
    app.abrir_seletor_tema(inicial=True)
    root.update()
    modal = next(
        w
        for w in root.winfo_children()
        if isinstance(w, ModalSelecaoPerguntas)
    )
    modal.arquivo_selecionado = {"caminho": str(banco), "titulo": "Teste"}
    modal._confirmar()
    root.update()


def _tecla(root, keysym, state=0):
    root.focus_force()
    root.update()
    root.event_generate("<KeyPress>", keysym=keysym, state=state)
    root.update()


def _avancar(app, root, relogio, segundos):
    relogio.avancar(segundos)
    app._cancelar_job_timer()
    root.after(0, app._tick)
    root.update()


def _confirmar_contagem(app, root, relogio):
    _avancar(app, root, relogio, app.jogo.contagem_largada)
    assert app.fase == FASE_AGUARDANDO


def test_f1_abre_sobre_reutiliza_e_respeita_contagem(montar_app):
    montar, _banco = montar_app
    app, root, _relogio = montar()

    assert root.bind("<F1>")
    app.abrir_sobre()
    root.update()

    janela = app._janela_sobre
    assert janela is not None
    assert janela.winfo_exists()

    app.abrir_sobre()
    root.update()
    assert app._janela_sobre is janela

    janela.fechar()
    root.update()
    assert app._janela_sobre is None

    # Enquanto a contagem (ou o "JÁ!") está visível, o F1 não abre a tela.
    app._contagem_visual = "JÁ!"
    app.abrir_sobre()
    root.update()
    assert app._janela_sobre is None


@pytest.mark.parametrize("num_equipes", [2, 3, 4])
def test_teclas_de_equipe_respeitam_numero_de_equipes(
    montar_app, num_equipes
):
    montar, banco = montar_app
    app, root, _relogio = montar(num_equipes=num_equipes)
    _escolher_tema(app, root, banco)

    ativas = "ABCD"[:num_equipes]
    inativas = "ABCD"[num_equipes:]

    # Teclas de equipe e de ponto inativas não podem apertar nem bloquear.
    for letra in inativas:
        _tecla(root, letra.lower())
        _tecla(root, letra.upper(), state=0x2)  # Caps Lock
        _tecla(root, str("ABCD".index(letra) + 1))
        assert app.fase == FASE_AGUARDANDO
        assert app.quem_apertou is None
        assert app.jogo.placar == {equipe: 0 for equipe in ativas}

    for indice, letra in enumerate(ativas):
        # Alterna minúscula e maiúscula (Shift/Caps Lock) na mesma regressão.
        if indice % 2:
            _tecla(root, letra.upper(), state=0x1)
        else:
            _tecla(root, letra)
        assert app.fase == FASE_RESPONDENDO
        assert app.quem_apertou == letra

        _tecla(root, "r")
        assert app.fase == FASE_REVELADA

        # Ponto de equipe inativa não pode pontuar.
        for outra in inativas:
            _tecla(root, str("ABCD".index(outra) + 1))
            assert app.jogo.placar[letra] == 0

        _tecla(root, str("ABCD".index(letra) + 1))
        assert app.jogo.placar[letra] == 1

        _tecla(root, "n")
        assert app.fase == FASE_AGUARDANDO


def test_countdown_ignora_equipes_e_avisa_nas_outras_teclas(montar_app):
    montar, banco = montar_app
    app, root, relogio = montar(contagem=3, num_equipes=4)
    _escolher_tema(app, root, banco)
    assert app.fase == FASE_CONTAGEM

    for letra in "ABCD":
        _tecla(root, letra.lower())
        assert app.fase == FASE_CONTAGEM
        assert app.quem_apertou is None

    for keysym in ("1", "3", "4", "r", "n"):
        _tecla(root, keysym)
        assert app.fase == FASE_CONTAGEM
        assert "Aguarde o JÁ!" in app.aviso

    _confirmar_contagem(app, root, relogio)
    _tecla(root, "d")
    assert app.fase == FASE_RESPONDENDO
    assert app.quem_apertou == "D"


def test_ctrl_c_e_ctrl_d_nao_aperam_equipe(montar_app):
    montar, banco = montar_app
    app, root, _relogio = montar(num_equipes=4)
    _escolher_tema(app, root, banco)

    _tecla(root, "c", state=0x4)
    _tecla(root, "d", state=0x4)
    _tecla(root, "C", state=0x5)
    _tecla(root, "D", state=0x5)

    assert app.fase == FASE_AGUARDANDO
    assert app.quem_apertou is None
    assert app.jogo.placar == {"A": 0, "B": 0, "C": 0, "D": 0}


@pytest.mark.parametrize(
    "protocolo, trecho",
    [
        ("v1", "Arduino v1"),
        ("sem_handshake", "Sem handshake"),
    ],
)
def test_protocolo_sem_suporte_limita_para_duas_e_avisa(
    montar_app, protocolo, trecho
):
    montar, _banco = montar_app
    app, root, _relogio = montar(num_equipes=4)

    app._aplicar_protocolo(protocolo)
    root.update()

    assert app.jogo.num_equipes == 2
    assert app.jogo.equipes_ativas == ("A", "B")
    assert set(app.cartoes_placar) == {"A", "B"}
    assert trecho in app.topo.aviso_protocolo
    assert "pontos de C/D guardados nesta sessão" in app.topo.aviso_protocolo
    assert trecho in app.aviso
    assert len(app.rodape.msg) > 0


def test_protocolo_v2_mantem_quatro_equipes(montar_app):
    montar, _banco = montar_app
    app, root, _relogio = montar(num_equipes=4)

    app.processar_evento("PRONTO")
    root.update()
    assert app._job_versao is not None

    app.processar_evento("VERSAO 2")
    root.update()

    assert app.protocolo_arduino == "v2"
    assert app._job_versao is None
    assert app.jogo.num_equipes == 4
    assert set(app.cartoes_placar) == {"A", "B", "C", "D"}
    assert app.topo.aviso_protocolo == ""


def test_pronto_sem_versao_cai_para_v1(montar_app):
    montar, _banco = montar_app
    relogio = Relogio()
    app, root, _relogio = montar(
        num_equipes=4, relogio_protocolo=relogio
    )

    app.processar_evento("PRONTO")
    relogio.avancar(desafio.TIMEOUT_PRONTO)
    app._confirmar_protocolo_v1()
    root.update()

    assert app.protocolo_arduino == "v1"
    assert app.jogo.num_equipes == 2


def test_janela_do_versao_2_usa_timeout_pronto_e_relogio(
    montar_app, monkeypatch
):
    montar, _banco = montar_app
    relogio = Relogio()
    app, root, _relogio = montar(
        num_equipes=3, relogio_protocolo=relogio
    )
    monkeypatch.setattr(desafio, "TIMEOUT_PRONTO", 2.5)

    agendados = []

    def after(ms, callback):
        agendados.append((ms, callback))
        return f"job{len(agendados)}"

    monkeypatch.setattr(root, "after", after)
    monkeypatch.setattr(root, "after_cancel", lambda job: None)

    app.processar_evento("PRONTO")

    assert agendados[-1][0] == 2500
    assert app._versao_prazo == relogio.agora + 2.5

    # Disparo antecipado do Tk não confirma v1: reagenda o restante.
    app._confirmar_protocolo_v1()
    assert app.protocolo_arduino is None
    assert agendados[-1][0] == 2500

    relogio.avancar(2.5)
    app._confirmar_protocolo_v1()
    root.update()

    assert app.protocolo_arduino == "v1"
    assert app.jogo.num_equipes == 2


@pytest.mark.parametrize("protocolo", ["v1", "sem_handshake"])
def test_versao_2_tardia_so_restaura_na_proxima_reconexao(
    montar_app, protocolo
):
    montar, _banco = montar_app
    app, root, _relogio = montar(num_equipes=4)
    app.jogo.placar.update({"A": 1, "B": 2, "C": 5, "D": 7})

    if protocolo == "v1":
        app.processar_evento("PRONTO")
        app._aplicar_protocolo("v1")
    else:
        app._aplicar_protocolo("sem_handshake")

    assert app.jogo.num_equipes == 2
    assert app.jogo.placar == {"A": 1, "B": 2}
    assert app._fallback_equipes is True

    # V2 chegou atrasado na mesma conexão: não muda a partida em andamento.
    app.processar_evento("VERSAO 2")
    root.update()

    assert app.protocolo_arduino == protocolo
    assert app.jogo.num_equipes == 2
    assert set(app.cartoes_placar) == {"A", "B"}
    assert app._fallback_equipes is True

    # Um novo PRONTO + VERSAO 2 é a próxima reconexão: aí sim restaura.
    app.processar_evento("PRONTO")
    app.processar_evento("VERSAO 2")
    root.update()

    assert app.protocolo_arduino == "v2"
    assert app._job_versao is None
    assert app.jogo.num_equipes == 4
    assert app.jogo.placar == {"A": 1, "B": 2, "C": 5, "D": 7}
    assert set(app.cartoes_placar) == {"A", "B", "C", "D"}
    assert app.topo.aviso_protocolo == ""
    assert "pontos de C/D recuperados" in app.aviso


def test_estado_com_numero_diferente_avisa_e_abre_partida_nova(
    montar_app, monkeypatch
):
    montar, _banco = montar_app
    app, root, _relogio = montar(num_equipes=2)
    motivo = (
        "estado salvo tem 3 equipes, mas o config.json usa 2; "
        "iniciando uma partida nova"
    )
    app._motivo_estado = motivo
    app._partida_salva = None

    avisos = []
    removidos = []
    monkeypatch.setattr(
        desafio.messagebox,
        "showwarning",
        lambda *a, **k: avisos.append((a, k)),
    )
    monkeypatch.setattr(
        desafio.persistencia,
        "remover_estado",
        lambda *a, **k: removidos.append((a, k)),
    )

    _INICIAR_FLUXO_ORIGINAL(app)
    root.update()

    assert len(avisos) == 1
    assert "3 equipes" in avisos[0][0][1]
    assert "nova partida" in avisos[0][0][1]
    assert len(removidos) == 1
    assert app._motivo_estado == ""
    assert any(
        isinstance(w, ModalSelecaoPerguntas) for w in root.winfo_children()
    )


def _colide(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _caixa_widget(widget):
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    return (x, y, x + widget.winfo_width(), y + widget.winfo_height())


def _textos_do_topo(app):
    topo = app.topo
    textos = {}
    for item in topo.find_all():
        if topo.type(item) != "text":
            continue
        bb = topo.bbox(item)
        if bb:
            textos[topo.itemcget(item, "text")] = bb
    return textos


def _verificar_barra_topo(app):
    topo = app.topo
    largura, altura = topo.winfo_width(), topo.winfo_height()
    textos = _textos_do_topo(app)
    titulo = next(bb for txt, bb in textos.items() if txt.startswith("Desafio"))
    status = next(bb for txt, bb in textos.items() if "Arduino" in txt)
    ajuda = next(bb for txt, bb in textos.items() if "F11" in txt)

    for bb in textos.values():
        assert 0 <= bb[0] and 0 <= bb[1]
        assert bb[2] <= largura and bb[3] <= altura

    assert not _colide(titulo, status), "status colidiu com o título"
    assert not _colide(titulo, ajuda), "ajuda colidiu com o título"
    assert not _colide(status, ajuda), "ajuda colidiu com o status"
    assert "Ctrl+T" in next(txt for txt in textos if "F11" in txt)


@pytest.mark.parametrize("tamanho", [(1366, 768), (1920, 1080), (900, 600)])
@pytest.mark.parametrize("num_equipes", [2, 3, 4])
def test_contagem_placar_e_topo_em_tamanhos_reais(
    montar_app, tamanho, num_equipes
):
    montar, banco = montar_app
    app, root, relogio = montar(
        contagem=3, num_equipes=num_equipes, tamanho=tamanho
    )
    _escolher_tema(app, root, banco)
    root.update()

    assert app.fase == FASE_CONTAGEM
    assert app.overlay_contagem.winfo_ismapped()
    textos_overlay = [
        app.overlay_contagem.itemcget(item, "text")
        for item in app.overlay_contagem.find_all()
        if app.overlay_contagem.type(item) == "text"
    ]
    assert "3" in textos_overlay

    assert len(app.cartoes_placar) == num_equipes
    caixas = []
    for equipe, cartao in app.cartoes_placar.items():
        assert cartao.winfo_ismapped(), f"cartão {equipe} não está visível"
        caixa = _caixa_widget(cartao)
        assert caixa[2] > caixa[0] and caixa[3] > caixa[1]
        caixas.append((equipe, caixa))

    for i, (equipe_a, caixa_a) in enumerate(caixas):
        for equipe_b, caixa_b in caixas[i + 1 :]:
            assert not _colide(caixa_a, caixa_b), (
                f"cartões {equipe_a}/{equipe_b} se sobrepõem em "
                f"{tamanho[0]}x{tamanho[1]}"
            )

    raiz = (root.winfo_rootx(), root.winfo_rooty(),
            root.winfo_rootx() + root.winfo_width(),
            root.winfo_rooty() + root.winfo_height())
    overlay = _caixa_widget(app.overlay_contagem)
    assert raiz[0] <= overlay[0] and raiz[1] <= overlay[1]
    assert overlay[2] <= raiz[2] and overlay[3] <= raiz[3]

    _verificar_barra_topo(app)

    _confirmar_contagem(app, root, relogio)
    assert app.overlay_contagem.winfo_ismapped()
    _verificar_barra_topo(app)
