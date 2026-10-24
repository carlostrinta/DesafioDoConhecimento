"""Testes da máquina de estados do jogo."""
import pytest
from jogo import (
    Jogo, Pergunta,
    FASE_AGUARDANDO, FASE_RESPONDENDO, FASE_REVELADA, FASE_PONTUADA
)


class TestMaquinaEstados:
    """Transições válidas e inválidas entre fases."""

    def test_estado_inicial(self, jogo_2_equipes):
        j = jogo_2_equipes
        assert j.estado.fase == FASE_AGUARDANDO
        assert j.estado.quem_apertou is None
        assert j.estado.pergunta_atual is not None
        assert j.placar == {"A": 0, "B": 0}

    def test_apertar_botao_apenas_em_aguardando(self, jogo_2_equipes):
        j = jogo_2_equipes
        # Em AGUARDANDO: aceita
        assert j.apertar_botao("A") is True
        assert j.estado.fase == FASE_RESPONDENDO
        assert j.estado.quem_apertou == "A"

        # Em RESPONDENDO: rejeita segundo aperto
        assert j.apertar_botao("B") is False
        assert j.estado.quem_apertou == "A"  # permanece quem apertou primeiro

    def test_revelar_apenas_em_respondendo(self, jogo_2_equipes):
        j = jogo_2_equipes
        # Antes de apertar: rejeita
        assert j.revelar_resposta() is False
        assert j.estado.fase == FASE_AGUARDANDO

        j.apertar_botao("A")
        # Em RESPONDENDO: aceita
        assert j.revelar_resposta() is True
        assert j.estado.fase == FASE_REVELADA
        assert j.timer_restante() == 0

    def test_confirmar_acerto_apenas_em_revelada(self, jogo_2_equipes):
        j = jogo_2_equipes
        j.apertar_botao("A")
        j.revelar_resposta()

        # Em REVELADA: aceita acerto de quem apertou
        assert j.confirmar_acerto("A") is True
        assert j.estado.fase == FASE_PONTUADA
        assert j.placar["A"] == 1

    def test_confirmar_acerto_rejeita_outra_equipe(self, jogo_2_equipes):
        j = jogo_2_equipes
        j.apertar_botao("A")
        j.revelar_resposta()
        # B não apertou, não pode pontuar
        assert j.confirmar_acerto("B") is False
        assert j.placar["A"] == 0
        assert j.placar["B"] == 0

    def test_confirmar_acerto_rejeita_se_tempo_estourou(self, jogo_2_equipes):
        j = jogo_2_equipes
        j.apertar_botao("A")
        # Simula estouro de timer
        j._tempo_esgotado()
        j.revelar_resposta()  # vai para REVELADA com tempo_estourou=True
        assert j.estado.tempo_estourou is True
        # Com PONTUAR_APOS_TEMPO=False (padrão), não pontua
        assert j.confirmar_acerto("A") is False
        assert j.placar["A"] == 0

    def test_confirmar_acerto_permite_se_pontuar_apos_tempo_true(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, pontuar_apos_tempo=True)
        j.apertar_botao("A")
        j._tempo_esgotado()
        j.revelar_resposta()
        assert j.confirmar_acerto("A") is True
        assert j.placar["A"] == 1

    def test_proxima_pergunta_avanca_estado(self, jogo_2_equipes):
        j = jogo_2_equipes
        p1 = j.estado.pergunta_atual
        n1 = j.estado.numero_pergunta

        # Só avança se rodada resolvida
        assert j.proxima_pergunta() is False

        j.apertar_botao("A")
        j.revelar_resposta()
        j.confirmar_acerto("A")
        assert j.proxima_pergunta() is True
        assert j.estado.fase == FASE_AGUARDANDO
        assert j.estado.quem_apertou is None
        assert j.estado.numero_pergunta == n1 + 1
        assert j.estado.pergunta_atual != p1  # pergunta diferente (embaralhada)

    def test_proxima_pergunta_forcar_pula_rodada(self, jogo_2_equipes):
        j = jogo_2_equipes
        assert j.proxima_pergunta(forcar=True) is True
        assert j.estado.fase == FASE_AGUARDANDO


class TestTresQuatroEquipes:
    """Comportamento com 3 e 4 equipes."""

    def test_3_equipes_apenas_ABC_ativos(self, jogo_3_equipes):
        j = jogo_3_equipes
        assert j.equipes_ativas == ("A", "B", "C")
        assert "D" not in j.placar
        # D não pode apertar
        assert j.apertar_botao("D") is False
        # A, B, C podem
        assert j.apertar_botao("A") is True

    def test_4_equipes_todas_ativas(self, jogo_4_equipes):
        j = jogo_4_equipes
        assert j.equipes_ativas == ("A", "B", "C", "D")
        for eq in "ABCD":
            assert eq in j.placar
            assert j.placar[eq] == 0

    def test_bloqueio_segundo_aperto_com_3_equipes(self, jogo_3_equipes):
        j = jogo_3_equipes
        j.apertar_botao("B")
        assert j.estado.quem_apertou == "B"
        assert j.apertar_botao("A") is False
        assert j.apertar_botao("C") is False

    def test_pontuacao_por_equipe_3_equipes(self, jogo_3_equipes):
        j = jogo_3_equipes
        for eq in ("A", "B", "C"):
            j.apertar_botao(eq)
            j.revelar_resposta()
            j.confirmar_acerto(eq)
            j.proxima_pergunta()
        assert j.placar == {"A": 1, "B": 1, "C": 1}

    def test_empate_placar(self, jogo_2_equipes):
        j = jogo_2_equipes
        # A pontua
        j.apertar_botao("A"); j.revelar_resposta(); j.confirmar_acerto("A"); j.proxima_pergunta()
        # B pontua
        j.apertar_botao("B"); j.revelar_resposta(); j.confirmar_acerto("B"); j.proxima_pergunta()
        assert j.placar == {"A": 1, "B": 1}

    def test_reiniciar_placar_zera_todas(self, jogo_4_equipes):
        j = jogo_4_equipes
        j.placar = {"A": 5, "B": 3, "C": 2, "D": 1}
        j.reiniciar_placar()
        assert all(v == 0 for v in j.placar.values())