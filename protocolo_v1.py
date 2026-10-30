"""Adaptador legado do protocolo serial v1 (2 equipes, LEDs e buzzer).

Este módulo concentra tudo que só existe no caminho v1: os comandos de
LED/buzzer, o `RESET` de fechamento e o reacendimento do LED quando o Arduino
reinicia (`PRONTO`). O protocolo v2 não importa nada daqui.

A saída é mantida byte a byte igual à do código anterior; os testes de
caracterização em `tests/test_protocolo_v1_caracterizacao.py` congelam esse
contrato.
"""

from __future__ import annotations

from jogo import Jogo
from protocolo import mapear_evento_arduino as _mapear_botoes

# ─── Eventos Arduino -> PC (v1) ───
EVENTOS_ARDUINO_PC_V1 = (
    "BTN_A",
    "BTN_B",
    "BTN_AVANCAR",
    "BTN_ACERTO_A",
    "BTN_ACERTO_B",
    "BTN_REVELAR",
    "PRONTO",
)

# ─── Comandos PC -> Arduino (v1) ───
COMANDOS_PC_ARDUINO_V1 = (
    "LED_A_ON",
    "LED_A_OFF",
    "LED_B_ON",
    "LED_B_OFF",
    "BUZZER_ON",
    "BUZZER_OFF",
    "BEEP",
    "BEEP_LONG",
    "RESET",
)

COMANDO_RESET = "RESET"


def mapear_evento_arduino(evento: str, jogo: Jogo) -> list[str]:
    """
    Executa no Jogo a ação de uma linha v1 e devolve os eventos de domínio.

    O `PRONTO` é específico do adaptador v1: se há uma equipe com a vez, o LED
    dela precisa ser reaceso. Os demais botões são compartilhados com o v2.
    """
    if evento == "PRONTO":
        if jogo.estado.quem_apertou:
            return [f"led_reacender:{jogo.estado.quem_apertou}"]
        return []
    return _mapear_botoes(evento, jogo)


def comandos_para_arduino(eventos_dominio: list[str]) -> list[str]:
    """
    Traduz eventos de domínio nos comandos seriais legados, na mesma ordem.

    LED_x_ON, BEEP, BEEP_LONG e RESET. Eventos apenas visuais (revelou,
    contagem, largada, reinícios informativos) não geram comando.
    """
    cmds: list[str] = []
    for ev in eventos_dominio:
        if ev.startswith("apertou:"):
            equipe = ev.split(":", 1)[1]
            cmds.append(f"LED_{equipe}_ON")
            cmds.append("BEEP")
        elif ev.startswith("pontuou:"):
            cmds.append("BEEP_LONG")
        elif ev == "tempo_esgotado":
            cmds.append("BEEP")
        elif ev == "proxima_pergunta":
            # "reiniciou_banco" também emite "proxima_pergunta": um RESET só
            cmds.append("RESET")
        elif ev.startswith("led_reacender:"):
            equipe = ev.split(":", 1)[1]
            cmds.append(f"LED_{equipe}_ON")
    return cmds


def comando_reset() -> str:
    """Comando enviado ao fechar a porta no caminho v1."""
    return COMANDO_RESET


# ─── Auxiliares para testes/documentação ───
def todos_eventos_v1() -> set[str]:
    return set(EVENTOS_ARDUINO_PC_V1)


def todos_comandos_v1() -> set[str]:
    return set(COMANDOS_PC_ARDUINO_V1)
