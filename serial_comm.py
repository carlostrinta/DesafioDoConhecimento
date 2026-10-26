"""
Comunicação serial com o Arduino (protocolo v1).

Este módulo é dono da thread de leitura, da fila de eventos e da detecção da
porta. A interface não toca em `serial` diretamente: ela só consome a fila e
chama `enviar()`.

Sem tkinter aqui. O `pyserial` é opcional: sem ele, `disponivel` fica False e
`iniciar()` não faz nada (o jogo segue no modo teclado).

Os parâmetros de tempo são injetáveis apenas para teste; a interface usa os
padrões (reconexão a cada 3 s, leitura de 0,1 s, handshake de 3 s).
"""

from __future__ import annotations

import queue
import threading
import time

from config import BAUD_RATE, PORTA_FORCADA

try:
    import serial as _serial_padrao
    import serial.tools.list_ports as _list_ports_padrao
except ImportError:  # pragma: no cover - depende do ambiente
    _serial_padrao = None
    _list_ports_padrao = None

SERIAL_DISPONIVEL = _serial_padrao is not None and _list_ports_padrao is not None

# ─── Quem pode ser o Arduino ───
# Placas Arduino oficiais: 2341 = Arduino SA, 2A03 = Arduino.org.
# Adaptadores USB-serial comuns: 1A86 = CH340/CH341, 10C4 = CP210x,
# 0403 = FTDI, 067B = PL2303. Compatíveis: SparkFun, Adafruit, Atmel,
# Microchip e pid.codes.
# Portas sem VID/PID (Bluetooth, virtuais) NUNCA entram: era o furo que
# fazia o app "conectar" na COM4 do Bluetooth.
VIDS_CONHECIDOS = frozenset({
    0x2341, 0x2A03,
    0x1A86, 0x10C4, 0x0403, 0x067B,
    0x1B4F, 0x239A, 0x03EB, 0x04D8, 0x1209,
})

# Descrições aceitas quando o driver não informa VID/PID.
PALAVRAS_CONHECIDAS = ("arduino", "ch340", "ch341")

INTERVALO_RECONEXAO = 3.0   # s entre varreduras enquanto não há conexão
TIMEOUT_LEITURA = 0.1       # s do readline (não bloqueia a thread por muito tempo)
TIMEOUT_HANDSHAKE = 3.0     # s esperando "PRONTO" depois de abrir a porta
TIMEOUT_ESCRITA = 0.5       # s do write (driver sem par não trava a UI)
TIMEOUT_PARADA = 1.0        # s esperando a thread terminar em parar()
TIMEOUT_FECHAMENTO = 0.5    # s esperando write+close em parar()


def porta_conhecida(porta):
    """True se a porta tem cara de Arduino/adaptador USB-serial."""
    if porta.vid in VIDS_CONHECIDOS:
        return True
    descricao = (porta.description or "").lower()
    return any(k in descricao for k in PALAVRAS_CONHECIDAS)


