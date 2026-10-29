"""
Testes de `serial_comm.py` (Etapas 3.4-A/B/C e 4.4).

A 3.4-A foi só movimentação (comportamento idêntico à v2.1). A 3.4-B corrigiu
o D1 (VID/PID + handshake PRONTO + sem fallback). A 3.4-C corrigiu o D2
(evento de parada, timeouts de leitura/escrita, fechamento seguro). A 4.4
centralizou a lista de VID/PID e a regra de prioridade.

Nada aqui abre porta real: `ModuloSerialFalso` substitui o pyserial.
"""

import queue
import subprocess
import sys
import time
from pathlib import Path

import serial_comm
from apoio_serial import (
    ModuloSerialFalso,
    Porta,
    criar_comm,
    drenar,
    esperar,
)

RAIZ = Path(__file__).resolve().parent.parent


def _evento(itens, nome):
    """Devolve a linha de evento enfileirada, ignorando o timestamp."""
    for item in itens:
        if (
            isinstance(item, tuple)
            and len(item) >= 3
            and item[0] == "evento"
            and item[1] == nome
        ):
            return item
    return None


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
        assert comm._candidatas() == ["COM9", "COM6"]

    def test_porta_forcada_por_vid_pid_vem_primeiro(self):
        """config.json aceita VID:PID além de COMx; casa a porta certa."""
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM5", "USB Serial Device", 0x2341, 0x0043),
            Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523),
        ]
        comm = criar_comm(queue.Queue(), modulo, porta_forcada="1a86:7523")
        assert comm._candidatas() == ["COM7", "COM5"]

    def test_vid_pid_sem_porta_correspondente_cai_nas_conhecidas(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM5", "USB Serial Device", 0x2341, 0x0043),
        ]
        comm = criar_comm(queue.Queue(), modulo, porta_forcada="FFFF:0001")
        assert comm._candidatas() == ["COM5"]

    def test_porta_configurada_ausente_avisa_uma_vez_na_fila(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM5", "Arduino Uno", 0x2341, 0x0043)]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo, porta_forcada="COM9")

        assert comm._candidatas() == ["COM9", "COM5"]
        assert comm._candidatas() == ["COM9", "COM5"]

        itens = drenar(fila)
        assert itens.count(("porta_ausente", "COM9")) == 1

    def test_vid_pid_configurado_ausente_avisa_na_fila(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM5", "Arduino Uno", 0x2341, 0x0043)]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo, porta_forcada="FFFF:0001")

        assert comm._candidatas() == ["COM5"]

        assert drenar(fila).count(("porta_ausente", "FFFF:0001")) == 1

    def test_aviso_de_porta_ausente_e_limpo_quando_ela_aparece(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM5", "Arduino Uno", 0x2341, 0x0043)]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo, porta_forcada="COM9")

        comm._candidatas()
        assert drenar(fila) == [("porta_ausente", "COM9")]

        modulo.portas.append(Porta("COM9", "USB-SERIAL CH340", 0x1A86, 0x7523))
        comm._candidatas()
        assert drenar(fila) == [("porta_ausente", None)]

    def test_descricao_conhecida_tem_prioridade(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM4", "Serial Padrão por link Bluetooth"),
            Porta("COM6", "Arduino Uno", 0x2341, 0x0043),
        ]
        comm = criar_comm(queue.Queue(), modulo)
        assert comm._candidatas() == ["COM6"]

    def test_vid_pid_arduino_uno_e_ch340(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM5", "USB Serial Device", 0x2341, 0x0043),
            Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523),
            Porta("COM8", "Arduino Mega 2560", 0x2341, 0x0042),
        ]
        comm = criar_comm(queue.Queue(), modulo)
        # Oficiais primeiro; o CH340 fica depois dos Arduinos oficiais.
        assert comm._candidatas() == ["COM5", "COM8", "COM7"]

    def test_regra_de_escolha_e_logada_com_porta_falsa(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM5", "USB Serial Device", 0x2341, 0x0043),
            Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523),
            Porta("COM8", "Arduino Mega 2560", 0x2341, 0x0042),
        ]
        logs = []
        comm = criar_comm(queue.Queue(), modulo, log=logs.append)

        assert comm._candidatas() == ["COM5", "COM8", "COM7"]
        texto = "\n".join(logs)
        assert "Regra de escolha" in texto
        assert "prioridade=oficial" in texto
        assert "prioridade=VID:PID conhecido" in texto

    def test_porta_sem_vid_pid_nao_e_candidata(self):
        """D1: Bluetooth (VID/PID None) nunca vira candidata."""
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM3", "Serial Padrão por link Bluetooth"),
            Porta("COM4", "Serial Padrão por link Bluetooth"),
            Porta("COM5", "USB Serial Device"),  # sem VID/PID e sem "arduino"
        ]
        comm = criar_comm(queue.Queue(), modulo)
        assert comm._candidatas() == []


