"""
Duelo de Conhecimento — Aplicação Windows
Versão 2.1 — interface de palco + máquina de estados + serial robusta + áudio

Requisitos: Python 3.9+, pyserial  (pip install pyserial)
Protocolo serial: IDÊNTICO ao da v1.1 (o firmware do Arduino não muda).

Atalhos de teclado (modo simulação, funcionam junto com o Arduino):
    A / B      apertar o botão do competidor
    R          revelar resposta
    1 / 2      acerto do A / acerto do B
    N          próxima pergunta
    S          ligar/desligar som
    F11        tela cheia  (Esc sai)
    Ctrl+R     zerar o placar
"""

import json
import math
import os
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import font as tkfont, messagebox, filedialog

from config import (
    ARQUIVO_PERGUNTAS,
    BAUD_RATE,
    NOMES_EQUIPES,
    NUM_EQUIPES,
    PONTUAR_APOS_TEMPO,
    PORTA_FORCADA,
    TEMPO_PERGUNTA,
    TEMPO_RESPOSTA,
    TITULO,
)
from jogo import (
    Jogo,
    FASE_AGUARDANDO,
    FASE_RESPONDENDO,
    FASE_REVELADA,
    FASE_PONTUADA,
    MOTIVO_ACERTO_FASE,
    MOTIVO_ACERTO_OUTRA_EQUIPE,
    MOTIVO_ACERTO_SEM_QUEM,
    MOTIVO_ACERTO_TEMPO,
    MOTIVO_AVANCAR,
    MOTIVO_REVELAR_AGUARDANDO,
    PREFIXO_RECUSA,
    TIMER_MOTIVO_REVELADA,
)
from perguntas import (
    formatar_nome_tema,
    inspecionar_arquivo_perguntas,
    ler_banco_perguntas,
    listar_arquivos_perguntas,
)
from protocolo import comandos_para_arduino, mapear_evento_arduino

try:
    import serial
    import serial.tools.list_ports
    SERIAL_DISPONIVEL = True
except ImportError:
    SERIAL_DISPONIVEL = False
    print("AVISO: pyserial não instalado. Modo teclado ativo.")

import io
import struct
import wave

# =========================================================
# CONFIGURAÇÕES
# Os valores (título, equipes, tempos, serial) ficam em config.py.
# Este módulo ainda NÃO lê config.json — isso entra na Etapa 4.2.
# =========================================================
NOME_A = NOMES_EQUIPES["A"]
NOME_B = NOMES_EQUIPES["B"]


# =========================================================
# PALETA
# =========================================================
class Cor:
    FUNDO = "#0A0F1F"
    PAINEL = "#121A33"
    BORDA = "#2A3560"
    TEXTO = "#EAF0FF"
    SUAVE = "#8F9BC4"
    APAGADO = "#56628F"
    A = "#3BA3FF"
    B = "#FF8F3F"
    CERTO = "#2BD99F"
    ERRO = "#FF5470"
    AVISO = "#FFD166"
    APOIO = "#B9A8FF"


# =========================================================
# TIPOGRAFIA (tudo é desenhado em Canvas e escala com a janela)
# =========================================================
ESCALA = 1.0
FAMILIAS = {"display": "Segoe UI", "corpo": "Segoe UI"}
FONTE_DEF = {
    "titulo":   ("display", 24, "bold"),
    "nome":     ("display", 20, "bold"),
    "placar":   ("display", 110, "bold"),
    "pequena":  ("corpo", 13, "normal"),
    "pergunta": ("corpo", 30, "bold"),
    "alt":      ("corpo", 21, "normal"),
    "letra":    ("display", 20, "bold"),
    "tempo":    ("display", 30, "bold"),
    "status":   ("corpo", 20, "bold"),
    "passo":    ("corpo", 12, "bold"),
    "explic":   ("corpo", 16, "normal"),
}


def F(nome, mult=1.0):
    familia, tam, peso = FONTE_DEF[nome]
    return (FAMILIAS[familia], max(7, int(tam * ESCALA * mult)), peso)


def escolher_fonte(candidatas, padrao="Segoe UI"):
    disponiveis = set(tkfont.families())
    for f in candidatas:
        if f in disponiveis:
            return f
    return padrao


