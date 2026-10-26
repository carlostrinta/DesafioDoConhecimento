"""Testes da máquina de estados do jogo."""
import pytest
from jogo import (
    Jogo,
    FASE_AGUARDANDO, FASE_RESPONDENDO, FASE_REVELADA, FASE_PONTUADA
)
from perguntas import Pergunta


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
        assert j.apertar_botao("A") == ["apertou:A"]
        assert j.estado.fase == FASE_RESPONDENDO
        assert j.estado.quem_apertou == "A"

        # Em RESPONDENDO: rejeita segundo aperto
        assert j.apertar_botao("B") == []
        assert j.estado.quem_apertou == "A"  # permanece quem apertou primeiro

    def test_apertar_botao_equipe_inexistente(self, jogo_2_equipes):
        j = jogo_2_equipes
        assert j.apertar_botao("C") == []  # C não está ativo em 2 equipes
        assert j.apertar_botao("X") == []  # equipe inválida

    def test_apertar_botao_sem_pergunta(self, perguntas_exemplo):
        j = Jogo([], num_equipes=2)  # sem perguntas
        assert j.apertar_botao("A") == []

    def test_revelar_apenas_em_respondendo(self, jogo_2_equipes):
        j = jogo_2_equipes
        # Antes de apertar (AGUARDANDO): rejeita com motivo
        assert j.revelar_resposta() == ["recusado:revelar_aguardando"]
        assert j.estado.fase == FASE_AGUARDANDO

        j.apertar_botao("A")
        # Em RESPONDENDO: aceita
        assert j.revelar_resposta() == ["revelou"]
        assert j.estado.fase == FASE_REVELADA
        assert j.timer_restante() == 0

    def test_confirmar_acerto_apenas_em_revelada(self, jogo_2_equipes):
        j = jogo_2_equipes
        j.apertar_botao("A")
        j.revelar_resposta()

        # Em REVELADA: aceita acerto de quem apertou
        assert j.confirmar_acerto("A") == ["pontuou:A"]
        assert j.estado.fase == FASE_PONTUADA
        assert j.placar["A"] == 1

    def test_confirmar_acerto_rejeita_outra_equipe(self, jogo_2_equipes):
        j = jogo_2_equipes
        j.apertar_botao("A")
        j.revelar_resposta()
        # B não apertou, não pode pontuar
        assert j.confirmar_acerto("B") == ["recusado:acerto_outra_equipe"]
        assert j.placar["A"] == 0
        assert j.placar["B"] == 0

    def test_confirmar_acerto_rejeita_se_ninguem_apertou(self, jogo_2_equipes):
        """REVELAR durante AGUARDANDO (sem ninguém apertar) -> confirmar_acerto rejeita."""
        j = jogo_2_equipes
        # Força estado REVELADA sem quem_apertou (simula tempo esgotado em AGUARDANDO)
        j.estado.fase = FASE_REVELADA
        j.estado.quem_apertou = None
        assert j.confirmar_acerto("A") == ["recusado:acerto_sem_quem"]
        assert j.placar["A"] == 0

    def test_confirmar_acerto_rejeita_se_tempo_estourou(self, jogo_2_equipes):
        j = jogo_2_equipes
        j.apertar_botao("A")
        # Simula estouro de timer
        j._tempo_esgotado()
        j.revelar_resposta()  # vai para REVELADA com tempo_estourou=True
        assert j.estado.tempo_estourou is True
        # Com PONTUAR_APOS_TEMPO=False (padrão), não pontua
        assert j.confirmar_acerto("A") == ["recusado:acerto_tempo"]
        assert j.placar["A"] == 0

    def test_confirmar_acerto_permite_se_pontuar_apos_tempo_true(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, pontuar_apos_tempo=True)
        j.apertar_botao("A")
        j._tempo_esgotado()
        j.revelar_resposta()
        assert j.confirmar_acerto("A") == ["pontuou:A"]
        assert j.placar["A"] == 1

    def test_proxima_pergunta_avanca_estado(self, jogo_2_equipes):
        j = jogo_2_equipes
        p1 = j.estado.pergunta_atual
        n1 = j.estado.numero_pergunta

        # Só avança se rodada resolvida
        assert j.proxima_pergunta() == ["recusado:avancar"]

        j.apertar_botao("A")
        j.revelar_resposta()
        j.confirmar_acerto("A")
        eventos = j.proxima_pergunta()
        assert "proxima_pergunta" in eventos
        assert j.estado.fase == FASE_AGUARDANDO
        assert j.estado.quem_apertou is None
        assert j.estado.numero_pergunta == n1 + 1
        assert j.estado.pergunta_atual != p1  # pergunta diferente (embaralhada)

    def test_proxima_pergunta_forcar_pula_rodada(self, jogo_2_equipes):
        j = jogo_2_equipes
        assert "proxima_pergunta" in j.proxima_pergunta(forcar=True)
        assert j.estado.fase == FASE_AGUARDANDO

    def test_tick_timer_retorna_evento_estouro(self, jogo_2_equipes):
        j = jogo_2_equipes
        # Avança tempo forçando timer_fim no passado
        j.timer_fim = j._clock() - 0.1
        eventos = j.tick_timer()
        assert "tempo_esgotado" in eventos
        assert j.estado.fase == FASE_REVELADA
        assert j.timer_restante() == 0

    def test_tick_timer_vazio_enquanto_rodando(self, jogo_2_equipes):
        j = jogo_2_equipes
        assert j.tick_timer() == []


