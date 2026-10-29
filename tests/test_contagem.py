"""
Testes da contagem de largada (Etapa 4.6).

Tudo usa relógio falso (nenhum `sleep`) e nenhuma janela. A UI é exercitada
apenas nas partes puras: a fila serial e as mensagens de recusa.
"""

import queue

import pytest

import desafio
from jogo import (
    CONTAGEM_LARGADA_PADRAO,
    CONTAGEM_LARGADA_MAXIMO,
    CONTAGEM_LARGADA_MINIMO,
    FASE_AGUARDANDO,
    FASE_CONTAGEM,
    Jogo,
    MOTIVO_CONTAGEM,
    PREFIXO_RECUSA,
)
from perguntas import Pergunta
from protocolo import mapear_evento_arduino


class Relogio:
    """Relógio fake: o teste move o tempo à mão."""

    def __init__(self, agora=100.0):
        self.agora = agora

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


def _perguntas(quantidade=6):
    return [
        Pergunta("Cat", f"Pergunta {i}?", ["Certa", "Errada"], 0, f"Explic {i}")
        for i in range(quantidade)
    ]


def _jogo(relogio=None, contagem=CONTAGEM_LARGADA_PADRAO, **kwargs):
    return Jogo(
        _perguntas(),
        num_equipes=2,
        tempo_pergunta=30,
        tempo_resposta=15,
        clock=relogio or Relogio(),
        contagem_largada=contagem,
        **kwargs,
    )


class TestSequencia:
    def test_nova_partida_comeca_em_contagem(self):
        jogo = _jogo()

        assert jogo.estado.fase == FASE_CONTAGEM
        assert jogo.estado.pergunta_atual is not None
        assert jogo.contagem_ativa is True
        assert jogo.contagem_restante() == pytest.approx(3.0)
        assert jogo.timer_ativo is False
        assert jogo.timer_restante() == 0.0

    def test_sequencia_3_2_1_ja_sem_sleep(self):
        relogio = Relogio()
        jogo = _jogo(relogio)

        assert jogo.tick_contagem() == ["contagem:3"]
        relogio.avancar(1.0)
        assert jogo.tick_contagem() == ["contagem:2"]
        relogio.avancar(1.0)
        assert jogo.tick_contagem() == ["contagem:1"]
        relogio.avancar(0.99)
        assert jogo.tick_contagem() == []
        relogio.avancar(0.01)

        assert jogo.tick_contagem() == ["largada"]
        assert jogo.estado.fase == FASE_AGUARDANDO
        assert jogo.contagem_ativa is False
        assert jogo.tick_contagem() == []

        # O tempo de 30 s só começa no "JÁ!".
        assert jogo.timer_ativo is True
        assert jogo.timer_restante() == pytest.approx(30.0)
        assert jogo.timer_rotulo == "Tempo para apertar"

    def test_contagem_zero_desativa(self):
        relogio = Relogio()
        jogo = _jogo(relogio, contagem=0)

        assert jogo.estado.fase == FASE_AGUARDANDO
        assert jogo.contagem_ativa is False
        assert jogo.contagem_restante() == 0.0
        assert jogo.tick_contagem() == []
        assert jogo.timer_ativo is True
        assert jogo.timer_restante() == pytest.approx(30.0)

    def test_duracao_personalizada(self):
        relogio = Relogio()
        jogo = _jogo(relogio, contagem=5)

        assert jogo.contagem_restante() == pytest.approx(5.0)
        assert jogo.tick_contagem() == ["contagem:5"]
        relogio.avancar(4.0)
        assert jogo.tick_contagem() == ["contagem:1"]
        relogio.avancar(1.0)
        assert jogo.tick_contagem() == ["largada"]

    @pytest.mark.parametrize("valor", [-1, 11, 99, "3", True, None, 1.5])
    def test_duracao_invalida_volta_ao_padrao(self, valor):
        jogo = _jogo(contagem=valor)

        assert jogo.contagem_largada == CONTAGEM_LARGADA_PADRAO == 3

    @pytest.mark.parametrize("valor", [CONTAGEM_LARGADA_MINIMO, 1, 10, CONTAGEM_LARGADA_MAXIMO])
    def test_duracao_na_faixa_e_aceita(self, valor):
        assert _jogo(contagem=valor).contagem_largada == valor

    def test_nova_pergunta_volta_para_a_contagem(self):
        relogio = Relogio()
        jogo = _jogo(relogio)

        relogio.avancar(3.0)
        jogo.tick_contagem()
        assert jogo.apertar_botao("A") == ["apertou:A"]
        jogo.revelar_resposta()
        jogo.confirmar_acerto("A")

        eventos = jogo.proxima_pergunta()
        assert "proxima_pergunta" in eventos
        assert jogo.estado.fase == FASE_CONTAGEM
        assert jogo.timer_ativo is False
        assert jogo.contagem_restante() == pytest.approx(3.0)

    def test_mostrar_pergunta_na_contagem_e_configuravel(self):
        assert _jogo().mostrar_pergunta_na_contagem is False
        assert _jogo(mostrar_pergunta_na_contagem=True).mostrar_pergunta_na_contagem is True

    def test_valor_invalido_de_mostrar_pergunta_volta_ao_padrao(self):
        assert _jogo(mostrar_pergunta_na_contagem="sim").mostrar_pergunta_na_contagem is False


