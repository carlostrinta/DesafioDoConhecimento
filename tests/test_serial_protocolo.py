"""Testes dos protocolos seriais v1 (legado) e v2, sem UI e sem serial real."""

from pathlib import Path

import pytest

import protocolo
from protocolo import (
    COMANDOS_PC_ARDUINO_V2,
    EVENTOS_ARDUINO_PC_V2,
    comando_config_equipes,
    equipes_confirmadas,
    mapear_evento_arduino,
    todos_comandos_v2,
    todos_eventos_v2,
)
from protocolo_v1 import (
    COMANDOS_PC_ARDUINO_V1,
    EVENTOS_ARDUINO_PC_V1,
    comandos_para_arduino,
    mapear_evento_arduino as mapear_evento_arduino_v1,
    todos_comandos_v1,
    todos_eventos_v1,
)
from jogo import Jogo


class TestProtocoloV1:
    """Contrato do adaptador legado: LEDs, buzzer, RESET e reacendimento."""

    def test_eventos_arduino_conhecidos(self):
        assert todos_eventos_v1() == {
            "BTN_A",
            "BTN_B",
            "BTN_AVANCAR",
            "BTN_ACERTO_A",
            "BTN_ACERTO_B",
            "BTN_REVELAR",
            "PRONTO",
        }

    def test_comandos_pc_conhecidos(self):
        assert todos_comandos_v1() == {
            "LED_A_ON",
            "LED_A_OFF",
            "LED_B_ON",
            "LED_B_OFF",
            "BUZZER_ON",
            "BUZZER_OFF",
            "BEEP",
            "BEEP_LONG",
            "RESET",
        }

    def test_mapeamento_evento_para_acao_real(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)

        assert mapear_evento_arduino_v1("BTN_A", j) == ["apertou:A"]
        assert j.estado.quem_apertou == "A"

        # BTN_B antes de revelar -> ignorado
        assert mapear_evento_arduino_v1("BTN_B", j) == []

        assert mapear_evento_arduino_v1("BTN_REVELAR", j) == ["revelou"]
        assert j.estado.fase == 2  # FASE_REVELADA

        assert mapear_evento_arduino_v1("BTN_ACERTO_A", j) == ["pontuou:A"]
        assert j.placar["A"] == 1

        assert "proxima_pergunta" in mapear_evento_arduino_v1("BTN_AVANCAR", j)
        assert j.estado.fase == 0  # FASE_AGUARDANDO

    def test_pronto_reacende_led_se_quem_apertou(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)
        j.apertar_botao("A")
        assert mapear_evento_arduino_v1("PRONTO", j) == ["led_reacender:A"]

    def test_pronto_sem_quem_apertou(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)
        assert mapear_evento_arduino_v1("PRONTO", j) == []

    def test_evento_desconhecido_retorna_vazio(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)
        assert mapear_evento_arduino_v1("XYZ", j) == []

    def test_comandos_para_arduino_mapeia_eventos(self):
        assert comandos_para_arduino(["apertou:A"]) == ["LED_A_ON", "BEEP"]
        assert comandos_para_arduino(["apertou:B"]) == ["LED_B_ON", "BEEP"]
        assert comandos_para_arduino(["pontuou:A"]) == ["BEEP_LONG"]
        assert comandos_para_arduino(["tempo_esgotado"]) == ["BEEP"]
        assert comandos_para_arduino(["proxima_pergunta"]) == ["RESET"]
        assert comandos_para_arduino(["reiniciou_banco"]) == []
        assert comandos_para_arduino(["led_reacender:A"]) == ["LED_A_ON"]
        assert comandos_para_arduino(["revelou"]) == []
        assert comandos_para_arduino(["apertou:A", "pontuou:A"]) == [
            "LED_A_ON",
            "BEEP",
            "BEEP_LONG",
        ]

    def test_botoes_equipes_3_4_nao_existem_no_protocolo_v1(self):
        eventos_v1 = set(EVENTOS_ARDUINO_PC_V1)
        assert "BTN_C" not in eventos_v1
        assert "BTN_D" not in eventos_v1
        assert "BTN_ACERTO_C" not in eventos_v1
        assert "BTN_ACERTO_D" not in eventos_v1


