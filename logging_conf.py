"""
Logging do Desafio do Conhecimento (Etapa 4.1).

- Um único log em arquivo rotativo: `logs/desafio.log`, ao lado do executável
  (ou na pasta do script quando não há permissão de escrita ali).
- Tamanho e quantidade limitados: 1 MB por arquivo e 3 backups
  (`desafio.log.1` … `desafio.log.3`).
- Console **só** com `--debug`; sem ele, o log vai apenas para o arquivo.
- Níveis aceitos: `DEBUG`, `INFO`, `WARNING` e `ERROR` (padrão `INFO`; pode ser
  trocado por `DESAFIO_LOG_NIVEL`).
- Exceções não tratadas (globais e em callbacks do Tk) vão com traceback para o
  log e o usuário vê uma mensagem curta, sem detalhes técnicos.

Sem tkinter no topo: importar este módulo não abre janela e funciona em
ambiente headless (a mensagem ao usuário é a única parte que tenta Tk).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from recursos import obter_diretorio_base

NOME_LOGGER = "desafio"
NOME_ARQUIVO = "desafio.log"
PASTA_LOGS = "logs"

MAX_BYTES = 1_000_000  # ~1 MB por arquivo
BACKUP_COUNT = 3       # desafio.log.1 … desafio.log.3

NIVEIS = ("DEBUG", "INFO", "WARNING", "ERROR")
FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"

_caminho_log = ""

# Enquanto ninguém configurar o logging, os avisos dos módulos ficam mudos
# (em vez de cair no lastResort/stderr). `configurar()` troca este handler.
logging.getLogger(NOME_LOGGER).addHandler(logging.NullHandler())


def obter_caminho_log(diretorio_base=None, diretorio_alternativo=None):
    """
    Caminho de `logs/desafio.log`.

    Tenta a pasta da aplicação (ao lado do `.exe`, ou a pasta do projeto rodando
    pelo fonte). Se não for possível criar/escrever ali, usa a pasta deste
    script.
    """
    base = diretorio_base or obter_diretorio_base()
    alternativo = diretorio_alternativo or os.path.dirname(os.path.abspath(__file__))

    candidatos = []
    for candidato in (base, alternativo):
        caminho = os.path.abspath(candidato)
        if caminho not in candidatos:
            candidatos.append(caminho)

    for candidato in candidatos:
        pasta = os.path.join(candidato, PASTA_LOGS)
        try:
            os.makedirs(pasta, exist_ok=True)
        except OSError:
            continue
        if os.access(pasta, os.W_OK):
            return os.path.join(pasta, NOME_ARQUIVO)

    raise OSError("Não foi possível criar uma pasta de logs gravável.")


def caminho_log():
    """Caminho do arquivo de log em uso (vazio antes de `configurar()`)."""
    return _caminho_log


def _resolver_nivel(nivel):
    nome = str(nivel).upper()
    if nome not in NIVEIS:
        raise ValueError(
            f"Nível de log inválido: {nivel!r}. Use um de: {', '.join(NIVEIS)}."
        )
    return getattr(logging, nome)


def configurar(debug=False, nivel=None, diretorio_base=None):
    """
    Configura o logger do jogo e devolve o `Logger`.

    `debug=True` adiciona o console (nível DEBUG) e, por padrão, sobe o arquivo
    para DEBUG. Sem debug, o arquivo fica em INFO e não há handler de console.
    """
    global _caminho_log

    nome_nivel = nivel or os.environ.get("DESAFIO_LOG_NIVEL")
    if not nome_nivel:
        nome_nivel = "DEBUG" if debug else "INFO"
    nivel_arquivo = _resolver_nivel(nome_nivel)

    logger = logging.getLogger(NOME_LOGGER)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    try:
        _caminho_log = obter_caminho_log(diretorio_base)
    except OSError:
        # Sem arquivo gravável o jogo ainda abre; o log fica desabilitado.
        _caminho_log = ""
        logger.addHandler(logging.NullHandler())
    else:
        arquivo = RotatingFileHandler(
            _caminho_log,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        arquivo.setLevel(nivel_arquivo)
        arquivo.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))
        logger.addHandler(arquivo)

    if debug:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))
        logger.addHandler(console)

    return logger


def mensagem_erro():
    """Texto curto mostrado ao usuário quando algo não tratado acontece."""
    destino = _caminho_log or "a pasta de logs do jogo"
    return (
        "Ocorreu um erro inesperado.\n\n"
        f"O detalhe foi gravado em:\n{destino}\n\n"
        "Feche e abra o jogo novamente. Se o problema continuar, "
        "envie esse arquivo para o responsável."
    )


def avisar_usuario(mensagem=None, parent=None):
    """Mostra a mensagem simples; em ambiente sem display, só ignora."""
    try:
        from tkinter import messagebox

        messagebox.showerror(
            "Desafio do Conhecimento",
            mensagem or mensagem_erro(),
            parent=parent,
        )
    except Exception:
        # Sem Tk/display: o traceback já está no log.
        pass


def tratar_excecao_tk(exc_type, exc, tb, parent=None):
    """`report_callback_exception` do Tk: loga o traceback e avisa o usuário."""
    logging.getLogger(NOME_LOGGER).error(
        "Erro não tratado em callback do Tk", exc_info=(exc_type, exc, tb)
    )
    avisar_usuario(mensagem_erro(), parent=parent)


def _excepthook(exc_type, exc, tb):
    logging.getLogger(NOME_LOGGER).critical(
        "Exceção não tratada", exc_info=(exc_type, exc, tb)
    )
    avisar_usuario(mensagem_erro())


def instalar_excepthook():
    """Faz exceções não tratadas passarem pelo log antes de encerrar."""
    sys.excepthook = _excepthook