# =========================================================
# FUNÇÕES AUXILIARES DE DESENHO
# =========================================================
def misturar(c1, c2, t):
    """Mistura duas cores hex. t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def retangulo_arredondado(cv, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
           x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
           x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def texto_ajustado(cv, x, y, largura, altura, texto, nome_fonte, minimo=10, **kw):
    """Desenha texto quebrado em linhas e reduz a fonte até caber na altura."""
    familia, tam, peso = F(nome_fonte)
    while True:
        item = cv.create_text(x, y, text=texto, width=max(1, int(largura)),
                              font=(familia, tam, peso), **kw)
        bb = cv.bbox(item)
        if bb is None or (bb[3] - bb[1]) <= altura or tam <= minimo:
            return item
        cv.delete(item)
        tam = max(minimo, tam - 2)


def obter_diretorio_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def caminho_recurso(nome):
    return os.path.join(obter_diretorio_base(), nome)


def obter_icone_tema(titulo, nome_arquivo):
    """Retorna um emoji representativo para a tecnologia ou tema."""
    t = (str(titulo) + " " + str(nome_arquivo)).lower()
    if "eletro" in t or "eletric" in t:
        return "⚡"
    if "radio" in t or "raio" in t or "nuclear" in t:
        return "🩻"
    if "geral" in t or "gerais" in t or "pergunta" in t:
        return "🌐"
    if "ti" in t or "comput" in t or "software" in t or "program" in t or "infor" in t:
        return "💻"
    if "mecan" in t or "motor" in t:
        return "⚙️"
    if "saude" in t or "enferm" in t or "medic" in t:
        return "🩺"
    if "quimic" in t:
        return "🧪"
    if "fisic" in t:
        return "🔬"
    if "matemat" in t:
        return "📐"
    if "hist" in t or "geogr" in t:
        return "🌍"
    return "📚"


# =========================================================
# COMPONENTES VISUAIS
# =========================================================
class Tela(tk.Canvas):
    """Canvas que se redesenha sozinho quando muda de tamanho."""

    def __init__(self, master, **kw):
        kw.setdefault("width", 10)
        kw.setdefault("height", 10)
        super().__init__(master, bg=Cor.FUNDO, highlightthickness=0, bd=0, **kw)
        self.bind("<Configure>", lambda e: self.desenhar())

    def desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 8 and h > 8:
            self.pintar(w, h)

    def pintar(self, w, h):
        pass


class Cartao(Tela):
    def __init__(self, master, raio=20, **kw):
        super().__init__(master, **kw)
        self.raio = raio
        self.fill = Cor.PAINEL
        self.borda = Cor.BORDA
        self.espessura = 2

    def pintar(self, w, h):
        e = self.espessura
        retangulo_arredondado(self, e, e, w - e, h - e, self.raio * min(ESCALA, 1.5),
                              fill=self.fill, outline=self.borda, width=e)
        self.conteudo(w, h)

    def conteudo(self, w, h):
        pass


class BarraTopo(Tela):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.conexao = None
        self.tema = ""

    def pintar(self, w, h):
        cy = h / 2
        s = h * 0.46
        x = 6
        retangulo_arredondado(self, x, cy - s * 0.62, x + s, cy + s * 0.38, s * 0.28,
                              fill=Cor.A, outline=Cor.FUNDO, width=3)
        retangulo_arredondado(self, x + s * 0.55, cy - s * 0.38, x + s * 1.55, cy + s * 0.62,
                              s * 0.28, fill=Cor.B, outline=Cor.FUNDO, width=3)

        texto_titulo = TITULO
        if self.tema:
            texto_titulo += f"  •  {self.tema}"
        self.create_text(x + s * 1.55 + 18, cy, text=texto_titulo, anchor="w",
                         fill=Cor.TEXTO, font=F("titulo"))

        if not SERIAL_DISPONIVEL:
            txt, cor = "pyserial não instalado. Modo teclado ativo.", Cor.AVISO
        elif self.conexao:
            txt, cor = f"Arduino conectado ({self.conexao})", Cor.CERTO
        else:
            txt, cor = "Arduino não conectado. Modo teclado ativo.", Cor.AVISO
        item = self.create_text(w - 6, cy - h * 0.16, text=txt, anchor="e",
                                fill=Cor.SUAVE, font=F("pequena"))
        bb = self.bbox(item)
        r = 5 * min(ESCALA, 1.5)
        self.create_oval(bb[0] - 14 - r, (bb[1] + bb[3]) / 2 - r,
                         bb[0] - 14 + r, (bb[1] + bb[3]) / 2 + r, fill=cor, outline="")
        self.create_text(w - 6, cy + h * 0.2, anchor="e", fill=Cor.APAGADO, font=F("pequena", 0.9),
                         text="F11 tela cheia   Ctrl+R zerar   Ctrl+T temas   S som on/off")


class CartaoPlacar(Cartao):
    def __init__(self, master, nome, cor, **kw):
        super().__init__(master, **kw)
        self.nome = nome
        self.cor = cor
        self.pontos = 0
        self.ativo = False
        self.brilho = True
        self.rotulo = ""

    def pintar(self, w, h):
        if self.ativo:
            self.fill = misturar(Cor.PAINEL, self.cor, 0.22 if self.brilho else 0.12)
            self.borda = self.cor
            self.espessura = 4
        else:
            self.fill, self.borda, self.espessura = Cor.PAINEL, Cor.BORDA, 2
        super().pintar(w, h)

    def conteudo(self, w, h):
        cx = w / 2
        self.create_text(cx, h * 0.12, text=self.nome, fill=self.cor, font=F("nome"))
        texto_ajustado(self, cx, h * 0.38, w - 30, h * 0.30, str(self.pontos), "placar",
                       anchor="center", justify="center", fill=Cor.TEXTO)
        self.create_text(cx, h * 0.60, text="ponto" if self.pontos == 1 else "pontos",
                         fill=Cor.SUAVE, font=F("pequena"))

        # "Lâmpada" que espelha o LED físico do competidor
        r = min(w, h) * 0.11
        cy = h * 0.78
        if self.ativo:
            if self.brilho:
                for mult, t in ((2.3, 0.12), (1.7, 0.25)):
                    self.create_oval(cx - r * mult, cy - r * mult, cx + r * mult, cy + r * mult,
                                     fill=misturar(self.fill, self.cor, t), outline="")
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.cor, outline="")
        else:
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             fill=misturar(Cor.PAINEL, self.cor, 0.22),
                             outline=misturar(Cor.PAINEL, self.cor, 0.4), width=2)
        self.create_text(cx, h * 0.93, text=self.rotulo,
                         fill=self.cor if self.ativo else Cor.SUAVE, font=F("pequena"))


class CartaoPergunta(Cartao):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.categoria = ""
        self.texto = ""
        self.numero = 0

    def conteudo(self, w, h):
        pad = max(18, w * 0.04)
        y = h * 0.15
        if self.categoria:
            r = 5 * min(ESCALA, 1.5)
            self.create_oval(pad - r, y - r, pad + r, y + r, fill=Cor.APOIO, outline="")
            self.create_text(pad + r + 10, y, text=self.categoria, anchor="w",
                             fill=Cor.SUAVE, font=F("pequena"))
        if self.numero:
            self.create_text(w - pad, y, text=f"Pergunta {self.numero}", anchor="e",
                             fill=Cor.SUAVE, font=F("pequena"))
        txt = self.texto if self.texto else "Aguardando seleção do tema de perguntas..."
        texto_ajustado(self, pad, h * 0.58, w - 2 * pad, h * 0.62, txt, "pergunta",
                       anchor="w", justify="left", fill=Cor.TEXTO)


class CartaoAlt(Cartao):
    def __init__(self, master, **kw):
        super().__init__(master, raio=16, **kw)
        self.letra = ""
        self.texto = ""
        self.estado = "normal"

    def definir(self, letra, texto, estado):
        self.letra, self.texto, self.estado = letra, texto, estado
        if estado == "correta":
            self.fill, self.borda, self.espessura = misturar(Cor.PAINEL, Cor.CERTO, 0.18), Cor.CERTO, 3
        elif estado == "apagada":
            self.fill, self.borda, self.espessura = "#0D1326", "#1A2342", 2
        else:
            self.fill, self.borda, self.espessura = Cor.PAINEL, Cor.BORDA, 2

    def conteudo(self, w, h):
        pad = max(14, h * 0.25)
        d = min(h * 0.62, 56 * ESCALA)
        bx, cy = pad + d / 2, h / 2
        if self.estado == "correta":
            fill_b, cor_l, simbolo, cor_t = Cor.CERTO, Cor.FUNDO, "✓", Cor.TEXTO
        elif self.estado == "apagada":
            fill_b, cor_l, simbolo, cor_t = "#151D3A", Cor.APAGADO, self.letra, Cor.APAGADO
        else:
            fill_b, cor_l, simbolo, cor_t = misturar(Cor.PAINEL, Cor.APOIO, 0.28), Cor.APOIO, self.letra, Cor.TEXTO
        self.create_oval(bx - d / 2, cy - d / 2, bx + d / 2, cy + d / 2, fill=fill_b, outline="")
        self.create_text(bx, cy, text=simbolo, fill=cor_l, font=F("letra"))
        x_txt = bx + d / 2 + 18
        texto_ajustado(self, x_txt, cy, w - x_txt - pad, h * 0.82, self.texto, "alt",
                       anchor="w", justify="left", fill=cor_t)


class CartaoExplicacao(Cartao):
    def __init__(self, master, **kw):
        super().__init__(master, raio=16, **kw)
        self.texto = ""
        self.borda = Cor.APOIO

    def pintar(self, w, h):
        if self.texto:
            super().pintar(w, h)

    def conteudo(self, w, h):
        pad = max(14, h * 0.2)
        r = min(h * 0.22, 15 * ESCALA)
        cx = pad + r
        self.create_oval(cx - r, h / 2 - r, cx + r, h / 2 + r, fill=Cor.APOIO, outline="")
        self.create_text(cx, h / 2, text="i", fill=Cor.FUNDO, font=F("passo"))
        x_txt = cx + r + 16
        texto_ajustado(self, x_txt, h / 2, w - x_txt - pad, h * 0.8, self.texto, "explic",
                       anchor="w", justify="left", fill="#CBD5F5")


class BarraTempo(Tela):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.rotulo = ""
        self.frac = 1.0
        self.segundos = TEMPO_PERGUNTA
        self.cor = Cor.APOIO

    def pintar(self, w, h):
        cy = h / 2
        esp = max(10, h * 0.28)
        x1 = w * 0.31 + esp / 2
        x2 = w * 0.84 - esp / 2
        self.create_text(4, cy, text=self.rotulo, anchor="w", fill=Cor.SUAVE, font=F("pequena"))
        self.create_line(x1, cy, x2, cy, width=esp, capstyle="round", fill="#18213F")
        if self.frac > 0.001:
            self.create_line(x1, cy, x1 + (x2 - x1) * self.frac, cy, width=esp,
                             capstyle="round", fill=self.cor)
        self.create_text(w - 4, cy, text=f"{self.segundos}s", anchor="e",
                         fill=self.cor, font=F("tempo"))


class Rodape(Cartao):
    PASSOS = ["Aguardando", "Respondendo", "Revelada", "Pontuada"]

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.msg = ""
        self.cor_msg = Cor.TEXTO
        self.passo = 0

    def conteudo(self, w, h):
        pad = max(18, w * 0.017)
        texto_ajustado(self, pad, h / 2, w * 0.45 - pad, h * 0.8, self.msg, "status",
                       anchor="w", justify="left", fill=self.cor_msg)
        x1, x2 = w * 0.47, w - pad
        gap = 8
        n = len(self.PASSOS)
        pw = (x2 - x1 - gap * (n - 1)) / n
        ph = h * 0.46
        py = h / 2 - ph / 2
        for i, nome in enumerate(self.PASSOS):
            xa = x1 + i * (pw + gap)
            if i < self.passo:
                fill, outline, cor_t = misturar(Cor.PAINEL, Cor.APOIO, 0.18), "", Cor.APOIO
            elif i == self.passo:
                fill, outline, cor_t = Cor.APOIO, "", Cor.FUNDO
            else:
                fill, outline, cor_t = "", Cor.BORDA, Cor.APAGADO
            retangulo_arredondado(self, xa, py, xa + pw, py + ph, ph / 2,
                                  fill=fill, outline=outline, width=2)
            self.create_text(xa + pw / 2, h / 2, text=nome, fill=cor_t, font=F("passo"))


# =========================================================
# FASES DA RODADA (definidas em jogo.py — fonte única)
# =========================================================
# Mensagens das recusas do Jogo. A regra mora no Jogo; aqui só o texto.
MENSAGENS_RECUSA = {
    MOTIVO_AVANCAR: "Resolva a pergunta atual (revele ou pontue) antes de avançar.",
    MOTIVO_REVELAR_AGUARDANDO: "Ninguém apertou ainda. REVELAR só funciona depois que A ou B apertar.",
    MOTIVO_ACERTO_FASE: "Revele a resposta (botão REVELAR) antes de pontuar.",
    MOTIVO_ACERTO_SEM_QUEM: "Ninguém apertou nesta rodada: não há ponto para dar.",
    MOTIVO_ACERTO_OUTRA_EQUIPE: "Só quem apertou pode pontuar (apertou: {equipe}).",
    MOTIVO_ACERTO_TEMPO: "O tempo de resposta esgotou: sem ponto nesta rodada.",
}


def mensagem_ignoradas(quantidade, nome_arquivo):
    """
    Texto do aviso de perguntas descartadas na carga.
    Devolve None quando nada foi ignorado.
    """
    if quantidade <= 0:
        return None
    substantivo = "pergunta ignorada" if quantidade == 1 else "perguntas ignoradas"
    return f"{quantidade} {substantivo} em {nome_arquivo}."


# =========================================================
# ÁUDIO — gera WAV em memória e reproduz via placa de som normal
# (winsound.Beep usa o PC Speaker, que notebooks modernos não têm)
# =========================================================
import io
import struct
import wave


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




class ModalSelecaoPerguntas(tk.Toplevel):
    """
    Janela modal para escolha do arquivo de perguntas (tema / tecnologia) na inicialização
    ou durante a execução do jogo.
    """
    def __init__(self, parent, lista_arquivos, arquivo_atual=None, ao_confirmar=None, permitir_cancelar=True, inicial=False):
        super().__init__(parent)
        self.parent = parent
        self.lista_arquivos = list(lista_arquivos)
        self.arquivo_selecionado = arquivo_atual
        self.ao_confirmar = ao_confirmar
        self.permitir_cancelar = permitir_cancelar
        self.inicial = inicial

        self.title("Duelo de Conhecimento — Escolha de Tema")
        self.configure(bg=Cor.FUNDO)
        self.resizable(False, False)

        ico_path = caminho_recurso("desafio.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        if not self.arquivo_selecionado and self.lista_arquivos:
            self.arquivo_selecionado = self.lista_arquivos[0]

        self.cards_widgets = []
        self._construir_ui()
        self._centralizar(700, 540)

        self.bind("<Return>", lambda e: self._confirmar())
        self.bind("<KP_Enter>", lambda e: self._confirmar())
        self.bind("<Up>", lambda e: self._mover_selecao(-1))
        self.bind("<Down>", lambda e: self._mover_selecao(1))
        if self.permitir_cancelar:
            self.bind("<Escape>", lambda e: self._cancelar())

        self.grab_set()
        self.focus_force()

    def _centralizar(self, w, h):
        self.update_idletasks()
        try:
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            if pw > 100 and ph > 100:
                x = px + (pw - w) // 2
                y = py + (ph - h) // 2
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = (sw - w) // 2
                y = (sh - h) // 2
        except Exception:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _construir_ui(self):
        # 1. Topo / Cabeçalho
        topo = tk.Frame(self, bg=Cor.PAINEL, padx=24, pady=16)
        topo.pack(side="top", fill="x")

        tk.Label(
            topo,
            text="🎯  ESCOLHA A TECNOLOGIA OU TEMA",
            font=("Segoe UI", 15, "bold"),
            fg=Cor.TEXTO,
            bg=Cor.PAINEL,
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            topo,
            text="Selecione o arquivo de perguntas (.json) para iniciar o duelo:",
            font=("Segoe UI", 10),
            fg=Cor.SUAVE,
            bg=Cor.PAINEL,
            anchor="w"
        ).pack(fill="x", pady=(4, 0))

        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        # 2. Área Central com Canvas e Scrollbar
        meio = tk.Frame(self, bg=Cor.FUNDO, padx=16, pady=14)
        meio.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(meio, bg=Cor.FUNDO, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(meio, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.container_cards = tk.Frame(self.canvas, bg=Cor.FUNDO)
        self.janela_canvas = self.canvas.create_window((0, 0), window=self.container_cards, anchor="nw")

        self.container_cards.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.janela_canvas, width=e.width)
        )

        def _rolar(event):
            if event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                self.canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                self.canvas.yview_scroll(1, "units")

        self.canvas.bind_all("<MouseWheel>", _rolar)

        self._reconstruir_cards()

        # 3. Rodapé com Botões de Ação
        tk.Frame(self, bg=Cor.BORDA, height=2).pack(fill="x")

        rodape = tk.Frame(self, bg=Cor.PAINEL, padx=20, pady=14)
        rodape.pack(side="bottom", fill="x")

        btn_procurar = tk.Button(
            rodape,
            text="📁 Procurar outro (.json)...",
            font=("Segoe UI", 9, "bold"),
            bg="#182244",
            fg=Cor.TEXTO,
            activebackground="#253568",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._procurar_arquivo
        )
        btn_procurar.pack(side="left", padx=(0, 8))

        btn_atualizar = tk.Button(
            rodape,
            text="🔄 Atualizar",
            font=("Segoe UI", 9),
            bg="#182244",
            fg=Cor.SUAVE,
            activebackground="#253568",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._atualizar_lista
        )
        btn_atualizar.pack(side="left")

        btn_iniciar = tk.Button(
            rodape,
            text="▶  Iniciar Desafio",
            font=("Segoe UI", 11, "bold"),
            bg=Cor.A,
            fg=Cor.FUNDO,
            activebackground="#5CB7FF",
            activeforeground=Cor.FUNDO,
            relief="flat",
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._confirmar
        )
        btn_iniciar.pack(side="right", padx=(8, 0))

        if self.permitir_cancelar:
            btn_cancelar = tk.Button(
                rodape,
                text="Cancelar",
                font=("Segoe UI", 9),
                bg="#231A26",
                fg=Cor.ERRO,
                activebackground="#3D1D28",
                activeforeground="#FF8599",
                relief="flat",
                bd=0,
                padx=14,
                pady=8,
                cursor="hand2",
                command=self._cancelar
            )
            btn_cancelar.pack(side="right")

    def _reconstruir_cards(self):
        for w in self.container_cards.winfo_children():
            w.destroy()
        self.cards_widgets = []

        if not self.lista_arquivos:
            vazio = tk.Frame(self.container_cards, bg=Cor.PAINEL, padx=20, pady=24, highlightthickness=1, highlightbackground=Cor.BORDA)
            vazio.pack(fill="x", pady=10)
            tk.Label(
                vazio,
                text="⚠️  Nenhum arquivo de perguntas (.json) válido encontrado.",
                font=("Segoe UI", 11, "bold"),
                fg=Cor.AVISO,
                bg=Cor.PAINEL
            ).pack(anchor="w")
            tk.Label(
                vazio,
                text="Coloque arquivos .json na pasta da aplicação (ex: eletrotecnica.json, radiologia.json)\nou use o botão 'Procurar outro (.json)...' abaixo.",
                font=("Segoe UI", 9),
                fg=Cor.SUAVE,
                bg=Cor.PAINEL,
                justify="left"
            ).pack(anchor="w", pady=(6, 0))
            return

        for idx, info in enumerate(self.lista_arquivos):
            selecionado = (
                self.arquivo_selecionado is not None and
                self.arquivo_selecionado.get("caminho") == info["caminho"]
            )

            cor_bg = "#1B2A54" if selecionado else Cor.PAINEL
            cor_borda = Cor.A if selecionado else Cor.BORDA
            esp_borda = 2 if selecionado else 1

            card = tk.Frame(
                self.container_cards,
                bg=cor_bg,
                highlightthickness=esp_borda,
                highlightbackground=cor_borda,
                padx=16,
                pady=10,
                cursor="hand2"
            )
            card.pack(fill="x", pady=4)

            icone = obter_icone_tema(info["titulo"], info["arquivo"])
            lbl_ico = tk.Label(
                card,
                text=icone,
                font=("Segoe UI Emoji", 20),
                fg=Cor.TEXTO,
                bg=cor_bg
            )
            lbl_ico.pack(side="left", padx=(0, 14))

            col = tk.Frame(card, bg=cor_bg)
            col.pack(side="left", fill="both", expand=True)

            lbl_tit = tk.Label(
                col,
                text=info["titulo"],
                font=("Segoe UI", 12, "bold"),
                fg=Cor.TEXTO,
                bg=cor_bg,
                anchor="w"
            )
            lbl_tit.pack(fill="x")

            sub_txt = f"{info['total']} perguntas  •  {info['arquivo']}"
            lbl_sub = tk.Label(
                col,
                text=sub_txt,
                font=("Segoe UI", 9),
                fg=Cor.SUAVE,
                bg=cor_bg,
                anchor="w"
            )
            lbl_sub.pack(fill="x")

            if info.get("categorias"):
                cats = ", ".join(info["categorias"][:3])
                if len(info["categorias"]) > 3:
                    cats += f" (+{len(info['categorias']) - 3})"
                lbl_cat = tk.Label(
                    col,
                    text="Tags: " + cats,
                    font=("Segoe UI", 8),
                    fg=Cor.APOIO,
                    bg=cor_bg,
                    anchor="w"
                )
                lbl_cat.pack(fill="x", pady=(2, 0))
            else:
                lbl_cat = None

            badge_txt = "●  SELECIONADO" if selecionado else "○  Escolher"
            badge_cor = Cor.A if selecionado else Cor.APAGADO
            lbl_badge = tk.Label(
                card,
                text=badge_txt,
                font=("Segoe UI", 9, "bold" if selecionado else "normal"),
                fg=badge_cor,
                bg=cor_bg
            )
            lbl_badge.pack(side="right", padx=(10, 0))

            card_info = {
                "idx": idx,
                "info": info,
                "card": card,
                "lbl_ico": lbl_ico,
                "col": col,
                "lbl_tit": lbl_tit,
                "lbl_sub": lbl_sub,
                "lbl_cat": lbl_cat,
                "lbl_badge": lbl_badge,
            }
            self.cards_widgets.append(card_info)

            def criar_cb_click(i):
                return lambda e: self._selecionar_indice(i)

            def criar_cb_dblclick(i):
                return lambda e: (self._selecionar_indice(i), self._confirmar())

            todos_widgets = [card, lbl_ico, col, lbl_tit, lbl_sub, lbl_badge]
            if lbl_cat:
                todos_widgets.append(lbl_cat)

            for w in todos_widgets:
                w.bind("<Button-1>", criar_cb_click(idx))
                w.bind("<Double-Button-1>", criar_cb_dblclick(idx))

    def _selecionar_indice(self, idx):
        if not (0 <= idx < len(self.lista_arquivos)):
            return
        self.arquivo_selecionado = self.lista_arquivos[idx]

        for item in self.cards_widgets:
            i = item["idx"]
            sel = (i == idx)
            cor_bg = "#1B2A54" if sel else Cor.PAINEL
            cor_borda = Cor.A if sel else Cor.BORDA
            esp = 2 if sel else 1

            item["card"].configure(bg=cor_bg, highlightbackground=cor_borda, highlightthickness=esp)
            item["lbl_ico"].configure(bg=cor_bg)
            item["col"].configure(bg=cor_bg)
            item["lbl_tit"].configure(bg=cor_bg)
            item["lbl_sub"].configure(bg=cor_bg)
            if item["lbl_cat"]:
                item["lbl_cat"].configure(bg=cor_bg)

            item["lbl_badge"].configure(
                bg=cor_bg,
                text="●  SELECIONADO" if sel else "○  Escolher",
                fg=Cor.A if sel else Cor.APAGADO,
                font=("Segoe UI", 9, "bold" if sel else "normal")
            )

    def _mover_selecao(self, delta):
        if not self.lista_arquivos:
            return
        atual_idx = 0
        if self.arquivo_selecionado:
            for i, it in enumerate(self.lista_arquivos):
                if it["caminho"] == self.arquivo_selecionado["caminho"]:
                    atual_idx = i
                    break
        novo_idx = max(0, min(len(self.lista_arquivos) - 1, atual_idx + delta))
        self._selecionar_indice(novo_idx)

    def _procurar_arquivo(self):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar arquivo de perguntas JSON",
            filetypes=[("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")]
        )
        if not caminho:
            return
        info = inspecionar_arquivo_perguntas(caminho)
        if not info:
            messagebox.showerror(
                "Arquivo Inválido",
                "O arquivo selecionado não contém um formato de perguntas válido.\n\n"
                "O JSON deve conter uma lista com os campos 'pergunta', 'alternativas' (2 a 4) e 'correta'.",
                parent=self
            )
            return

        encontrado_idx = None
        for i, item in enumerate(self.lista_arquivos):
            if os.path.abspath(item["caminho"]) == os.path.abspath(info["caminho"]):
                encontrado_idx = i
                break

        if encontrado_idx is None:
            self.lista_arquivos.append(info)
            self.arquivo_selecionado = info
            self._reconstruir_cards()
            self._selecionar_indice(len(self.lista_arquivos) - 1)
        else:
            self._selecionar_indice(encontrado_idx)

    def _atualizar_lista(self):
        diretorio = obter_diretorio_base()
        self.lista_arquivos = listar_arquivos_perguntas(diretorio)
        self._reconstruir_cards()
        if self.lista_arquivos:
            self._selecionar_indice(0)

    def _limpar_mousewheel(self):
        try:
            self.canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass

    def _confirmar(self):
        if not self.arquivo_selecionado:
            messagebox.showwarning("Seleção", "Por favor, selecione um arquivo de perguntas.", parent=self)
            return
        self._limpar_mousewheel()
        escolhido = self.arquivo_selecionado
        cb = self.ao_confirmar
        self.destroy()
        if cb:
            cb(escolhido)

    def _cancelar(self):
        self._limpar_mousewheel()
        self.destroy()

    def _ao_fechar(self):
        self._limpar_mousewheel()
        if self.inicial:
            # Modal inicial: fechar a janela = sair do app
            if messagebox.askyesno("Sair", "Deseja fechar o Duelo de Conhecimento?", parent=self):
                self.parent.destroy()
        else:
            # Modal durante o jogo: apenas fecha o modal
            self.destroy()


# =========================================================
# APLICAÇÃO PRINCIPAL
# =========================================================
class DueloDeConhecimento:
    def __init__(self, root):
        self.root = root
        self.root.title(TITULO)
        self.root.geometry("1280x800")
        self.root.minsize(900, 600)
        self.root.configure(bg=Cor.FUNDO)
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

        FAMILIAS["display"] = escolher_fonte(["Bahnschrift", "Segoe UI Semibold", "Segoe UI", "Arial"])
        FAMILIAS["corpo"] = escolher_fonte(["Segoe UI", "Calibri", "Arial"])

        # ---------- Estado ----------
        # O Jogo é o dono único das regras, do placar e do tempo.
        # A UI lê o estado por propriedades (placar_a/b, fase, ...) e não
        # reimplementa nenhuma regra.
        self.arquivo_atual = None
        self.tema_atual = ""
        self.erro_carga = ""
        self.jogo = Jogo(
            [],
            num_equipes=NUM_EQUIPES,
            tempo_pergunta=TEMPO_PERGUNTA,
            tempo_resposta=TEMPO_RESPOSTA,
            pontuar_apos_tempo=PONTUAR_APOS_TEMPO,
            nomes_equipes=dict(NOMES_EQUIPES),
        )

        self.aviso = None
        self._aviso_carga = None

        self._job_timer = None
        self._job_aviso = None
        self._job_escala = None

        self.serial = None
        self.rodando = True
        self.fila = queue.Queue()

        # Ícone da janela principal
        ico_path = caminho_recurso("desafio.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        # ---------- Áudio ----------
        self.som = Som()
        self._ultimo_seg_tick = None

        # ---------- Inicialização ----------
        self.montar_interface()
        self.iniciar_thread_serial()

        self.root.bind("<Key>", self.tecla_pressionada)
        self.root.bind("<F11>", lambda e: self.alternar_tela_cheia())
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<Control-r>", lambda e: self.reiniciar_placar())
        self.root.bind("<Control-R>", lambda e: self.reiniciar_placar())
        self.root.bind("<Control-t>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Control-T>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Control-o>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Control-O>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<F2>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Configure>", self._ao_redimensionar)
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)

        self.root.after(20, self.drenar_fila)
        self.render()

        # Abre o seletor de temas na inicialização da aplicação
        self.root.after(100, lambda: self.abrir_seletor_tema(inicial=True))

    # -----------------------------------------------------
    # LEITURA DO ESTADO (compatibilidade: a UI antiga continua
    # usando os mesmos nomes; a verdade está no Jogo)
    # -----------------------------------------------------
    @property
    def perguntas(self):
        return self.jogo.perguntas_base

    @property
    def pergunta_atual(self):
        return self.jogo.estado.pergunta_atual

    @property
    def indice(self):
        return self.jogo.estado.indice_pergunta

    @property
    def numero(self):
        return self.jogo.estado.numero_pergunta

    @property
    def fase(self):
        return self.jogo.estado.fase

    @property
    def quem_apertou(self):
        return self.jogo.estado.quem_apertou

    @property
    def tempo_estourou(self):
        return self.jogo.estado.tempo_estourou

    @property
    def placar_a(self):
        return self.jogo.placar.get("A", 0)

    @placar_a.setter
    def placar_a(self, valor):
        self.jogo.placar["A"] = valor

    @property
    def placar_b(self):
        return self.jogo.placar.get("B", 0)

    @placar_b.setter
    def placar_b(self, valor):
        self.jogo.placar["B"] = valor

    # -----------------------------------------------------
    # PERGUNTAS E TEMAS
    # -----------------------------------------------------
    def carregar_perguntas(self, caminho=None, nome_tema=None):
        self._cancelar_job_timer()
        if caminho is None:
            caminho = caminho_recurso(ARQUIVO_PERGUNTAS)

        self.arquivo_atual = caminho
        nome_arquivo = os.path.basename(caminho)

        # Carregador/validador único do projeto (jogo.ler_banco_perguntas)
        carga = ler_banco_perguntas(
            caminho,
            tema_padrao=nome_tema or formatar_nome_tema(nome_arquivo),
            aceitar_tema_do_arquivo=not nome_tema,
        )
        self.tema_atual = carga.tema
        self.erro_carga = carga.erro
        if carga.erro:
            print(carga.erro)
        for linha in carga.ignoradas:
            print(linha)

        self.jogo.recarregar_perguntas(carga.perguntas)
        print(f"[{self.tema_atual}] {len(carga.perguntas)} perguntas carregadas de {nome_arquivo}.")
        # Aviso na tela (o detalhe de cada pergunta vai para o log na Etapa 4.1)
        self._aviso_carga = mensagem_ignoradas(len(carga.ignoradas), nome_arquivo)

        if hasattr(self, "topo"):
            self.topo.tema = self.tema_atual
            self.topo.desenhar()

    def abrir_seletor_tema(self, inicial=False):
        """Abre a tela modal para escolha de tema/arquivo de perguntas."""
        if self._job_timer:
            self._cancelar_job_timer()

        diretorio = obter_diretorio_base()
        arquivos = listar_arquivos_perguntas(diretorio)

        atual = None
        if self.arquivo_atual:
            for arq in arquivos:
                if os.path.abspath(arq["caminho"]) == os.path.abspath(self.arquivo_atual):
                    atual = arq
                    break
        if atual is None and arquivos:
            atual = arquivos[0]

        def ao_confirmar(info_escolhida):
            if not info_escolhida:
                return
            mesmo_arquivo = self.arquivo_atual and (os.path.abspath(info_escolhida["caminho"]) == os.path.abspath(self.arquivo_atual))

            if not inicial and not mesmo_arquivo and (self.placar_a > 0 or self.placar_b > 0):
                if messagebox.askyesno(TITULO, f"Zerar o placar dos competidores para '{info_escolhida['titulo']}'?", parent=self.root):
                    self.placar_a = self.placar_b = 0

            self.carregar_perguntas(info_escolhida["caminho"], info_escolhida["titulo"])
            self.proxima_pergunta(forcar=True)

        modal = ModalSelecaoPerguntas(
            parent=self.root,
            lista_arquivos=arquivos,
            arquivo_atual=atual,
            ao_confirmar=ao_confirmar,
            permitir_cancelar=True,
            inicial=inicial
        )

    def proxima_pergunta(self, forcar=False):
        # A regra de bloqueio e o avanço do baralho são do Jogo.
        self._despachar(self.jogo.proxima_pergunta(forcar))

    # -----------------------------------------------------
    # INTERFACE
    # -----------------------------------------------------
    def montar_interface(self):
        r = self.root
        r.columnconfigure(0, weight=2, uniform="lado")
        r.columnconfigure(1, weight=5)
        r.columnconfigure(2, weight=2, uniform="lado")
        r.rowconfigure(0, minsize=64)
        r.rowconfigure(1, weight=1)
        r.rowconfigure(2, minsize=84)
        P = 16

        self.topo = BarraTopo(r, height=64)
        self.topo.grid(row=0, column=0, columnspan=3, sticky="ew", padx=P, pady=(10, 0))

        self.cartao_a = CartaoPlacar(r, NOME_A, Cor.A)
        self.cartao_a.grid(row=1, column=0, sticky="nsew", padx=(P, 8), pady=10)
        self.cartao_b = CartaoPlacar(r, NOME_B, Cor.B)
        self.cartao_b.grid(row=1, column=2, sticky="nsew", padx=(8, P), pady=10)

        palco = tk.Frame(r, bg=Cor.FUNDO)
        palco.grid(row=1, column=1, sticky="nsew", padx=8, pady=10)
        palco.columnconfigure(0, weight=1)
        palco.rowconfigure(0, minsize=56)
        palco.rowconfigure(1, weight=5)
        for i in range(2, 6):
            palco.rowconfigure(i, weight=2, uniform="alt")
        palco.rowconfigure(6, weight=2)

        self.barra = BarraTempo(palco, height=56)
        self.barra.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.cartao_pergunta = CartaoPergunta(palco)
        self.cartao_pergunta.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        self.cartoes_alt = []
        for i in range(4):
            c = CartaoAlt(palco)
            c.grid(row=2 + i, column=0, sticky="nsew", pady=3)
            self.cartoes_alt.append(c)
        self.cartao_explic = CartaoExplicacao(palco)
        self.cartao_explic.grid(row=6, column=0, sticky="nsew", pady=(6, 0))

        self.rodape = Rodape(r, height=84)
        self.rodape.grid(row=2, column=0, columnspan=3, sticky="ew", padx=P, pady=(0, 14))

        self.telas = [self.topo, self.cartao_a, self.cartao_b, self.barra,
                      self.cartao_pergunta, *self.cartoes_alt, self.cartao_explic, self.rodape]

    def _nome(self, letra):
        return NOME_A if letra == "A" else NOME_B

    def _cor(self, letra):
        return Cor.A if letra == "A" else Cor.B

    def _status_padrao(self):
        if self.pergunta_atual is None:
            if not self.perguntas:
                return (self.erro_carga or "Aguardando seleção de tema de perguntas.", Cor.SUAVE)
            return (self.erro_carga or "Nenhuma pergunta válida carregada.", Cor.ERRO)
        q = self.quem_apertou
        if self.fase == FASE_AGUARDANDO:
            return ("Valendo! O primeiro a apertar o botão responde.", Cor.APOIO)
        if self.fase == FASE_RESPONDENDO:
            return (f"{self._nome(q)} apertou. Monitor: revele a resposta.", self._cor(q))
        if self.fase == FASE_REVELADA:
            if q is None:
                return ("Ninguém apertou. Aperte AVANÇAR.", Cor.SUAVE)
            if self.tempo_estourou and not PONTUAR_APOS_TEMPO:
                return (f"Tempo esgotado para {self._nome(q)}. Aperte AVANÇAR.", Cor.ERRO)
            return (f"{self._nome(q)} acertou? Pontue ou aperte AVANÇAR.", Cor.TEXTO)
        return (f"Ponto para {self._nome(q)}! Aperte AVANÇAR.", self._cor(q))

    def render(self):
        """Desenha a tela inteira a partir do estado atual."""
        p = self.pergunta_atual
        revelado = self.fase in (FASE_REVELADA, FASE_PONTUADA)

        for cartao, letra, pts, outro in ((self.cartao_a, "A", self.placar_a, self.placar_b),
                                          (self.cartao_b, "B", self.placar_b, self.placar_a)):
            cartao.pontos = pts
            cartao.ativo = (self.quem_apertou == letra)
            cartao.rotulo = "Apertou primeiro" if cartao.ativo else ("Na frente" if pts > outro else "")
            cartao.desenhar()

        cp = self.cartao_pergunta
        if p:
            cp.categoria, cp.texto, cp.numero = p.categoria, p.texto, self.numero
        else:
            cp.categoria, cp.texto, cp.numero = "", "Nenhuma pergunta carregada.", 0
        cp.desenhar()

        for i, c in enumerate(self.cartoes_alt):
            if p and i < len(p.alternativas):
                c.grid()
                if revelado:
                    estado = "correta" if i == p.correta else "apagada"
                else:
                    estado = "normal"
                c.definir(chr(65 + i), p.alternativas[i], estado)
                c.desenhar()
            else:
                c.grid_remove()

        self.cartao_explic.texto = p.explicacao if (p and revelado) else ""
        self.cartao_explic.desenhar()

        msg, cor = (self.aviso, Cor.AVISO) if self.aviso else self._status_padrao()
        self.rodape.msg, self.rodape.cor_msg, self.rodape.passo = msg, cor, self.fase
        self.rodape.desenhar()

    def avisar(self, texto):
        """Aviso temporário no rodapé (some sozinho, não altera o estado)."""
        self._limpar_aviso()
        self.aviso = texto
        self._job_aviso = self.root.after(3500, self._expirar_aviso)
        self.render()

    def _expirar_aviso(self):
        self._job_aviso = None
        self.aviso = None
        self.render()

    def _limpar_aviso(self):
        if self._job_aviso:
            self.root.after_cancel(self._job_aviso)
            self._job_aviso = None
        self.aviso = None

    def piscar(self, letra, n=5):
        cartao = self.cartao_a if letra == "A" else self.cartao_b

        def passo(i):
            cartao.brilho = (i % 2 == 1)
            cartao.desenhar()
            if i < n:
                self.root.after(110, passo, i + 1)
        passo(0)

    def alternar_tela_cheia(self):
        atual = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not atual)

    def _ao_redimensionar(self, ev):
        if ev.widget is not self.root:
            return
        if self._job_escala:
            self.root.after_cancel(self._job_escala)
        self._job_escala = self.root.after(60, self._aplicar_escala)

    def _aplicar_escala(self):
        global ESCALA
        self._job_escala = None
        w, h = self.root.winfo_width(), self.root.winfo_height()
        nova = max(0.6, min(w / 1280, h / 800, 2.2))
        if abs(nova - ESCALA) > 0.02:
            ESCALA = nova
            for t in self.telas:
                t.desenhar()

    # -----------------------------------------------------
    # TIMER — o prazo é do Jogo; a UI só agenda o after(),
    # consulta timer_restante()/timer_fracao() e desenha.
    # -----------------------------------------------------
    def _cancelar_job_timer(self):
        if self._job_timer:
            self.root.after_cancel(self._job_timer)
            self._job_timer = None

    def _reiniciar_loop_timer(self):
        self._cancelar_job_timer()
        if self.jogo.timer_ativo:
            self._tick()

    def _tick(self):
        self._job_timer = None
        if not self.jogo.timer_ativo:
            return

        eventos = self.jogo.tick_timer()
        if eventos:
            self._despachar(eventos)   # estouro: o Jogo já fez a transição
            return

        self._atualizar_barra()
        restante = self.jogo.timer_restante()
        seg = math.ceil(restante)
        if seg != self._ultimo_seg_tick:
            self._ultimo_seg_tick = seg
            self.som.tick(seg, self.fase)
        self._job_timer = self.root.after(100, self._tick)

    def _atualizar_barra(self):
        j = self.jogo
        if j.estado.pergunta_atual is None:
            return
        b = self.barra
        b.rotulo = j.timer_rotulo
        b.frac = j.timer_fracao()
        b.segundos = math.ceil(max(0.0, j.timer_restante_visual()))
        if j.timer_motivo == TIMER_MOTIVO_REVELADA:
            b.cor = Cor.APAGADO
        elif b.frac <= 0.34:
            b.cor = Cor.ERRO
        elif j.timer_cor:
            b.cor = self._cor(j.timer_cor)
        else:
            b.cor = Cor.APOIO
        b.desenhar()

    # -----------------------------------------------------
    # EVENTOS DO JOGO -> LED, som e tela (nenhuma regra aqui)
    # -----------------------------------------------------
    def _despachar(self, eventos):
        if eventos and eventos[0].startswith(PREFIXO_RECUSA):
            self.avisar(self._texto_recusa(eventos[0]))
            return

        for cmd in comandos_para_arduino(eventos):
            self.enviar_serial(cmd)

        quem_piscar = None
        for ev in eventos:
            if ev.startswith("apertou:"):
                quem_piscar = ev.split(":", 1)[1]
                self._limpar_aviso()
                self.som.apertou(quem_piscar)
            elif ev == "revelou":
                self._limpar_aviso()
                self.som.revelou()
            elif ev.startswith("pontuou:"):
                self._limpar_aviso()
                self.som.acertou()
            elif ev == "tempo_esgotado":
                self._limpar_aviso()
                self.som.tempo_esgotado()
            elif ev == "proxima_pergunta":
                self._limpar_aviso()
                self._ultimo_seg_tick = None
                self.som.nova_pergunta()
            elif ev == "reiniciou_placar":
                self._limpar_aviso()
            # "reiniciou_banco" e "led_reacender:*" só têm efeito serial/tela

        self.render()
        self._atualizar_barra()
        if quem_piscar:
            self.piscar(quem_piscar)
        self._reiniciar_loop_timer()
        self._mostrar_aviso_carga()

    def _mostrar_aviso_carga(self):
        if self._aviso_carga:
            texto, self._aviso_carga = self._aviso_carga, None
            self.avisar(texto)

    def _texto_recusa(self, evento):
        motivo = evento.split(":", 1)[1]
        texto = MENSAGENS_RECUSA.get(motivo, "")
        if motivo == MOTIVO_ACERTO_OUTRA_EQUIPE:
            quem = self.quem_apertou
            texto = texto.format(equipe=self._nome(quem) if quem else "?")
        return texto

    # -----------------------------------------------------
    # SERIAL
    # -----------------------------------------------------
    def iniciar_thread_serial(self):
        if not SERIAL_DISPONIVEL:
            return
        threading.Thread(target=self.loop_serial, daemon=True).start()

    def _candidatas(self):
        portas = list(serial.tools.list_ports.comports())
        print("\n=== PORTAS SERIAIS DETECTADAS ===")
        for p in portas:
            print(f"  {p.device} | descrição: {p.description}")
        print("=================================\n")
        chaves = ("arduino", "ch340", "ch341", "usb serial", "usb-serial")
        lista = []
        if PORTA_FORCADA:
            lista.append(PORTA_FORCADA)
        lista += [p.device for p in portas if any(k in (p.description or "").lower() for k in chaves)]
        lista += [p.device for p in portas]
        vistas, unicas = set(), []
        for porta in lista:
            if porta not in vistas:
                vistas.add(porta)
                unicas.append(porta)
        return unicas

    def _tentar_conectar(self, porta):
        try:
            s = serial.Serial(porta, BAUD_RATE, timeout=0.1)
            time.sleep(2)  # Arduino reinicia ao abrir a serial
            s.reset_input_buffer()
            self.serial = s
            print(f"✓ Conectado em {porta}")
            return True
        except Exception as e:
            print(f"✗ Falha em {porta}: {e}")
            return False

    def _fechar_serial(self):
        s, self.serial = self.serial, None
        try:
            if s:
                s.close()
        except Exception:
            pass

    def enviar_serial(self, cmd):
        s = self.serial
        if s and s.is_open:
            try:
                s.write((cmd + "\n").encode())
            except Exception:
                pass

    def loop_serial(self):
        """Thread: nunca mexe na interface, só coloca mensagens na fila."""
        ultima_busca = 0.0
        while self.rodando:
            s = self.serial
            if not (s and s.is_open):
                if time.monotonic() - ultima_busca >= 3:
                    ultima_busca = time.monotonic()
                    for porta in self._candidatas():
                        if self._tentar_conectar(porta):
                            self.fila.put(("conexao", porta))
                            break
                time.sleep(0.2)
                continue
            try:
                linha = s.readline().decode(errors="ignore").strip()
                if linha:
                    print(f"[ARDUINO] {linha}")
                    self.fila.put(("evento", linha))
            except Exception as e:
                print(f"[ERRO SERIAL] {e} — tentando reconectar")
                self._fechar_serial()
                self.fila.put(("conexao", None))

    def drenar_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                try:
                    if tipo == "evento":
                        self.processar_evento(valor)
                    elif tipo == "conexao":
                        self.topo.conexao = valor
                        self.topo.desenhar()
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        if self.rodando:
            self.root.after(20, self.drenar_fila)

    def processar_evento(self, evento):
        # Mapeamento linha-da-serial -> ação é uma função pura (protocolo.py)
        if evento == "PRONTO":
            print("Arduino reiniciado.")
        self._despachar(mapear_evento_arduino(evento, self.jogo))

    # -----------------------------------------------------
    # AÇÕES DA UI (só delegam ao Jogo e despacham os eventos)
    # AGUARDANDO -> RESPONDENDO -> REVELADA -> PONTUADA
    # -----------------------------------------------------
    def apertar_botao(self, quem):
        self._despachar(self.jogo.apertar_botao(quem))

    def revelar_resposta(self):
        self._despachar(self.jogo.revelar_resposta())

    def confirmar_acerto(self, quem):
        self._despachar(self.jogo.confirmar_acerto(quem))

    def reiniciar_placar(self):
        if messagebox.askyesno(TITULO, "Zerar o placar dos dois competidores?"):
            self._despachar(self.jogo.reiniciar_placar())

    
    def alternar_som(self):
        if not self.som.disponivel:
            self.avisar("Áudio indisponível. Verifique a instalação do pygame.")
            return

        self.som.ativo = not self.som.ativo

        if self.som.ativo:
            self.som.tocar_ja(("C5", 80), ("E5", 110))

        self.avisar(
            "Som ativado." if self.som.ativo else "Som silenciado."
        )


    # -----------------------------------------------------
    # TECLADO (simulação)
    # -----------------------------------------------------
    def tecla_pressionada(self, event):
        k = event.char.lower()
        if k == "a":
            self.apertar_botao("A")
        elif k == "b":
            self.apertar_botao("B")
        elif k == "n":
            self.proxima_pergunta()
        elif k == "1":
            self.confirmar_acerto("A")
        elif k == "2":
            self.confirmar_acerto("B")
        elif k == "r":
            self.revelar_resposta()
        elif k == "s":
            self.alternar_som()
        elif k == "t" and (event.state & 0x4):
            self.abrir_seletor_tema(inicial=False)

    def fechar(self):
        self.rodando = False
        self.enviar_serial("RESET")
        self._fechar_serial()
        self.som.parar()
        self.root.destroy()


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = DueloDeConhecimento(root)
    root.mainloop()