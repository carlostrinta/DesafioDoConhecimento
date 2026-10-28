"""
Áudio do Duelo de Conhecimento: arquivos externos em `sons/` + efeitos
sintetizados de fallback, tocados via pygame.mixer.

Módulo independente de tkinter e de serial. O `pygame` é opcional: sem ele (ou
sem placa de som) `Som` fica inativo (`ativo=False`, `disponivel=False`) e
todas as chamadas viram no-op — o jogo continua, apenas sem som.

A pasta `sons/` fica ao lado do executável (rodando pelo fonte, na pasta do
projeto). Para cada evento, o app procura o nome-base de `ARQUIVOS_SOM` com
`.wav` e depois com `.ogg`; se o arquivo não existir ou estiver corrompido,
usa o efeito sintetizado equivalente e registra um único WARNING por arquivo.
Os bytes dos efeitos sintetizados continuam idênticos aos da v2.2 (ver
tests/test_audio.py).
"""

from __future__ import annotations

import io
import logging
import math
import os
import struct
import wave

from jogo import FASE_AGUARDANDO, FASE_RESPONDENDO
from recursos import obter_diretorio_base

log = logging.getLogger("desafio.audio")

PASTA_SONS = "sons"
EXTENSOES_SOM = (".wav", ".ogg")

# Nome-base de cada evento. A extensão (.wav ou .ogg) é resolvida em
# `_localizar_arquivo`; WAV tem preferência quando os dois existem.
ARQUIVOS_SOM = {
    "nova_pergunta": "nova_pergunta",
    "botao_a": "botao_a",
    "botao_b": "botao_b",
    "botao_c": "botao_c",
    "botao_d": "botao_d",
    "revelou": "revelar",
    "acertou": "acerto",
    "tempo_esgotado": "tempo_esgotado",
    "tick": "tick",
    "tick_final": "tick_final",
    "vitoria": "vitoria",
    "troca_tema": "troca_tema",
}

# Sons de botão têm de ser curtos (< 1 s); as notas de fallback preservam a
# identidade sonora antiga para A/B e completam C/D com timbres distintos.
NOTAS_APERTOU = {
    "A": (("A4", 90), ("C5", 110)),
    "B": (("G4", 90), ("D5", 110)),
    "C": (("E4", 90), ("A4", 110)),
    "D": (("D4", 90), ("G4", 110)),
}


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


