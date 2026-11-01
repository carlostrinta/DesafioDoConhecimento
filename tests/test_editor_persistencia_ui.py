"""
Persistência real do editor (E2): grava em disco, relê e confere.

Estes testes NÃO substituem `salvar_banco` nem `salvar_como_copia`: apenas
os diálogos (`messagebox`) são injetados. Cada caso lê o arquivo gravado de
volta do disco para provar que a operação persistiu.
"""

import json
import logging
import os

import pytest

import editor_modelo as em
import ui_editor
from apoio_tk import criar_raiz_tk


# =========================================================
# Infraestrutura
# =========================================================
class MensagensFalsas:
    def __init__(self, *, yes=True, yesnocancel=False):
        self.yes = yes
        self.yesnocancel = yesnocancel
        self.chamadas = []

    def askyesno(self, *args, **kwargs):
        self.chamadas.append(("askyesno", args))
        return self.yes

    def askyesnocancel(self, *args, **kwargs):
        self.chamadas.append(("askyesnocancel", args))
        return self.yesnocancel

    def showwarning(self, *args, **kwargs):
        self.chamadas.append(("showwarning", args))

    def showerror(self, *args, **kwargs):
        self.chamadas.append(("showerror", args))

    def showinfo(self, *args, **kwargs):
        self.chamadas.append(("showinfo", args))

    def tipos(self):
        return [tipo for tipo, _ in self.chamadas]


@pytest.fixture
def mensagens(monkeypatch):
    falsas = MensagensFalsas()
    for nome in (
        "askyesno",
        "askyesnocancel",
        "showwarning",
        "showerror",
        "showinfo",
    ):
        monkeypatch.setattr(ui_editor.messagebox, nome, getattr(falsas, nome))
    return falsas


@pytest.fixture(scope="module")
def raiz_tk():
    try:
        root = criar_raiz_tk()
    except Exception as exc:
        pytest.skip(f"Tk indisponível: {exc}")

    def reportar(tipo, valor, tb):
        raise valor

    root.report_callback_exception = reportar
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def _questionario(textos):
    return {
        "tema": "Tema Original",
        "autor": "Ana",
        "licenca": "CC BY 4.0",
        "perguntas": [
            {
                "pergunta": texto,
                "alternativas": [f"Alternativa {i}A", f"Alternativa {i}B"],
                "correta": 0,
                "categoria": "Cat",
                "explicacao": f"Explicação {i}.",
            }
            for i, texto in enumerate(textos, start=1)
        ],
    }


def _escrever_banco(diretorio, *, textos=None, tema="Tema Original", nome="original.json"):
    diretorio.mkdir(parents=True, exist_ok=True)
    caminho = diretorio / nome
    dados = _questionario(textos or ["Pergunta 1?", "Pergunta 2?", "Pergunta 3?"])
    dados["tema"] = tema
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def _ler(caminho):
    return json.loads(open(caminho, encoding="utf-8").read())


def _abrir_editor(raiz_tk, caminho, *, pasta, aplicacao):
    banco = em.carregar_banco(str(caminho), diretorio_aplicacao=str(aplicacao))
    editor = ui_editor.EditorPerguntas(
        raiz_tk,
        banco,
        estado_path=str(pasta / "sem_partida.json"),
        diretorio_base=str(pasta),
        diretorio_aplicacao=str(aplicacao),
        pasta_config=str(pasta),
    )
    raiz_tk.update()
    return editor, banco


def _digitar(editor, campo, valor):
    if campo == "pergunta":
        editor.formulario._set_texto("pergunta", valor)
    elif campo == "explicacao":
        editor.formulario._set_texto("explicacao", valor)
    elif campo == "categoria":
        editor.formulario._var_categoria.set(valor)
    elif campo == "correta":
        editor.formulario._var_correta.set(valor)
    elif campo == "alternativas":
        for var, texto in zip(editor.formulario._vars_alternativas, valor):
            var.set(texto)
    editor.formulario._ao_digitar(campo)


