"""
Testes dos componentes visuais (Etapa 3.5).

A prova principal é um dump dos itens de Canvas (tipo, coordenadas, cores,
fonte e texto) de cada componente em tamanhos fixos, comparado com o golden
capturado **antes** da movimentação para `ui_componentes.py`.

O golden é **opt-in** (`DESAFIO_GOLDEN_UI=1`) porque as métricas de fonte
variam entre PCs e ele é uma guarda de refatoração local, não um teste de CI.
O dump usa Tk de verdade; em ambiente sem display o teste é pulado.
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
