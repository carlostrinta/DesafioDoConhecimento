"""
Comunicação serial com o Arduino (protocolo v1).

Este módulo é dono da thread de leitura, da fila de eventos e da detecção da
porta. A interface não toca em `serial` diretamente: ela só consome a fila e
chama `enviar()`.

Sem tkinter aqui. O `pyserial` é opcional: sem ele, `disponivel` fica False e
`iniciar()` não faz nada (o jogo segue no modo teclado).

Os parâmetros de tempo são injetáveis apenas para teste. A interface usa os
padrões de `config.py`: reconexão a cada 3 s, leitura de 0,1 s e handshake
`PRONTO` configurável em `serial.timeout_pronto` (padrão 3 s).
"""

from __future__ import annotations

import queue
import threading
import time

from config import BAUD_RATE, PORTA_FORCADA, TIMEOUT_PRONTO
from dispositivos import (
    PALAVRAS_CONHECIDAS,
    VIDS_CONHECIDOS,
    descricao_placa,
    porta_conhecida,
    prioridade_porta,
    rotulo_prioridade,
    separar_vid_pid,
)

try:
    import serial as _serial_padrao
    import serial.tools.list_ports as _list_ports_padrao
except ImportError:  # pragma: no cover - depende do ambiente
    _serial_padrao = None
    _list_ports_padrao = None

SERIAL_DISPONIVEL = _serial_padrao is not None and _list_ports_padrao is not None

# A lista de VID/PID e as regras de prioridade ficam em `dispositivos.py`.
# `VIDS_CONHECIDOS`/`porta_conhecida` continuam disponíveis aqui para
# compatibilidade com quem já importava este módulo.
_separar_vid_pid = separar_vid_pid

INTERVALO_RECONEXAO = 3.0   # s entre varreduras enquanto não há conexão
TIMEOUT_LEITURA = 0.1       # s do readline (não bloqueia a thread por muito tempo)
TIMEOUT_HANDSHAKE = TIMEOUT_PRONTO  # s esperando "PRONTO" depois de abrir a porta
TIMEOUT_ESCRITA = 0.5       # s do write (driver sem par não trava a UI)
TIMEOUT_PARADA = 1.0        # s esperando a thread terminar em parar()
TIMEOUT_FECHAMENTO = 0.5    # s esperando write+close em parar()


