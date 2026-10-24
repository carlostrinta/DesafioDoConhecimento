"""Fixtures compartilhados para pytest."""
import pytest
from jogo import Jogo, Pergunta, FASE_AGUARDANDO, FASE_RESPONDENDO, FASE_REVELADA, FASE_PONTUADA


@pytest.fixture
def perguntas_exemplo():
    return [
        Pergunta("Cat1", "Pergunta 1?", ["A1", "B1", "C1", "D1"], 0, "Explic 1"),
        Pergunta("Cat2", "Pergunta 2?", ["A2", "B2", "C2"], 1, "Explic 2"),
        Pergunta("Cat1", "Pergunta 3?", ["A3", "B3"], 1, "Explic 3"),
    ]


@pytest.fixture
def jogo_2_equipes(perguntas_exemplo):
    return Jogo(perguntas_exemplo, num_equipes=2, tempo_pergunta=30, tempo_resposta=15)


@pytest.fixture
def jogo_3_equipes(perguntas_exemplo):
    return Jogo(perguntas_exemplo, num_equipes=3, tempo_pergunta=30, tempo_resposta=15)


@pytest.fixture
def jogo_4_equipes(perguntas_exemplo):
    return Jogo(perguntas_exemplo, num_equipes=4, tempo_pergunta=30, tempo_resposta=15)