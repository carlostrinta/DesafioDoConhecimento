"""
Mapeamento puro do protocolo serial Arduino v1 <-> eventos do jogo.

Sem dependências de UI, serial ou pygame: pode ser importado e testado
em ambiente headless. A camada de apresentação usa estas duas funções
para traduzir linha-da-serial -> ação e evento-de-domínio -> comando.
"""

from __future__ import annotations

from jogo import Jogo


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

# Linha da serial -> ação no Jogo
_ACOES = {
    "BTN_A": lambda j: j.apertar_botao("A"),
    "BTN_B": lambda j: j.apertar_botao("B"),
    "BTN_AVANCAR": lambda j: j.proxima_pergunta(),
    "BTN_ACERTO_A": lambda j: j.confirmar_acerto("A"),
    "BTN_ACERTO_B": lambda j: j.confirmar_acerto("B"),
    "BTN_REVELAR": lambda j: j.revelar_resposta(),
}


def mapear_evento_arduino(evento: str, jogo: Jogo) -> list[str]:
    """
    Executa no Jogo a ação correspondente a uma linha vinda do Arduino.
    Devolve os eventos de domínio (a UI decide LED, som e tela).
    """
    if evento == "PRONTO":
        # Arduino reiniciou: re-sincroniza o LED se a rodada está em andamento
        if jogo.estado.quem_apertou:
            return [f"led_reacender:{jogo.estado.quem_apertou}"]
        return []

    acao = _ACOES.get(evento)
    if acao is None:
        return []
    return acao(jogo)


def comandos_para_arduino(eventos_dominio: list[str]) -> list[str]:
    """
    Traduz eventos de domínio em comandos seriais, na mesma ordem do protótipo.

    Só o que o firmware v1 já recebia: LED_x_ON, BEEP, BEEP_LONG e RESET.
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


# ─── Auxiliares para testes/documentação ───
def todos_eventos_v1() -> set[str]:
    return set(EVENTOS_ARDUINO_PC_V1)


def todos_comandos_v1() -> set[str]:
    return set(COMANDOS_PC_ARDUINO_V1)