# ─────────────────────────────────────────────────────────
# Conexão, leitura e envio
# ─────────────────────────────────────────────────────────
class TestConexao:
    def test_conecta_apos_pronto_e_avisa_na_fila(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno", 0x2341, 0x0043)]
        modulo.manda_pronto = {"COM6"}
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM6"
            assert modulo.abertas[0].resets == 0  # não descarta o PRONTO
            itens = drenar(fila)
            assert ("conexao", "COM6") in itens
            pronto = _evento(itens, "PRONTO")
            assert pronto is not None
            assert isinstance(pronto[2], float)
        finally:
            comm.rodando = False
            comm.fechar()

    def test_vid_pid_explicito_conecta_antes_do_arduino_oficial(self):
        """
        Escolha explícita do usuário: com `1A86:7523` no config e um Arduino
        oficial (2341:0043) presente, o CH340/COM7 é aberto e conectado; o
        COM5 oficial nem chega a ser tentado.
        """
        modulo = ModuloSerialFalso()
        modulo.portas = [
            Porta("COM5", "USB Serial Device", 0x2341, 0x0043),
            Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523),
        ]
        modulo.manda_pronto = {"COM5", "COM7"}
        fila = queue.Queue()
        comm = criar_comm(fila, modulo, porta_forcada="1A86:7523")

        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM7"
            assert [aberta.port for aberta in modulo.abertas] == ["COM7"]
            assert ("conexao", "COM7") in drenar(fila)
        finally:
            comm.rodando = False
            comm.fechar()

    def test_avisa_placa_conhecida_na_fila(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523)]
        modulo.manda_pronto = {"COM7"}
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            itens = drenar(fila)
            assert ("conexao", "COM7") in itens
            assert (
                "placa", "CH340/CH341 (clone Arduino) (1A86:7523)"
            ) in itens
            assert comm.placa_atual == "CH340/CH341 (clone Arduino) (1A86:7523)"
        finally:
            comm.rodando = False
            comm.fechar()

    def test_porta_configurada_ausente_cai_no_automatico_e_avisa(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM5", "Arduino Uno", 0x2341, 0x0043)]
        modulo.manda_pronto = {"COM5"}
        fila = queue.Queue()
        comm = criar_comm(fila, modulo, porta_forcada="COM9")

        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM5"
            itens = drenar(fila)
            assert ("porta_ausente", "COM9") in itens
            assert ("conexao", "COM5") in itens
        finally:
            comm.rodando = False
            comm.fechar()

    def test_nao_conecta_sem_pronto(self):
        """D1: abrir a porta não basta; precisa do handshake."""
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno", 0x2341, 0x0043)]
        modulo.manda_pronto = set()  # nunca manda PRONTO
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            assert esperar(lambda: len(modulo.abertas) >= 1, timeout=0.5)
            assert esperar(lambda: comm.serial is not None, timeout=0.5) is False
            assert comm.serial is None
            assert modulo.abertas[0].fechado is True
            assert ("protocolo", "sem_handshake") in drenar(fila)
        finally:
            comm.rodando = False
            comm.fechar()

    def test_encaminha_linhas_do_arduino(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)
        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            comm.serial.linhas.append(b"BTN_A\n")
            comm.serial.linhas.append(b"PRONTO\n")
            assert esperar(
                lambda: _evento(drenar(fila), "BTN_A") is not None
            )
        finally:
            comm.rodando = False
            comm.fechar()

    def test_erro_de_leitura_fecha_e_avisa(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
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
            assert ("protocolo", "sem_handshake") in drenar(fila)
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
class TestD1PortaCerta:
    def test_porta_sem_pronto_nao_e_conectada(self):
        """D1: Bluetooth sem PRONTO nunca é aceita como Arduino."""
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM4", "Serial Padrão por link Bluetooth")]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)

        comm.iniciar()
        try:
            esperar(lambda: len(modulo.abertas) >= 1, timeout=0.5)
            assert esperar(lambda: comm.serial is not None, timeout=0.5) is False
            assert comm.serial is None
            assert drenar(fila) == []
        finally:
            comm.rodando = False
            comm.fechar()

    def test_volta_para_a_com6_quando_ela_reaparece(self):
        """D1: queda na COM6, COM4 fantasma no meio, placa volta na COM6."""
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

    def test_so_o_arduino_e_aberto_quando_ha_bluetooth(self):
        """A COM4 nem chega a ser aberta se a COM6 está presente."""
        modulo = ModuloSerialFalso()
        modulo.manda_pronto = {"COM6"}
        modulo.portas = [
            Porta("COM4", "Serial Padrão por link Bluetooth"),
            Porta("COM6", "Arduino Uno", 0x2341, 0x0043),
        ]
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        try:
            assert esperar(lambda: comm.serial is not None)
            assert [s.port for s in modulo.abertas] == ["COM6"]
        finally:
            comm.rodando = False
            comm.fechar()


class TestD2Encerramento:
    def test_fechar_durante_a_conexao_nao_deixa_porta_aberta(self):
        """Fechar enquanto o handshake corre: o worker fecha a porta."""
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno", 0x2341, 0x0043)]
        comm = criar_comm(queue.Queue(), modulo, timeout_handshake=0.3)

        comm.iniciar()
        assert esperar(lambda: len(modulo.abertas) == 1, timeout=0.5)

        comm.rodando = False
        comm.fechar()
        if comm._thread is not None:
            comm._thread.join(timeout=2)

        assert comm.serial is None or comm.serial.is_open is False
        assert modulo.abertas[0].fechado is True

    def test_parar_e_limitado_pelo_timeout(self):
        """Driver travado não pode segurar o fechamento da janela."""
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        assert esperar(lambda: comm.serial is not None)

        comm.serial.bloqueio_escrita = 5.0
        comm.serial.write_timeout = None  # driver que ignora o timeout

        inicio = time.monotonic()
        comm.parar(timeout=0.3)
        decorrido = time.monotonic() - inicio
        assert decorrido < 1.5

    def test_parar_sem_placa_nao_trava(self):
        modulo = ModuloSerialFalso()
        modulo.portas = []
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        time.sleep(0.05)

        inicio = time.monotonic()
        comm.parar(timeout=0.5)
        decorrido = time.monotonic() - inicio

        assert decorrido < 0.5
        assert comm._thread is not None and not comm._thread.is_alive()
        assert comm.rodando is False

    def test_parar_manda_reset_e_fecha(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        assert esperar(lambda: comm.serial is not None)
        aberta = comm.serial

        comm.parar(timeout=1.0)

        assert aberta.escritas == [b"RESET\n"]
        assert aberta.fechado is True
        assert comm.serial is None
        assert not comm._thread.is_alive()

    def test_parar_no_v2_nao_manda_reset(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
        comm = criar_comm(queue.Queue(), modulo)
        comm.definir_protocolo("v2")
        comm.iniciar()
        assert esperar(lambda: comm.serial is not None)
        aberta = comm.serial

        comm.parar(timeout=1.0)

        assert aberta.escritas == []
        assert aberta.fechado is True
        assert comm.serial is None

    def test_parar_com_close_travado_nao_espera_para_sempre(self):
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM6", "Arduino Uno")]
        modulo.manda_pronto = {"COM6"}
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        assert esperar(lambda: comm.serial is not None)
        comm.serial.bloqueio_fechamento = 5.0

        inicio = time.monotonic()
        comm.parar(timeout=0.3)
        decorrido = time.monotonic() - inicio
        assert decorrido < 1.5


# ─────────────────────────────────────────────────────────
# Cenário do usuário (D1/D2 no Windows real, sem hardware)
# ─────────────────────────────────────────────────────────
class TestCenarioReal:
    def test_ciclo_completo_com4_fantasma_com6_real_e_troca_de_porta(self):
        """
        Abre sem placa (só COM4 Bluetooth) -> COM6 aparece -> cabo cai ->
        COM4 continua lá -> placa volta em outra porta (COM7) -> fecha.
        """
        modulo = ModuloSerialFalso()
        modulo.portas = [Porta("COM4", "Serial Padrão por link Bluetooth")]
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)
        comm.iniciar()

        try:
            # 1. Sem placa: a COM4 nem é aberta.
            time.sleep(0.3)
            assert comm.serial is None
            assert modulo.abertas == []

            # 2. Arduino real na COM6: conecta com PRONTO.
            modulo.portas.append(Porta("COM6", "Arduino Uno", 0x2341, 0x0043))
            modulo.manda_pronto.add("COM6")
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM6"

            # 3. Eventos continuam chegando.
            comm.serial.linhas.append(b"BTN_A\n")
            assert esperar(lambda: _evento(drenar(fila), "BTN_A") is not None)

            # 4. Cabo cai; a COM4 fantasma continua disponível.
            comm.serial.queda = True
            modulo.portas = [Porta("COM4", "Serial Padrão por link Bluetooth")]
            assert esperar(lambda: comm.serial is None)
            time.sleep(0.3)
            assert comm.serial is None, "assumiu a COM4 depois da queda"

            # 5. Placa volta em outra porta: COM7 (clone CH340).
            modulo.portas.append(
                Porta("COM7", "USB-SERIAL CH340", 0x1A86, 0x7523)
            )
            modulo.manda_pronto.add("COM7")
            assert esperar(
                lambda: comm.serial is not None and comm.serial.port == "COM7",
                timeout=2.0,
            )

            # 6. Fecha sem travar e sem deixar porta aberta.
            aberta = comm.serial
            inicio = time.monotonic()
            comm.parar(timeout=1.0)
            assert time.monotonic() - inicio < 1.5
            assert aberta.fechado is True
            assert comm.serial is None
            assert not comm._thread.is_alive()
        finally:
            comm.rodando = False
            comm.fechar()

    def test_sem_portas_conecta_quando_a_placa_aparece(self):
        modulo = ModuloSerialFalso()
        modulo.portas = []
        fila = queue.Queue()
        comm = criar_comm(fila, modulo)
        comm.iniciar()
        try:
            time.sleep(0.2)
            assert comm.serial is None
            assert drenar(fila) == []

            modulo.portas = [Porta("COM6", "Arduino Mega 2560", 0x2341, 0x0042)]
            modulo.manda_pronto.add("COM6")
            assert esperar(lambda: comm.serial is not None)
            assert comm.serial.port == "COM6"
        finally:
            comm.parar(timeout=1.0)

    def test_parar_duas_vezes_e_idempotente(self):
        modulo = ModuloSerialFalso()
        modulo.portas = []
        comm = criar_comm(queue.Queue(), modulo)
        comm.iniciar()
        comm.parar(timeout=0.5)
        comm.parar(timeout=0.5)  # não levanta
        assert comm.rodando is False
