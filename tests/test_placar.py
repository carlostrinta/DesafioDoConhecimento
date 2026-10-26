"""Testes de placar e pontuação."""
import pytest
from jogo import Jogo
from perguntas import Pergunta


@pytest.fixture
def jogo_2(perguntas_exemplo):
    return Jogo(perguntas_exemplo, num_equipes=2)


@pytest.fixture
def jogo_3(perguntas_exemplo):
    return Jogo(perguntas_exemplo, num_equipes=3)


class TestPlacar:
    def test_incrementa_apenas_quem_apertou(self, jogo_2):
        j = jogo_2
        j.apertar_botao("A")
        j.revelar_resposta()
        assert j.confirmar_acerto("A") == ["pontuou:A"]
        assert j.placar == {"A": 1, "B": 0}

    def test_nao_incrementa_se_nao_apertou(self, jogo_2):
        j = jogo_2
        j.apertar_botao("A")
        j.revelar_resposta()
        assert j.confirmar_acerto("B") == ["recusado:acerto_outra_equipe"]
        assert j.placar == {"A": 0, "B": 0}

    def test_pontos_acumulam(self, jogo_2):
        j = jogo_2
        for _ in range(3):
            j.apertar_botao("A")
            j.revelar_resposta()
            assert j.confirmar_acerto("A") == ["pontuou:A"]
            j.proxima_pergunta()
        assert j.placar["A"] == 3

    def test_placar_3_equipes_independente(self, jogo_3):
        j = jogo_3
        for eq in ("A", "B", "C"):
            j.apertar_botao(eq)
            j.revelar_resposta()
            assert j.confirmar_acerto(eq) == [f"pontuou:{eq}"]
            j.proxima_pergunta()
        assert j.placar == {"A": 1, "B": 1, "C": 1}

    def test_reiniciar_placar_mantem_equipes_ativas(self, jogo_2):
        j = jogo_2
        j.placar["A"] = 5
        assert j.reiniciar_placar() == ["reiniciou_placar"]
        assert set(j.placar.keys()) == {"A", "B"}
        assert all(v == 0 for v in j.placar.values())

    def test_num_equipes_invalido_levanta_erro(self, perguntas_exemplo):
        with pytest.raises(ValueError):
            Jogo(perguntas_exemplo, num_equipes=1)
        with pytest.raises(ValueError):
            Jogo(perguntas_exemplo, num_equipes=5)

    def test_nomes_equipes_personalizados(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=3, nomes_equipes={"A": "Alpha", "B": "Beta", "C": "Gamma"})
        assert j.nomes_equipes["A"] == "Alpha"
        assert j.nomes_equipes["C"] == "Gamma"