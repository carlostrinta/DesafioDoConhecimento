"""
Testes de `config.py` (Etapa 3.1): constantes centralizadas, sem I/O.

Nesta etapa o módulo apenas concentra valores que estavam em `desafio.py`;
ele ainda não lê `config.json` (isso é a Etapa 4.2).
"""

import subprocess
import sys
from pathlib import Path

import pytest

import config
from jogo import TODAS_EQUIPES, Jogo


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
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert saida.returncode == 0, saida.stderr

    def test_nao_le_config_json(self):
        """Sem leitura de arquivo nesta etapa: os valores são literais."""
        origem = (Path(__file__).resolve().parent.parent / "config.py").read_text(
            encoding="utf-8"
        )
        assert "open(" not in origem
        assert "import json" not in origem


class TestValoresAtuais:
    def test_equipes(self):
        assert config.NUM_EQUIPES == 2
        assert set(config.NOMES_EQUIPES) == set(TODAS_EQUIPES[: config.NUM_EQUIPES])
        assert all(nome.strip() for nome in config.NOMES_EQUIPES.values())

    def test_tempos_sao_positivos(self):
        assert config.TEMPO_PERGUNTA > 0
        assert config.TEMPO_RESPOSTA > 0

    def test_banco_padrao_e_um_json(self):
        assert config.ARQUIVO_PERGUNTAS.endswith(".json")

    def test_serial(self):
        assert config.BAUD_RATE > 0
        assert config.PORTA_FORCADA is None  # autodetectar


class TestLigacaoComJogo:
    def test_jogo_aceita_a_configuracao_do_app(self):
        """A UI monta o Jogo só com valores de config.py."""
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


class TestUiUsaConfig:
    """A UI não pode manter uma segunda cópia dos valores."""

    def test_desafio_reexporta_os_mesmos_valores(self):
        desafio = pytest.importorskip("desafio")

        assert desafio.TITULO == config.TITULO
        assert desafio.ARQUIVO_PERGUNTAS == config.ARQUIVO_PERGUNTAS
        assert desafio.TEMPO_PERGUNTA == config.TEMPO_PERGUNTA
        assert desafio.TEMPO_RESPOSTA == config.TEMPO_RESPOSTA
        assert desafio.PONTUAR_APOS_TEMPO == config.PONTUAR_APOS_TEMPO
        assert desafio.NOME_A == config.NOMES_EQUIPES["A"]
        assert desafio.NOME_B == config.NOMES_EQUIPES["B"]

    def test_serial_comm_usa_os_mesmos_valores(self):
        """A serial saiu da UI na Etapa 3.4: os valores vêm de config.py."""
        serial_comm = pytest.importorskip("serial_comm")

        assert serial_comm.BAUD_RATE == config.BAUD_RATE
        assert serial_comm.PORTA_FORCADA == config.PORTA_FORCADA
