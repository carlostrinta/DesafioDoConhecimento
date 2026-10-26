"""Testes do protocolo serial (função pura real, headless)."""
from pathlib import Path

import pytest
from protocolo import (
    mapear_evento_arduino,
    comandos_para_arduino,
    todos_eventos_v1,
    todos_comandos_v1,
    EVENTOS_ARDUINO_PC_V1,
    COMANDOS_PC_ARDUINO_V1,
)
from jogo import Jogo
from perguntas import Pergunta


class TestProtocoloSerial:
    """Valida que os eventos/comandos esperados batem com o firmware atual."""

    def test_eventos_arduino_conhecidos(self):
        assert todos_eventos_v1() == {
            "BTN_A", "BTN_B", "BTN_AVANCAR",
            "BTN_ACERTO_A", "BTN_ACERTO_B", "BTN_REVELAR", "PRONTO"
        }

    def test_comandos_pc_conhecidos(self):
        assert todos_comandos_v1() == {
            "LED_A_ON", "LED_A_OFF", "LED_B_ON", "LED_B_OFF",
            "BUZZER_ON", "BUZZER_OFF", "BEEP", "BEEP_LONG", "RESET"
        }

    def test_mapeamento_evento_para_acao_real(self, perguntas_exemplo):
        """Testa a função pura mapear_evento_arduino (sem UI, sem serial)."""
        j = Jogo(perguntas_exemplo, num_equipes=2)

        # BTN_A -> apertar_botao("A")
        assert mapear_evento_arduino("BTN_A", j) == ["apertou:A"]
        assert j.estado.quem_apertou == "A"

        # BTN_B antes de revelar -> ignorado
        assert mapear_evento_arduino("BTN_B", j) == []

        # BTN_REVELAR -> revelar_resposta
        assert mapear_evento_arduino("BTN_REVELAR", j) == ["revelou"]
        assert j.estado.fase == 2  # FASE_REVELADA

        # BTN_ACERTO_A -> confirmar_acerto("A")
        assert mapear_evento_arduino("BTN_ACERTO_A", j) == ["pontuou:A"]
        assert j.placar["A"] == 1

        # BTN_AVANCAR -> proxima_pergunta
        assert "proxima_pergunta" in mapear_evento_arduino("BTN_AVANCAR", j)
        assert j.estado.fase == 0  # FASE_AGUARDANDO

    def test_PRONTO_reacende_led_se_quem_apertou(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2)
        j.apertar_botao("A")
        assert mapear_evento_arduino("PRONTO", j) == ["led_reacender:A"]

    def test_PRONTO_sem_quem_apertou(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2)
        assert mapear_evento_arduino("PRONTO", j) == []

    def test_evento_desconhecido_retorna_vazio(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2)
        assert mapear_evento_arduino("XYZ", j) == []

    def test_comandos_para_arduino_mapeia_eventos(self):
        """Testa conversão eventos domínio -> comandos serial."""
        assert comandos_para_arduino(["apertou:A"]) == ["LED_A_ON", "BEEP"]
        assert comandos_para_arduino(["apertou:B"]) == ["LED_B_ON", "BEEP"]
        assert comandos_para_arduino(["pontuou:A"]) == ["BEEP_LONG"]
        assert comandos_para_arduino(["tempo_esgotado"]) == ["BEEP"]
        assert comandos_para_arduino(["proxima_pergunta"]) == ["RESET"]
        assert comandos_para_arduino(["reiniciou_banco"]) == []  # informativo: RESET vem de proxima_pergunta
        assert comandos_para_arduino(["led_reacender:A"]) == ["LED_A_ON"]
        assert comandos_para_arduino(["revelou"]) == []  # sem comando serial
        # Múltiplos eventos
        assert comandos_para_arduino(["apertou:A", "pontuou:A"]) == ["LED_A_ON", "BEEP", "BEEP_LONG"]

    def test_botoes_equipes_3_4_nao_existem_no_protocolo_v1(self):
        """Documentação: BTN_C, BTN_D, BTN_ACERTO_C, BTN_ACERTO_D
        serão adicionados na Etapa 5 com protocolo v2."""
        eventos_v1 = set(EVENTOS_ARDUINO_PC_V1)
        assert "BTN_C" not in eventos_v1
        assert "BTN_ACERTO_C" not in eventos_v1


class TestProtocoloHeadless:
    """O módulo de protocolo não pode arrastar UI nem pygame."""

    def test_importa_sem_tkinter_serial_ou_pygame(self):
        import subprocess
        import sys

        codigo = (
            "import sys; import protocolo; "
            "proibidos = {'tkinter', 'serial', 'pygame'}; "
            "achados = proibidos & set(sys.modules); "
            "assert not achados, achados"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert saida.returncode == 0, saida.stderr