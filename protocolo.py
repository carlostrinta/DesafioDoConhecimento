"""
Mapeamento puro do protocolo serial Arduino v2 <-> eventos do jogo.

Sem dependências de UI, serial ou pygame: pode ser importado e testado
em ambiente headless. O v2 só usa botões e o comando de configuração de
equipes; LEDs, buzzer e `RESET` pertencem ao adaptador legado
`protocolo_v1.py`.
"""

from __future__ import annotations

from jogo import Jogo


# ─── Eventos Arduino -> PC (v2) ───
EVENTOS_BOTOES_V2 = (
    "BTN_A",
    "BTN_B",
    "BTN_AVANCAR",
    "BTN_ACERTO_A",
    "BTN_ACERTO_B",
    "BTN_REVELAR",
    "BTN_C",
    "BTN_D",
    "BTN_ACERTO_C",
    "BTN_ACERTO_D",
)

EVENTOS_ARDUINO_PC_V2 = EVENTOS_BOTOES_V2 + (
    "PRONTO",
    "VERSAO 2",
    "EQUIPES N",
    "ERRO EQUIPES",
)

# ─── Comandos PC -> Arduino (v2) ───
# O v2 não tem saída física de LED/buzzer; o único comando é a configuração
# de equipes. A resposta `EQUIPES N` é o ACK.
COMANDOS_PC_ARDUINO_V2 = ("CONFIG_TEAMS N",)


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
    Executa no Jogo a ação correspondente a uma linha vinda do Arduino v2.

    Devolve os eventos de domínio (a UI decide som e tela). As linhas de
    controle (`PRONTO`, `VERSAO 2`, `EQUIPES N` e `ERRO EQUIPES`) não alteram
    o Jogo e não geram comando físico no v2.
    """
    if evento in ("PRONTO", "VERSAO 2", "ERRO EQUIPES") or evento.startswith(
        "EQUIPES "
    ):
        return []

    acao = _ACOES.get(evento)
    if acao is None:
        return []
    return acao(jogo)


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
def todos_eventos_v2() -> set[str]:
    return set(EVENTOS_ARDUINO_PC_V2)


def todos_comandos_v2() -> set[str]:
    return set(COMANDOS_PC_ARDUINO_V2)
