"""Ida e volta do estado do Jogo (persistência da Etapa 4.3)."""

import pytest

from jogo import (
    FASE_AGUARDANDO,
    FASE_PONTUADA,
    Jogo,
)
from perguntas import Pergunta


class Relogio:
    def __init__(self):
        self.agora = 100.0

    def __call__(self):
        return self.agora


def _perguntas():
    return [
        Pergunta("Cat1", f"Pergunta {i}?", ["A", "B"], 0, f"Explic {i}")
        for i in range(6)
    ]


def _jogo(perguntas, num_equipes=2, clock=None):
    return Jogo(
        perguntas,
        num_equipes=num_equipes,
        tempo_pergunta=30,
        tempo_resposta=15,
        nomes_equipes={
            "A": "Azul",
            "B": "Laranja",
            "C": "Ciano",
            "D": "Rosa",
        },
        clock=clock,
    )


class TestIdaEVolta:
    def test_to_dict_nao_guarda_fase_nem_timer(self):
        jogo = _jogo(_perguntas())
        dados = jogo.to_dict()

        assert "fase" not in dados
        assert "quem_apertou" not in dados
        assert "tempo_estourou" not in dados

    def test_roundtrip_preserva_placar_nomes_ordem_indice_e_rodada(self):
        relogio = Relogio()
        perguntas = _perguntas()
        jogo = _jogo(perguntas, clock=relogio)

        jogo.apertar_botao("A")
        jogo.revelar_resposta()
        jogo.confirmar_acerto("A")
        jogo.proxima_pergunta()
        dados = jogo.to_dict()

        novo = Jogo.from_dict(dados, perguntas, clock=relogio)

        assert novo.placar == {"A": 1, "B": 0}
        assert novo.nomes_equipes == jogo.nomes_equipes
        assert novo.estado.indice_pergunta == jogo.estado.indice_pergunta
        assert novo.estado.numero_pergunta == jogo.estado.numero_pergunta
        assert novo.estado.pergunta_atual.texto == jogo.estado.pergunta_atual.texto
        assert [p.texto for p in novo.perguntas] == [p.texto for p in jogo.perguntas]

    def test_roundtrip_preserva_equipes_extras(self):
        relogio = Relogio()
        perguntas = _perguntas()
        jogo = _jogo(perguntas, num_equipes=3, clock=relogio)
        jogo.placar["C"] = 4
        dados = jogo.to_dict()

        novo = Jogo.from_dict(dados, perguntas, clock=relogio)

        assert novo.num_equipes == 3
        assert novo.placar == {"A": 0, "B": 0, "C": 4}
        assert novo.nomes_equipes["C"] == "Ciano"

    def test_restaura_em_aguardando_com_tempo_cheio(self):
        relogio = Relogio()
        perguntas = _perguntas()
        jogo = _jogo(perguntas, clock=relogio)

        jogo.apertar_botao("B")
        jogo.revelar_resposta()
        dados = jogo.to_dict()
        dados["fase"] = FASE_PONTUADA
        dados["quem_apertou"] = "B"
        dados["tempo_estourou"] = True

        novo = Jogo.from_dict(dados, perguntas, clock=relogio)

        assert novo.estado.fase == FASE_AGUARDANDO
        assert novo.estado.quem_apertou is None
        assert novo.estado.tempo_estourou is False
        assert novo.timer_restante() == pytest.approx(30.0)
        assert novo.timer_rotulo == "Tempo para apertar"

    def test_ordem_invalida_nao_derruba(self):
        relogio = Relogio()
        perguntas = _perguntas()
        jogo = _jogo(perguntas, clock=relogio)
        dados = jogo.to_dict()
        dados["ordem"] = [0, 0, 1, 2, 3, 4]

        novo = Jogo.from_dict(dados, perguntas, clock=relogio)

        assert len(novo.perguntas) == len(perguntas)
        assert {p.texto for p in novo.perguntas} == {p.texto for p in perguntas}

    def test_dados_invalidos_nao_derrubam(self):
        perguntas = _perguntas()
        dados = {
            "num_equipes": "x",
            "placar": {"A": -3, "B": "2"},
            "indice_pergunta": "x",
            "numero_pergunta": -1,
            "ordem": "x",
        }

        novo = Jogo.from_dict(dados, perguntas)

        assert novo.num_equipes == 2
        assert novo.placar == {"A": 0, "B": 0}
        assert novo.estado.indice_pergunta == 0
        assert novo.estado.numero_pergunta == 0
        assert novo.estado.pergunta_atual is None
        assert novo.estado.fase == FASE_AGUARDANDO
