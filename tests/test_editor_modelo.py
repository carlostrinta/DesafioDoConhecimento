"""Testes headless do modelo e da gravação segura do editor (E1)."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path

import pytest

import editor_modelo as em
import perguntas
import persistencia


def _q(
    texto: str = "Qual é a resposta correta?",
    alternativas=None,
    correta: int = 0,
    categoria: str = "Geral",
    explicacao: str = "",
    **extras,
) -> dict:
    dados = {
        "pergunta": texto,
        "alternativas": ["Alternativa A", "Alternativa B"]
        if alternativas is None
        else alternativas,
        "correta": correta,
        "categoria": categoria,
        "explicacao": explicacao,
    }
    dados.update(extras)
    return dados


def _escrever(caminho: Path, dados) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return caminho


def _banco_lista(tmp_path: Path, perguntas_dados=None, nome="banco.json") -> Path:
    dados = perguntas_dados or [
        _q("Primeira pergunta?", categoria="Cat A"),
        _q("Segunda pergunta?", alternativas=["C", "D"], correta=1, categoria="Cat B"),
        _q("Terceira pergunta?", categoria="Cat A", explicacao="Explicação"),
    ]
    return _escrever(tmp_path / nome, dados)


def _banco_envelope(tmp_path: Path, nome="envelope.json", extras=None) -> Path:
    dados = {
        "versao_formato": 1,
        "tema": "Tema de Teste",
        "autor": "Carlos",
        "licenca": "CC BY 4.0",
        "perguntas": [
            _q("Pergunta do envelope?", categoria="Cat", resposta_extra="x"),
        ],
    }
    if extras:
        dados.update(extras)
    return _escrever(tmp_path / nome, dados)


def _banco_editavel(tmp_path: Path, nome="banco.json") -> em.BancoEditavel:
    return em.carregar_banco(str(_banco_lista(tmp_path, nome=nome)))


# ─────────────────────────────────────────────────────────
# Validação
# ─────────────────────────────────────────────────────────
class TestValidacao:
    def test_pergunta_valida_sem_erros(self):
        assert perguntas.validar_pergunta(_q()) == []

    @pytest.mark.parametrize(
        "dados, trecho",
        [
            (_q(texto=""), "Escreva o enunciado"),
            (_q(texto="abc"), "pelo menos 5"),
            (_q(texto="x" * 501), "limite de 500"),
            (_q(alternativas=["A"]), "pelo menos 2"),
            (_q(alternativas=["A", "B", "C", "D", "E"]), "no máximo 4"),
            (_q(alternativas=["A", ""]), "alternativa 2 está vazia"),
            (_q(alternativas=["A", "x" * 301]), "limite de 300"),
            (_q(correta=2), "correta válida"),
            (_q(correta=-1), "correta válida"),
            (_q(correta="0"), "correta válida"),
            (_q(categoria=""), "Informe a categoria"),
            (_q(categoria="x" * 81), "limite de 80"),
            (_q(categoria=1), "categoria deve ser um texto"),
            (_q(explicacao="x" * 1001), "limite de 1.000"),
            (_q(explicacao=1), "explicação deve ser um texto"),
            (_q(alternativas="A,B"), "Informe as alternativas"),
            (_q(alternativas=["A", 2]), "alternativa 2 deve ser um texto"),
            (_q(texto=123), "enunciado deve ser um texto"),
        ],
    )
    def test_campos_invalidos(self, dados, trecho):
        erros = perguntas.validar_pergunta(dados)
        assert any(trecho in erro.mensagem for erro in erros)

    def test_correta_ausente(self):
        dados = _q()
        del dados["correta"]
        assert any(
            "Marque qual alternativa" in e.mensagem
            for e in perguntas.validar_pergunta(dados)
        )

    def test_enunciado_ausente(self):
        dados = _q()
        del dados["pergunta"]
        assert any(
            "Escreva o enunciado da pergunta" in e.mensagem
            for e in perguntas.validar_pergunta(dados)
        )

    def test_pergunta_nao_e_objeto(self):
        erros = perguntas.validar_pergunta("texto")
        assert len(erros) == 1
        assert "objeto JSON" in erros[0].mensagem

    def test_texto_alias_e_aceito(self):
        dados = _q()
        dados["texto"] = dados.pop("pergunta")
        assert perguntas.validar_pergunta(dados) == []

    def test_alternativa_repetida_e_apenas_aviso(self):
        erros = perguntas.validar_pergunta(
            _q(alternativas=["Igual", " igual "])
        )
        avisos = [e for e in erros if not e.bloqueante]
        assert any("são iguais" in e.mensagem for e in avisos)
        assert perguntas.erros_bloqueantes(erros) == []

    def test_banco_vazio(self):
        erros = perguntas.validar_banco([])
        assert any("pelo menos 1 pergunta" in e.mensagem for e in erros)

    def test_banco_muito_grande(self):
        dados = [_q(f"Pergunta {i}?") for i in range(5001)]
        erros = perguntas.validar_banco(dados)
        assert any("limite prático" in e.mensagem for e in erros)

    def test_banco_nao_e_lista(self):
        erros = perguntas.validar_banco({"perguntas": []})
        assert any("lista de perguntas" in e.mensagem for e in erros)

    def test_duplicata_de_pergunta_e_aviso(self):
        dados = [_q("Pergunta repetida?"), _q("  PERGUNTA   repetida?  ")]
        erros = perguntas.validar_banco(dados)
        avisos = perguntas.avisos_de_validacao(erros)
        assert len(avisos) == 1
        assert "repete a pergunta 1" in avisos[0].mensagem
        assert perguntas.erros_bloqueantes(erros) == []

    def test_duplicata_com_alias_texto(self):
        dados = [
            {
                "texto": "Pergunta repetida?",
                "alternativas": ["A", "B"],
                "correta": 0,
                "categoria": "C",
            },
            {
                "texto": "pergunta repetida?",
                "alternativas": ["A", "B"],
                "correta": 0,
                "categoria": "C",
            },
        ]
        avisos = perguntas.avisos_de_validacao(perguntas.validar_banco(dados))
        assert len(avisos) == 1
        assert "repete a pergunta 1" in avisos[0].mensagem

    def test_banco_com_item_nao_objeto(self):
        erros = perguntas.validar_banco(["texto", _q()])
        assert any("objeto JSON" in e.mensagem for e in erros)

    def test_normalizar_duplicata(self):
        assert (
            perguntas.normalizar_texto_duplicata("  A   B  ")
            == perguntas.normalizar_texto_duplicata("a b")
        )

    def test_erro_campo_tem_indice_e_str(self):
        erro = perguntas.validar_pergunta(_q(texto=""), indice=2)[0]
        assert erro.indice == 2
        assert str(erro).startswith("Pergunta 3:")


# ─────────────────────────────────────────────────────────
# Leitura e formato
# ─────────────────────────────────────────────────────────
class TestLeitura:
    def test_lista_legada(self, tmp_path):
        caminho = _banco_lista(tmp_path)
        banco = em.carregar_banco(str(caminho))
        assert banco.formato_origem == "lista"
        assert len(banco.perguntas) == 3
        assert banco.tema == ""
        assert banco.versao_formato == 1
        assert banco.somente_leitura is False
        assert banco.alterado is False
        assert banco.hash_origem

    def test_envelope_preserva_metadados_e_extras(self, tmp_path):
        caminho = _banco_envelope(
            tmp_path,
            extras={"campo_futuro": {"a": 1}, "titulo": "Título antigo"},
        )
        banco = em.carregar_banco(str(caminho))
        assert banco.formato_origem == "envelope"
        assert banco.tema == "Tema de Teste"
        assert banco.autor == "Carlos"
        assert banco.licenca == "CC BY 4.0"
        assert banco.extras["campo_futuro"] == {"a": 1}
        assert banco.extras["titulo"] == "Título antigo"
        assert banco.perguntas[0].extras["resposta_extra"] == "x"
        assert banco.perguntas[0].para_dict()["resposta_extra"] == "x"

    def test_envelope_com_titulo_como_tema(self, tmp_path):
        caminho = _escrever(
            tmp_path / "titulo.json",
            {"titulo": "Título", "perguntas": [_q()]},
        )
        banco = em.carregar_banco(str(caminho))
        assert banco.tema == "Título"
        assert "titulo" in banco.extras

    def test_envelope_sem_perguntas_e_recusado(self, tmp_path):
        caminho = _escrever(tmp_path / "vazio.json", {"tema": "Vazio"})
        with pytest.raises(ValueError):
            em.carregar_banco(str(caminho))

    def test_envelope_com_lista_vazia_carrega(self, tmp_path):
        caminho = _escrever(
            tmp_path / "vazio.json",
            {"tema": "Vazio", "perguntas": []},
        )
        banco = em.carregar_banco(str(caminho))
        assert banco.perguntas == []
        assert banco.validar()

    @pytest.mark.parametrize(
        "conteudo",
        [42, "texto", None],
    )
    def test_topo_invalido(self, tmp_path, conteudo):
        caminho = _escrever(tmp_path / "invalido.json", conteudo)
        with pytest.raises(ValueError):
            em.carregar_banco(str(caminho))

    def test_perguntas_nao_e_lista(self, tmp_path):
        caminho = _escrever(
            tmp_path / "invalido.json",
            {"perguntas": {"pasta": "."}},
        )
        with pytest.raises(ValueError):
            em.carregar_banco(str(caminho))

    def test_arquivo_inexistente(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            em.carregar_banco(str(tmp_path / "nao_existe.json"))

    def test_json_invalido(self, tmp_path):
        caminho = tmp_path / "quebrado.json"
        caminho.write_text("isto não é json", encoding="utf-8")
        with pytest.raises(ValueError):
            em.carregar_banco(str(caminho))

    def test_override_somente_leitura(self, tmp_path):
        caminho = _banco_lista(tmp_path)
        banco = em.carregar_banco(
            str(caminho),
            somente_leitura=True,
            distribuidos=[],
        )
        assert banco.somente_leitura is True

    @pytest.mark.parametrize(
        "nome, total",
        [
            ("conhecimentos_gerais.json", 97),
            ("eletrotecnica.json", 20),
            ("radiologia.json", 20),
        ],
    )
    def test_bancos_distribuidos_validos_e_somente_leitura(self, nome, total):
        banco = em.carregar_banco(nome)
        assert len(banco.perguntas) == total
        assert banco.somente_leitura is True
        assert banco.erros_bloqueantes() == []
        assert banco.avisos() == []

    def test_lista_de_distribuidos_por_nome(self, tmp_path):
        caminho = _banco_lista(tmp_path, nome="meu.json")
        banco = em.carregar_banco(
            str(caminho),
            distribuidos=["meu.json"],
        )
        assert banco.somente_leitura is True


# ─────────────────────────────────────────────────────────
# Operações
# ─────────────────────────────────────────────────────────
class TestOperacoes:
    def test_adicionar_editar_excluir_duplicar(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        nova = banco.adicionar(
            texto="Nova pergunta?",
            alternativas=["A", "B"],
            categoria="Nova",
        )
        assert len(banco.perguntas) == 4
        assert nova in banco.perguntas

        banco.editar(0, texto="Editada?", alternativas=["X", "Y"], correta=1)
        assert banco.perguntas[0].texto == "Editada?"
        assert banco.perguntas[0].alternativas == ["X", "Y"]

        copia = banco.duplicar(0)
        assert copia.texto.endswith("(cópia)")
        assert banco.perguntas[1] is copia
        assert copia.id_interno != banco.perguntas[0].id_interno

        removida = banco.excluir(1)
        assert removida is copia
        assert len(banco.perguntas) == 4

        substituida = banco.substituir(0, _q("Substituta?"))
        assert substituida.texto == "Substituta?"

    def test_adicionar_em_indice_e_tipos_invalidos(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.adicionar(_q("No meio?"), indice=1)
        assert banco.perguntas[1].texto == "No meio?"
        with pytest.raises(IndexError):
            banco.adicionar(_q(), indice=99)
        with pytest.raises(TypeError):
            banco.adicionar(42)  # type: ignore[arg-type]

    def test_editar_campo_desconhecido_e_correta_invalida(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        with pytest.raises(ValueError):
            banco.editar(0, inexistente=1)
        with pytest.raises(ValueError):
            banco.editar(0, correta="0")

    def test_mover_e_limites(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        primeiro = banco.perguntas[0]
        assert banco.mover(0, 2) == 2
        assert banco.perguntas[2] is primeiro
        assert banco.mover_cima(0) == 0
        assert banco.mover_baixo(2) == 2
        assert banco.mover_baixo(0) == 1
        with pytest.raises(IndexError):
            banco.mover(0, 99)
        with pytest.raises(IndexError):
            banco.mover(99, 0)

    def test_mover_sem_mudanca_nao_cria_undo(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        assert banco.mover(1, 1) == 1
        assert not banco.pode_desfazer

    def test_busca_e_filtro(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.editar(0, explicacao="Texto com coração")
        banco.editar(1, alternativas=["Coração", "D"])

        assert [p.texto for p in banco.buscar("coração")] == [
            banco.perguntas[0].texto,
            banco.perguntas[1].texto,
        ]
        assert banco.indices_filtrados(categoria="cat a") == [0, 2]
        assert banco.filtrar(categoria="Cat B") == [banco.perguntas[1]]
        assert banco.buscar("inexistente") == []
        assert banco.filtrar(texto="terceira", categoria="Cat A") == [
            banco.perguntas[2]
        ]

    def test_categorias(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        assert banco.categorias() == ["Cat A", "Cat B"]

    def test_undo_redo_e_alterado(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        assert banco.alterado is False
        banco.editar(0, texto="Versão 1?")
        banco.editar(0, texto="Versão 2?")
        assert banco.alterado is True
        assert banco.desfazer() is True
        assert banco.perguntas[0].texto == "Versão 1?"
        assert banco.desfazer() is True
        assert banco.perguntas[0].texto == "Primeira pergunta?"
        assert banco.alterado is False
        assert banco.desfazer() is False

        assert banco.refazer() is True
        assert banco.perguntas[0].texto == "Versão 1?"
        banco.editar(0, texto="Versão 3?")
        assert banco.pode_refazer is False

        banco.limpar_historico()
        assert banco.pode_desfazer is False
        assert banco.pode_refazer is False

    def test_undo_limitado_a_100(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        for i in range(105):
            banco.editar(0, texto=f"Pergunta {i}?")
        assert len(banco._undo) == em.LIMITE_HISTORICO
        desfeitos = 0
        while banco.desfazer():
            desfeitos += 1
        assert desfeitos == em.LIMITE_HISTORICO

    def test_redizer_limitado(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        for i in range(105):
            banco.editar(0, texto=f"Pergunta {i}?")
        while banco.desfazer():
            pass
        assert len(banco._redo) <= em.LIMITE_HISTORICO


# ─────────────────────────────────────────────────────────
# Serialização / round-trip
# ─────────────────────────────────────────────────────────
class TestSerializacao:
    def test_para_dict_lista_e_formato_invalido(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        lista = banco.para_dict("lista")
        assert isinstance(lista, list)
        assert len(lista) == 3
        with pytest.raises(ValueError):
            banco.para_dict("outro")

    def test_json_utf8_sem_bom_e_lf(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.editar(0, texto="Pergunta com coração e ação?")
        destino = tmp_path / "utf8.json"
        resultado = em.salvar_banco(banco, str(destino))
        assert resultado.ok
        bruto = destino.read_bytes()
        assert not bruto.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" not in bruto
        assert "coração".encode("utf-8") in bruto

    def test_ordem_das_chaves_e_extras(self, tmp_path):
        caminho = _escrever(
            tmp_path / "ordem.json",
            [
                {
                    "extra": 1,
                    "correta": 0,
                    "pergunta": "Ordem?",
                    "categoria": "Cat",
                    "alternativas": ["A", "B"],
                    "explicacao": "",
                }
            ],
        )
        banco = em.carregar_banco(str(caminho))
        dados = banco.para_dict("lista")[0]
        assert list(dados)[:2] == ["extra", "correta"]
        assert dados["extra"] == 1

    def test_round_trip_lista_para_envelope(self, tmp_path):
        original = _banco_lista(tmp_path)
        banco = em.carregar_banco(str(original))
        destino = tmp_path / "novo.json"
        resultado = em.salvar_banco(banco, str(destino))
        assert resultado.ok
        recarregado = em.carregar_banco(str(destino))
        assert recarregado.formato_origem == "envelope"
        assert [p.para_pergunta() for p in recarregado.perguntas] == [
            p.para_pergunta() for p in banco.perguntas
        ]
        assert recarregado.erros_bloqueantes() == []

    @pytest.mark.parametrize(
        "nome",
        ["conhecimentos_gerais.json", "eletrotecnica.json", "radiologia.json"],
    )
    def test_round_trip_bancos_distribuidos(self, tmp_path, nome):
        original = Path(nome).resolve()
        antes = persistencia.hash_arquivo(str(original))
        banco = em.carregar_banco(str(original))
        copia = tmp_path / nome
        resultado = em.salvar_banco(banco, str(copia))
        assert resultado.ok, resultado.erro
        assert persistencia.hash_arquivo(str(original)) == antes
        assert banco.somente_leitura is False

        carga = perguntas.ler_banco_perguntas(str(copia))
        assert carga.erro == ""
        assert carga.ignoradas == []
        assert [p.texto for p in carga.perguntas] == [
            p.texto for p in banco.perguntas
        ]

    def test_hash_serializado_muda_ao_editar(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        antes = banco.hash_serializado()
        banco.editar(0, texto="Outro texto?")
        assert banco.hash_serializado() != antes

    def test_extras_com_nan_nao_serializa(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.perguntas[0].extras["nan"] = float("nan")
        with pytest.raises(ValueError):
            banco.para_json()


# ─────────────────────────────────────────────────────────
# Gravação segura
# ─────────────────────────────────────────────────────────
class TestSalvamento:
    def test_salvar_novo_e_depois_criar_bak(self, tmp_path):
        destino = tmp_path / "novo.json"
        banco = _banco_editavel(tmp_path)
        primeiro = em.salvar_banco(banco, str(destino))
        assert primeiro.ok
        assert primeiro.backup == ""
        assert not (tmp_path / "novo.json.bak").exists()
        conteudo_antigo = destino.read_bytes()

        banco.editar(0, texto="Mudou?")
        segundo = em.salvar_banco(banco, str(destino))
        assert segundo.ok
        assert segundo.backup.endswith(".bak")
        assert (tmp_path / "novo.json.bak").read_bytes() == conteudo_antigo
        assert not (tmp_path / "novo.json.tmp").exists()

    def test_falha_disco_cheio_mantem_original(self, tmp_path, monkeypatch):
        destino = tmp_path / "banco.json"
        _escrever(destino, [_q("Original?")])
        original = destino.read_bytes()
        banco = em.carregar_banco(str(destino))
        banco.editar(0, texto="Novo?")

        def fsync_falha(_):
            raise OSError(errno.ENOSPC, "disco cheio")

        monkeypatch.setattr(em.os, "fsync", fsync_falha)
        resultado = em.salvar_banco(banco, str(destino))
        assert not resultado.ok
        assert destino.read_bytes() == original
        assert not (tmp_path / "banco.json.tmp").exists()

    def test_falha_no_backup_mantem_original(self, tmp_path, monkeypatch):
        destino = tmp_path / "banco.json"
        _escrever(destino, [_q("Original?")])
        original = destino.read_bytes()
        banco = em.carregar_banco(str(destino))
        banco.editar(0, texto="Novo?")

        def copia_falha(*args, **kwargs):
            raise OSError(errno.EACCES, "sem permissão")

        monkeypatch.setattr(em.shutil, "copyfile", copia_falha)
        resultado = em.salvar_banco(banco, str(destino))
        assert not resultado.ok
        assert destino.read_bytes() == original
        assert not (tmp_path / "banco.json.tmp").exists()

    def test_falha_no_replace_mantem_original(self, tmp_path, monkeypatch):
        destino = tmp_path / "banco.json"
        _escrever(destino, [_q("Original?")])
        original = destino.read_bytes()
        banco = em.carregar_banco(str(destino))
        banco.editar(0, texto="Novo?")
        replace_original = os.replace

        def replace_falha(src, dst):
            if os.path.abspath(src) == os.path.abspath(str(destino) + ".tmp"):
                raise OSError(errno.EIO, "falha de I/O")
            return replace_original(src, dst)

        monkeypatch.setattr(em.os, "replace", replace_falha)
        resultado = em.salvar_banco(banco, str(destino))
        assert not resultado.ok
        assert destino.read_bytes() == original
        assert not (tmp_path / "banco.json.tmp").exists()

    def test_pasta_sem_permissao(self, tmp_path, monkeypatch):
        destino = tmp_path / "banco.json"
        _escrever(destino, [_q("Original?")])
        original = destino.read_bytes()
        banco = em.carregar_banco(str(destino))
        banco.editar(0, texto="Novo?")
        monkeypatch.setattr(em, "_pasta_gravavel", lambda _: False)
        resultado = em.salvar_banco(banco, str(destino))
        assert not resultado.ok
        assert "permissão" in resultado.erro
        assert destino.read_bytes() == original

    def test_pasta_de_destino_inexistente(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        resultado = em.salvar_banco(
            banco,
            str(tmp_path / "nao_existe" / "banco.json"),
        )
        assert not resultado.ok
        assert "não existe" in resultado.erro

    def test_trava_de_outra_instancia(self, tmp_path):
        destino = tmp_path / "banco.json"
        _escrever(destino, [_q("Original?")])
        original = destino.read_bytes()
        banco = em.carregar_banco(str(destino))
        banco.editar(0, texto="Novo?")
        trava = Path(str(destino) + ".lock")
        trava.write_text(str(os.getpid()), encoding="ascii")
        try:
            resultado = em.salvar_banco(banco, str(destino))
        finally:
            trava.unlink(missing_ok=True)
        assert not resultado.ok
        assert resultado.conflito
        assert destino.read_bytes() == original

    def test_conflito_de_nome(self, tmp_path):
        origem = _banco_lista(tmp_path, nome="origem.json")
        alvo = _escrever(tmp_path / "alvo.json", [_q("Alvo original?")])
        alvo_original = alvo.read_bytes()
        banco = em.carregar_banco(str(origem))
        banco.editar(0, texto="Novo?")

        conflito = em.salvar_banco(banco, str(alvo))
        assert not conflito.ok
        assert conflito.conflito
        assert alvo.read_bytes() == alvo_original

        confirmado = em.salvar_banco(
            banco,
            str(alvo),
            permitir_sobrescrever=True,
        )
        assert confirmado.ok
        assert alvo.read_bytes() != alvo_original
        assert (tmp_path / "alvo.json.bak").exists()

    def test_salvar_sem_caminho_e_sem_origem(self):
        banco = em.criar_banco_novo()
        banco.adicionar(_q())
        resultado = em.salvar_banco(banco)
        assert not resultado.ok
        assert "caminho de destino" in resultado.erro

    def test_banco_invalido_nao_e_salvo(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.editar(0, texto="")
        destino = tmp_path / "nao_salvar.json"
        resultado = em.salvar_banco(banco, str(destino))
        assert not resultado.ok
        assert resultado.erros
        assert not destino.exists()

    def test_avisos_nao_bloqueiam(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.duplicar(0)
        destino = tmp_path / "com_aviso.json"
        resultado = em.salvar_banco(banco, str(destino))
        assert resultado.ok
        assert destino.exists()

    def test_salvar_distribuido_no_mesmo_caminho_e_bloqueado(self):
        caminho = Path("conhecimentos_gerais.json").resolve()
        antes = persistencia.hash_arquivo(str(caminho))
        banco = em.carregar_banco(str(caminho))
        banco.editar(0, texto="Não pode gravar?")
        resultado = em.salvar_banco(banco, str(caminho))
        assert not resultado.ok
        assert resultado.somente_leitura
        assert persistencia.hash_arquivo(str(caminho)) == antes

    def test_outro_banco_nao_sobrescreve_distribuido(self, tmp_path):
        caminho = Path("conhecimentos_gerais.json").resolve()
        antes = persistencia.hash_arquivo(str(caminho))
        banco = _banco_editavel(tmp_path)
        resultado = em.salvar_banco(
            banco,
            str(caminho),
            permitir_sobrescrever=True,
        )
        assert not resultado.ok
        assert resultado.somente_leitura
        assert persistencia.hash_arquivo(str(caminho)) == antes

    def test_salvar_preserva_undo_e_marca_salvo(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.editar(0, texto="Editada?")
        assert banco.pode_desfazer
        resultado = em.salvar_banco(banco, str(tmp_path / "salvo.json"))
        assert resultado.ok
        assert banco.pode_desfazer
        assert banco.alterado is False
        assert banco.caminho_origem == str(tmp_path / "salvo.json")
        assert banco.somente_leitura is False

    def test_estado_salvo_pede_confirmacao_e_invalida(self, tmp_path):
        destino = _banco_lista(tmp_path, nome="partida.json")
        estado = tmp_path / "estado_partida.json"
        _escrever(
            estado,
            {
                "caminho_perguntas": str(destino.resolve()),
                "hash_perguntas": persistencia.hash_arquivo(str(destino)),
            },
        )
        banco = em.carregar_banco(str(destino))
        banco.editar(0, texto="Nova pergunta?")
        original = destino.read_bytes()

        pendente = em.salvar_banco(banco, str(destino), estado_path=str(estado))
        assert not pendente.ok
        assert pendente.partida_salva_afetada
        assert estado.exists()
        assert destino.read_bytes() == original

        confirmado = em.salvar_banco(
            banco,
            str(destino),
            estado_path=str(estado),
            confirmar_invalidacao=True,
        )
        assert confirmado.ok
        assert confirmado.partida_salva_afetada
        assert confirmado.estado_invalidado
        assert not estado.exists()
        assert Path(confirmado.estado_invalidado).exists()
        assert destino.read_bytes() != original

    def test_salvar_de_outro_banco_nao_mexe_no_estado(self, tmp_path):
        alvo_estado = _banco_lista(tmp_path, nome="alvo_estado.json")
        estado = tmp_path / "estado_partida.json"
        _escrever(
            estado,
            {
                "caminho_perguntas": str(alvo_estado.resolve()),
                "hash_perguntas": persistencia.hash_arquivo(str(alvo_estado)),
            },
        )
        banco = _banco_editavel(tmp_path, nome="outro.json")
        resultado = em.salvar_banco(
            banco,
            str(tmp_path / "novo.json"),
            estado_path=str(estado),
        )
        assert resultado.ok
        assert estado.exists()
        assert not resultado.partida_salva_afetada


# ─────────────────────────────────────────────────────────
# Nomes, pastas e salvar como cópia
# ─────────────────────────────────────────────────────────
class TestNomesEPastas:
    @pytest.mark.parametrize(
        "entrada, esperado",
        [
            ("Meu Tema!.json", "meu_tema.json"),
            ("../../evil.json", "evil.json"),
            ("CON", "banco_con.json"),
            ("", "banco.json"),
            ("Já com ação", "ja_com_acao.json"),
            ("a" * 150, "a" * 100 + ".json"),
        ],
    )
    def test_sanitizar_nome(self, entrada, esperado):
        assert em.sanitizar_nome_arquivo(entrada) == esperado

    def test_nome_sugerido(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.tema = "Meu Tema!"
        assert em.nome_sugerido_copia(banco) == "meu_tema.json"
        banco.tema = ""
        assert em.nome_sugerido_copia(banco) == "banco.json"

    def test_pastas_candidatas_ordem_e_sem_app(self, tmp_path, monkeypatch):
        app = tmp_path / "app"
        config = tmp_path / "config"
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
        candidatas = em.pastas_salvamento_candidatas(
            str(config),
            diretorio_aplicacao=str(app),
        )
        assert candidatas[0] == str(config)
        assert "Documents" in candidatas[1]
        assert candidatas[2] == str(tmp_path / "roaming" / "DesafioDoConhecimento" / "perguntas")
        assert str(app) not in candidatas

    def test_pasta_config_igual_app_e_ignorada(self, tmp_path, monkeypatch):
        app = tmp_path / "app"
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
        candidatas = em.pastas_salvamento_candidatas(
            str(app),
            diretorio_aplicacao=str(app),
        )
        assert str(app) not in candidatas

    def test_resolver_pasta_cria_config(self, tmp_path):
        pasta = tmp_path / "perguntas"
        assert em.resolver_pasta_salvamento(str(pasta)) == str(pasta)
        assert pasta.is_dir()

    def test_resolver_pasta_fallback(self, tmp_path, monkeypatch):
        config = tmp_path / "config"
        app = tmp_path / "app"
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
        candidatas = em.pastas_salvamento_candidatas(
            str(config),
            diretorio_aplicacao=str(app),
        )

        def gravavel(caminho):
            return caminho == candidatas[1]

        monkeypatch.setattr(em, "_pasta_gravavel", gravavel)
        assert em.resolver_pasta_salvamento(
            str(config),
            diretorio_aplicacao=str(app),
        ) == candidatas[1]

    def test_resolver_sem_pasta_gravavel_devolve_ultima(self, tmp_path, monkeypatch):
        config = tmp_path / "config"
        app = tmp_path / "app"
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
        candidatas = em.pastas_salvamento_candidatas(
            str(config),
            diretorio_aplicacao=str(app),
        )
        monkeypatch.setattr(em, "_pasta_gravavel", lambda _: False)
        assert em.resolver_pasta_salvamento(
            str(config),
            diretorio_aplicacao=str(app),
        ) == candidatas[-1]

    def test_salvar_como_copia_e_conflito(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        pasta = tmp_path / "copias"
        primeiro = em.salvar_como_copia(
            banco,
            nome="Minha Cópia!",
            pasta_config=str(pasta),
        )
        assert primeiro.ok
        assert Path(primeiro.caminho).name == "minha_copia.json"

        # Um segundo banco, ainda com origem no arquivo antigo, tenta usar o
        # mesmo nome: é conflito de nome, não um salvamento normal da cópia.
        outro = _banco_editavel(tmp_path, nome="outro.json")
        outro.editar(0, texto="Outra?")
        conflito = em.salvar_como_copia(
            outro,
            nome="Minha Cópia!",
            pasta_config=str(pasta),
        )
        assert not conflito.ok
        assert conflito.conflito

        confirmado = em.salvar_como_copia(
            outro,
            nome="Minha Cópia!",
            pasta_config=str(pasta),
            permitir_sobrescrever=True,
        )
        assert confirmado.ok
        assert (pasta / "minha_copia.json.bak").exists()


# ─────────────────────────────────────────────────────────
# Partida salva
# ─────────────────────────────────────────────────────────
class TestPartidaSalva:
    def test_relacao_sem_estado(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        relacao = em.relacao_com_partida_salva(
            banco,
            estado_path=str(tmp_path / "nao_existe.json"),
        )
        assert relacao.mesmo_banco is False
        assert em.banco_e_da_partida_salva(
            banco,
            estado_path=str(tmp_path / "nao_existe.json"),
        ) is False

    def test_relacao_hash_e_caminho(self, tmp_path):
        caminho = _banco_lista(tmp_path)
        estado = tmp_path / "estado_partida.json"
        _escrever(
            estado,
            {
                "caminho_perguntas": str(caminho.resolve()),
                "hash_perguntas": persistencia.hash_arquivo(str(caminho)),
            },
        )
        banco = em.carregar_banco(str(caminho))
        relacao = em.relacao_com_partida_salva(banco, estado_path=str(estado))
        assert relacao.mesmo_caminho
        assert relacao.hash_confere
        assert relacao.mesmo_banco
        assert em.banco_e_da_partida_salva(banco, estado_path=str(estado))

        _escrever(caminho, [_q("Mudou o arquivo?")])
        relacao = em.relacao_com_partida_salva(banco, estado_path=str(estado))
        assert relacao.mesmo_caminho
        assert not relacao.hash_confere
        assert not relacao.mesmo_banco

    def test_relacao_caminho_diferente(self, tmp_path):
        caminho = _banco_lista(tmp_path, nome="a.json")
        outro = _banco_lista(tmp_path, nome="b.json")
        estado = tmp_path / "estado_partida.json"
        _escrever(
            estado,
            {
                "caminho_perguntas": str(outro.resolve()),
                "hash_perguntas": persistencia.hash_arquivo(str(outro)),
            },
        )
        banco = em.carregar_banco(str(caminho))
        assert not em.banco_e_da_partida_salva(banco, estado_path=str(estado))

    def test_invalidar_sem_estado(self, tmp_path):
        assert (
            em.invalidar_partida_salva(
                estado_path=str(tmp_path / "nao_existe.json")
            )
            is None
        )

    def test_invalidar_nome_e_colisao(self, tmp_path):
        estado = _escrever(tmp_path / "estado_partida.json", {"x": 1})
        primeiro = em.invalidar_partida_salva(
            estado_path=str(estado),
            data="2026-10-30",
        )
        assert primeiro is not None
        assert Path(primeiro).name == "estado_partida.invalida-2026-10-30.json"

        _escrever(estado, {"x": 2})
        segundo = em.invalidar_partida_salva(
            estado_path=str(estado),
            data="2026-10-30",
        )
        assert segundo is not None
        assert Path(segundo).name == "estado_partida.invalida-2026-10-30-2.json"

    def test_invalidar_com_date(self, tmp_path):
        from datetime import date

        estado = _escrever(tmp_path / "estado_partida.json", {"x": 1})
        alvo = em.invalidar_partida_salva(
            estado_path=str(estado),
            data=date(2026, 10, 30),
        )
        assert alvo is not None
        assert "2026-10-30" in alvo

    def test_invalidar_falha_de_replace(self, tmp_path, monkeypatch):
        estado = _escrever(tmp_path / "estado_partida.json", {"x": 1})
        monkeypatch.setattr(
            em.os,
            "replace",
            lambda *a, **k: (_ for _ in ()).throw(OSError("falha")),
        )
        assert em.invalidar_partida_salva(estado_path=str(estado)) is None
        assert estado.exists()


# ─────────────────────────────────────────────────────────
# Cobertura de ramos auxiliares
# ─────────────────────────────────────────────────────────
class TestCoberturaAuxiliar:
    def test_from_dict_com_alias_e_campos_ausentes(self):
        vazia = em.PerguntaEditavel.from_dict(42)
        assert vazia.texto == ""
        assert vazia.correta is None

        pergunta = em.PerguntaEditavel.from_dict(
            {
                "texto": "Pergunta pelo alias?",
                "alternativas": "não é lista",
                "correta": 0,
                "categoria": "Cat",
            }
        )
        assert pergunta.texto == "Pergunta pelo alias?"
        assert pergunta.alternativas == []
        dados = pergunta.para_dict()
        assert list(dados)[0] == "pergunta"
        assert "explicacao" in dados
        assert pergunta.validar()

    def test_banco_sem_estado_salvo_e_commit_sem_mudanca(self):
        banco = em.BancoEditavel()
        assert banco.alterado is True
        assert banco.refazer() is False
        banco.adicionar(_q())
        assert len(banco._undo) == 1
        assert banco.editar(0) is banco.perguntas[0]
        assert len(banco._undo) == 1

    def test_coerce_de_objeto_e_editar_alias_extras_ordem(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        pergunta = em.PerguntaEditavel.from_dict(_q("Objeto?"))
        assert banco.adicionar(pergunta) is pergunta
        banco.editar(0, pergunta="Alias?")
        assert banco.perguntas[0].texto == "Alias?"
        banco.editar(0, extras={"novo": 1})
        assert banco.perguntas[0].para_dict()["novo"] == 1
        banco.editar(
            0,
            ordem_chaves=(
                "pergunta",
                "alternativas",
                "correta",
                "categoria",
                "explicacao",
            ),
        )
        assert list(banco.perguntas[0].para_dict())[0] == "pergunta"

    def test_mover_cima_de_indice_nao_zero(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        segundo = banco.perguntas[1]
        assert banco.mover_cima(1) == 0
        assert banco.perguntas[0] is segundo

    def test_envelope_com_ordem_extra_e_campos_ausentes(self, tmp_path):
        caminho = _escrever(
            tmp_path / "envelope_ordem.json",
            {
                "versao_formato": 1,
                "tema": "Tema",
                "perguntas": [_q()],
                "extra_ordem": {"x": 1},
            },
        )
        banco = em.carregar_banco(str(caminho))
        banco.extras["fora_da_ordem"] = 2
        dados = banco.para_dict()
        assert dados["extra_ordem"] == {"x": 1}
        assert dados["autor"] == ""
        assert dados["licenca"] == ""
        assert dados["fora_da_ordem"] == 2

    def test_eh_distribuido_por_caminho_absoluto_e_sem_match(self, tmp_path):
        caminho = str(tmp_path / "banco.json")
        assert em._eh_distribuido(caminho, distribuidos=[caminho])
        assert not em._eh_distribuido(caminho, distribuidos=["outro.json"])

    def test_meta_versao_invalida(self, tmp_path):
        caminho = _escrever(
            tmp_path / "versao.json",
            {"versao_formato": "1", "perguntas": [_q()]},
        )
        banco = em.carregar_banco(str(caminho))
        assert banco.versao_formato == 1

    def test_carregar_com_hash_indisponivel(self, tmp_path, monkeypatch):
        caminho = _banco_lista(tmp_path)
        monkeypatch.setattr(
            em.persistencia,
            "hash_arquivo",
            lambda *a, **k: (_ for _ in ()).throw(OSError("sem hash")),
        )
        banco = em.carregar_banco(str(caminho))
        assert banco.hash_origem == ""

    def test_resultado_precisa_confirmar(self):
        assert em.ResultadoSalvamento(conflito=True).precisa_confirmar is True
        assert em.ResultadoSalvamento().precisa_confirmar is False

    def test_ler_estado_quebrado(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        estado = tmp_path / "estado_partida.json"
        estado.write_text("{quebrado", encoding="utf-8")
        relacao = em.relacao_com_partida_salva(banco, estado_path=str(estado))
        assert relacao.mesmo_banco is False

    def test_relacao_com_hash_indisponivel(self, tmp_path, monkeypatch):
        caminho = _banco_lista(tmp_path)
        estado = tmp_path / "estado_partida.json"
        _escrever(
            estado,
            {
                "caminho_perguntas": str(caminho.resolve()),
                "hash_perguntas": "abc",
            },
        )
        banco = em.carregar_banco(str(caminho))
        monkeypatch.setattr(
            em.persistencia,
            "hash_arquivo",
            lambda *a, **k: (_ for _ in ()).throw(OSError("sem hash")),
        )
        relacao = em.relacao_com_partida_salva(banco, estado_path=str(estado))
        assert relacao.hash_atual == ""

    def test_salvamento_afeta_partida_sem_estado_ou_caminho(self, tmp_path):
        assert (
            em._salvamento_afeta_partida(
                str(tmp_path / "banco.json"),
                estado_path=str(tmp_path / "nao_existe.json"),
            )
            is False
        )
        estado = _escrever(tmp_path / "estado_partida.json", {"x": 1})
        assert (
            em._salvamento_afeta_partida(
                str(tmp_path / "banco.json"),
                estado_path=str(estado),
            )
            is False
        )

    def test_salvar_em_pasta_como_destino(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        pasta = tmp_path / "uma_pasta"
        pasta.mkdir()
        resultado = em.salvar_banco(banco, str(pasta))
        assert not resultado.ok
        assert "pasta" in resultado.erro

    def test_salvar_com_erro_de_serializacao(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        banco.perguntas[0].extras["nan"] = float("nan")
        resultado = em.salvar_banco(banco, str(tmp_path / "nan.json"))
        assert not resultado.ok
        assert "serializar" in resultado.erro

    def test_salvar_com_hash_posterior_indisponivel(self, tmp_path, monkeypatch):
        banco = _banco_editavel(tmp_path)
        monkeypatch.setattr(
            em.persistencia,
            "hash_arquivo",
            lambda *a, **k: (_ for _ in ()).throw(OSError("sem hash")),
        )
        resultado = em.salvar_banco(banco, str(tmp_path / "salvo.json"))
        assert resultado.ok
        assert banco.hash_origem == ""

    def test_sanitizar_underscores_repetidos(self):
        assert em.sanitizar_nome_arquivo("a  b") == "a_b.json"

    def test_pastas_com_pasta_config_vazia_e_sem_appdata(self, tmp_path, monkeypatch):
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        candidatas = em.pastas_salvamento_candidatas(
            "",
            diretorio_aplicacao=str(tmp_path / "app"),
        )
        assert any("xdg" in caminho for caminho in candidatas)
        assert not any(caminho.endswith("app") for caminho in candidatas)

    def test_pasta_gravavel_casos_de_falha(self, tmp_path, monkeypatch):
        assert em._pasta_gravavel(str(tmp_path / "nao_existe")) is False
        assert em._pasta_gravavel(str(tmp_path)) is True

        monkeypatch.setattr(em.os, "access", lambda *a, **k: False)
        assert em._pasta_gravavel(str(tmp_path)) is False
        monkeypatch.undo()

        def remove_falha(_):
            raise OSError("sem remoção")

        monkeypatch.setattr(em.os, "remove", remove_falha)
        assert em._pasta_gravavel(str(tmp_path)) is False

    def test_resolver_pula_pasta_com_erro_de_criacao(self, tmp_path, monkeypatch):
        primeira = str(tmp_path / "primeira")
        segunda = str(tmp_path / "segunda")
        monkeypatch.setattr(
            em,
            "pastas_salvamento_candidatas",
            lambda *a, **k: [primeira, segunda],
        )
        real_makedirs = os.makedirs

        def makedirs(caminho, exist_ok=False):
            if caminho == primeira:
                raise OSError("não pode criar")
            return real_makedirs(caminho, exist_ok=exist_ok)

        monkeypatch.setattr(em.os, "makedirs", makedirs)
        monkeypatch.setattr(em, "_pasta_gravavel", lambda caminho: caminho == segunda)
        assert em.resolver_pasta_salvamento() == segunda

    def test_remover_silencioso_ignora_oserror(self, tmp_path, monkeypatch):
        arquivo = tmp_path / "arquivo.json"
        arquivo.write_text("x", encoding="utf-8")
        monkeypatch.setattr(
            em.os,
            "remove",
            lambda *a, **k: (_ for _ in ()).throw(OSError("sem remoção")),
        )
        em._remover_silencioso(str(arquivo))
        assert arquivo.exists()

    def test_limites_de_redo_e_undo(self, tmp_path):
        banco = _banco_editavel(tmp_path)
        snapshot = banco._snapshot()

        banco._undo = [snapshot] * 101
        banco._redo = [snapshot]
        assert banco.refazer() is True

        banco._undo = [snapshot]
        banco._redo = [snapshot] * 101
        assert banco.desfazer() is True


# ─────────────────────────────────────────────────────────
# Pureza
# ─────────────────────────────────────────────────────────
def test_editor_modelo_nao_importa_interface():
    fonte = Path(em.__file__).read_text(encoding="utf-8")
    for proibido in ("import tkinter", "import pygame", "import serial"):
        assert proibido not in fonte
