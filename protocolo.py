"""
Mapeamento puro do protocolo serial Arduino v1/v2 <-> eventos do jogo.

Sem dependências de UI, serial ou pygame: pode ser importado e testado
em ambiente headless. A camada de apresentação usa estas funções para
traduzir linha-da-serial -> ação e evento-de-domínio -> comando.
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

# ─── Eventos/comandos do protocolo v2 ───
# O firmware v2 de produção não tem LEDs/buzzer; os comandos de saída
# continuam sendo aceitos pelo protocolo e são ignorados pelo firmware.
EVENTOS_ARDUINO_PC_V2 = EVENTOS_ARDUINO_PC_V1 + (
    "BTN_C",
    "BTN_D",
    "BTN_ACERTO_C",
    "BTN_ACERTO_D",
    "VERSAO 2",
    "EQUIPES N",
    "ERRO EQUIPES",
)

COMANDOS_PC_ARDUINO_V2 = COMANDOS_PC_ARDUINO_V1 + (
    "LED_C_ON",
    "LED_C_OFF",
    "LED_D_ON",
    "LED_D_OFF",
    "CONFIG_TEAMS N",
)

# Linha da serial -> ação no Jogo
_ACOES = {
    "BTN_A": lambda j: j.apertar_botao("A"),
    "BTN_B": lambda j: j.apertar_botao("B"),
    "BTN_C": lambda j: j.apertar_botao("C"),
    "BTN_D": lambda j: j.apertar_botao("D"),
    "BTN_AVANCAR": lambda j: j.proxima_pergunta(),
    "BTN_ACERTO_A": lambda j: j.confirmar_acerto("A"),
    "BTN_ACERTO_B": lambda j: j.confirmar_acerto("B"),
    "BTN_ACERTO_C": lambda j: j.confirmar_acerto("C"),
    "BTN_ACERTO_D": lambda j: j.confirmar_acerto("D"),
    "BTN_REVELAR": lambda j: j.revelar_resposta(),
}


def mapear_evento_arduino(evento: str, jogo: Jogo) -> list[str]:
    """
    Executa no Jogo a ação correspondente a uma linha vinda do Arduino.
    Devolve os eventos de domínio (a UI decide LED, som e tela).

    As linhas de controle do v2 (`VERSAO 2`, `EQUIPES N` e `ERRO EQUIPES`)
    são reconhecidas pela camada serial, mas não alteram o Jogo.
    """
    if evento == "PRONTO":
        # Arduino reiniciou: re-sincroniza o LED se a rodada está em andamento
        if jogo.estado.quem_apertou:
            return [f"led_reacender:{jogo.estado.quem_apertou}"]
        return []

    if evento in ("VERSAO 2", "ERRO EQUIPES") or evento.startswith("EQUIPES "):
        return []

    acao = _ACOES.get(evento)
    if acao is None:
        return []
    return acao(jogo)


def comandos_para_arduino(
    eventos_dominio: list[str], *, protocolo: str | None = None
) -> list[str]:
    """
    Traduz eventos de domínio em comandos seriais, na mesma ordem do protótipo.

    LED_x_ON, BEEP, BEEP_LONG e RESET. No protocolo v2 o PC não envia comandos
    de saída física; `CONFIG_TEAMS` é enviado à parte. O caminho v1 (inclusive
    `protocolo=None`, antes do handshake) permanece idêntico.
    """
    if protocolo == "v2":
        return []

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


def comando_config_equipes(num_equipes: int) -> str:
    """Comando v2 para configurar o número de equipes no firmware."""
    quantidade = int(num_equipes)
    if not 2 <= quantidade <= 4:
        raise ValueError("o firmware v2 aceita de 2 a 4 equipes")
    return f"CONFIG_TEAMS {quantidade}"


def equipes_confirmadas(linha: str) -> int | None:
    """Interpreta `EQUIPES N`; devolve None para ACK inválido/ausente."""
    if not linha.startswith("EQUIPES "):
        return None
    valor = linha.split(" ", 1)[1].strip()
    if valor not in ("2", "3", "4"):
        return None
    return int(valor)


# ─── Auxiliares para testes/documentação ───
def todos_eventos_v1() -> set[str]:
    return set(EVENTOS_ARDUINO_PC_V1)


def todos_comandos_v1() -> set[str]:
    return set(COMANDOS_PC_ARDUINO_V1)


def todos_eventos_v2() -> set[str]:
    return set(EVENTOS_ARDUINO_PC_V2)


def todos_comandos_v2() -> set[str]:
    return set(COMANDOS_PC_ARDUINO_V2)
