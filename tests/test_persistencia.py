"""Testes da persistência da partida (Etapa 4.3), sem display."""

import errno
import json
import logging
from pathlib import Path

import pytest

import persistencia
from jogo import Jogo
from perguntas import Pergunta


class _Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.mensagens = []

    def emit(self, record):
        self.mensagens.append(record.getMessage())


@pytest.fixture
def logs_persistencia():
    logger = logging.getLogger("desafio.persistencia")
    handler = _Captura()
    nivel = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)


def _escrever_banco(tmp_path, quantidade=6, nome="banco.json"):
    caminho = tmp_path / nome
    dados = [
        {
            "categoria": "Teste",
            "pergunta": f"Pergunta {i}?",
            "alternativas": ["Certa", "Errada"],
            "correta": 0,
            "explicacao": f"Explic {i}",
        }
        for i in range(quantidade)
    ]
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


def _perguntas(quantidade=6):
    return [
        Pergunta("Teste", f"Pergunta {i}?", ["Certa", "Errada"], 0)
        for i in range(quantidade)
    ]


def _jogo(quantidade=6, num_equipes=2):
    return Jogo(
        _perguntas(quantidade),
        num_equipes=num_equipes,
        tempo_pergunta=30,
        tempo_resposta=15,
        nomes_equipes={
            "A": "Azul",
            "B": "Laranja",
            "C": "Ciano",
            "D": "Rosa",
        },
    )


def _salvar_estado(tmp_path, quantidade=6, num_equipes=2, tema="Tema Teste"):
    banco = _escrever_banco(tmp_path, quantidade)
    jogo = _jogo(quantidade, num_equipes)
    jogo.placar["A"] = 2
    jogo.placar["B"] = 1
    if num_equipes > 2:
        jogo.placar["C"] = 1
    estado = tmp_path / persistencia.NOME_ARQUIVO
    caminho = persistencia.salvar(jogo, tema, str(banco), caminho=str(estado))
    assert caminho == str(estado)
    return banco, jogo, estado


def _dados_estado(estado):
    return json.loads(Path(estado).read_text(encoding="utf-8"))


class TestGravacao:
    def test_salva_de_forma_atomica_e_versionada(self, tmp_path):
        banco = _escrever_banco(tmp_path)
        jogo = _jogo()
        estado = tmp_path / persistencia.NOME_ARQUIVO

        caminho = persistencia.salvar(
            jogo, "Tema Teste", str(banco), caminho=str(estado)
        )

        assert caminho == str(estado)
        assert estado.is_file()
        assert not Path(str(estado) + ".tmp").exists()
        dados = _dados_estado(estado)
        assert dados["versao"] == persistencia.VERSAO_FORMATO
        assert dados["tema"] == "Tema Teste"
        assert dados["arquivo"] == "banco.json"
        assert dados["total_perguntas"] == len(jogo.perguntas_base)
        assert dados["jogo"]["ordem"] == jogo.to_dict()["ordem"]

    @pytest.mark.parametrize("codigo", [errno.ENOSPC, errno.EACCES])
    def test_falha_de_gravacao_nao_derruba_nem_deixa_tmp(
        self, tmp_path, monkeypatch, logs_persistencia, codigo
    ):
        banco = _escrever_banco(tmp_path)
        estado = tmp_path / persistencia.NOME_ARQUIVO

        def falhar(*args, **kwargs):
            raise OSError(codigo, "falha simulada")

        monkeypatch.setattr(persistencia.os, "replace", falhar)

        resultado = persistencia.salvar(
            _jogo(), "Tema", str(banco), caminho=str(estado)
        )

        assert resultado is None
        assert not estado.exists()
        assert not Path(str(estado) + ".tmp").exists()
        assert any("Não foi possível gravar" in m for m in logs_persistencia.mensagens)

    def test_salvar_sem_pergunta_atual_nao_grava(self, tmp_path):
        banco = _escrever_banco(tmp_path)
        jogo = _jogo()
        jogo.recarregar_perguntas(_perguntas())
        estado = tmp_path / persistencia.NOME_ARQUIVO

        assert persistencia.salvar(
            jogo, "Tema", str(banco), caminho=str(estado)
        ) is None
        assert not estado.exists()

    def test_remove_estado(self, tmp_path):
        _, _, estado = _salvar_estado(tmp_path)

        assert persistencia.remover_estado(caminho=str(estado)) is True
        assert not estado.exists()
        assert persistencia.remover_estado(caminho=str(estado)) is False

    def test_fallback_para_pasta_do_script(self, tmp_path, monkeypatch):
        script = tmp_path / "script"
        script.mkdir()
        monkeypatch.setattr(persistencia, "__file__", str(script / "persistencia.py"))
        banco = _escrever_banco(tmp_path)
        app_que_nao_e_pasta = tmp_path / "arquivo"
        app_que_nao_e_pasta.write_text("x", encoding="utf-8")

        caminho = persistencia.salvar(
            _jogo(),
            "Tema",
            str(banco),
            diretorio_base=str(app_que_nao_e_pasta),
        )

        assert caminho == str(script / persistencia.NOME_ARQUIVO)
        assert Path(caminho).is_file()
        assert persistencia.localizar_estado(str(app_que_nao_e_pasta)) == caminho


