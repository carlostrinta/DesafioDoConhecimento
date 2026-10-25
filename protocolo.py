"""
Mapeamento puro do protocolo serial Arduino v1 <-> eventos do jogo.
Sem dependências de UI, serial, pygame, tkinter.
"""

from __future__ import annotations
from typing import Literal
from jogo import Jogo, FASE_AGUARDANDO, FASE_RESPONDENDO, FASE_REVELADA, FASE_PONTUADA


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


def mapear_evento_arduino(evento: str, jogo: Jogo) -> list[str]:
    """
    Processa uma linha vinda do Arduino e delega ao Jogo.
    Retorna lista de eventos de domínio para a UI disparar efeitos (LED, som, serial).
    """
    if evento == "BTN_A":
        return jogo.apertar_botao("A")
    elif evento == "BTN_B":
        return jogo.apertar_botao("B")
    elif evento == "BTN_AVANCAR":
        return jogo.proxima_pergunta()
    elif evento == "BTN_ACERTO_A":
        return jogo.confirmar_acerto("A")
    elif evento == "BTN_ACERTO_B":
        return jogo.confirmar_acerto("B")
    elif evento == "BTN_REVELAR":
        return jogo.revelar_resposta()
    elif evento == "PRONTO":
        # Arduino reiniciou: re-sincroniza LED se alguém apertou
        eventos = []
        if jogo.estado.quem_apertou:
            # A UI deve enviar LED_ON para quem_apertou
            eventos.append(f"led_reacender:{jogo.estado.quem_apertou}")
        return eventos
    else:
        return []


def comandos_para_arduino(eventos_dominio: list[str]) -> list[str]:
    """
    Converte eventos de domínio em comandos serial para o Arduino.
    A UI chama esta função após processar eventos do Jogo.
    """
    cmds = []
    for ev in eventos_dominio:
        if ev.startswith("apertou:"):
            equipe = ev.split(":")[1]
            cmds.append(f"LED_{equipe}_ON")
            cmds.append("BEEP")
        elif ev == "revelou":
            pass  # sem comando serial específico
        elif ev.startswith("pontuou:"):
            equipe = ev.split(":")[1]
            cmds.append("BEEP_LONG")
        elif ev == "tempo_esgotado":
            cmds.append("BEEP")
        elif ev == "proxima_pergunta":
            cmds.append("RESET")
        elif ev == "reiniciou_banco":
            cmds.append("RESET")
        elif ev.startswith("led_reacender:"):
            equipe = ev.split(":")[1]
            cmds.append(f"LED_{equipe}_ON")
    return cmds


# ─── Funções auxiliares para testes ───
def todos_eventos_v1() -> set[str]:
    return set(EVENTOS_ARDUINO_PC_V1)


def todos_comandos_v1() -> set[str]:
    return set(COMANDOS_PC_ARDUINO_V1)