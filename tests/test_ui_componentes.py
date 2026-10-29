"""
Testes dos componentes visuais (Etapa 3.5).

A prova principal é um dump dos itens de Canvas (tipo, coordenadas, cores,
fonte e texto) de cada componente em tamanhos fixos, comparado com o golden
capturado **antes** da movimentação para `ui_componentes.py`.

O golden é **opt-in** (`DESAFIO_GOLDEN_UI=1`) porque as métricas de fonte
variam entre PCs e ele é uma guarda de refatoração local, não um teste de CI.
O dump usa Tk de verdade; em ambiente sem display o teste é pulado.

Na Etapa 4.6 foram acrescentados os casos `contagem_numero` e `contagem_ja`
(overlay de largada). Os casos `barra_topo_*` são os mais sensíveis às
métricas de fonte da máquina: se apenas eles divergirem, o layout de
referência continua válido e não é preciso regenerar o arquivo inteiro.
"""

import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "dados" / "ui_componentes_v23.json"
GOLDEN_ATIVO = os.environ.get("DESAFIO_GOLDEN_UI") == "1"

# Casos fixos: (nome, classe, atributos, largura, altura)
CASOS = [
    ("cartao", "Cartao", {"raio": 20}, 400, 200),
    (
        "barra_topo_conectado",
        "BarraTopo",
        {"conexao": "COM6", "tema": "Conhecimentos Gerais"},
        1000,
        90,
    ),
    (
        "barra_topo_desconectado",
        "BarraTopo",
        {"conexao": None, "tema": ""},
        1000,
        90,
    ),
    (
        "placar_inativo",
        "CartaoPlacar",
        {"nome": "Competidor A", "cor": "#3BA3FF", "pontos": 7, "rotulo": "AGUARDANDO"},
        320,
        420,
    ),
    (
        "placar_ativo",
        "CartaoPlacar",
        {
            "nome": "Competidor B",
            "cor": "#FF8F3F",
            "pontos": 12,
            "ativo": True,
            "brilho": True,
            "rotulo": "RESPONDENDO",
        },
        320,
        420,
    ),
    (
        "placar_ativo_sem_brilho",
        "CartaoPlacar",
        {
            "nome": "Competidor B",
            "cor": "#FF8F3F",
            "pontos": 12,
            "ativo": True,
            "brilho": False,
            "rotulo": "REVELADA",
        },
        320,
        420,
    ),
    ("pergunta_vazia", "CartaoPergunta", {}, 900, 320),
    (
        "pergunta",
        "CartaoPergunta",
        {
            "categoria": "Tecnologia",
            "numero": 7,
            "texto": "Qual é a capital do estado de Minas Gerais e o que ela "
            "tem em comum com a capital federal?",
        },
        900,
        320,
    ),
    (
        "alt_normal",
        "CartaoAlt",
        {"letra": "A", "texto": "Belo Horizonte", "estado": "normal"},
        700,
        80,
    ),
    (
        "alt_correta",
        "CartaoAlt",
        {"letra": "B", "texto": "Belo Horizonte", "estado": "correta"},
        700,
        80,
    ),
    (
        "alt_apagada",
        "CartaoAlt",
        {"letra": "C", "texto": "Brasília", "estado": "apagada"},
        700,
        80,
    ),
    (
        "explicacao",
        "CartaoExplicacao",
        {
            "texto": "A capital de Minas Gerais é Belo Horizonte; a capital "
            "federal é Brasília."
        },
        800,
        90,
    ),
    ("explicacao_vazia", "CartaoExplicacao", {"texto": ""}, 800, 90),
    (
        "barra_tempo",
        "BarraTempo",
        {"rotulo": "Tempo", "frac": 0.42, "segundos": 12, "cor": "#FFD166"},
        900,
        70,
    ),
    (
        "rodape",
        "Rodape",
        {"msg": "Competidor A respondendo", "cor_msg": "#EAF0FF", "passo": 1},
        1000,
        90,
    ),
    (
        "rodape_final",
        "Rodape",
        {"msg": "Ponto confirmado", "cor_msg": "#2BD99F", "passo": 3},
        1000,
        90,
    ),
    (
        "contagem_numero",
        "OverlayContagem",
        {"valor": "3"},
        700,
        380,
    ),
    (
        "contagem_ja",
        "OverlayContagem",
        {"valor": "JÁ!"},
        700,
        380,
    ),
]

OPCOES = ("fill", "outline", "width", "text", "font", "anchor", "justify", "capstyle", "smooth")


def _criar(mod, root, nome_classe, atributos):
    classe = getattr(mod, nome_classe)
    if nome_classe == "CartaoPlacar":
        widget = classe(root, atributos["nome"], atributos["cor"])
        resto = {k: v for k, v in atributos.items() if k not in ("nome", "cor")}
    else:
        widget = classe(root)
        resto = atributos
    for chave, valor in resto.items():
        setattr(widget, chave, valor)
    return widget


def _dump(cv):
    itens = []
    for item in cv.find_all():
        dados = {
            "tipo": cv.type(item),
            "coords": [round(float(c), 3) for c in cv.coords(item)],
        }
        for opcao in OPCOES:
            try:
                valor = cv.itemcget(item, opcao)
            except Exception:
                continue
            if valor != "":
                dados[opcao] = valor
        itens.append(dados)
    return itens


