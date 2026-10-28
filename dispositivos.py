"""
Lista única de VID/PID conhecidos (Etapa 4.4).

Este módulo é puro (sem tkinter, pyserial ou áudio). A UI e o `serial_comm`
usam a mesma lista para decidir quais portas podem ser o Arduino e para
mostrar a placa na barra de status.

A prioridade de escolha é:
    0. VID de Arduino oficial (2341 ou 2A03);
    1. par VID:PID exato de uma placa/adaptador conhecido (inclui o clone
       CH340/CH341, muito comum em Arduino Uno/Mega clones);
    2. outro PID de um VID de adaptador compatível;
    3. descrição que contenha "arduino", "ch340" ou "ch341".
Portas Bluetooth/virtuais sem VID/PID não entram.
"""

from __future__ import annotations

import re

# Arduino SA e Arduino.org.
VIDS_ARDUINO_OFICIAIS = frozenset({0x2341, 0x2A03})

# Fonte única dos pares VID:PID conhecidos e do nome exibido na barra.
DISPOSITIVOS_CONHECIDOS: dict[tuple[int, int], str] = {
    (0x2341, 0x0043): "Arduino Uno",
    (0x2341, 0x0001): "Arduino Uno (bootloader)",
    (0x2341, 0x0243): "Arduino Uno WiFi",
    (0x2341, 0x0042): "Arduino Mega 2560",
    (0x2341, 0x0010): "Arduino Mega 2560 (bootloader)",
    (0x2341, 0x8036): "Arduino Leonardo",
    (0x2341, 0x8037): "Arduino Micro",
    (0x2A03, 0x0043): "Arduino Uno (arduino.org)",
    (0x2A03, 0x0042): "Arduino Mega 2560 (arduino.org)",
    (0x1A86, 0x7523): "CH340/CH341 (clone Arduino)",
    (0x1A86, 0x5523): "CH341 (clone)",
    (0x10C4, 0xEA60): "CP2102",
    (0x0403, 0x6001): "FTDI FT232R",
    (0x067B, 0x2303): "PL2303",
}

VID_PID_CONHECIDOS = frozenset(DISPOSITIVOS_CONHECIDOS)

# VIDs aceitos mesmo quando o PID não está na tabela acima. Mantém a
# compatibilidade com clones e placas de fabricantes parceiros.
VIDS_CONHECIDOS = frozenset(
    {vid for vid, _ in DISPOSITIVOS_CONHECIDOS}
    | {
        0x1B4F,  # SparkFun
        0x239A,  # Adafruit
        0x03EB,  # Atmel
        0x04D8,  # Microchip
        0x1209,  # pid.codes
    }
)

# Descrições aceitas quando o driver não informa VID/PID.
PALAVRAS_CONHECIDAS = ("arduino", "ch340", "ch341")

_RE_VID_PID = re.compile(r"^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})$")


def separar_vid_pid(valor) -> tuple[int, int] | None:
    """Converte "1A86:7523" em (0x1A86, 0x7523); None se não for VID:PID."""
    if not isinstance(valor, str):
        return None
    casado = _RE_VID_PID.match(valor.strip())
    if not casado:
        return None
    return int(casado.group(1), 16), int(casado.group(2), 16)


def _descricao(porta) -> str:
    return (getattr(porta, "description", "") or "").strip()


def prioridade_porta(porta) -> int | None:
    """Prioridade da porta (menor tenta primeiro); None = não candidata."""
    if porta is None:
        return None
    vid = getattr(porta, "vid", None)
    pid = getattr(porta, "pid", None)
    if vid in VIDS_ARDUINO_OFICIAIS:
        return 0
    if (vid, pid) in DISPOSITIVOS_CONHECIDOS:
        return 1
    if vid in VIDS_CONHECIDOS:
        return 2
    descricao = _descricao(porta).lower()
    if any(palavra in descricao for palavra in PALAVRAS_CONHECIDAS):
        return 3
    return None


def porta_conhecida(porta) -> bool:
    """True se a porta tem cara de Arduino/adaptador USB-serial."""
    return prioridade_porta(porta) is not None


def rotulo_prioridade(porta) -> str:
    """Texto curto para o log da regra de escolha."""
    prioridade = prioridade_porta(porta)
    return {
        0: "oficial",
        1: "VID:PID conhecido",
        2: "adaptador",
        3: "descrição",
    }.get(prioridade, "ignorada")


def descricao_placa(porta) -> str:
    """Nome amigável para a barra de status, com VID:PID quando houver."""
    if porta is None:
        return ""
    vid = getattr(porta, "vid", None)
    pid = getattr(porta, "pid", None)
    nome = DISPOSITIVOS_CONHECIDOS.get((vid, pid))
    if nome:
        return f"{nome} ({vid:04X}:{pid:04X})"
    if vid is not None and pid is not None:
        return f"USB serial {vid:04X}:{pid:04X}"
    return _descricao(porta)
