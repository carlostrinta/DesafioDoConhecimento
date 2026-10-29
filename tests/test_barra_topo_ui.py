"""Regressão da barra de topo em Tk real (Etapa 4.7).

A barra da aplicação tem 64 px de altura e precisa mostrar os três controles
(som, tela cheia e troca de tema) em qualquer tamanho de janela. O status da
serial é secundário: pode encurtar/truncar, mas nunca pode empurrar os
controles para fora. Em ambiente headless os testes são pulados.
"""

import tkinter as tk

import pytest

import ui_componentes as mod
from apoio_tk import criar_raiz_tk


@pytest.fixture(scope="module")
def raiz_tk():
    try:
        root = criar_raiz_tk()
    except tk.TclError as e:
        pytest.skip(f"Tk indisponível: {e}")
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def restaurar_escala():
    """Evita que a escala escolhida aqui vaze para o golden visual."""
    original = mod.ESCALA
    yield
    mod.definir_escala(original)


def _textos(barra):
    return {
        barra.itemcget(item, "text"): barra.bbox(item)
        for item in barra.find_all()
        if barra.type(item) == "text"
    }


def _montar(raiz, largura, altura, conexao, placa, tema="Conhecimentos Gerais"):
    mod.definir_escala(max(0.6, min(largura / 1280, altura / 800, 2.2)))
    janela = tk.Toplevel(raiz)
    janela.withdraw()
    barra = mod.BarraTopo(janela, height=64)
    largura_barra = largura - 32
    barra.place(x=16, y=10, width=largura_barra, height=64)
    barra.conexao = conexao
    barra.placa = placa
    barra.tema = tema
    janela.update_idletasks()
    barra.delete("all")
    barra.pintar(largura_barra, 64)
    janela.update_idletasks()
    return janela, barra, largura_barra


def _assert_controles_e_limites(barra, largura_barra):
    textos = _textos(barra)
    todos = " ".join(textos)

    assert "som" in todos.lower(), "controle de som ausente"
    assert "F11" in todos, "controle de tela cheia ausente"
    assert "Ctrl+T" in todos, "controle de troca de tema ausente"
    assert "2341:0042" not in todos, "VID:PID não deve aparecer na barra"

    for texto, bbox in textos.items():
        assert bbox is not None, texto
        assert bbox[0] >= 0, (texto, bbox)
        assert bbox[1] >= 0, (texto, bbox)
        assert bbox[2] <= largura_barra, (texto, bbox)
        assert bbox[3] <= 64, (texto, bbox)

    status = next(
        bbox for texto, bbox in textos.items()
        if texto.startswith("COM6") or "não conectado" in texto
    )
    ajuda = next(bbox for texto, bbox in textos.items() if "F11" in texto)
    assert status[3] <= ajuda[1], "status colidiu com a linha de controles"
    return textos


@pytest.mark.parametrize(
    "largura,altura",
    [(900, 600), (1366, 768), (1920, 1080)],
)
@pytest.mark.parametrize(
    "conexao,placa",
    [
        ("COM6", "Arduino Mega 2560 (2341:0042)"),
        (None, ""),
    ],
)
def test_barra_mostra_controles_em_tamanhos_comuns(
    raiz_tk, largura, altura, conexao, placa
):
    janela, barra, largura_barra = _montar(
        raiz_tk, largura, altura, conexao, placa
    )
    try:
        textos = _assert_controles_e_limites(barra, largura_barra)
        if conexao:
            status = next(t for t in textos if t.startswith("COM6"))
            assert "Mega 2560" in status
            assert "2341:0042" not in status
        else:
            assert any("não conectado" in t for t in textos)
    finally:
        janela.destroy()


def test_barra_em_tela_cheia_mostra_controles(raiz_tk):
    janela = tk.Toplevel(raiz_tk)
    try:
        janela.attributes("-fullscreen", True)
        janela.update()
        largura, altura = janela.winfo_width(), janela.winfo_height()
        mod.definir_escala(max(0.6, min(largura / 1280, altura / 800, 2.2)))
        barra = mod.BarraTopo(janela, height=64)
        largura_barra = largura - 32
        barra.place(x=16, y=10, width=largura_barra, height=64)
        barra.conexao = "COM6"
        barra.placa = "Arduino Mega 2560 (2341:0042)"
        barra.tema = "Conhecimentos Gerais"
        janela.update_idletasks()
        barra.delete("all")
        barra.pintar(largura_barra, 64)
        janela.update_idletasks()

        _assert_controles_e_limites(barra, largura_barra)
    finally:
        janela.attributes("-fullscreen", False)
        janela.destroy()


def test_ajuda_encurta_antes_de_omitir():
    completa = mod.escolher_ajuda_topo(len, 1000)
    compacta = mod.escolher_ajuda_topo(len, 10)

    assert completa == mod.AJUDAS_TOPO[0]
    assert compacta == mod.AJUDAS_TOPO[-1]
    for variante in mod.AJUDAS_TOPO:
        assert "F11" in variante
        assert "Ctrl+T" in variante
        assert "S som" in variante


def test_nome_curto_da_placa_remove_vid_pid():
    assert (
        mod.nome_curto_placa("Arduino Mega 2560 (2341:0042)")
        == "Mega 2560"
    )
    assert mod.nome_curto_placa("Arduino Uno (2341:0043)") == "Uno"
    assert (
        mod.nome_curto_placa("CH340/CH341 (clone Arduino) (1A86:7523)")
        == "CH340"
    )
    assert mod.nome_curto_placa("") == ""