def capturar_componentes(mod):
    """Captura o dump de todos os casos usando o módulo informado."""
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Tk indisponível: {e}")

    try:
        familias_originais = dict(mod.FAMILIAS)
        serial_original = getattr(mod, "SERIAL_DISPONIVEL", None)
        # O golden é de layout: fixa o estado "pyserial disponível" para não
        # depender do ambiente (o texto do topo muda sem pyserial).
        mod.SERIAL_DISPONIVEL = True
        root.geometry("+4000+4000")
        # Mesmas famílias escolhidas por DueloDeConhecimento.__init__.
        mod.FAMILIAS["display"] = mod.escolher_fonte(
            ["Bahnschrift", "Segoe UI Semibold", "Segoe UI", "Arial"]
        )
        mod.FAMILIAS["corpo"] = mod.escolher_fonte(["Segoe UI", "Calibri", "Arial"])

        resultado = {}
        for nome, classe, atributos, largura, altura in CASOS:
            widget = _criar(mod, root, classe, atributos)
            widget.place(x=0, y=0, width=largura, height=altura)
            root.update_idletasks()
            widget.delete("all")
            widget.pintar(largura, altura)
            root.update_idletasks()
            resultado[nome] = _dump(widget)
            widget.destroy()
        return resultado
    finally:
        mod.FAMILIAS.update(familias_originais)
        if serial_original is not None:
            mod.SERIAL_DISPONIVEL = serial_original
        root.destroy()


def test_truncar_texto_respeita_o_limite_e_preserva_texto_curto():
    from ui_componentes import truncar_texto

    assert truncar_texto("abc", 10, len) == "abc"
    assert truncar_texto("abcdef", 5, len) == "abcd…"
    assert truncar_texto("", 5, len) == ""
    assert truncar_texto("abc", 0, len) == ""
    assert truncar_texto("abc", 2, lambda _: 5) == ""


def test_barra_topo_nao_sobrepoe_status_ao_titulo_em_janela_pequena():
    import tkinter as tk

    import ui_componentes as mod

    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Tk indisponível: {e}")

    original = mod.SERIAL_DISPONIVEL
    try:
        mod.SERIAL_DISPONIVEL = True
        widget = mod.BarraTopo(root)
        widget.place(x=0, y=0, width=760, height=64)
        widget.conexao = "COM6"
        widget.placa = "Arduino Uno (2341:0043)"
        widget.aviso_porta = "COM9"
        root.update_idletasks()
        widget.pintar(760, 64)
        root.update_idletasks()

        textos = {}
        for item in widget.find_all():
            if widget.type(item) != "text":
                continue
            texto = widget.itemcget(item, "text")
            textos[texto] = widget.bbox(item)

        titulo = next(bb for txt, bb in textos.items() if txt.startswith(mod.TITULO))
        status = next(
            (bb for txt, bb in textos.items() if "Arduino conectado" in txt),
            None,
        )
        ajuda = next(
            (bb for txt, bb in textos.items() if "F11" in txt), None
        )

        assert status is not None, "status deveria caber truncado nesta largura"
        assert status[0] >= titulo[2], "status invadiu o título"
        assert status[2] <= 760 - 5, "status passou da borda direita"
        assert 0 <= status[1] and status[3] <= 64
        if ajuda is not None:
            assert ajuda[1] >= titulo[3], "linha de ajuda colidiu com o título"
    finally:
        mod.SERIAL_DISPONIVEL = original
        root.destroy()


@pytest.mark.skipif(
    not GOLDEN_ATIVO,
    reason="golden visual é opt-in: defina DESAFIO_GOLDEN_UI=1",
)
@pytest.mark.skipif(sys.platform != "win32", reason="golden capturado no Windows")
def test_layout_dos_componentes_nao_mudou():
    import ui_componentes

    atual = capturar_componentes(ui_componentes)
    esperado = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert atual == esperado


def test_overlay_contagem_desenha_e_escala_com_a_janela():
    import tkinter as tk

    import ui_componentes as mod

    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Tk indisponível: {e}")

    escala_original = mod.ESCALA
    try:
        mod.definir_escala(1.0)
        widget = mod.OverlayContagem(root)
        widget.valor = "3"
        widget.place(x=0, y=0, width=620, height=340)
        root.update_idletasks()
        widget.pintar(620, 340)
        root.update_idletasks()

        def tamanho_do_texto(texto):
            item = next(
                item for item in widget.find_all()
                if widget.type(item) == "text"
                and widget.itemcget(item, "text") == texto
            )
            return abs(int(widget.itemcget(item, "font").rsplit(" ", 2)[-2]))

        pequeno = tamanho_do_texto("3")
        mod.definir_escala(2.0)
        widget.delete("all")
        widget.pintar(620, 340)
        root.update_idletasks()
        grande = tamanho_do_texto("3")

        assert grande > pequeno, "o número deve crescer com ESCALA"

        mod.definir_escala(1.0)
        widget.valor = "JÁ!"
        widget.delete("all")
        widget.pintar(620, 340)
        root.update_idletasks()
        assert tamanho_do_texto("JÁ!") > 0

        # O overlay é desenhado dentro do próprio Canvas, sem invadir as
        # coordenadas externas (o placar fica nas colunas laterais da janela).
        for item in widget.find_all():
            x1, y1, x2, y2 = widget.bbox(item)
            assert 0 <= x1 and 0 <= y1
            assert x2 <= 620 and y2 <= 340
    finally:
        mod.definir_escala(escala_original)
        root.destroy()


def test_modulo_visual_nao_importa_logica_de_jogo():
    codigo = (
        "import sys; import ui_componentes; "
        "proibidos = {'jogo', 'perguntas', 'protocolo'}; "
        "achados = proibidos & set(sys.modules); "
        "assert not achados, achados"
    )
    import subprocess

    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=str(RAIZ),
    )
    assert saida.returncode == 0, saida.stderr