# =========================================================
# Editar + Salvar regrava o original e cria .bak
# =========================================================
def test_editar_e_salvar_regrava_original_e_cria_bak(
    raiz_tk, tmp_path, mensagens
):
    origem = tmp_path / "origem"
    pasta = tmp_path / "usuario"
    aplicacao = tmp_path / "app"
    pasta.mkdir()
    aplicacao.mkdir()
    caminho = _escrever_banco(origem)
    antes = _ler(caminho)

    editor, banco = _abrir_editor(
        raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
    )
    try:
        assert str(editor.btn_salvar.cget("state")) == "normal"
        assert not editor.title().startswith("*")

        _digitar(editor, "pergunta", "Pergunta reescrita pela UI")
        raiz_tk.update()

        # Estado "alterado" visível imediatamente, antes do debounce.
        assert editor.banco.alterado or editor._tem_alteracoes_pendentes()
        assert editor.title().startswith("*")
        assert str(editor.btn_salvar.cget("state")) == "normal"

        # Usa o widget real do botão Salvar.
        editor.btn_salvar.invoke()
        raiz_tk.update()

        depois = _ler(caminho)
        assert depois["perguntas"][0]["pergunta"] == "Pergunta reescrita pela UI"
        assert depois["perguntas"][0]["pergunta"] != antes["perguntas"][0]["pergunta"]

        bak = caminho.with_name(caminho.name + ".bak")
        assert bak.is_file()
        assert _ler(bak)["perguntas"][0]["pergunta"] == antes["perguntas"][0]["pergunta"]

        assert not editor.title().startswith("*")
        print(f"[editar] gravado em: {caminho}")
        print(f"[editar] backup em: {bak}")
    finally:
        editor.destroy()
        raiz_tk.update()


# =========================================================
# Ctrl+S também grava no disco
# =========================================================
def test_ctrl_s_grava_no_disco(raiz_tk, tmp_path, mensagens):
    origem = tmp_path / "origem"
    pasta = tmp_path / "usuario"
    aplicacao = tmp_path / "app"
    pasta.mkdir()
    aplicacao.mkdir()
    caminho = _escrever_banco(origem)

    editor, _banco = _abrir_editor(
        raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
    )
    try:
        _digitar(editor, "pergunta", "Pergunta salva com Ctrl+S")
        raiz_tk.update()
        assert editor.title().startswith("*")

        editor.deiconify()
        editor.focus_force()
        raiz_tk.update()
        editor.event_generate("<Control-s>")
        raiz_tk.update()

        depois = _ler(caminho)
        assert depois["perguntas"][0]["pergunta"] == "Pergunta salva com Ctrl+S"
        assert not editor.title().startswith("*")
        print(f"[ctrl+s] gravado em: {caminho}")
    finally:
        editor.destroy()
        raiz_tk.update()


# =========================================================
# Excluir + Salvar persiste a redução
# =========================================================
def test_excluir_e_salvar_persiste_no_disco(raiz_tk, tmp_path, mensagens):
    origem = tmp_path / "origem"
    pasta = tmp_path / "usuario"
    aplicacao = tmp_path / "app"
    pasta.mkdir()
    aplicacao.mkdir()
    caminho = _escrever_banco(origem)

    editor, banco = _abrir_editor(
        raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
    )
    try:
        alvo = banco.perguntas[1]
        assert editor._ao_excluir(alvo) is True
        raiz_tk.update()

        assert banco.alterado
        assert editor.title().startswith("*")
        assert str(editor.btn_salvar.cget("state")) == "normal"

        assert editor.salvar() is True
        raiz_tk.update()

        depois = _ler(caminho)
        assert len(depois["perguntas"]) == 2
        textos = [p["pergunta"] for p in depois["perguntas"]]
        assert "Pergunta 2?" not in textos
        print(f"[excluir] gravado em: {caminho} ({len(depois['perguntas'])} perguntas)")
    finally:
        editor.destroy()
        raiz_tk.update()


# =========================================================
# Salvar como cópia grava um arquivo novo na pasta candidata
# =========================================================
def test_salvar_como_copia_grava_arquivo_novo(raiz_tk, tmp_path, mensagens):
    origem = tmp_path / "origem"
    pasta = tmp_path / "usuario"
    aplicacao = tmp_path / "app"
    pasta.mkdir()
    aplicacao.mkdir()
    caminho = _escrever_banco(origem, tema="Tema Copia", nome="banco_origem.json")

    editor, _banco = _abrir_editor(
        raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
    )
    try:
        _digitar(editor, "pergunta", "Pergunta da copia")
        raiz_tk.update()

        assert editor.salvar_como_copia() is True
        raiz_tk.update()

        destino = editor._ultimo_caminho_salvo
        assert destino, "o editor não registrou o caminho gravado"
        assert os.path.abspath(destino) != os.path.abspath(str(caminho))
        assert os.path.isfile(destino)
        assert os.path.commonpath(
            [os.path.abspath(destino), os.path.abspath(str(pasta))]
        ) == os.path.abspath(str(pasta))

        lido = _ler(destino)
        assert lido["perguntas"][0]["pergunta"] == "Pergunta da copia"
        print(f"[copia] gravado em: {destino}")
    finally:
        editor.destroy()
        raiz_tk.update()


