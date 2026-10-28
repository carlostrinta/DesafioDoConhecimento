"""Testes da lista única de VID/PID (Etapa 4.4)."""

from apoio_serial import Porta
from dispositivos import (
    DISPOSITIVOS_CONHECIDOS,
    VIDS_ARDUINO_OFICIAIS,
    descricao_placa,
    porta_conhecida,
    prioridade_porta,
    separar_vid_pid,
)


def test_lista_tem_arduino_oficial_e_clone_ch340():
    assert (0x2341, 0x0043) in DISPOSITIVOS_CONHECIDOS
    assert (0x2A03, 0x0043) in DISPOSITIVOS_CONHECIDOS
    assert DISPOSITIVOS_CONHECIDOS[(0x1A86, 0x7523)] == (
        "CH340/CH341 (clone Arduino)"
    )
    assert VIDS_ARDUINO_OFICIAIS == {0x2341, 0x2A03}


def test_separar_vid_pid_aceita_maiusculas_e_minusculas():
    assert separar_vid_pid("1a86:7523") == (0x1A86, 0x7523)
    assert separar_vid_pid("2341:0043") == (0x2341, 0x0043)
    assert separar_vid_pid("COM5") is None
    assert separar_vid_pid(None) is None


def test_oficial_tem_prioridade_sobre_clone():
    oficial = Porta("COM5", "USB Serial Device", 0x2341, 0x0043)
    clone = Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523)

    assert prioridade_porta(oficial) == 0
    assert prioridade_porta(clone) == 1
    assert prioridade_porta(oficial) < prioridade_porta(clone)


def test_descricao_sem_vid_pid_ainda_e_candidata():
    porta = Porta("COM6", "Arduino Uno")

    assert porta_conhecida(porta) is True
    assert prioridade_porta(porta) == 3


def test_bluetooth_sem_vid_pid_nao_e_candidata():
    assert porta_conhecida(Porta("COM4", "Serial Padrão por link Bluetooth")) is False
    assert prioridade_porta(Porta("COM4", "Serial Padrão por link Bluetooth")) is None


def test_descricao_placa_mostra_nome_e_vid_pid():
    assert (
        descricao_placa(Porta("COM5", "USB Serial Device", 0x2341, 0x0043))
        == "Arduino Uno (2341:0043)"
    )
    assert (
        descricao_placa(Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523))
        == "CH340/CH341 (clone Arduino) (1A86:7523)"
    )
    assert descricao_placa(Porta("COM6", "Arduino Uno")) == "Arduino Uno"