class ComunicacaoSerial:
    """
    Thread única que abre a porta, lê linhas e recoloca eventos na fila.

    Mensagens na fila (mesmo formato do protótipo):
        ("conexao", "COM6")  -> conectou
        ("conexao", None)    -> caiu
        ("evento", "BTN_A")  -> linha recebida do Arduino
    """

    def __init__(
        self,
        fila,
        *,
        serial_modulo=None,
        listar_portas=None,
        baud_rate=BAUD_RATE,
        porta_forcada=PORTA_FORCADA,
        intervalo_reconexao=INTERVALO_RECONEXAO,
        timeout_leitura=TIMEOUT_LEITURA,
        timeout_handshake=TIMEOUT_HANDSHAKE,
        timeout_escrita=TIMEOUT_ESCRITA,
        log=print,
    ):
        self.fila = fila
        self.baud_rate = baud_rate
        self.porta_forcada = porta_forcada
        self.intervalo_reconexao = intervalo_reconexao
        self.timeout_leitura = timeout_leitura
        self.timeout_handshake = timeout_handshake
        self.timeout_escrita = timeout_escrita
        self.log = log

        modulo = serial_modulo if serial_modulo is not None else _serial_padrao
        listar = listar_portas
        if listar is None and _list_ports_padrao is not None:
            listar = _list_ports_padrao.comports

        self._serial_modulo = modulo
        self._listar_portas = listar
        self.disponivel = modulo is not None and listar is not None

        self.serial = None
        self._parar = threading.Event()
        self._parar.set()  # parado até iniciar()
        self._thread = None

    # -----------------------------------------------------
    # Ciclo de vida
    # -----------------------------------------------------
    @property
    def rodando(self):
        return not self._parar.is_set()

    @rodando.setter
    def rodando(self, valor):
        if valor:
            self._parar.clear()
        else:
            self._parar.set()

    def iniciar(self):
        if not self.disponivel or self.rodando:
            return
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="serial-arduino",
        )
        self._thread.start()

    def parar(self, timeout=TIMEOUT_PARADA):
        """
        Para a thread e fecha a porta sem travar a interface.

        O `write`+`close` correm numa thread daemon com espera limitada: se o
        driver de uma porta fantasma travar, o app fecha mesmo assim.
        """
        self._parar.set()

        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout)

        s, self.serial = self.serial, None
        if s is not None:
            self._encerrar_porta(s)

    def _encerrar_porta(self, s):
        """Manda RESET (apaga LEDs) e fecha, com tempo limitado."""

        def alvo():
            try:
                if s.is_open:
                    s.write(b"RESET\n")
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass

        t = threading.Thread(target=alvo, daemon=True, name="serial-fechar")
        t.start()
        t.join(TIMEOUT_FECHAMENTO)

    def fechar(self):
        """Fecha a porta (não mexe na thread; use `parar()` para encerrar)."""
        s, self.serial = self.serial, None
        try:
            if s:
                s.close()
        except Exception:
            pass

    # -----------------------------------------------------
    # Detecção
    # -----------------------------------------------------
    def _candidatas(self):
        portas = list(self._listar_portas())
        self.log("\n=== PORTAS SERIAIS DETECTADAS ===")
        for p in portas:
            self.log(f"  {p.device} | descrição: {p.description}")
        self.log("=================================\n")

        lista = []
        if self.porta_forcada:
            lista.append(self.porta_forcada)
        lista += [p.device for p in portas if porta_conhecida(p)]

        vistas, unicas = set(), []
        for porta in lista:
            if porta not in vistas:
                vistas.add(porta)
                unicas.append(porta)
        return unicas

    def _tentar_conectar(self, porta):
        """
        Abre a porta e só considera conectada depois de receber "PRONTO".

        A placa reinicia quando a serial abre; o firmware manda PRONTO no
        setup(). Se a linha não chegar em `timeout_handshake`, fecha e deixa
        a próxima candidata tentar. Sem isso, uma porta fantasma (Bluetooth)
        era aceita como se fosse o Arduino.
        """
        try:
            s = self._serial_modulo.Serial(
                porta,
                self.baud_rate,
                timeout=self.timeout_leitura,
                write_timeout=self.timeout_escrita,
            )
        except Exception as e:
            self.log(f"✗ Falha em {porta}: {e}")
            return False

        limite = time.monotonic() + self.timeout_handshake
        try:
            while time.monotonic() < limite:
                if not self.rodando:
                    s.close()
                    return False
                linha = s.readline().decode(errors="ignore").strip()
                if linha == "PRONTO":
                    self.serial = s
                    self.log(f"✓ Conectado em {porta}")
                    # Avisa a UI (reacende o LED se a rodada está em andamento).
                    self.fila.put(("evento", "PRONTO"))
                    return True
            s.close()
            self.log(f"✗ {porta}: sem PRONTO em {self.timeout_handshake:.0f}s")
            return False
        except Exception as e:
            try:
                s.close()
            except Exception:
                pass
            self.log(f"✗ Falha em {porta}: {e}")
            return False

    # -----------------------------------------------------
    # Envio e leitura
    # -----------------------------------------------------
    def enviar(self, cmd):
        s = self.serial
        if s and s.is_open:
            try:
                s.write((cmd + "\n").encode())
            except Exception:
                pass

    def _loop(self):
        """Thread: nunca mexe na interface, só coloca mensagens na fila."""
        ultima_busca = 0.0
        while self.rodando:
            s = self.serial
            if not (s and s.is_open):
                if time.monotonic() - ultima_busca >= self.intervalo_reconexao:
                    ultima_busca = time.monotonic()
                    for porta in self._candidatas():
                        if self._tentar_conectar(porta):
                            self.fila.put(("conexao", porta))
                            break
                self._parar.wait(0.2)
                continue
            try:
                linha = s.readline().decode(errors="ignore").strip()
                if linha:
                    self.log(f"[ARDUINO] {linha}")
                    self.fila.put(("evento", linha))
            except Exception as e:
                self.log(f"[ERRO SERIAL] {e} — tentando reconectar")
                self.fechar()
                self.fila.put(("conexao", None))
