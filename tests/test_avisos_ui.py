"""
Testes dos textos de aviso da interface (sem abrir janela).

O modulo `desafio` importa tkinter, pyserial e pygame (opcionais); aqui so
usamos funcoes puras de formatacao, entao nenhuma janela e criada.
"""

import queue

import pytest

desafio = pytest.importorskip("desafio")
ui_componentes = pytest.importorskip("ui_componentes")


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


def test_barra_de_status_mostra_porta_e_placa_curta():
    from ui_componentes import texto_status_serial

    texto, _ = texto_status_serial(
        "COM7", "CH340/CH341 (clone Arduino) (1A86:7523)", disponivel=True
    )

    assert "COM7" in texto
    assert "CH340" in texto
    # O VID:PID completo fica no log da serial, não na barra.
    assert "1A86:7523" not in texto


def test_barra_de_status_sem_conexao_nao_mostra_placa():
    from ui_componentes import texto_status_serial

    texto, _ = texto_status_serial(None, "", disponivel=True)

    assert "não conectado" in texto


def test_drenar_fila_entrega_porta_e_placa_para_a_barra():
    import queue

    class TopoFalso:
        conexao = None
        placa = ""
        desenhos = 0

        def desenhar(self):
            self.desenhos += 1

    app = object.__new__(desafio.DueloDeConhecimento)
    app.fila = queue.Queue()
    app.fila.put(("conexao", "COM7"))
    app.fila.put(("placa", "CH340/CH341 (clone Arduino) (1A86:7523)"))
    app.topo = TopoFalso()
    app.rodando = False

    app.drenar_fila()

    assert app.topo.conexao == "COM7"
    assert app.topo.placa == "CH340/CH341 (clone Arduino) (1A86:7523)"
    assert app.topo.desenhos == 2

    app.fila.put(("conexao", None))
    app.drenar_fila()
    assert app.topo.conexao is None
    assert app.topo.placa == ""


def test_barra_de_status_avisa_porta_configurada_ausente():
    from ui_componentes import texto_status_serial

    texto, cor = texto_status_serial(
        None, "", disponivel=True, aviso_porta="COM9"
    )

    assert "COM9" in texto
    assert "não encontrada" in texto
    assert "detecção automática" in texto
    assert cor == ui_componentes.Cor.AVISO


def test_barra_de_status_mostra_fallback_quando_conectou_em_outra_porta():
    from ui_componentes import texto_status_serial

    texto, _ = texto_status_serial(
        "COM5", "", disponivel=True, aviso_porta="COM9"
    )

    assert "COM5" in texto
    assert "COM9" in texto
    assert "não encontrada" in texto


def test_drenar_fila_entrega_aviso_de_porta_ausente_para_a_barra():
    class TopoFalso:
        aviso_porta = ""
        desenhos = 0

        def desenhar(self):
            self.desenhos += 1

    app = object.__new__(desafio.DueloDeConhecimento)
    app.fila = queue.Queue()
    app.fila.put(("porta_ausente", "COM9"))
    app.topo = TopoFalso()
    app.rodando = False

    app.drenar_fila()

    assert app.topo.aviso_porta == "COM9"
    assert app.topo.desenhos == 1

    app.fila.put(("porta_ausente", None))
    app.drenar_fila()
    assert app.topo.aviso_porta == ""