class TestCarga:
    def test_ida_e_volta_completa(self, tmp_path):
        banco, jogo, estado = _salvar_estado(tmp_path)
        dados = _dados_estado(estado)

        resultado = persistencia.carregar(
            str(tmp_path), caminho=str(estado)
        )

        assert resultado.motivo == ""
        assert resultado.partida is not None
        partida = resultado.partida
        assert partida.tema == "Tema Teste"
        assert partida.arquivo == "banco.json"
        assert Path(partida.caminho_perguntas) == Path(banco).resolve()
        assert partida.jogo.placar == {"A": 2, "B": 1}
        assert partida.jogo.estado.indice_pergunta == jogo.estado.indice_pergunta
        assert partida.jogo.estado.numero_pergunta == jogo.estado.numero_pergunta
        assert partida.jogo.estado.fase == 0
        assert partida.jogo.timer_restante() > 0
        assert partida.jogo.timer_rotulo == "Tempo para apertar"
        esperado = [partida.jogo.perguntas_base[i].texto for i in dados["jogo"]["ordem"]]
        assert [p.texto for p in partida.jogo.perguntas] == esperado
        assert "Tema: Tema Teste" in partida.resumo
        assert "Azul 2 x 1 Laranja" in partida.resumo

    def test_configuracao_atual_substitui_nomes_e_tempos(self, tmp_path):
        _, _, estado = _salvar_estado(tmp_path)

        resultado = persistencia.carregar(
            str(tmp_path),
            caminho=str(estado),
            nomes_equipes={"A": "Novo A", "B": "Novo B"},
            tempo_pergunta=45,
            tempo_resposta=12,
        )

        partida = resultado.partida
        assert partida is not None
        assert partida.jogo.nomes_equipes["A"] == "Novo A"
        assert partida.jogo.nomes_equipes["B"] == "Novo B"
        assert partida.jogo.tempo_pergunta == 45
        assert partida.jogo.tempo_resposta == 12
        assert partida.jogo.timer_restante() > 0

    def test_estado_ausente_nao_gera_aviso(self, tmp_path, logs_persistencia):
        resultado = persistencia.carregar(
            str(tmp_path), caminho=str(tmp_path / "nao_existe.json")
        )

        assert resultado.partida is None
        assert resultado.motivo == ""
        assert logs_persistencia.mensagens == []

    @pytest.mark.parametrize("conteudo", ["", "{", "[]"])
    def test_arquivo_vazio_corrompido_ou_nao_objeto(
        self, tmp_path, logs_persistencia, conteudo
    ):
        estado = tmp_path / persistencia.NOME_ARQUIVO
        estado.write_text(conteudo, encoding="utf-8")

        resultado = persistencia.carregar(
            str(tmp_path), caminho=str(estado)
        )

        assert resultado.partida is None
        assert resultado.motivo
        assert logs_persistencia.mensagens

    def test_versao_desconhecida(self, tmp_path, logs_persistencia):
        _, _, estado = _salvar_estado(tmp_path)
        dados = _dados_estado(estado)
        dados["versao"] = 999
        estado.write_text(json.dumps(dados), encoding="utf-8")

        resultado = persistencia.carregar(str(tmp_path), caminho=str(estado))

        assert resultado.partida is None
        assert "versão" in resultado.motivo
        assert logs_persistencia.mensagens

    def test_tema_removido(self, tmp_path, logs_persistencia):
        banco, _, estado = _salvar_estado(tmp_path)
        banco.unlink()

        resultado = persistencia.carregar(str(tmp_path), caminho=str(estado))

        assert resultado.partida is None
        assert "não existe mais" in resultado.motivo
        assert logs_persistencia.mensagens

    def test_total_de_perguntas_diferente(self, tmp_path, logs_persistencia):
        banco, _, estado = _salvar_estado(tmp_path)
        _escrever_banco(tmp_path, quantidade=5)

        resultado = persistencia.carregar(str(tmp_path), caminho=str(estado))

        assert resultado.partida is None
        assert "5" in resultado.motivo and "6" in resultado.motivo
        assert logs_persistencia.mensagens

    @pytest.mark.parametrize(
        "alteracao, trecho",
        [
            (lambda d: d["jogo"].update({"ordem": [0, 0, 1, 2, 3, 4]}), "ordem"),
            (lambda d: d["jogo"].update({"indice_pergunta": 0}), "índice"),
            (lambda d: d["jogo"].update({"placar": {"A": -1}}), "placar"),
            (lambda d: d["jogo"].update({"numero_pergunta": 0}), "rodada"),
        ],
    )
    def test_estrutura_invalida(self, tmp_path, logs_persistencia, alteracao, trecho):
        _, _, estado = _salvar_estado(tmp_path)
        dados = _dados_estado(estado)
        alteracao(dados)
        estado.write_text(json.dumps(dados), encoding="utf-8")

        resultado = persistencia.carregar(str(tmp_path), caminho=str(estado))

        assert resultado.partida is None
        assert trecho in resultado.motivo
        assert logs_persistencia.mensagens

    def test_resumo_com_nomes_placar_e_rodada(self):
        dados = {
            "tema": "Radiologia",
            "jogo": {
                "placar": {"A": 2, "B": 1},
                "nomes_equipes": {"A": "Azul", "B": "Laranja"},
                "numero_pergunta": 7,
            },
        }

        assert persistencia.resumo_partida(dados) == (
            "Tema: Radiologia\n"
            "Placar: Azul 2 x 1 Laranja\n"
            "Rodada: 7"
        )


class TestAgendador:
    def test_debounce_cancela_anterior_e_grava_uma_vez(self):
        agendados = []
        cancelados = []
        salvos = []

        def agendar(atraso, funcao):
            agendados.append((atraso, funcao))
            return len(agendados)

        def cancelar(job):
            cancelados.append(job)

        agendador = persistencia.AgendadorSalvamento(
            lambda: salvos.append("salvo"),
            agendar,
            cancelar,
            atraso_ms=250,
        )

        agendador.pedir()
        agendador.pedir()

        assert len(agendados) == 2
        assert agendados[0][0] == 250
        assert cancelados == [1]
        assert agendador.pendente is True

        agendados[-1][1]()
        assert salvos == ["salvo"]
        assert agendador.pendente is False

        agendador.pedir()
        agendador.executar_agora()
        assert cancelados == [1, 3]
        assert salvos == ["salvo", "salvo"]
        assert agendador.pendente is False
