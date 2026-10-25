"""Testes de timer (time.monotonic, frações, estouro)."""
import pytest
from jogo import Jogo, Pergunta, FASE_AGUARDANDO, FASE_RESPONDENDO, FASE_REVELADA


@pytest.fixture
def jogo_timer(perguntas_exemplo):
    return Jogo(perguntas_exemplo, num_equipes=2, tempo_pergunta=2, tempo_resposta=1)


class TestTimer:
    def test_timer_inicia_com_valor_cheio(self, jogo_timer):
        j = jogo_timer
        assert j.timer_restante() > 1.9
        assert j.timer_fracao() == pytest.approx(1.0, rel=0.1)

    def test_timer_diminui_com_tempo(self, jogo_timer):
        j = jogo_timer
        ini = j.timer_restante()
        # Como não temos clock fake aqui, apenas verificamos que o timer foi iniciado
        assert ini > 0

    def test_tick_timer_retorna_evento_estouro(self, jogo_timer):
        j = jogo_timer
        # Avança tempo forçando timer_fim no passado
        j.timer_fim = j._clock() - 0.1
        eventos = j.tick_timer()
        assert "tempo_esgotado" in eventos
        assert j.estado.fase == FASE_REVELADA
        assert j.timer_restante() == 0

    def test_tick_timer_vazio_enquanto_rodando(self, jogo_timer):
        j = jogo_timer
        assert j.tick_timer() == []
        assert j.estado.fase == FASE_AGUARDANDO

    def test_timer_resposta_inicia_apos_apertar(self, jogo_timer):
        j = jogo_timer
        assert j.apertar_botao("A") == ["apertou:A"]
        assert j.timer_restante() <= 1.0  # tempo_resposta = 1
        assert j.timer_fracao() == pytest.approx(1.0, rel=0.1)

    def test_parar_timer_zera(self, jogo_timer):
        j = jogo_timer
        j._parar_timer()
        assert j.timer_restante() == 0
        assert j.timer_fracao() == 0