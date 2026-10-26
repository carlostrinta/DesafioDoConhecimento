"""
Dublês de `serial` para os testes (sem hardware).

`ModuloSerialFalso` imita o mínimo de `pyserial` usado por `serial_comm.py`:
`Serial(...)` e `comports()`. Cada `FakeSerial` permite simular placa real
(manda PRONTO), porta fantasma (nunca manda), queda de cabo e driver travado.
"""

from __future__ import annotations

import time


class SerialException(Exception):
    pass


class Porta:
    def __init__(self, device, description="", vid=None, pid=None):
        self.device = device
        self.description = description
        self.vid = vid
        self.pid = pid


class FakeSerial:
    def __init__(
        self,
        porta,
        baudrate=None,
        timeout=None,
        write_timeout=None,
        *,
        manda_pronto=False,
        atraso_pronto=0.05,
    ):
        self.port = porta
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.is_open = True
        self.fechado = False

        self.linhas = []
        self.escritas = []
        self.resets = 0
        self.queda = False
        self.erro_escrita = False
        self.bloqueio_escrita = 0.0
        self.bloqueio_fechamento = 0.0

        self._pronto_at = time.monotonic() + atraso_pronto if manda_pronto else None
        self._pronto_enviado = False

    def reset_input_buffer(self):
        self.resets += 1

    def readline(self):
        if self.queda:
            raise SerialException("device reports readiness to read but returned no data")
        if self._pronto_at is not None and not self._pronto_enviado:
            if time.monotonic() >= self._pronto_at:
                self._pronto_enviado = True
                return b"PRONTO\n"
        if self.linhas:
            return self.linhas.pop(0)
        time.sleep(self.timeout if self.timeout is not None else 0.01)
        return b""

    def write(self, dados):
        if self.bloqueio_escrita:
            espera = self.bloqueio_escrita
            if self.write_timeout is not None:
                espera = min(espera, self.write_timeout)
            time.sleep(espera)
            if self.write_timeout is not None:
                raise SerialException("write timeout")
        if self.erro_escrita:
            raise SerialException("write failed")
        self.escritas.append(dados)

    def close(self):
        if self.bloqueio_fechamento:
            time.sleep(self.bloqueio_fechamento)
        self.fechado = True
        self.is_open = False


class ModuloSerialFalso:
    SerialException = SerialException

    def __init__(self):
        self.portas = []
        self.abertas = []
        self.falhar = set()
        self.manda_pronto = set()
        self.atraso_pronto = 0.05

    def Serial(self, porta, baudrate=None, timeout=None, **kwargs):
        if porta in self.falhar:
            raise SerialException(f"Acesso negado: {porta}")
        s = FakeSerial(
            porta,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=kwargs.get("write_timeout"),
            manda_pronto=porta in self.manda_pronto,
            atraso_pronto=self.atraso_pronto,
        )
        self.abertas.append(s)
        return s

    def comports(self):
        return list(self.portas)


def criar_comm(fila, modulo, **kwargs):
    """Comunicação com tempos curtos (testes rápidos) e log silencioso."""
    from serial_comm import ComunicacaoSerial

    params = dict(
        serial_modulo=modulo,
        listar_portas=modulo.comports,
        intervalo_reconexao=0.05,
        timeout_leitura=0.01,
        timeout_handshake=0.2,
        log=lambda *a, **k: None,
    )
    params.update(kwargs)
    return ComunicacaoSerial(fila, **params)


def esperar(condicao, timeout=3.0, intervalo=0.01):
    """Espera ativa (sem sleep longo) por uma condição de teste."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(intervalo)
    return bool(condicao())


def drenar(fila):
    itens = []
    while True:
        try:
            itens.append(fila.get_nowait())
        except Exception:
            return itens
