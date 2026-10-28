"""
Testes da configuração (`config.py`, Etapa 4.2).

Cobrem a leitura do `config.json` ao lado da aplicação (inclusive o caso
congelado do `.exe`), o fallback para a pasta do script, valores ausentes,
parciais e inválidos, chaves desconhecidas e o comportamento idêntico ao
anterior quando não existe arquivo.

Nada aqui abre janela, porta serial ou áudio.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

import config
from jogo import TODAS_EQUIPES, Jogo

RAIZ = Path(__file__).resolve().parent.parent


class _Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.mensagens = []

    def emit(self, record):
        self.mensagens.append(record.getMessage())


@pytest.fixture
def logs_config():
    logger = logging.getLogger("desafio.config")
    handler = _Captura()
    nivel = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)


@pytest.fixture(autouse=True)
def isolar_fallback(tmp_path, monkeypatch):
    """Impede que o fallback ache um config.json real da pasta do projeto."""
    monkeypatch.setattr(config, "__file__", str(tmp_path / "script" / "config.py"))


def _escrever(tmp_path, dados):
    caminho = tmp_path / "config.json"
    if isinstance(dados, str):
        caminho.write_text(dados, encoding="utf-8")
    else:
        caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


def _carregar(tmp_path, dados=None):
    if dados is not None:
        _escrever(tmp_path, dados)
    return config.carregar(diretorio_base=str(tmp_path))


# ─────────────────────────────────────────────────────────
# Módulo puro e valores em uso
# ─────────────────────────────────────────────────────────
class TestModuloConfig:
    def test_importa_sem_tkinter_serial_ou_pygame(self):
        """Configuração pura: pode ser lida em qualquer ambiente headless."""
        codigo = (
            "import sys; import config; "
            "proibidos = {'tkinter', 'serial', 'pygame'}; "
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

    def test_constantes_espelham_a_configuracao(self):
        assert config.TEMPO_PERGUNTA == config.CONFIG.tempo_pergunta
        assert config.TEMPO_RESPOSTA == config.CONFIG.tempo_resposta
        assert config.PONTUAR_APOS_TEMPO is config.CONFIG.pontuar_apos_tempo
        assert config.NUM_EQUIPES == config.CONFIG.num_equipes
        assert config.NOMES_EQUIPES == config.CONFIG.nomes_equipes
        assert config.PORTA_FORCADA == config.CONFIG.porta_serial
        assert config.TIMEOUT_PRONTO == config.CONFIG.timeout_pronto
        assert config.BAUD_RATE == config.CONFIG.baud_rate
        assert config.PASTA_PERGUNTAS == config.CONFIG.pasta_perguntas
        assert config.ARQUIVO_PERGUNTAS == config.CONFIG.arquivo_perguntas
        assert config.SOM_ATIVO is config.CONFIG.som_ativo
        assert config.AVISOS_CONFIG == config.CONFIG.avisos


# ─────────────────────────────────────────────────────────
# Sem arquivo: comportamento idêntico ao anterior
# ─────────────────────────────────────────────────────────
class TestSemArquivo:
    def test_arquivo_ausente_usa_os_defaults_atuais(self, tmp_path):
        cfg = config.carregar(diretorio_base=str(tmp_path))

        assert cfg.encontrado is False
        assert cfg.caminho_config is None
        assert cfg.avisos == ()
        assert cfg.tempo_pergunta == 30
        assert cfg.tempo_resposta == 15
        assert cfg.pontuar_apos_tempo is False
        assert cfg.num_equipes == 2
        assert cfg.num_equipes_configurado == 2
        assert cfg.nomes_equipes == config.NOMES_EQUIPES_PADRAO
        assert cfg.porta_serial is None
        assert cfg.timeout_pronto == 3.0
        assert cfg.baud_rate == 9600
        assert cfg.pasta_perguntas == str(tmp_path)
        assert cfg.arquivo_perguntas == "conhecimentos_gerais.json"
        assert cfg.som_ativo is True

    def test_comportamento_identico_sem_config_json(self, tmp_path):
        """O Jogo montado com os defaults não muda em relação à versão 4.1."""
        cfg = config.carregar(diretorio_base=str(tmp_path))

        jogo = Jogo(
            [],
            num_equipes=cfg.num_equipes,
            tempo_pergunta=cfg.tempo_pergunta,
            tempo_resposta=cfg.tempo_resposta,
            pontuar_apos_tempo=cfg.pontuar_apos_tempo,
            nomes_equipes=dict(cfg.nomes_equipes),
        )

        assert jogo.num_equipes == 2
        assert jogo.tempo_pergunta == 30
        assert jogo.tempo_resposta == 15
        assert jogo.pontuar_apos_tempo is False
        assert jogo.nomes_equipes["A"] == "Competidor A"
        assert jogo.nomes_equipes["B"] == "Competidor B"


# ─────────────────────────────────────────────────────────
# Leitura e tolerância a arquivo inválido
# ─────────────────────────────────────────────────────────
class TestLeitura:
    def test_config_completo_e_aplicado(self, tmp_path):
        (tmp_path / "perguntas").mkdir()
        cfg = _carregar(
            tmp_path,
            {
                "tempos": {"tempo_pergunta": 45, "tempo_resposta": 20},
                "jogo": {"num_equipes": 2, "pontuar_apos_tempo": True},
                "nomes_equipes": {"A": "Time Azul", "B": "Time Laranja"},
                "serial": {
                    "porta": "COM5",
                    "baud_rate": 19200,
                    "timeout_pronto": 4.5,
                },
                "perguntas": {
                    "pasta": "perguntas",
                    "arquivo_padrao": "meu_banco.json",
                },
                "audio": {"ativo": False},
            },
        )

        assert cfg.avisos == ()
        assert cfg.tempo_pergunta == 45
        assert cfg.tempo_resposta == 20
        assert cfg.pontuar_apos_tempo is True
        assert cfg.num_equipes == 2
        assert cfg.nomes_equipes["A"] == "Time Azul"
        assert cfg.nomes_equipes["B"] == "Time Laranja"
        assert cfg.nomes_equipes["C"] == "Competidor C"
        assert cfg.porta_serial == "COM5"
        assert cfg.baud_rate == 19200
        assert cfg.timeout_pronto == 4.5
        assert cfg.pasta_perguntas == str(tmp_path / "perguntas")
        assert cfg.arquivo_perguntas == "meu_banco.json"
        assert cfg.som_ativo is False
        assert cfg.encontrado is True
        assert Path(cfg.caminho_config) == tmp_path / "config.json"

    def test_valores_parciais_completam_com_os_padroes(self, tmp_path):
        cfg = _carregar(tmp_path, {"tempos": {"tempo_pergunta": 45}})

        assert cfg.tempo_pergunta == 45
        assert cfg.tempo_resposta == 15
        assert cfg.num_equipes == 2
        assert cfg.nomes_equipes == config.NOMES_EQUIPES_PADRAO
        assert cfg.avisos == ()

    def test_arquivo_vazio_usa_padroes(self, tmp_path):
        cfg = _carregar(tmp_path, "")

        assert cfg.tempo_pergunta == 30
        assert cfg.avisos
        assert "config.json inválido" in cfg.avisos[0]

    def test_json_invalido_nao_derruba_o_app(self, tmp_path, logs_config):
        cfg = _carregar(tmp_path, '{"tempos": ')

        assert cfg.tempo_pergunta == 30
        assert cfg.num_equipes == 2
        assert cfg.avisos
        assert any("config.json inválido" in m for m in logs_config.mensagens)

    def test_json_que_nao_e_objeto_usa_padroes(self, tmp_path):
        cfg = _carregar(tmp_path, "[]")

        assert cfg.tempo_pergunta == 30
        assert cfg.avisos
        assert "objeto JSON" in cfg.avisos[0]

    def test_secao_com_tipo_errado_usa_padroes(self, tmp_path):
        cfg = _carregar(tmp_path, {"tempos": 30, "serial": "COM5"})

        assert cfg.tempo_pergunta == 30
        assert cfg.porta_serial is None
        assert len(cfg.avisos) == 2


class TestChavesDesconhecidas:
    def test_chave_desconhecida_gera_warning_sem_aviso_na_tela(
        self, tmp_path, logs_config
    ):
        cfg = _carregar(
            tmp_path,
            {
                "extra": 1,
                "tempos": {"foo": 2, "tempo_pergunta": 30},
                "nomes_equipes": {"E": "Time E"},
            },
        )

        assert cfg.avisos == ()
        mensagens = "\n".join(logs_config.mensagens)
        assert "extra" in mensagens
        assert "tempos.foo" in mensagens
        assert "nomes_equipes.E" in mensagens


# ─────────────────────────────────────────────────────────
# Validação de valores
# ─────────────────────────────────────────────────────────
class TestValidacao:
    @pytest.mark.parametrize(
        "dados, atributo, esperado",
        [
            ({"tempos": {"tempo_pergunta": 0}}, "tempo_pergunta", 30),
            ({"tempos": {"tempo_resposta": -5}}, "tempo_resposta", 15),
            ({"tempos": {"tempo_pergunta": "30"}}, "tempo_pergunta", 30),
            ({"tempos": {"tempo_pergunta": True}}, "tempo_pergunta", 30),
            ({"tempos": {"tempo_pergunta": 1.5}}, "tempo_pergunta", 30),
            ({"jogo": {"num_equipes": 1}}, "num_equipes", 2),
            ({"jogo": {"num_equipes": 5}}, "num_equipes", 2),
            ({"jogo": {"num_equipes": "3"}}, "num_equipes", 2),
            ({"jogo": {"pontuar_apos_tempo": "sim"}}, "pontuar_apos_tempo", False),
            ({"jogo": {"pontuar_apos_tempo": 0}}, "pontuar_apos_tempo", False),
            ({"audio": {"ativo": 1}}, "som_ativo", True),
            ({"audio": {"ativo": "sim"}}, "som_ativo", True),
            ({"serial": {"baud_rate": 0}}, "baud_rate", 9600),
            ({"serial": {"baud_rate": 3000000}}, "baud_rate", 9600),
            ({"serial": {"baud_rate": "9600"}}, "baud_rate", 9600),
            ({"serial": {"timeout_pronto": 0}}, "timeout_pronto", 3.0),
            ({"serial": {"timeout_pronto": "3"}}, "timeout_pronto", 3.0),
            ({"serial": {"timeout_pronto": True}}, "timeout_pronto", 3.0),
            ({"serial": {"porta": "ttyUSB0"}}, "porta_serial", None),
            ({"serial": {"porta": "COM"}}, "porta_serial", None),
            ({"serial": {"porta": 3}}, "porta_serial", None),
            ({"perguntas": {"arquivo_padrao": "sub/x.json"}}, "arquivo_perguntas", "conhecimentos_gerais.json"),
            ({"perguntas": {"arquivo_padrao": "x.txt"}}, "arquivo_perguntas", "conhecimentos_gerais.json"),
            ({"perguntas": {"arquivo_padrao": 10}}, "arquivo_perguntas", "conhecimentos_gerais.json"),
        ],
    )
    def test_valor_invalido_volta_ao_padrao(
        self, tmp_path, logs_config, dados, atributo, esperado
    ):
        cfg = _carregar(tmp_path, dados)

        assert getattr(cfg, atributo) == esperado
        assert cfg.avisos
        assert logs_config.mensagens

    def test_nomes_invalidos_voltam_ao_padrao(self, tmp_path, logs_config):
        cfg = _carregar(
            tmp_path,
            {
                "nomes_equipes": {
                    "A": "",
                    "B": "   ",
                    "C": "x" * 25,
                    "D": 42,
                }
            },
        )

        assert cfg.nomes_equipes == config.NOMES_EQUIPES_PADRAO
        assert len(cfg.avisos) == 4
        assert len(logs_config.mensagens) == 4

    def test_nomes_validos_sao_aparados(self, tmp_path):
        cfg = _carregar(
            tmp_path,
            {"nomes_equipes": {"A": "  Azul  ", "B": "Laranja"}},
        )

        assert cfg.nomes_equipes["A"] == "Azul"
        assert cfg.nomes_equipes["B"] == "Laranja"
        assert cfg.avisos == ()

    @pytest.mark.parametrize(
        "valor, esperado",
        [
            ("auto", None),
            ("AUTO", None),
            (None, None),
            ("com5", "COM5"),
            ("1a86:7523", "1A86:7523"),
            ("2341:0043", "2341:0043"),
        ],
    )
    def test_formatos_validos_de_porta(self, tmp_path, valor, esperado):
        cfg = _carregar(tmp_path, {"serial": {"porta": valor}})

        assert cfg.porta_serial == esperado
        assert cfg.avisos == ()

    def test_num_equipes_3_ou_4_avisa_e_mantem_ui_com_2(
        self, tmp_path, logs_config
    ):
        for pedido in (3, 4):
            cfg = _carregar(tmp_path, {"jogo": {"num_equipes": pedido}})

            assert cfg.num_equipes == 2
            assert cfg.num_equipes_configurado == pedido
            assert any("Etapa 5" in aviso for aviso in cfg.avisos)

    @pytest.mark.parametrize("pedido", [2, 3, 4])
    def test_num_equipes_na_faixa_e_aceito(self, tmp_path, pedido):
        cfg = _carregar(tmp_path, {"jogo": {"num_equipes": pedido}})

        assert cfg.num_equipes_configurado == pedido
        assert not [
            a for a in cfg.avisos if "valor inválido" in a
        ]


# ─────────────────────────────────────────────────────────
# Pasta/arquivo de perguntas
# ─────────────────────────────────────────────────────────
class TestPerguntas:
    def test_pasta_relativa_existente(self, tmp_path):
        (tmp_path / "perguntas").mkdir()
        cfg = _carregar(tmp_path, {"perguntas": {"pasta": "perguntas"}})

        assert cfg.pasta_perguntas == str(tmp_path / "perguntas")
        assert cfg.avisos == ()

    def test_pasta_absoluta_existente(self, tmp_path):
        pasta = tmp_path / "banco"
        pasta.mkdir()
        cfg = _carregar(tmp_path, {"perguntas": {"pasta": str(pasta)}})

        assert cfg.pasta_perguntas == str(pasta)
        assert cfg.avisos == ()

    def test_pasta_inexistente_volta_para_a_base(self, tmp_path):
        cfg = _carregar(tmp_path, {"perguntas": {"pasta": "naoexiste"}})

        assert cfg.pasta_perguntas == str(tmp_path)
        assert any("não encontrada" in aviso for aviso in cfg.avisos)

    def test_pasta_invalida_volta_para_a_base(self, tmp_path):
        cfg = _carregar(tmp_path, {"perguntas": {"pasta": 123}})

        assert cfg.pasta_perguntas == str(tmp_path)
        assert cfg.avisos

    def test_caminho_padrao_junta_pasta_e_arquivo(self, tmp_path):
        cfg = _carregar(tmp_path, {"perguntas": {"arquivo_padrao": "x.json"}})

        assert cfg.caminho_perguntas_padrao == str(tmp_path / "x.json")


# ─────────────────────────────────────────────────────────
# Localização: .exe congelado e fallback do script
# ─────────────────────────────────────────────────────────
class TestLocalizacao:
    def test_executavel_congelado_le_config_ao_lado_do_exe(
        self, tmp_path, monkeypatch
    ):
        caminho = _escrever(tmp_path, {"tempos": {"tempo_pergunta": 45}})
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "Desafio.exe"))

        cfg = config.carregar()

        assert cfg.encontrado is True
        assert cfg.caminho_config == str(caminho)
        assert cfg.tempo_pergunta == 45

    def test_fallback_para_a_pasta_do_script(self, tmp_path, monkeypatch):
        script = tmp_path / "script"
        script.mkdir()
        caminho = script / "config.json"
        caminho.write_text(
            json.dumps({"tempos": {"tempo_resposta": 25}}), encoding="utf-8"
        )
        monkeypatch.setattr(config, "__file__", str(script / "config.py"))

        cfg = config.carregar(diretorio_base=str(tmp_path / "exe"))

        assert cfg.caminho_config == str(caminho)
        assert cfg.tempo_resposta == 25

    def test_sem_arquivo_em_lugar_nenhum_usa_padroes(self, tmp_path):
        cfg = config.carregar(diretorio_base=str(tmp_path))

        assert cfg.encontrado is False
        assert cfg.caminho_config is None


class TestExemploECriacao:
    def test_config_exemplo_do_projeto_e_valido(self):
        cfg = config.carregar(
            caminho=str(RAIZ / "config.exemplo.json"),
            diretorio_base=str(RAIZ),
        )

        assert cfg.encontrado is True
        assert cfg.avisos == ()
        assert cfg.tempo_pergunta == 30
        assert cfg.pasta_perguntas == str(RAIZ)

    def test_criar_config_exemplo(self, tmp_path):
        assert config.criar_config_exemplo(diretorio_base=str(tmp_path)) is True
        destino = tmp_path / "config.json"
        assert destino.is_file()

        assert config.criar_config_exemplo(diretorio_base=str(tmp_path)) is False

        cfg = config.carregar(diretorio_base=str(tmp_path))
        assert cfg.encontrado is True
        assert cfg.avisos == ()

    def test_texto_avisos_e_simples(self):
        texto = config.texto_avisos(["um problema", "outro problema"])

        assert texto.startswith("Configuração:")
        assert "• um problema" in texto
        assert "• outro problema" in texto


# ─────────────────────────────────────────────────────────
# Ligação com o resto do app
# ─────────────────────────────────────────────────────────
class TestLigacaoComJogo:
    def test_jogo_aceita_a_configuracao_do_app(self):
        jogo = Jogo(
            [],
            num_equipes=config.NUM_EQUIPES,
            tempo_pergunta=config.TEMPO_PERGUNTA,
            tempo_resposta=config.TEMPO_RESPOSTA,
            pontuar_apos_tempo=config.PONTUAR_APOS_TEMPO,
            nomes_equipes=dict(config.NOMES_EQUIPES),
        )
        assert jogo.num_equipes == config.NUM_EQUIPES
        assert jogo.tempo_pergunta == config.TEMPO_PERGUNTA
        assert jogo.tempo_resposta == config.TEMPO_RESPOSTA
        assert jogo.pontuar_apos_tempo is config.PONTUAR_APOS_TEMPO
        assert jogo.nomes_equipes == config.NOMES_EQUIPES
        assert set(config.NOMES_EQUIPES) == set(TODAS_EQUIPES)


class TestUiUsaConfig:
    """A UI não pode manter uma segunda cópia dos valores."""

    def test_desafio_reexporta_os_mesmos_valores(self):
        desafio = pytest.importorskip("desafio")

        assert desafio.TITULO == config.TITULO
        assert desafio.ARQUIVO_PERGUNTAS == config.ARQUIVO_PERGUNTAS
        assert desafio.PASTA_PERGUNTAS == config.PASTA_PERGUNTAS
        assert desafio.TEMPO_PERGUNTA == config.TEMPO_PERGUNTA
        assert desafio.TEMPO_RESPOSTA == config.TEMPO_RESPOSTA
        assert desafio.PONTUAR_APOS_TEMPO == config.PONTUAR_APOS_TEMPO
        assert desafio.SOM_ATIVO == config.SOM_ATIVO
        assert desafio.NOME_A == config.NOMES_EQUIPES["A"]
        assert desafio.NOME_B == config.NOMES_EQUIPES["B"]

    def test_serial_comm_usa_os_mesmos_valores(self):
        """A serial saiu da UI na Etapa 3.4: os valores vêm de config.py."""
        serial_comm = pytest.importorskip("serial_comm")

        assert serial_comm.BAUD_RATE == config.BAUD_RATE
        assert serial_comm.PORTA_FORCADA == config.PORTA_FORCADA
        assert serial_comm.TIMEOUT_HANDSHAKE == config.TIMEOUT_PRONTO


class TestArquivoInicial:
    """O `perguntas.arquivo_padrao` preseleciona o tema na abertura."""

    @staticmethod
    def _arquivos(tmp_path):
        return [
            {"caminho": str(tmp_path / "a.json"), "titulo": "a"},
            {
                "caminho": str(tmp_path / "conhecimentos_gerais.json"),
                "titulo": "cg",
            },
        ]

    def test_prefere_o_arquivo_atual(self, tmp_path):
        desafio = pytest.importorskip("desafio")
        arquivos = self._arquivos(tmp_path)

        escolhido = desafio.escolher_arquivo_inicial(
            arquivos,
            arquivos[0]["caminho"],
            str(tmp_path),
            "conhecimentos_gerais.json",
        )

        assert escolhido["titulo"] == "a"

    def test_usa_o_padrao_quando_nao_ha_arquivo_atual(self, tmp_path):
        desafio = pytest.importorskip("desafio")
        arquivos = self._arquivos(tmp_path)

        escolhido = desafio.escolher_arquivo_inicial(
            arquivos, None, str(tmp_path), "conhecimentos_gerais.json"
        )

        assert escolhido["titulo"] == "cg"

    def test_cai_no_primeiro_quando_o_padrao_nao_existe(self, tmp_path):
        desafio = pytest.importorskip("desafio")
        arquivos = self._arquivos(tmp_path)

        escolhido = desafio.escolher_arquivo_inicial(
            arquivos, None, str(tmp_path), "nao_existe.json"
        )

        assert escolhido["titulo"] == "a"

    def test_lista_vazia_devolve_none(self, tmp_path):
        desafio = pytest.importorskip("desafio")

        escolhido = desafio.escolher_arquivo_inicial(
            [], None, str(tmp_path), "x.json"
        )

        assert escolhido is None
