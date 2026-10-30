"""Testes da fonte única dos metadados de publicação."""

import re
import subprocess
import sys
from pathlib import Path

import versao

RAIZ = Path(__file__).resolve().parent.parent


def test_metadados_oficiais():
    assert versao.NOME == "Desafio do Conhecimento"
    assert versao.VERSAO == "2.8.1"
    assert versao.AUTOR == "Carlos Santos"
    assert versao.URL == (
        "https://github.com/carlostrinta/DesafioDoConhecimento"
    )
    assert versao.LICENCA == "MIT"


def test_versao_tem_formato_numerico_para_o_exe():
    assert re.fullmatch(r"\d+\.\d+\.\d+", versao.VERSAO)


def test_licenca_mit_do_codigo():
    texto = (RAIZ / "LICENSE").read_text(encoding="utf-8")
    assert texto.startswith("MIT License\n")
    assert "Copyright (c) 2026 Carlos Santos" in texto
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in texto


def test_licenca_cc_by_dos_bancos_de_perguntas():
    texto = (RAIZ / "LICENCA_PERGUNTAS.md").read_text(encoding="utf-8")
    assert "CC BY 4.0" in texto
    assert "Carlos Santos" in texto
    assert "https://creativecommons.org/licenses/by/4.0/legalcode.pt" in texto


def test_spec_do_exe_usa_o_arquivo_de_versao():
    spec = (RAIZ / "Desafio do Conhecimento.spec").read_text(
        encoding="utf-8"
    )
    info = (RAIZ / "versao_info.txt").read_text(encoding="utf-8")
    assert "version='versao_info.txt'" in spec
    assert '__import__("versao").VERSAO' in info
    assert "Copyright (c) 2026 " in info


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
