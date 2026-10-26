"""
Testes de `serial_comm.py` (Etapa 3.4).

A Etapa 3.4 é só movimentação: o comportamento é o mesmo do protótipo v2.1.
Por isso os defeitos D1/D2 aparecem aqui como `xfail(strict=True)` — eles
documentam a falha atual e viram testes normais nas Etapas 3.4-B e 3.4-C.

Nada aqui abre porta real: `ModuloSerialFalso` substitui o pyserial.
"""

import queue
import subprocess
import sys
from pathlib import Path

import pytest

import serial_comm
from apoio_serial import (
    ModuloSerialFalso,
    Porta,
    criar_comm,
    drenar,
    esperar,
)

RAIZ = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────
# Detecção de portas
# ─────────────────────────────────────────────────────────
class TestCandidatas:
    def test_porta_forcada_vem_primeiro(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM4", "Serial Padrão por link Bluetooth"),
            Porta("COM6", "Arduino Uno", 0x2341, 0x0043),
        ]
        comm = criar_comm(queue.Queue(), modulo, porta_forcada="COM9")
        assert comm._candidatas() == ["COM9", "COM6", "COM4"]

    def test_descricao_conhecida_tem_prioridade(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM4", "Serial Padrão por link Bluetooth"),
            Porta("COM6", "Arduino Uno", 0x2341, 0x0043),
        ]
        comm = criar_comm(queue.Queue(), modulo)
        assert comm._candidatas() == ["COM6", "COM4"]

    def test_sem_descricao_conhecida_ainda_lista_todas(self):
        """Comportamento atual (D1): qualquer porta vira candidata."""
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM3", "Serial Padrão por link Bluetooth"),
            Porta("COM4", "Serial Padrão por link Bluetooth"),
        ]
        comm = criar_comm(queue.Queue(), modulo)
        assert comm._candidatas() == ["COM3", "COM4"]


# ─────────────────────────────────────────────────────────
# Conexão, leitura e envio
# ─────────────────────────────────────────────────────────
class TestConexao:
    def test_conecta_avisa_na_fila_e_reseta_o_buffer(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno", 0x2341, 0x0043)]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM6"
            assert modulo.abertas[0].resets == 1
            assert ("conexao", "COM6") in drenar(fila)
        finally:
            comm.rodando = False
            comm.fechar()

    def test_encaminha_linhas_do_arduino(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)
        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            comm.serial.linhas.append(b"BTN_A\n")
            comm.serial.linhas.append(b"PRONTO\n")
            assert esperar(
                lambda: ("evento", "BTN_A") in drenar(fila)
            )
        finally:
            comm.rodando = False
            comm.fechar()

    def test_erro_de_leitura_fecha_e_avisa(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)
        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            aberta = comm.serial
            aberta.queda = True

            assert esperar(lambda: comm.serial is None)
            assert aberta.fechado is True
            assert ("conexao", None) in drenar(fila)
        finally:
            comm.rodando = False
            comm.fechar()

    def test_nao_conecta_quando_a_porta_falha(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.falhar = {"COM6"}
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)
        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None, timeout=0.5) is False
            assert comm.serial is None
            assert drenar(fila) == []
        finally:
            comm.rodando = False
            comm.fechar()

    def test_enviar_escreve_com_newline(self):
        modulo = ModuloSerialFalso()
        comm = criar_comm(queue.Queue(), modulo)
        fake = modulo.Serial("COM6", 9600, timeout=0.1)
        comm.serial = fake

        comm.enviar("LED_A_ON")
        assert fake.escritas == [b"LED_A_ON\n"]

    def test_enviar_sem_porta_nao_falha(self):
        comm = criar_comm(queue.Queue(), ModuloSerialFalso())
        comm.enviar("RESET")  # no-op

    def test_enviar_engole_erro_de_escrita(self):
        modulo = ModuloSerialFalso()
        comm = criar_comm(queue.Queue(), modulo)
        fake = modulo.Serial("COM6", 9600, timeout=0.1)
        fake.erro_escrita = True
        comm.serial = fake
        comm.enviar("BEEP")  # não levanta

    def test_fechar_fecha_a_porta(self):
        modulo = ModuloSerialFalso()
        comm = criar_comm(queue.Queue(), modulo)
        fake = modulo.Serial("COM6", 9600, timeout=0.1)
        comm.serial = fake

        comm.fechar()
        assert comm.serial is None
        assert fake.fechado is True


