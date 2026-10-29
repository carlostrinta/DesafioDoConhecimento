"""Testes de carregamento, validação e embaralhamento de perguntas."""
import pytest
import tempfile
import os
import json
from jogo import Jogo
from perguntas import Pergunta, carregar_perguntas_json


class TestCarregamentoPerguntas:
    def test_carrega_json_lista_direta(self, perguntas_exemplo):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([p.__dict__ for p in perguntas_exemplo], f, ensure_ascii=False)
            tmp = f.name
        try:
            carregadas = carregar_perguntas_json(tmp)
            assert len(carregadas) == 3
            assert carregadas[0].categoria == "Cat1"
            assert carregadas[0].correta == 0
        finally:
            os.unlink(tmp)

    def test_carrega_json_com_chave_perguntas(self, perguntas_exemplo):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"tema": "Teste", "perguntas": [p.__dict__ for p in perguntas_exemplo]}, f, ensure_ascii=False)
            tmp = f.name
        try:
            carregadas = carregar_perguntas_json(tmp)
            assert len(carregadas) == 3
        finally:
            os.unlink(tmp)

    def test_rejeita_alternativas_menos_2(self):
        dados = [{"categoria": "X", "pergunta": "P?", "alternativas": ["A"], "correta": 0}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(dados, f)
            tmp = f.name
        try:
            carregadas = carregar_perguntas_json(tmp)
            assert len(carregadas) == 0
        finally:
            os.unlink(tmp)

    def test_rejeita_alternativas_mais_4(self):
        dados = [{"categoria": "X", "pergunta": "P?", "alternativas": ["A","B","C","D","E"], "correta": 0}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(dados, f)
            tmp = f.name
        try:
            carregadas = carregar_perguntas_json(tmp)
            assert len(carregadas) == 0
        finally:
            os.unlink(tmp)

    def test_rejeita_correta_fora_intervalo(self):
        dados = [{"categoria": "X", "pergunta": "P?", "alternativas": ["A","B"], "correta": 5}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(dados, f)
            tmp = f.name
        try:
            carregadas = carregar_perguntas_json(tmp)
            assert len(carregadas) == 0
        finally:
            os.unlink(tmp)

    def test_embaralha_na_carga(self, perguntas_exemplo, monkeypatch):
        # Determinístico: troca o shuffle por uma inversão de ordem
        monkeypatch.setattr("jogo.random.shuffle", lambda seq: seq.reverse())
        original = [p.texto for p in perguntas_exemplo]

        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)

        assert [p.texto for p in j.perguntas] == list(reversed(original))
        # A lista recebida não é alterada no lugar (o Jogo trabalha numa cópia)
        assert [p.texto for p in perguntas_exemplo] == original

    def test_reinicia_banco_ao_final(self, perguntas_exemplo):
        j = Jogo(perguntas_exemplo, num_equipes=2, contagem_largada=0)
        total = len(j.perguntas)
        # Avança total + 2 vezes: __init__ já fez 1 próxima, então loop roda total+2 vezes
        for _ in range(total + 2):
            j.apertar_botao("A")
            j.revelar_resposta()
            j.confirmar_acerto("A")
            j.proxima_pergunta()
        # Após total+2 chamadas de proxima_pergunta (índice inicial 1 + total+2):
        #   índice = 1 + (total+2) = total+3, com resets a cada total
        #   para total=3: índice final = 1+5=6 -> resets em 3 e 6 -> índice 0
        #   mas o reset ocorre ANTES de usar o índice, então após usar índice 2 (último),
        #   o próximo incremento deixa índice=3 (>=3), pronto para reset na próxima chamada
        assert j.estado.indice_pergunta == 3  # pronto para reset na próxima chamada
        assert j.estado.numero_pergunta == total + 3  # 1 inicial + total+2 no loop