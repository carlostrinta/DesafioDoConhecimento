"""
Testes de `perguntas.py` (Etapa 3.2): módulo puro de perguntas/temas.

O carregamento em si já é coberto por `test_perguntas.py` e
`test_regras_equivalentes.py`; aqui ficam a pureza do módulo, os temas,
a inspeção e a listagem.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import perguntas
from perguntas import (
    formatar_nome_tema,
    inspecionar_arquivo_perguntas,
    listar_arquivos_perguntas,
)

RAIZ = Path(__file__).resolve().parent.parent


def escrever_banco(caminho: Path, textos=("P1?", "P2?"), tema=None) -> Path:
    dados = [
        {"pergunta": t, "alternativas": ["a", "b"], "correta": 0, "categoria": "Cat"}
        for t in textos
    ]
    conteudo = {"perguntas": dados}
    if tema:
        conteudo["tema"] = tema
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")
    return caminho


class TestModuloPuro:
    def test_importa_sem_tkinter_serial_ou_pygame(self):
        codigo = (
            "import sys; import perguntas; "
            "proibidos = {'tkinter', 'serial', 'pygame', 'jogo'}; "
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

    def test_jogo_importa_de_perguntas_sem_ciclo(self):
        """`jogo` pode importar `perguntas`; o contrário não."""
        codigo = "import jogo, perguntas; assert jogo.Pergunta is perguntas.Pergunta"
        saida = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            cwd=str(RAIZ),
        )
        assert saida.returncode == 0, saida.stderr

    def test_existe_um_unico_json_load_no_projeto(self):
        """Só o carregador único abre e decodifica JSON."""
        arquivos = [
            p for p in RAIZ.glob("*.py") if p.name not in {"setup.py"}
        ]
        achados = {
            p.name: p.read_text(encoding="utf-8").count("json.load(")
            for p in arquivos
        }
        achados = {nome: n for nome, n in achados.items() if n}
        assert achados == {"perguntas.py": 1}


class TestPerguntaCompatibilidade:
    def test_mesma_classe_reexportada_por_jogo(self):
        import jogo

        assert jogo.Pergunta is perguntas.Pergunta
        assert jogo.ler_banco_perguntas is perguntas.ler_banco_perguntas
        assert (
            jogo.carregar_perguntas_json is perguntas.carregar_perguntas_json
        )


class TestFormatarNomeTema:
    @pytest.mark.parametrize(
        "entrada, esperado",
        [
            ("conhecimentos_gerais.json", "Conhecimentos Gerais"),
            ("eletrotecnica.json", "Eletrotécnica"),
            ("eletrotécnica.json", "Eletrotécnica"),
            ("radiologia.json", "Radiologia"),
            ("ti.json", "Tecnologia da Informação"),
            ("seguranca_do_trabalho.json", "Segurança do Trabalho"),
            ("tema_novo.json", "Tema Novo"),
            ("meu-tema.json", "Meu Tema"),
            ("C:\\dados\\tema_novo.json", "Tema Novo"),
            ("/tmp/tema_novo.json", "Tema Novo"),
        ],
    )
    def test_nomes(self, entrada, esperado):
        assert formatar_nome_tema(entrada) == esperado


class TestInspecionar:
    def test_banco_valido_devolve_metadados(self, tmp_path):
        arquivo = escrever_banco(tmp_path / "tema_novo.json", tema="Meu Tema")
        info = inspecionar_arquivo_perguntas(str(arquivo))
        assert info == {
            "caminho": str(arquivo.resolve()),
            "arquivo": "tema_novo.json",
            "titulo": "Meu Tema",
            "total": 2,
            "categorias": ["Cat"],
        }

    def test_arquivo_inexistente_devolve_none(self, tmp_path):
        assert inspecionar_arquivo_perguntas(str(tmp_path / "nada.json")) is None

    def test_arquivo_que_nao_e_banco_devolve_none(self, tmp_path):
        arquivo = tmp_path / "config.json"
        arquivo.write_text('{"perguntas": {"pasta": "perguntas"}}', encoding="utf-8")
        assert inspecionar_arquivo_perguntas(str(arquivo)) is None

    def test_texto_invalido_nao_levanta(self, tmp_path):
        arquivo = tmp_path / "lixo.json"
        arquivo.write_text("isto nao e json", encoding="utf-8")
        assert inspecionar_arquivo_perguntas(str(arquivo)) is None


class TestListar:
    def test_lista_so_bancos_validos_em_ordem_de_titulo(self, tmp_path):
        escrever_banco(tmp_path / "radiologia.json")
        escrever_banco(tmp_path / "eletrotecnica.json")
        escrever_banco(tmp_path / "conhecimentos_gerais.json")
        (tmp_path / "config.json").write_text('{"jogo": {}}', encoding="utf-8")
        (tmp_path / "notas.txt").write_text("x", encoding="utf-8")

        infos = listar_arquivos_perguntas(str(tmp_path))

        assert [i["titulo"] for i in infos] == [
            "Conhecimentos Gerais",
            "Eletrotécnica",
            "Radiologia",
        ]

    def test_inclui_subpasta_perguntas_sem_duplicar(self, tmp_path):
        escrever_banco(tmp_path / "raiz.json")
        escrever_banco(tmp_path / "perguntas" / "dentro.json")

        infos = listar_arquivos_perguntas(str(tmp_path))

        assert sorted(i["arquivo"] for i in infos) == ["dentro.json", "raiz.json"]

    def test_diretorio_inexistente_devolve_lista_vazia(self, tmp_path):
        assert listar_arquivos_perguntas(str(tmp_path / "nao_existe")) == []