# =========================================================
# Erros de gravação: tela + log
# =========================================================
def _resultado_somente_leitura(tmp_path):
    origem = tmp_path / "somente_leitura"
    origem.mkdir()
    caminho = _escrever_banco(origem, nome="distribuido.json")
    banco = em.carregar_banco(
        str(caminho),
        somente_leitura=True,
        diretorio_aplicacao=str(tmp_path / "app"),
    )
    return em.salvar_banco(
        banco,
        str(caminho),
        estado_path=str(tmp_path / "sem_partida.json"),
        diretorio_base=str(origem),
        diretorio_aplicacao=str(tmp_path / "app"),
    )


def test_erro_de_permissao_aparece_na_tela_e_no_log(
    raiz_tk, tmp_path, mensagens, monkeypatch, caplog
):
    origem = tmp_path / "origem"
    pasta = tmp_path / "usuario"
    aplicacao = tmp_path / "app"
    pasta.mkdir()
    aplicacao.mkdir()
    caminho = _escrever_banco(origem)
    editor, _banco = _abrir_editor(
        raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
    )
    try:
        _digitar(editor, "pergunta", "Pergunta com erro de permissao")
        monkeypatch.setattr(em, "_pasta_gravavel", lambda _p: False)

        with caplog.at_level(logging.WARNING, logger="desafio.editor_modelo"):
            assert editor.salvar() is False
        raiz_tk.update()

        assert "showerror" in mensagens.tipos()
        assert any(
            "permiss" in registro.getMessage().lower()
            for registro in caplog.records
        ), [r.getMessage() for r in caplog.records]
        # O arquivo original permanece intacto.
        assert _ler(caminho)["perguntas"][0]["pergunta"] == "Pergunta 1?"
    finally:
        editor.destroy()
        raiz_tk.update()


def test_conflito_aparece_na_tela_e_no_log(
    raiz_tk, tmp_path, caplog
):
    mensagens = MensagensFalsas(yes=False)
    # Injeta os diálogos localmente para o helper acima.
    import ui_editor as modulo

    originais = {}
    for nome in ("askyesno", "showwarning", "showerror"):
        originais[nome] = getattr(modulo.messagebox, nome)
        setattr(modulo.messagebox, nome, getattr(mensagens, nome))
    try:
        origem = tmp_path / "origem"
        pasta = tmp_path / "usuario"
        aplicacao = tmp_path / "app"
        pasta.mkdir()
        aplicacao.mkdir()
        caminho = _escrever_banco(
            origem, tema="Tema Copia", nome="banco_origem.json"
        )
        # Já existe uma cópia com o nome sugerido.
        pre_existente = pasta / "tema_copia.json"
        pre_existente.write_text('{"perguntas": []}', encoding="utf-8")

        editor, _banco = _abrir_editor(
            raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
        )
        try:
            _digitar(editor, "pergunta", "Pergunta que nao deve sobrescrever")
            with caplog.at_level(logging.WARNING, logger="desafio.editor_modelo"):
                assert editor.salvar_como_copia() is False
            raiz_tk.update()

            assert "askyesno" in mensagens.tipos()
            assert any(
                "conflito" in registro.getMessage().lower()
                for registro in caplog.records
            ), [r.getMessage() for r in caplog.records]
            # Cancelado: o pré-existente não foi alterado.
            assert _ler(pre_existente) == {"perguntas": []}
        finally:
            editor.destroy()
            raiz_tk.update()
    finally:
        for nome, funcao in originais.items():
            setattr(modulo.messagebox, nome, funcao)