class TestBloqueiosDuranteAContagem:
    def test_aperto_durante_a_contagem_nao_vale(self):
        relogio = Relogio()
        jogo = _jogo(relogio)

        assert jogo.apertar_botao("A") == []
        assert jogo.apertar_botao("B") == []
        assert jogo.estado.quem_apertou is None
        assert jogo.estado.fase == FASE_CONTAGEM

        relogio.avancar(3.0)
        assert jogo.tick_contagem() == ["largada"]
        assert jogo.apertar_botao("B") == ["apertou:B"]
        assert jogo.estado.quem_apertou == "B"

    def test_revelar_acerto_e_avancar_recusados(self):
        jogo = _jogo()
        recusa = [PREFIXO_RECUSA + MOTIVO_CONTAGEM]

        assert jogo.revelar_resposta() == recusa
        assert jogo.confirmar_acerto("A") == recusa
        assert jogo.confirmar_acerto("B") == recusa
        assert jogo.proxima_pergunta() == recusa
        assert jogo.estado.fase == FASE_CONTAGEM
        assert jogo.placar == {"A": 0, "B": 0}

    def test_mensagem_de_recusa_e_clara(self):
        texto = desafio.MENSAGENS_RECUSA[MOTIVO_CONTAGEM]

        assert "JÁ!" in texto
        assert "contagem" in texto.lower()

    def test_protocolo_serial_v1_nao_muda_e_respeita_a_contagem(self):
        jogo = _jogo()

        assert mapear_evento_arduino("BTN_A", jogo) == []
        assert mapear_evento_arduino("BTN_REVELAR", jogo) == [
            PREFIXO_RECUSA + MOTIVO_CONTAGEM
        ]
        assert mapear_evento_arduino("BTN_AVANCAR", jogo) == [
            PREFIXO_RECUSA + MOTIVO_CONTAGEM
        ]
        assert jogo.estado.fase == FASE_CONTAGEM


class TestPartidaRestaurada:
    def _dados_de_partida(self):
        relogio = Relogio()
        jogo = _jogo(relogio)
        relogio.avancar(3.0)
        jogo.tick_contagem()
        jogo.apertar_botao("A")
        jogo.revelar_resposta()
        jogo.confirmar_acerto("A")
        jogo.proxima_pergunta()
        return jogo.to_dict(), _perguntas()

    def test_restaura_em_contagem_e_nao_em_aguardando(self):
        dados, perguntas = self._dados_de_partida()
        relogio = Relogio()

        novo = Jogo.from_dict(dados, perguntas, clock=relogio)

        assert novo.estado.fase == FASE_CONTAGEM
        assert novo.contagem_ativa is True
        assert novo.contagem_restante() == pytest.approx(3.0)
        assert novo.timer_ativo is False
        assert novo.placar == {"A": 1, "B": 0}

        # Aperto durante a contagem da partida restaurada também não vale.
        assert novo.apertar_botao("B") == []
        relogio.avancar(3.0)
        assert novo.tick_contagem() == ["largada"]
        assert novo.apertar_botao("B") == ["apertou:B"]

    def test_restaura_em_aguardando_se_contagem_estiver_desativada(self):
        dados, perguntas = self._dados_de_partida()
        relogio = Relogio()

        novo = Jogo.from_dict(
            dados, perguntas, clock=relogio, contagem_largada=0
        )

        assert novo.estado.fase == FASE_AGUARDANDO
        assert novo.contagem_ativa is False
        assert novo.timer_ativo is True


