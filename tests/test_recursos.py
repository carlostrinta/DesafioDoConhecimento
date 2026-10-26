"""
Testes de `recursos.py`: pasta de recursos no código-fonte e "congelado".

O modo congelado é simulado com monkeypatch em `sys.frozen` / `sys.executable`
/ `sys._MEIPASS` — nenhum teste precisa de PyInstaller nem de arquivo real.
"""

import os
import subprocess
import sys
from pathlib import Path

import recursos

RAIZ = Path(__file__).resolve().parent.parent


class TestModuloPuro:
    def test_importa_sem_dependencias_de_interface(self):
        codigo = (
            "import sys; import recursos; "
            "proibidos = {'tkinter', 'serial', 'pygame', 'jogo', 'perguntas'}; "
            "achados = proibidos & set(sys.modules); "
            "assert not achados, achados"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            cwd=str(RAIZ),
        )
        assert saida.returncode == 0, saida.stderr


class TestCodigoFonte:
    def test_usa_a_pasta_do_projeto(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert os.path.normcase(recursos.obter_diretorio_base()) == os.path.normcase(
            str(RAIZ)
        )

    def test_caminho_recurso_junta_o_nome(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        esperado = os.path.join(str(RAIZ), "conhecimentos_gerais.json")
        assert os.path.normcase(
            recursos.caminho_recurso("conhecimentos_gerais.json")
        ) == os.path.normcase(esperado)


class TestCongelado:
    def test_usa_a_pasta_do_executavel(self, monkeypatch, tmp_path):
        exe = tmp_path / "dist" / "Desafio do Conhecimento.exe"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe), raising=False)

        assert recursos.obter_diretorio_base() == str(exe.parent)
        assert recursos.caminho_recurso("tema.json") == str(exe.parent / "tema.json")

    def test_meipass_nao_altera_enquanto_nada_e_empacotado(self, monkeypatch, tmp_path):
        """
        Com `datas=[]` no .spec não há recurso dentro do .exe: a pasta de
        referência continua sendo a do executável (onde o usuário põe os JSONs).
        """
        exe = tmp_path / "dist" / "app.exe"
        meipass = tmp_path / "_MEI123456"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe), raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

        assert recursos.obter_diretorio_base() == str(exe.parent)
        assert recursos.caminho_recurso("tema.json") == str(exe.parent / "tema.json")