class ComunicacaoSerial:
    """
    Thread única que abre a porta, lê linhas e recoloca eventos na fila.

    Mensagens na fila (mesmo formato do protótipo):
        ("conexao", "COM6")  -> conectou
        ("conexao", None)    -> caiu
        ("placa", "Arduino Uno (2341:0043)")  -> nome para a barra de status
        ("porta_ausente", "COM9") -> configurada, mas não encontrada
        ("porta_ausente", None)   -> a porta configurada voltou a existir
        ("evento", "BTN_A", ts)   -> linha recebida do Arduino; `ts` é
                                     `time.monotonic()` no instante da leitura
                                     no PC (não é o instante físico do aperto)
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
        self.placa_atual = ""
        self._info_portas = {}
        self._porta_ausente_avisada = False
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
        self.placa_atual = ""
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
        self.placa_atual = ""
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
        self._info_portas = {p.device: p for p in portas}
        self.log("\n=== PORTAS SERIAIS DETECTADAS ===")
        for p in portas:
            vid = getattr(p, "vid", None)
            pid = getattr(p, "pid", None)
            if vid is not None and pid is not None:
                identificacao = f"VID:PID {vid:04X}:{pid:04X}"
            else:
                identificacao = "sem VID:PID"
            self.log(
                f"  {p.device} | {getattr(p, 'description', '')} | "
                f"{identificacao} | {rotulo_prioridade(p)}"
            )
        self.log("=================================\n")

        forcadas = []
        if self.porta_forcada:
            vid_pid = separar_vid_pid(self.porta_forcada)
            if vid_pid:
                forcadas = [
                    p.device for p in portas if (p.vid, p.pid) == vid_pid
                ]
                if not forcadas:
                    self.log(
                        f"!! Nenhuma porta com VID:PID {self.porta_forcada}"
                    )
            else:
                forcadas = [self.porta_forcada]

        conhecidas = []
        for ordem, p in enumerate(portas):
            prioridade = prioridade_porta(p)
            if prioridade is not None:
                conhecidas.append((prioridade, ordem, p.device))
        # Regra: oficial > VID:PID exato > adaptador > descricao. Em cada
        # faixa, preserva a ordem em que o sistema enumerou as portas.
        conhecidas.sort(key=lambda item: (item[0], item[1]))

        lista = list(forcadas)
        lista += [device for _, _, device in conhecidas]

        vistas, unicas = set(), []
        for porta in lista:
            if porta not in vistas:
                vistas.add(porta)
                unicas.append(porta)

        if unicas:
            self.log(
                "Regra de escolha: forcada > oficial > VID:PID conhecido > "
                "adaptador > descricao"
            )
            for indice, porta in enumerate(unicas, 1):
                info = self._info_portas.get(porta)
                nome = descricao_placa(info) or "sem metadados"
                rotulo = "forcada" if porta in forcadas else rotulo_prioridade(info)
                self.log(f"  {indice}. {porta} | {nome} | prioridade={rotulo}")
        else:
            self.log("Nenhuma porta candidata (Arduino/adaptador) encontrada.")

        self._atualizar_aviso_porta_configurada(portas, forcadas)
        return unicas

    def _atualizar_aviso_porta_configurada(self, portas, forcadas):
        """
        Avisa a UI uma única vez quando a porta explícita do config.json não
        existe. A detecção automática continua (decisão da Etapa 4.4): o app
        tenta a porta configurada e, se ela não estiver disponível, usa as
        demais candidatas, mas a barra de status deixa de ficar em silêncio.
        """
        if not self.porta_forcada:
            return

        vid_pid = separar_vid_pid(self.porta_forcada)
        if vid_pid:
            presente = bool(forcadas)
        else:
            alvo = self.porta_forcada.upper()
            presente = any(
                (getattr(p, "device", "") or "").upper() == alvo for p in portas
            )

        if presente:
            if self._porta_ausente_avisada:
                self._porta_ausente_avisada = False
                self.fila.put(("porta_ausente", None))
            return

        if self._porta_ausente_avisada:
            return
        self._porta_ausente_avisada = True
        self.log(
            f"!! Porta configurada {self.porta_forcada} não encontrada; "
            "usando a detecção automática."
        )
        self.fila.put(("porta_ausente", self.porta_forcada))

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
                    info = self._info_portas.get(porta)
                    self.placa_atual = descricao_placa(info)
                    detalhe = f" - {self.placa_atual}" if self.placa_atual else ""
                    self.log(f"✓ Conectado em {porta}{detalhe}")
                    # Caso a enumeração não tenha listado a COMx forçada, mas
                    # ela tenha aberto e respondido, o aviso deixa de valer.
                    if (
                        self.porta_forcada
                        and porta.upper() == self.porta_forcada.upper()
                        and self._porta_ausente_avisada
                    ):
                        self._porta_ausente_avisada = False
                        self.fila.put(("porta_ausente", None))
                    # Avisa a UI (reacende o LED se a rodada está em andamento).
                    self.fila.put(("evento", "PRONTO", time.monotonic()))
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
                            if self.placa_atual:
                                self.fila.put(("placa", self.placa_atual))
                            break
                self._parar.wait(0.2)
                continue
            try:
                linha = s.readline().decode(errors="ignore").strip()
                if linha:
                    # Marca o instante de recepção no PC. A UI usa esse
                    # timestamp para separar apertos anteriores ao "JÁ!" dos
                    # que chegaram depois dele; o protocolo v1 não traz
                    # timestamp nem número de sequência do firmware.
                    recebido_em = time.monotonic()
                    self.log(f"[ARDUINO] {linha}")
                    self.fila.put(("evento", linha, recebido_em))
            except Exception as e:
                self.log(f"[ERRO SERIAL] {e} — tentando reconectar")
                self.placa_atual = ""
                self.fechar()
                self.fila.put(("conexao", None))
