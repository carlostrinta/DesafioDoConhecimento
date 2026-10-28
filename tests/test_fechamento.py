"""Testes dos caminhos de fechamento sem abrir janela (Etapa 4.3)."""

import pytest

desafio = pytest.importorskip("desafio")
ui_selecao = pytest.importorskip("ui_selecao")


class _SalvadorFalso:
    def __init__(self):
        self.execucoes = 0

    def executar_agora(self):
        self.execucoes += 1


class _ServicoFalso:
    def __init__(self):
        self.paradas = 0

    def parar(self):
        self.paradas += 1


class _TravaFalsa:
    def __init__(self):
        self.liberacoes = 0

    def liberar(self):
        self.liberacoes += 1


class _RootFalso:
    def __init__(self):
        self.destruida = False

    def destroy(self):
        self.destruida = True


def test_fechar_remove_o_estado_partida_lock_real(tmp_path):
    """O caminho normal (X, Esc nos modais, modal inicial) apaga a trava."""
    trava = desafio.persistencia.TravaInstancia(diretorio_base=str(tmp_path))
    assert trava.adquirir() is True
    caminho_lock = tmp_path / desafio.persistencia.NOME_TRAVA
    assert caminho_lock.exists()

    app = object.__new__(desafio.DueloDeConhecimento)
    app._salvador = _SalvadorFalso()
    app.serial_comm = _ServicoFalso()
    app.som = _ServicoFalso()
    app._trava = trava
    app.root = _RootFalso()
    app.rodando = True

    app.fechar()

    assert app.rodando is False
    assert app.root.destruida is True
    assert not caminho_lock.exists()
    assert trava.ativa is False


def test_fechar_grava_para_servicos_libera_trava_e_destroi_root():
    app = object.__new__(desafio.DueloDeConhecimento)
    app._salvador = _SalvadorFalso()
    app.serial_comm = _ServicoFalso()
    app.som = _ServicoFalso()
    app._trava = _TravaFalsa()
    app.root = _RootFalso()
    app.rodando = True

    app.fechar()

    assert app._salvador.execucoes == 1
    assert app.serial_comm.paradas == 1
    assert app.som.paradas == 1
    assert app._trava.liberacoes == 1
    assert app.root.destruida is True
    assert app.rodando is False


def test_modal_continuar_fechar_nao_escolhe_nem_apaga_estado():
    chamadas = []
    modal = object.__new__(ui_selecao.ModalContinuarPartida)
    modal._respondido = False
    modal.ao_fechar = lambda: chamadas.append("fechar")
    modal.ao_escolher = lambda continuar: chamadas.append(("escolher", continuar))
    modal.grab_release = lambda: None
    modal.destroy = lambda: chamadas.append("destroy")

    modal._fechar_sem_alterar()

    assert modal._respondido is True
    assert chamadas == ["destroy", "fechar"]


def test_modal_inicial_x_e_escape_passam_pelo_fechamento(monkeypatch):
    chamadas = []

    monkeypatch.setattr(ui_selecao.messagebox, "askyesno", lambda *a, **k: True)
    modal = object.__new__(ui_selecao.ModalSelecaoPerguntas)
    modal.inicial = True
    modal.ao_sair = lambda: chamadas.append("sair")
    modal.parent = object()
    modal._limpar_mousewheel = lambda: chamadas.append("limpar")
    modal.destroy = lambda: chamadas.append("destroy")

    modal._ao_fechar()
    modal._cancelar()

    assert chamadas == ["limpar", "destroy", "sair", "limpar", "destroy", "sair"]


def test_modal_inicial_cancelar_sem_confirmar_nao_sai(monkeypatch):
    chamadas = []
    monkeypatch.setattr(ui_selecao.messagebox, "askyesno", lambda *a, **k: False)

    modal = object.__new__(ui_selecao.ModalSelecaoPerguntas)
    modal.inicial = True
    modal.ao_sair = lambda: chamadas.append("sair")
    modal.parent = object()
    modal._limpar_mousewheel = lambda: chamadas.append("limpar")
    modal.destroy = lambda: chamadas.append("destroy")

    modal._ao_fechar()

    assert chamadas == []
