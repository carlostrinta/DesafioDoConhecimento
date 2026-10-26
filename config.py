"""
Configuração do Desafio do Conhecimento — Etapa 3.1.

Este módulo concentra, num só lugar, os valores que hoje estavam fixos no
topo de `desafio.py` (título, equipes, tempos e serial).

IMPORTANTE: nesta etapa ele **não lê** `config.json` nem `config.exemplo.json`.
A leitura de arquivo de configuração entra na Etapa 4.2; até lá, editar o JSON
não muda nada no jogo.

Sem dependências de UI, serial ou pygame: pode ser importado em qualquer
ambiente, inclusive nos testes headless.
"""

# ─── Identidade ───
TITULO = "Desafio de Conhecimento"

# ─── Equipes ───
# A interface (2 equipes) usa NUM_EQUIPES e as teclas A/B da UI;
# a lógica (Jogo) já aceita de 2 a 4 equipes.
NUM_EQUIPES = 2
NOMES_EQUIPES = {
    "A": "Competidor A",
    "B": "Competidor B",
}

# ─── Banco de perguntas padrão ───
ARQUIVO_PERGUNTAS = "conhecimentos_gerais.json"

# ─── Tempos (segundos) ───
TEMPO_PERGUNTA = 30   # tempo para alguém apertar o botão
TEMPO_RESPOSTA = 15   # tempo para quem apertou responder

# True = o monitor ainda pode pontuar depois que o tempo esgotar
PONTUAR_APOS_TEMPO = False

# ─── Comunicação serial ───
BAUD_RATE = 9600
PORTA_FORCADA = None  # ex.: "COM3" — None = autodetectar

# Obs.: paleta de cores e tipografia continuam em `desafio.py` — são
# apresentação, não configuração de jogo. `cores_equipes` do
# `config.exemplo.json` será tratado junto com a leitura do arquivo (4.2).
