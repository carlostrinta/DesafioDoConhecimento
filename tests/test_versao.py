"""Testes da fonte única dos metadados de publicação."""

import re
import subprocess
import sys
from pathlib import Path

import versao

RAIZ = Path(__file__).resolve().parent.parent


def test_metadados_oficiais():
    assert versao.NOME == "Desafio do Conhecimento"
    assert versao.VERSAO == "2.7.0"
    assert versao.AUTOR == "Carlos Santos"
    assert versao.URL == (
        "https://github.com/carlostrinta/DesafioDoConhecimento"
    )
    assert versao.LICENCA == "MIT"


def test_versao_tem_formato_numerico_para_o_exe():
    assert re.fullmatch(r"\d+\.\d+\.\d+", versao.VERSAO)


def test_importar_versao_nao_carrega_interface_audio_ou_serial():
    codigo = (
        "import sys, versao; "
        "proibidos = {'tkinter', '_tkinter', 'pygame', 'serial'}; "
        "carregados = sorted(proibidos.intersection(sys.modules)); "
        "assert not carregados, carregados; "
        "print(versao.NOME)"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=str(RAIZ),
    )
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.strip() == "Desafio do Conhecimento"