class TestTresQuatroEquipes:
    """Comportamento com 3 e 4 equipes."""

    def test_3_equipes_apenas_ABC_ativos(self, jogo_3_equipes):
        j = jogo_3_equipes
        assert j.equipes_ativas == ("A", "B", "C")
        assert "D" not in j.placar
        # D não pode apertar
        assert j.apertar_botao("D") == []
        # A, B, C podem
        assert j.apertar_botao("A") == ["apertou:A"]

    def test_4_equipes_todas_ativas(self, jogo_4_equipes):
        j = jogo_4_equipes
        assert j.equipes_ativas == ("A", "B", "C", "D")
        for eq in "ABCD":
            assert eq in j.placar
            assert j.placar[eq] == 0

    def test_bloqueio_segundo_aperto_com_3_equipes(self, jogo_3_equipes):
        j = jogo_3_equipes
        assert j.apertar_botao("B") == ["apertou:B"]
        assert j.estado.quem_apertou == "B"
        assert j.apertar_botao("A") == []
        assert j.apertar_botao("C") == []

    def test_pontuacao_por_equipe_3_equipes(self, jogo_3_equipes):
        j = jogo_3_equipes
        for eq in ("A", "B", "C"):
            assert j.apertar_botao(eq) == [f"apertou:{eq}"]
            assert j.revelar_resposta() == ["revelou"]
            assert j.confirmar_acerto(eq) == [f"pontuou:{eq}"]
            assert "proxima_pergunta" in j.proxima_pergunta()
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
        assert j.reiniciar_placar() == ["reiniciou_placar"]
        assert all(v == 0 for v in j.placar.values())

    def test_recarregar_perguntas_reinicia_estado(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2)
        j.apertar_botao("A")
        j.revelar_resposta()
        j.confirmar_acerto("A")
        assert j.placar["A"] == 1

        novas = [Pergunta("Nova", "P?", ["X", "Y"], 0, "")]
        assert j.recarregar_perguntas(novas) == ["reiniciou_banco"]
        # A UI decide sobre o placar (o carregador não zera por conta própria)
        assert j.placar["A"] == 1
        assert j.estado.fase == FASE_AGUARDANDO
        assert j.estado.pergunta_atual is None
        assert j.timer_restante() == 0

        # Quem apresenta chama proxima_pergunta(forcar=True) em seguida
        assert "proxima_pergunta" in j.proxima_pergunta(forcar=True)
        assert j.estado.pergunta_atual.texto == "P?"

    def test_recarregar_perguntas_com_zerar_placar(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2)
        j.placar["A"] = 7
        j.recarregar_perguntas(perguntas_exemplo, zerar_placar=True)
        assert j.placar == {"A": 0, "B": 0}


class TestTimerComClockInjetavel:
    """Testes de timer usando clock fake (sem sleep)."""

    def test_timer_avanca_com_clock_fake(self, perguntas_exemplo):
        tempo = 0.0
        def clock_fake():
            return tempo

        j = Jogo(perguntas_exemplo, num_equipes=2, tempo_pergunta=30, tempo_resposta=15, clock=clock_fake)
        # Timer inicia cheio
        assert j.timer_restante() == 30.0
        assert j.timer_fracao() == pytest.approx(1.0)

        # Avança clock 10s
        tempo = 10.0
        assert j.timer_restante() == 20.0
        assert j.timer_fracao() == pytest.approx(20/30)

        # Avança até estourar
        tempo = 31.0
        eventos = j.tick_timer()
        assert "tempo_esgotado" in eventos
        assert j.estado.fase == FASE_REVELADA

    def test_timer_resposta_com_clock_fake(self, perguntas_exemplo):
        tempo = 0.0
        def clock_fake():
            return tempo

        j = Jogo(perguntas_exemplo, num_equipes=2, tempo_pergunta=30, tempo_resposta=15, clock=clock_fake)
        j.apertar_botao("A")
        # Timer de resposta inicia
        assert j.timer_restante() == 15.0

        # Avança 16s -> estoura
        tempo = 16.0
        eventos = j.tick_timer()
        assert "tempo_esgotado" in eventos
        assert j.estado.fase == FASE_REVELADA
        assert j.estado.tempo_estourou is True