# ─────────────────────────────────────────────────────────
# Sem pyserial / módulo puro
# ─────────────────────────────────────────────────────────
class TestSemPyserial:
    def test_sem_serial_nao_inicia_thread(self, monkeypatch):
        monkeypatch.setattr(serial_comm, "_serial_padrao", None)
        monkeypatch.setattr(serial_comm, "_list_ports_padrao", None)

        comm = serial_comm.ComunicacaoSerial(queue.Queue())
        assert comm.disponivel is False
        comm.iniciar()
        assert comm._thread is None
        assert comm.rodando is False

    def test_importa_sem_tkinter(self):
        codigo = (
            "import sys; import serial_comm; "
            "assert 'tkinter' not in sys.modules"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            cwd=str(RAIZ),
        )
        assert saida.returncode == 0, saida.stderr


# ─────────────────────────────────────────────────────────
# Defeitos conhecidos (documentados; corrigidos em B e C)
# ─────────────────────────────────────────────────────────
class TestDefeitosAtuais:
    @pytest.mark.xfail(
        strict=True,
        reason="D1: porta Bluetooth sem PRONTO é aceita como conectada",
    )
    def test_d1_porta_sem_pronto_nao_deve_ser_conectada(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM4", "Serial Padrão por link Bluetooth")]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            esperar(lambda: comm.serial is not None, timeout=0.5)
            assert comm.serial is None, "conectou sem handshake"
        finally:
            comm.rodando = False
            comm.fechar()

    @pytest.mark.xfail(
        strict=True,
        reason="D1: com a COM4 aceita, o app não volta para a COM6 ao reconectar",
    )
    def test_d1_volta_para_a_com6_quando_ela_reaparece(self):
        modulo = ModuloSerialFalso()
        modulo.manda_pronto = {"COM6"}
        modulo.portas = [Porta("COM6", "Arduino Uno", 0x2341, 0x0043)]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM6"

            # Cabo cai: a porta some e a COM4 (fantasma) continua lá.
            comm.serial.queda = True
            modulo.portas = [Porta("COM4", "Serial Padrão por link Bluetooth")]
            assert esperar(lambda: comm.serial is None)

            # A placa volta na COM6.
            modulo.portas.append(Porta("COM6", "Arduino Uno", 0x2341, 0x0043))
            assert esperar(
                lambda: comm.serial is not None and comm.serial.port == "COM6",
                timeout=1.5,
            )
        finally:
            comm.rodando = False
            comm.fechar()

    @pytest.mark.xfail(
        strict=True,
        reason="D2: fechar durante a abertura deixa a porta aberta",
    )
    def test_d2_fechar_durante_a_conexao_nao_deixa_porta_aberta(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM4", "Serial Padrão por link Bluetooth")]
        comm = criar_comm(queue.Queue(), modulo, pausa_reset=0.3)

        comm.iniciar()
        assert esperar(lambda: len(modulo.abertas) == 1, timeout=0.5)

        comm.rodando = False
        comm.fechar()
        if comm._thread is not None:
            comm._thread.join(timeout=2)

        assert comm.serial is None or comm.serial.is_open is False

    @pytest.mark.xfail(
        strict=True,
        reason="D2: não existe parada com timeout; fechar pode travar no driver",
    )
    def test_d2_parar_e_limitado_pelo_timeout(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        assert esperar(lambda: comm.serial is not None)
        comm.serial.bloqueio_escrita = 5.0
        comm.serial.write_timeout = None

        try:
            comm.parar(timeout=0.3)  # ainda não existe na Etapa 3.4-A
        finally:
            comm.rodando = False