class TestFilaSerial:
    def _app_com_fila(self, *itens):
        app = object.__new__(desafio.DueloDeConhecimento)
        app.fila = queue.Queue()
        for item in itens:
            app.fila.put(item)
        return app

    def test_descarta_apenas_botoes_de_equipe(self):
        app = self._app_com_fila(
            ("evento", "BTN_A"),
            ("conexao", "COM7"),
            ("evento", "BTN_B"),
            ("placa", "CH340"),
            ("evento", "PRONTO"),
            ("evento", "BTN_AVANCAR"),
        )

        assert app.descartar_botoes_fila() == 2

        restantes = []
        while not app.fila.empty():
            restantes.append(app.fila.get_nowait())
        assert restantes == [
            ("conexao", "COM7"),
            ("placa", "CH340"),
            ("evento", "PRONTO"),
            ("evento", "BTN_AVANCAR"),
        ]

    def test_evento_antigo_na_fila_nao_ganha_a_rodada(self):
        """Aperto enfileirado durante a contagem é descartado no "JÁ!"."""
        relogio = Relogio()
        jogo = _jogo(relogio)
        app = self._app_com_fila(("evento", "BTN_A"))

        # O BTN_A ficou na fila enquanto a contagem corria.
        relogio.avancar(3.0)
        assert jogo.tick_contagem() == ["largada"]
        assert app.descartar_botoes_fila() == 1

        # Nada mais na fila: nenhum aperto chega ao Jogo depois do "JÁ!".
        assert app.fila.empty()
        assert jogo.estado.quem_apertou is None
        assert jogo.estado.fase == FASE_AGUARDANDO

    def test_descarte_sem_botoes_e_inofensivo(self):
        app = self._app_com_fila(("evento", "PRONTO"))

        assert app.descartar_botoes_fila() == 0
        assert app.fila.get_nowait() == ("evento", "PRONTO")

    def test_aperto_recebido_antes_do_corte_nao_vence(self):
        """(a) BTN recebido antes do instante do "JÁ!" é descartado."""
        relogio = Relogio()
        jogo = _jogo(relogio)
        app = self._app_com_fila(("evento", "BTN_A", 100.0))

        relogio.avancar(3.0)
        assert jogo.tick_contagem() == ["largada"]
        assert app.descartar_botoes_fila(103.0) == 1

        assert app.fila.empty()
        assert jogo.estado.quem_apertou is None

    def test_aperto_recebido_depois_do_corte_vale(self):
        """(b) BTN recebido depois do "JÁ!" chega ao Jogo e vence."""
        relogio = Relogio()
        jogo = _jogo(relogio)

        relogio.avancar(3.0)
        assert jogo.tick_contagem() == ["largada"]

        app = self._app_com_fila(("evento", "BTN_A", 103.001))
        assert app.descartar_botoes_fila(103.0) == 0

        tipo, evento, _ = app.fila.get_nowait()
        assert tipo == "evento"
        assert mapear_evento_arduino(evento, jogo) == ["apertou:A"]
        assert jogo.estado.quem_apertou == "A"

    def test_botao_mantido_na_contagem_e_solto_depois_nao_vale(self):
        """
        (c) O firmware v1 só envia BTN na borda de descida; manter o botão
        pressionado durante a contagem não gera novas linhas, e soltar também
        não gera evento. O único BTN recebido é o da contagem e é descartado.
        """
        relogio = Relogio()
        jogo = _jogo(relogio)
        app = self._app_com_fila(("evento", "BTN_A", 100.0))

        relogio.avancar(3.0)
        assert jogo.tick_contagem() == ["largada"]
        assert app.descartar_botoes_fila(103.0) == 1

        # A soltura não enfileira nada; não há evento válido para o Jogo.
        assert app.fila.empty()
        assert jogo.estado.quem_apertou is None
        assert jogo.estado.fase == FASE_AGUARDANDO

    def test_corte_preserva_botoes_recebidos_depois_e_outros_itens(self):
        app = self._app_com_fila(
            ("evento", "BTN_A", 100.0),
            ("conexao", "COM7"),
            ("evento", "BTN_B", 100.5),
            ("evento", "BTN_C", 101.0),
        )

        assert app.descartar_botoes_fila(100.5) == 1

        restantes = []
        while not app.fila.empty():
            restantes.append(app.fila.get_nowait())
        assert restantes == [
            ("conexao", "COM7"),
            ("evento", "BTN_B", 100.5),
            ("evento", "BTN_C", 101.0),
        ]
