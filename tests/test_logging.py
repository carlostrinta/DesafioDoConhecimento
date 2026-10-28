"""Testes do logging (Etapa 4.1) — nenhum abre janela Tk."""

import json
import logging
import sys
from logging.handlers import RotatingFileHandler

import pytest

import logging_conf
import perguntas


@pytest.fixture(autouse=True)
def restaurar_logging():
    excepthook = sys.excepthook
    yield
    logger = logging.getLogger(logging_conf.NOME_LOGGER)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logging_conf._caminho_log = ""
    sys.excepthook = excepthook


def _ler(caminho):
    return caminho.read_text(encoding="utf-8")


def _handlers_de_arquivo(logger):
    return [h for h in logger.handlers if isinstance(h, logging.FileHandler)]


def _handlers_de_console(logger):
    return [h for h in logger.handlers if not isinstance(h, logging.FileHandler)]


def test_arquivo_rotativo_ao_lado_do_app(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_conf, "obter_diretorio_base", lambda: str(tmp_path))

    logger = logging_conf.configurar()
    logger.info("mensagem de teste")

    caminho = tmp_path / "logs" / "desafio.log"
    assert caminho.exists()
    assert logging_conf.caminho_log() == str(caminho)

    conteudo = _ler(caminho)
    assert "INFO" in conteudo
    assert "mensagem de teste" in conteudo

    arquivos = _handlers_de_arquivo(logger)
    assert len(arquivos) == 1
    assert isinstance(arquivos[0], RotatingFileHandler)
    assert arquivos[0].maxBytes == logging_conf.MAX_BYTES
    assert arquivos[0].backupCount == logging_conf.BACKUP_COUNT


def test_fallback_para_a_pasta_do_script(tmp_path):
    bloqueado = tmp_path / "sem_escrita"
    bloqueado.write_text("sou um arquivo, não uma pasta", encoding="utf-8")
    alternativo = tmp_path / "script"

    caminho = logging_conf.obter_caminho_log(str(bloqueado), str(alternativo))

    esperado = alternativo / "logs" / "desafio.log"
    assert caminho == str(esperado)
    assert esperado.parent.is_dir()


def test_console_so_com_debug(tmp_path):
    logger = logging_conf.configurar(diretorio_base=str(tmp_path))
    assert _handlers_de_console(logger) == []

    logger = logging_conf.configurar(debug=True, diretorio_base=str(tmp_path))
    consoles = _handlers_de_console(logger)
    assert len(consoles) == 1
    assert consoles[0].level == logging.DEBUG


def test_configurar_nao_duplica_handlers(tmp_path):
    logging_conf.configurar(diretorio_base=str(tmp_path))
    logger = logging_conf.configurar(diretorio_base=str(tmp_path))

    assert len(logger.handlers) == 1
    assert len(_handlers_de_arquivo(logger)) == 1


def test_rotacao_limita_tamanho_e_quantidade(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_conf, "MAX_BYTES", 2000)
    monkeypatch.setattr(logging_conf, "BACKUP_COUNT", 2)
    logger = logging_conf.configurar(diretorio_base=str(tmp_path))

    for i in range(200):
        logger.info("linha %03d %s", i, "x" * 80)

    pasta = tmp_path / "logs"
    nomes = sorted(p.name for p in pasta.iterdir())
    assert "desafio.log" in nomes
    assert "desafio.log.1" in nomes
    backups = [nome for nome in nomes if nome.startswith("desafio.log.")]
    assert len(backups) <= 2


@pytest.mark.parametrize("nivel", logging_conf.NIVEIS)
def test_niveis_aceitos(nivel, tmp_path):
    logger = logging_conf.configurar(nivel=nivel, diretorio_base=str(tmp_path))

    arquivo = _handlers_de_arquivo(logger)[0]
    assert arquivo.level == getattr(logging, nivel)


def test_nivel_invalido(tmp_path):
    with pytest.raises(ValueError, match="inválido"):
        logging_conf.configurar(nivel="TRACE", diretorio_base=str(tmp_path))


def test_pergunta_ignorada_fica_no_log_com_detalhe(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_conf, "obter_diretorio_base", lambda: str(tmp_path))
    logging_conf.configurar()

    banco = tmp_path / "banco.json"
    banco.write_text(
        json.dumps(
            [
                {"pergunta": "Válida?", "alternativas": ["A", "B"], "correta": 0},
                {"pergunta": "Inválida?", "alternativas": ["A"], "correta": 0},
            ]
        ),
        encoding="utf-8",
    )

    carga = perguntas.ler_banco_perguntas(str(banco))

    assert len(carga.perguntas) == 1
    assert len(carga.ignoradas) == 1
    conteudo = _ler(tmp_path / "logs" / "desafio.log")
    assert "Pergunta #2 ignorada em banco.json: use de 2 a 4 alternativas" in conteudo


def test_excecao_nao_tratada_loga_e_avisa(tmp_path, monkeypatch):
    avisos = []
    monkeypatch.setattr(
        logging_conf,
        "avisar_usuario",
        lambda mensagem=None, parent=None: avisos.append(mensagem),
    )
    logging_conf.configurar(diretorio_base=str(tmp_path))
    logging_conf.instalar_excepthook()

    try:
        raise RuntimeError("quebrou de propósito")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())

    conteudo = _ler(tmp_path / "logs" / "desafio.log")
    assert "CRITICAL" in conteudo
    assert "Exceção não tratada" in conteudo
    assert "Traceback" in conteudo
    assert "RuntimeError: quebrou de propósito" in conteudo

    assert len(avisos) == 1
    assert "desafio.log" in avisos[0]
    assert "Traceback" not in avisos[0]
    assert "RuntimeError" not in avisos[0]


def test_erro_em_callback_tk_loga_e_avisa(tmp_path, monkeypatch):
    avisos = []
    monkeypatch.setattr(
        logging_conf,
        "avisar_usuario",
        lambda mensagem=None, parent=None: avisos.append(mensagem),
    )
    logging_conf.configurar(diretorio_base=str(tmp_path))

    try:
        raise ValueError("callback quebrado")
    except ValueError:
        logging_conf.tratar_excecao_tk(*sys.exc_info())

    conteudo = _ler(tmp_path / "logs" / "desafio.log")
    assert "ERROR" in conteudo
    assert "callback do Tk" in conteudo
    assert "ValueError: callback quebrado" in conteudo
    assert len(avisos) == 1
