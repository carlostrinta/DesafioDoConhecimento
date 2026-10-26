"""
Testes dos textos de aviso da interface (sem abrir janela).

O modulo `desafio` importa tkinter, pyserial e pygame (opcionais); aqui so
usamos funcoes puras de formatacao, entao nenhuma janela e criada.
"""

import pytest

desafio = pytest.importorskip("desafio")


class TestMensagemIgnoradas:
    def test_nenhuma_ignorada_nao_gera_aviso(self):
        assert desafio.mensagem_ignoradas(0, "conhecimentos_gerais.json") is None

    def test_singular(self):
        assert (
            desafio.mensagem_ignoradas(1, "banco.json")
            == "1 pergunta ignorada em banco.json."
        )

    def test_plural(self):
        assert (
            desafio.mensagem_ignoradas(12, "banco.json")
            == "12 perguntas ignoradas em banco.json."
        )

    def test_texto_nao_depende_de_caminho_completo(self):
        # A carga passa apenas o nome do arquivo, nunca o caminho absoluto.
        assert (
            desafio.mensagem_ignoradas(2, "tema.json")
            == "2 perguntas ignoradas em tema.json."
        )