class TestProtocoloV2:
    """Contrato do v2: somente botões, CONFIG_TEAMS e ACK."""

    def test_eventos_v2_adicionam_botoes_e_handshake(self):
        assert todos_eventos_v2() == todos_eventos_v1() | {
            "BTN_C",
            "BTN_D",
            "BTN_ACERTO_C",
            "BTN_ACERTO_D",
            "VERSAO 2",
            "EQUIPES N",
            "ERRO EQUIPES",
        }
        assert {
            "BTN_C",
            "BTN_D",
            "BTN_ACERTO_C",
            "BTN_ACERTO_D",
        } <= set(EVENTOS_ARDUINO_PC_V2)

    def test_comandos_v2_sao_somente_config_teams(self):
        assert todos_comandos_v2() == {"CONFIG_TEAMS N"}
        assert COMANDOS_PC_ARDUINO_V2 == ("CONFIG_TEAMS N",)
        for proibido in ("LED_", "BEEP", "BUZZER_", "RESET"):
            assert not any(
                cmd.startswith(proibido) for cmd in COMANDOS_PC_ARDUINO_V2
            )

    def test_protocolo_v2_nao_expoe_tradutor_de_comandos_fisicos(self):
        assert not hasattr(protocolo, "comandos_para_arduino")

    def test_mapeamento_c_d_no_jogo_de_quatro_equipes(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=4, contagem_largada=0)

        assert mapear_evento_arduino("BTN_C", j) == ["apertou:C"]
        assert j.estado.quem_apertou == "C"
        assert mapear_evento_arduino("BTN_D", j) == []
        assert mapear_evento_arduino("BTN_REVELAR", j) == ["revelou"]
        assert mapear_evento_arduino("BTN_ACERTO_C", j) == ["pontuou:C"]
        assert j.placar["C"] == 1

    def test_c_d_ignorados_quando_a_partida_tem_duas_equipes(
        self, perguntas_exemplo
    ):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)
        assert mapear_evento_arduino("BTN_C", j) == []
        assert j.estado.quem_apertou is None

    def test_pronto_no_v2_nao_reacende_led(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)
        j.apertar_botao("A")
        assert mapear_evento_arduino("PRONTO", j) == []

    def test_configuracao_de_equipes(self):
        assert comando_config_equipes(2) == "CONFIG_TEAMS 2"
        assert comando_config_equipes(4) == "CONFIG_TEAMS 4"
        assert equipes_confirmadas("EQUIPES 2") == 2
        assert equipes_confirmadas("EQUIPES 4") == 4
        assert equipes_confirmadas("EQUIPES 5") is None
        assert equipes_confirmadas("EQUIPES X") is None
        assert equipes_confirmadas("EQUIPES 22") is None
        assert equipes_confirmadas("OUTRA COISA") is None

    @pytest.mark.parametrize("valor", [0, 1, 5, 22])
    def test_comando_config_equipes_rejeita_n_invalido(self, valor):
        with pytest.raises(ValueError):
            comando_config_equipes(valor)

    @pytest.mark.parametrize(
        "evento", ["VERSAO 2", "EQUIPES 2", "EQUIPES 4", "ERRO EQUIPES"]
    )
    def test_eventos_de_controle_v2_nao_alteram_o_jogo(
        self, perguntas_exemplo, evento
    ):
        j = Jogo(perguntas_exemplo, num_equipes=4, contagem_largada=0)
        antes = (j.estado.fase, j.estado.quem_apertou, dict(j.placar))
        assert mapear_evento_arduino(evento, j) == []
        assert (j.estado.fase, j.estado.quem_apertou, dict(j.placar)) == antes


class TestProtocoloHeadless:
    """Nenhum dos dois módulos pode arrastar UI, serial ou pygame."""

    def test_importa_sem_tkinter_serial_ou_pygame(self):
        import subprocess
        import sys

        codigo = (
            "import sys; import protocolo, protocolo_v1; "
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
