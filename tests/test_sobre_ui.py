"""Testes de Tk real da tela Sobre e do crédito no seletor de temas."""

import tkinter as tk

import pytest

from apoio_tk import criar_raiz_tk
from ui_selecao import ModalSelecaoPerguntas
from ui_sobre import TelaSobre
from versao import AUTOR, LICENCA, NOME, URL, VERSAO


@pytest.fixture(scope="module")
def raiz_tk():
    try:
        root = criar_raiz_tk(retirar=False)
    except tk.TclError as e:
        pytest.skip(f"Tk indisponível: {e}")
    root.geometry("1280x800+0+0")
    root.update()
    yield root
    root.destroy()


def _textos(widget):
    encontrados = []
    for filho in widget.winfo_children():
        try:
            if isinstance(filho, (tk.Label, tk.Button)):
                encontrados.append(filho.cget("text"))
        except tk.TclError:
            pass
        encontrados.extend(_textos(filho))
    return encontrados


def test_sobre_mostra_metadados_e_fica_na_area_central(raiz_tk):
    janela = TelaSobre(raiz_tk)
    try:
        raiz_tk.update()
        textos = _textos(janela)

        assert NOME in textos
        assert any(VERSAO in texto for texto in textos)
        assert AUTOR in textos
        assert any(URL in texto for texto in textos)
        assert LICENCA in textos

        # A janela nasce dentro da coluna central: não cobre a barra de topo,
        # os cartões laterais do placar nem o rodapé da aplicação.
        largura_raiz = raiz_tk.winfo_width()
        altura_raiz = raiz_tk.winfo_height()
        x = janela.winfo_rootx() - raiz_tk.winfo_rootx()
        y = janela.winfo_rooty() - raiz_tk.winfo_rooty()
        largura = janela.winfo_width()
        altura = janela.winfo_height()

        assert x >= int(largura_raiz * 0.22)
        assert x + largura <= int(largura_raiz * 0.79)
        assert y >= 80
        assert y + altura <= altura_raiz - 80
    finally:
        janela.fechar()
        raiz_tk.update()


def test_seletor_tem_credito_discreto(raiz_tk):
    modal = ModalSelecaoPerguntas(
        raiz_tk,
        lista_arquivos=[],
        permitir_cancelar=True,
    )
    try:
        raiz_tk.update()
        textos = _textos(modal)
        assert any(AUTOR in texto for texto in textos)
        assert any(NOME in texto for texto in textos)
    finally:
        modal.destroy()
        raiz_tk.update()
