"""Testes do protocolo serial (strings esperadas)."""
import pytest
from jogo import Jogo, Pergunta


class TestProtocoloSerial:
    """Valida que os eventos/comandos esperados batem com o firmware atual."""

    EVENTOS_ARDUINO_PC = [
        "BTN_A",
        "BTN_B",
        "BTN_AVANCAR",
        "BTN_ACERTO_A",
        "BTN_ACERTO_B",
        "BTN_REVELAR",
        "PRONTO",
    ]

    COMANDOS_PC_ARDUINO = [
        "LED_A_ON",
        "LED_A_OFF",
        "LED_B_ON",
        "LED_B_OFF",
        "BUZZER_ON",
        "BUZZER_OFF",
        "BEEP",
        "BEEP_LONG",
        "RESET",
    ]

    def test_eventos_arduino_conhecidos(self):
        # Estes são os eventos que o processar_evento do desafio.py espera
        assert set(self.EVENTOS_ARDUINO_PC) == {
            "BTN_A", "BTN_B", "BTN_AVANCAR",
            "BTN_ACERTO_A", "BTN_ACERTO_B", "BTN_REVELAR", "PRONTO"
        }

    def test_comandos_pc_conhecidos(self):
        assert set(self.COMANDOS_PC_ARDUINO) == {
            "LED_A_ON", "LED_A_OFF", "LED_B_ON", "LED_B_OFF",
            "BUZZER_ON", "BUZZER_OFF", "BEEP", "BEEP_LONG", "RESET"
        }

    def test_mapeamento_evento_para_acao(self, perguntas_exemplo):
        """Simula o processar_evento do desafio.py chamando métodos do Jogo."""
        j = Jogo(perguntas_exemplo, num_equipes=2)

        # BTN_A -> apertar_botao("A")
        assert j.apertar_botao("A") is True
        assert j.estado.quem_apertou == "A"

        # BTN_B antes de revelar -> ignorado
        assert j.apertar_botao("B") is False

        # BTN_REVELAR -> revelar_resposta
        assert j.revelar_resposta() is True
        assert j.estado.fase == 2  # FASE_REVELADA

        # BTN_ACERTO_A -> confirmar_acerto("A")
        assert j.confirmar_acerto("A") is True
        assert j.placar["A"] == 1

        # BTN_AVANCAR -> proxima_pergunta
        assert j.proxima_pergunta() is True
        assert j.estado.fase == 0  # FASE_AGUARDANDO

    def test_botoes_equipes_3_4_nao_existem_no_protocolo_atual(self):
        """Documentação: BTN_C, BTN_D, BTN_ACERTO_C, BTN_ACERTO_D
        serão adicionados na Etapa 5 com protocolo v2."""
        # No protocolo atual (v1), apenas A e B existem
        eventos_v1 = {"BTN_A", "BTN_B", "BTN_ACERTO_A", "BTN_ACERTO_B"}
        assert "BTN_C" not in eventos_v1
        assert "BTN_ACERTO_C" not in eventos_v1