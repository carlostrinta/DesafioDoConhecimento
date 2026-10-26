"""
Áudio do Duelo de Conhecimento: gera WAV em memória e toca via pygame.mixer.

Módulo independente de tkinter e de serial. O `pygame` é opcional: sem ele (ou
sem placa de som) `Som` fica inativo (`ativo=False`, `disponivel=False`) e
todas as chamadas viram no-op — o jogo continua, apenas sem som.

Nenhum arquivo externo: os efeitos são sintetizados aqui (senoides com
envelope suave). A tabela evento -> arquivo e o pacote de sons entram na
Etapa 4.5; por enquanto as notas de cada evento ficam nos métodos, idênticas
ao protótipo v2.2 (bytes WAV verificados por sha256 em tests/test_audio.py).
"""

from __future__ import annotations

import io
import math
import struct
import wave

from jogo import FASE_AGUARDANDO, FASE_RESPONDENDO


def _gerar_wav(notas, taxa=22050, volume=0.55):
    """Gera um WAV em memória a partir de uma lista de (freq_hz, dur_ms)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        frames = bytearray()
        amp_max = int(32767 * volume)
        for freq, dur in notas:
            n = max(1, int(taxa * dur / 1000))
            if freq <= 0:
                frames.extend(b"\x00\x00" * n)
                continue
            # Envelope suave (evita "cliques" no início e no fim de cada nota)
            fade = max(1, int(n * 0.08))
            for i in range(n):
                if i < fade:
                    env = i / fade
                elif i > n - fade:
                    env = (n - i) / fade
                else:
                    env = 1.0
                val = int(amp_max * env * math.sin(2 * math.pi * freq * i / taxa))
                frames.extend(struct.pack("<h", val))
        w.writeframes(bytes(frames))
    return buf.getvalue()


class Som:
    """
    Identidade sonora do Duelo de Conhecimento.
    Usa pygame.mixer para reprodução assíncrona e sem fila de efeitos.
    """

    NOTAS = {
        "A3": 220.00, "C4": 261.63, "D4": 293.66,
        "E4": 329.63, "G4": 392.00, "A4": 440.00,
        "C5": 523.25, "D5": 587.33, "E5": 659.25,
        "G5": 783.99, "A5": 880.00, "C6": 1046.50,
    }

    def __init__(self, ativo=True):
        self.ativo = bool(ativo)
        self.disponivel = False
        self._pygame = None
        self._canal = None
        self._cache = {}
        self._ultimo_tick = None

        try:
            import pygame

            pygame.mixer.init(
                frequency=22050,
                size=-16,
                channels=1,
                buffer=512
            )

            pygame.mixer.set_num_channels(4)
            self._pygame = pygame
            self._canal = pygame.mixer.Channel(0)
            self.disponivel = True

            print("[SOM] Sistema de áudio inicializado.")

        except Exception as e:
            print(f"[SOM] Não foi possível inicializar pygame.mixer: {e}")
            self.ativo = False

    def _wav(self, notas):
        """Cria e armazena em cache um efeito WAV."""
        chave = tuple(notas)

        if chave not in self._cache:
            notas_resolvidas = []

            for nota, duracao in notas:
                freq = self.NOTAS.get(nota, 0) if isinstance(nota, str) else nota
                notas_resolvidas.append((freq, duracao))

            dados = _gerar_wav(notas_resolvidas, volume=0.42)
            self._cache[chave] = self._pygame.mixer.Sound(
                file=io.BytesIO(dados)
            )

        return self._cache[chave]

    def tocar_ja(self, *notas):
        """
        Compatibilidade com a interface anterior.
        Aceita chamadas como tocar_ja(("C5", 80), ("E5", 110)).
        """
        if not self.ativo or not self.disponivel:
            return

        try:
            som = self._wav(list(notas))
            self._canal.stop()
            self._canal.play(som)
        except Exception as e:
            print(f"[SOM] Erro em tocar_ja: {e}")

    def tocar(self, *notas):
        """Compatibilidade: efeito de baixa prioridade."""
        if not self.ativo or not self.disponivel:
            return

        try:
            som = self._wav(list(notas))
            if not self._canal.get_busy():
                self._canal.play(som)
        except Exception as e:
            print(f"[SOM] Erro em tocar: {e}")

    def parar(self):
        """Encerra a reprodução e libera o mixer."""
        try:
            if self.disponivel:
                self._canal.stop()
                self._pygame.mixer.quit()
                self.disponivel = False
        except Exception as e:
            print(f"[SOM] Erro ao encerrar: {e}")

    # ---------- Sons específicos do jogo ----------

    def nova_pergunta(self):
        self.tocar_ja(("E5", 90), ("G5", 90), ("C6", 140))

    def apertou(self, quem):
        if quem == "A":
            self.tocar_ja(("A4", 90), ("C5", 110))
        else:
            self.tocar_ja(("G4", 90), ("D5", 110))

    def revelou(self):
        self.tocar_ja(("C5", 80), ("E5", 80), ("G5", 130))

    def acertou(self):
        self.tocar_ja(("C5", 90), ("E5", 90), ("G5", 90), ("C6", 220))

    def tempo_esgotado(self):
        self.tocar_ja(("E4", 200), ("C4", 220), ("A3", 320))

    def tick(self, segundos, fase):
        if segundos <= 0:
            return
        if fase == FASE_AGUARDANDO:
            if segundos <= 3:
                self.tocar((880, 45))
            elif segundos <= 10 and segundos % 3 == 0:
                self.tocar((587, 35))
        elif fase == FASE_RESPONDENDO:
            if segundos <= 3:
                self.tocar((988, 55))
            elif segundos <= 8:
                self.tocar((740, 40))
