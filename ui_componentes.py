"""
Componentes visuais (Canvas) do Duelo de Conhecimento.

Só apresentação: paleta, tipografia e widgets desenhados no Canvas. Nenhuma
regra de jogo mora aqui; o estado chega por atributos (pontos, fase, texto,
conexão) e a UI decide quando redesenhar.

Extraído de desafio.py na Etapa 3.5 sem mudar layout, textos, cores ou fontes.
tests/test_ui_componentes.py compara o dump dos itens de Canvas com o golden
capturado antes da movimentação.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from config import TEMPO_PERGUNTA, TITULO
from serial_comm import SERIAL_DISPONIVEL


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


def truncar_texto(texto, largura_max, medir, reticencias="…"):
    """
    Encurta `texto` para caber em `largura_max`, terminando em reticências.

    `medir` recebe uma string e devolve a largura em pixels. A função é pura e
    recebe a medição de fora para poder ser testada sem abrir uma janela Tk.
    Devolve "" quando nem as reticências cabem.
    """
    texto = str(texto)
    if largura_max <= 0:
        return ""
    if medir(texto) <= largura_max:
        return texto
    if medir(reticencias) > largura_max:
        return ""

    # Busca binária pelo maior prefixo que ainda cabe com as reticências.
    inicio, fim = 0, len(texto)
    while inicio < fim:
        meio = (inicio + fim + 1) // 2
        candidato = texto[:meio].rstrip() + reticencias
        if medir(candidato) <= largura_max:
            inicio = meio
        else:
            fim = meio - 1

    if inicio <= 0:
        return ""
    return texto[:inicio].rstrip() + reticencias


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


def texto_status_serial(conexao, placa="", disponivel=None, aviso_porta=""):
    """Texto e cor da barra de status; função pura para facilitar testes."""
    if disponivel is None:
        disponivel = SERIAL_DISPONIVEL
    if not disponivel:
        return "pyserial não instalado. Modo teclado ativo.", Cor.AVISO
    if aviso_porta:
        if conexao:
            return (
                f"Arduino conectado ({conexao}) · "
                f"porta {aviso_porta} não encontrada",
                Cor.AVISO,
            )
        return (
            f"Porta {aviso_porta} não encontrada; "
            "usando detecção automática.",
            Cor.AVISO,
        )
    if conexao:
        detalhe = f" · {placa}" if placa else ""
        return f"Arduino conectado ({conexao}){detalhe}", Cor.CERTO
    return "Arduino não conectado. Modo teclado ativo.", Cor.AVISO


class BarraTopo(Tela):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.conexao = None
        self.placa = ""
        self.tema = ""
        self.aviso_porta = ""

    def _largura_texto(self, texto, fonte):
        """Largura real de um texto na fonte, medida pelo próprio Canvas."""
        item = self.create_text(-10000, -10000, text=texto, anchor="w", font=fonte)
        bb = self.bbox(item)
        self.delete(item)
        return (bb[2] - bb[0]) if bb else 0

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
        item_titulo = self.create_text(
            x + s * 1.55 + 18, cy, text=texto_titulo, anchor="w",
            fill=Cor.TEXTO, font=F("titulo"),
        )
        bb_titulo = self.bbox(item_titulo)
        x_min_status = (bb_titulo[2] if bb_titulo else 0) + 18

        txt, cor = texto_status_serial(
            self.conexao, self.placa, aviso_porta=self.aviso_porta
        )
        fonte_status = F("pequena")
        r = 5 * min(ESCALA, 1.5)
        largura_max = (w - 6) - x_min_status - (14 + 2 * r)
        if largura_max > 0:
            txt = truncar_texto(
                txt,
                largura_max,
                lambda valor: self._largura_texto(valor, fonte_status),
            )
            if txt:
                item = self.create_text(
                    w - 6, cy - h * 0.16, text=txt, anchor="e",
                    fill=Cor.SUAVE, font=fonte_status,
                )
                bb = self.bbox(item)
                # Se a medição divergir, não desenha: melhor esconder do que
                # sobrepor o título/placar.
                if bb and bb[0] >= x_min_status:
                    self.create_oval(
                        bb[0] - 14 - r, (bb[1] + bb[3]) / 2 - r,
                        bb[0] - 14 + r, (bb[1] + bb[3]) / 2 + r,
                        fill=cor, outline="",
                    )

        # Linha de ajuda: em altura pequena não há espaço vertical para ela
        # sem colidir com o título; nesse caso é omitida (o status continua).
        if h >= 80:
            y_ajuda = h - max(10, h * 0.12)
            self.create_text(
                w - 6, y_ajuda, anchor="e", fill=Cor.APAGADO,
                font=F("pequena", 0.9),
                text="F11 tela cheia   Ctrl+R zerar   Ctrl+T temas   S som on/off",
            )


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


def definir_escala(valor):
    """Atualiza a escala global usada por F() e pelos componentes."""
    global ESCALA
    ESCALA = valor