def test_erro_de_permissao_vai_para_logs_desafio_log(tmp_path, monkeypatch):
    """O log real do jogo (`logs/desafio.log`) recebe o erro de gravação."""
    import logging
    import logging_conf

    logger = logging.getLogger(logging_conf.NOME_LOGGER)
    propagate_antes = logger.propagate
    try:
        logging_conf.configurar(
            debug=False, nivel="DEBUG", diretorio_base=str(tmp_path)
        )
        caminho_log = logging_conf.caminho_log()
        assert caminho_log.endswith(os.path.join("logs", "desafio.log"))

        origem = tmp_path / "origem"
        origem.mkdir()
        caminho = _escrever_banco(origem)
        banco = em.carregar_banco(str(caminho))
        monkeypatch.setattr(em, "_pasta_gravavel", lambda _p: False)

        resultado = em.salvar_banco(
            banco,
            str(caminho),
            estado_path=str(tmp_path / "sem_partida.json"),
            diretorio_base=str(origem),
        )
        assert resultado.ok is False
        assert "permiss" in (resultado.erro or "").lower()

        for handler in logger.handlers:
            handler.flush()
        texto = open(caminho_log, encoding="utf-8").read()
        assert "permiss" in texto.lower()
        print(f"[log] arquivo real do jogo: {caminho_log}")
        print(f"[log] trecho: {[l for l in texto.splitlines() if 'permiss' in l.lower()][-1]}")
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        logging_conf._caminho_log = ""
        logger.propagate = propagate_antes


def test_fechar_apos_excluir_pergunta_sobre_salvar(
    raiz_tk, tmp_path, mensagens
):
    origem = tmp_path / "origem"
    pasta = tmp_path / "usuario"
    aplicacao = tmp_path / "app"
    pasta.mkdir()
    aplicacao.mkdir()
    caminho = _escrever_banco(origem)

    editor, banco = _abrir_editor(
        raiz_tk, caminho, pasta=pasta, aplicacao=aplicacao
    )
    try:
        assert editor._ao_excluir(banco.perguntas[0]) is True
        raiz_tk.update()
        # Excluir só altera o modelo em memória.
        assert len(_ler(caminho)["perguntas"]) == 3
        assert editor.title().startswith("*")

        # Cancelar no diálogo mantém o editor aberto e nada é gravado.
        mensagens.yesnocancel = None
        editor._confirmar_fechar()
        raiz_tk.update()
        assert "askyesnocancel" in mensagens.tipos()
        assert editor.winfo_exists()
        assert len(_ler(caminho)["perguntas"]) == 3

        # Confirmar salva antes de fechar.
        mensagens.yesnocancel = True
        editor._confirmar_fechar()
        raiz_tk.update()
        assert len(_ler(caminho)["perguntas"]) == 2
        print(f"[fechar] salvo antes de fechar em: {caminho}")
    finally:
        if editor.winfo_exists():
            editor.destroy()
        raiz_tk.update()


def test_somente_leitura_aparece_na_tela_e_no_log(
    raiz_tk, tmp_path, caplog
):
    mensagens = MensagensFalsas(yes=False)
    import ui_editor as modulo

    originais = {}
    for nome in ("askyesno", "showwarning", "showerror"):
        originais[nome] = getattr(modulo.messagebox, nome)
        setattr(modulo.messagebox, nome, getattr(mensagens, nome))
    try:
        origem = tmp_path / "origem"
        pasta = tmp_path / "usuario"
        aplicacao = tmp_path / "app"
        pasta.mkdir()
        aplicacao.mkdir()
        with caplog.at_level(logging.WARNING, logger="desafio.editor_modelo"):
            resultado = _resultado_somente_leitura(tmp_path)
        assert resultado.ok is False
        assert resultado.somente_leitura is True
        assert any(
            "somente leitura" in registro.getMessage().lower()
            for registro in caplog.records
        ), [r.getMessage() for r in caplog.records]

        editor = ui_editor.EditorPerguntas(
            raiz_tk,
            em.criar_banco_novo(tema="X"),
            estado_path=str(pasta / "sem_partida.json"),
            diretorio_base=str(pasta),
            diretorio_aplicacao=str(aplicacao),
            pasta_config=str(pasta),
        )
        raiz_tk.update()
        try:
            assert editor._processar_resultado(resultado, salvar_como=True) is False
            raiz_tk.update()
            assert "showerror" in mensagens.tipos()
        finally:
            editor.destroy()
            raiz_tk.update()
    finally:
        for nome, funcao in originais.items():
            setattr(modulo.messagebox, nome, funcao)