def _normalizar_volume(valor):
    """Volume de reprodução em 0.0..1.0; valor inválido vira 1.0."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(numero):
        return 1.0
    return max(0.0, min(1.0, numero))


class Som:
    """
    Identidade sonora do Duelo de Conhecimento.

    Usa pygame.mixer para reprodução assíncrona e sem fila de efeitos. A
    tabela `ARQUIVOS_SOM` mapeia cada evento para um arquivo em `sons/`; o
    fallback sintetizado usa as mesmas notas da v2.2.
    """

    NOTAS = {
        "A3": 220.00, "C4": 261.63, "D4": 293.66,
        "E4": 329.63, "G4": 392.00, "A4": 440.00,
        "C5": 523.25, "D5": 587.33, "E5": 659.25,
        "G5": 783.99, "A5": 880.00, "C6": 1046.50,
    }

    def __init__(self, ativo=True, volume=1.0, diretorio_sons=None):
        self.ativo = bool(ativo)
        self.disponivel = False
        self.volume = _normalizar_volume(volume)
        self._pygame = None
        self._canal = None
        self._cache = {}
        self._cache_arquivos = {}
        self._avisos_emitidos = set()
        self._ultimo_tick = None
        self._pasta_sons = (
            os.path.abspath(diretorio_sons)
            if diretorio_sons
            else os.path.join(obter_diretorio_base(), PASTA_SONS)
        )

        try:
            # O pygame imprime um banner ao importar; sem --debug o app deve
            # ficar silencioso no console.
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame

            # Buffer pequeno = menos latência no botão. `pre_init` precisa vir
            # antes de `init`; `set_num_channels` continua igual.
            pygame.mixer.pre_init(
                frequency=22050,
                size=-16,
                channels=1,
                buffer=256,
            )
            pygame.mixer.init()
            pygame.mixer.set_num_channels(4)

            self._pygame = pygame
            self._canal = pygame.mixer.Channel(0)
            self.disponivel = True

            log.info(
                "[SOM] Sistema de áudio inicializado (pasta de sons: %s).",
                self._pasta_sons,
            )

        except Exception as e:
            log.warning("[SOM] Não foi possível inicializar pygame.mixer: %s", e)
            self.ativo = False

    # -----------------------------------------------------
    # Carregamento e volume
    # -----------------------------------------------------
    def _aplicar_volume(self, som):
        """Aplica o volume configurado a um Sound, sem alterar os bytes WAV."""
        ajustar = getattr(som, "set_volume", None)
        if not ajustar:
            return
        try:
            ajustar(self.volume)
        except Exception as e:
            log.warning("[SOM] Não foi possível ajustar o volume: %s", e)

    def _wav(self, notas):
        """Cria e armazena em cache um efeito WAV sintetizado."""
        chave = tuple(notas)

        if chave not in self._cache:
            notas_resolvidas = []

            for nota, duracao in notas:
                freq = self.NOTAS.get(nota, 0) if isinstance(nota, str) else nota
                notas_resolvidas.append((freq, duracao))

            dados = _gerar_wav(notas_resolvidas, volume=0.42)
            som = self._pygame.mixer.Sound(file=io.BytesIO(dados))
            self._aplicar_volume(som)
            self._cache[chave] = som

        return self._cache[chave]

    def _localizar_arquivo(self, nome_base):
        """Caminho do primeiro arquivo existente (.wav ou .ogg), ou None."""
        for extensao in EXTENSOES_SOM:
            caminho = os.path.join(self._pasta_sons, nome_base + extensao)
            if os.path.isfile(caminho):
                return caminho
        return None

    def _avisar_uma_vez(self, chave, mensagem):
        if chave in self._avisos_emitidos:
            return
        self._avisos_emitidos.add(chave)
        log.warning("[SOM] %s", mensagem)

    def _som_externo(self, evento):
        """
        Sound do arquivo do evento, ou None para usar o sintetizado.

        Arquivo ausente, sem permissão ou inválido nunca levanta exceção: fica
        um WARNING (uma vez por arquivo) e o evento cai no fallback.
        """
        if evento in self._cache_arquivos:
            return self._cache_arquivos[evento]

        nome_base = ARQUIVOS_SOM.get(evento)
        if not nome_base:
            self._cache_arquivos[evento] = None
            return None

        caminho = self._localizar_arquivo(nome_base)
        if not caminho:
            self._avisar_uma_vez(
                nome_base,
                f"Arquivo {nome_base}.wav/.ogg não encontrado em "
                f"{self._pasta_sons}; usando o som sintetizado.",
            )
            self._cache_arquivos[evento] = None
            return None

        try:
            som = self._pygame.mixer.Sound(file=caminho)
            self._aplicar_volume(som)
            self._cache_arquivos[evento] = som
            log.info("[SOM] Usando arquivo externo: %s", caminho)
            return som
        except Exception as e:
            self._avisar_uma_vez(
                nome_base,
                f"Arquivo de som inválido/corrompido {caminho}: {e}; "
                "usando o som sintetizado.",
            )
            self._cache_arquivos[evento] = None
            return None

    # -----------------------------------------------------
    # Reprodução
    # -----------------------------------------------------
    def _tocar_evento(self, evento, notas, *, interromper=True):
        if not self.ativo or not self.disponivel:
            return

        try:
            if not interromper and self._canal.get_busy():
                return

            som = self._som_externo(evento)
            if som is None:
                som = self._wav(list(notas))

            if interromper:
                self._canal.stop()
            self._canal.play(som)
        except Exception as e:
            log.warning("[SOM] Erro ao tocar o evento %s: %s", evento, e)

    def tocar_ja(self, *notas):
        """
        Compatibilidade com a interface anterior: efeito sintetizado de alta
        prioridade. Aceita chamadas como tocar_ja(("C5", 80), ("E5", 110)).
        """
        if not self.ativo or not self.disponivel:
            return

        try:
            som = self._wav(list(notas))
            self._canal.stop()
            self._canal.play(som)
        except Exception as e:
            log.warning("[SOM] Erro em tocar_ja: %s", e)

    def tocar(self, *notas):
        """Compatibilidade: efeito sintetizado de baixa prioridade."""
        if not self.ativo or not self.disponivel:
            return

        try:
            som = self._wav(list(notas))
            if not self._canal.get_busy():
                self._canal.play(som)
        except Exception as e:
            log.warning("[SOM] Erro em tocar: %s", e)

    def parar(self):
        """Encerra a reprodução e libera o mixer."""
        try:
            if self.disponivel:
                self._canal.stop()
                self._pygame.mixer.quit()
                self.disponivel = False
        except Exception as e:
            log.warning("[SOM] Erro ao encerrar: %s", e)

    # ---------- Sons específicos do jogo ----------

    def nova_pergunta(self):
        self._tocar_evento(
            "nova_pergunta", (("E5", 90), ("G5", 90), ("C6", 140))
        )

    def apertou(self, quem):
        notas = NOTAS_APERTOU.get(quem)
        if notas is None:
            return
        self._tocar_evento(f"botao_{quem.lower()}", notas)

    def revelou(self):
        self._tocar_evento(
            "revelou", (("C5", 80), ("E5", 80), ("G5", 130))
        )

    def acertou(self):
        self._tocar_evento(
            "acertou", (("C5", 90), ("E5", 90), ("G5", 90), ("C6", 220))
        )

    def tempo_esgotado(self):
        self._tocar_evento(
            "tempo_esgotado", (("E4", 200), ("C4", 220), ("A3", 320))
        )

    def tick(self, segundos, fase):
        if segundos <= 0:
            return
        if fase == FASE_AGUARDANDO:
            if segundos <= 3:
                self._tocar_evento(
                    "tick_final", ((880, 45),), interromper=False
                )
            elif segundos <= 10 and segundos % 3 == 0:
                self._tocar_evento("tick", ((587, 35),), interromper=False)
        elif fase == FASE_RESPONDENDO:
            if segundos <= 3:
                self._tocar_evento(
                    "tick_final", ((988, 55),), interromper=False
                )
            elif segundos <= 8:
                self._tocar_evento("tick", ((740, 40),), interromper=False)

    def vitoria(self):
        """Som de vitória/fim de partida (a tela de campeão é da Etapa 5)."""
        self._tocar_evento(
            "vitoria", (("C5", 120), ("E5", 120), ("G5", 120), ("C6", 320))
        )

    def fim_partida(self):
        """Alias explícito para `vitoria()`."""
        self.vitoria()

    def troca_tema(self):
        self._tocar_evento(
            "troca_tema", (("G4", 80), ("C5", 100), ("E5", 150))
        )
