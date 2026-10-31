"""
Testes da Etapa E2: editor de perguntas com Tk real.

Os testes de interface usam uma raiz Tk de verdade e são pulados em ambiente
sem display. Os testes de regra (bloqueio, hash, recarga) rodam sem Tk.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import desafio
import editor_modelo as em
import ui_editor
import ui_editor_form
import ui_editor_lista
from apoio_tk import criar_raiz_tk
from jogo import FASE_AGUARDANDO, FASE_RESPONDENDO
from perguntas import ErroCampo


# =========================================================
# Infraestrutura
# =========================================================
class MensagensFalsas:
    def __init__(self, *, yes=True, yesnocancel=False, askstring=None):
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
    except Exception as exc:  # tk.TclError ou falha de inicialização do Tcl
        pytest.skip(f"Tk indisponível: {exc}")

    def reportar(tipo, valor, tb):
        raise valor

    root.report_callback_exception = reportar
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def _pergunta(i, categoria="Alfa"):
    return em.PerguntaEditavel(
        texto=f"Pergunta {i} sobre assunto",
        alternativas=[f"Alternativa {i}A", f"Alternativa {i}B"],
        correta=0,
        categoria=categoria,
        explicacao=f"Explicação {i}.",
    )


def criar_banco(
    tmp_path,
    *,
    quantidade=3,
    categorias=("Alfa", "Beta", "Alfa"),
    somente_leitura=False,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    perguntas = [
        _pergunta(i + 1, categorias[i % len(categorias)])
        for i in range(quantidade)
    ]
    banco = em.criar_banco_novo(
        tema="Banco de teste",
        autor="Ana",
        perguntas=perguntas,
    )
    caminho = tmp_path / "banco.json"
    resultado = em.salvar_banco(
        banco,
        str(caminho),
        estado_path=str(tmp_path / "sem_partida.json"),
        diretorio_base=str(tmp_path),
        diretorio_aplicacao=str(tmp_path),
    )
    assert resultado.ok, resultado.erro
    if somente_leitura:
        banco = em.carregar_banco(
            str(caminho),
            somente_leitura=True,
            diretorio_aplicacao=str(tmp_path),
        )
    return banco, caminho


@pytest.fixture
def abrir_editor(raiz_tk, tmp_path, mensagens):
    criados = []

    def abrir(banco=None, **kwargs):
        if banco is None:
            banco, _ = criar_banco(tmp_path)
        kwargs.setdefault("pasta_config", str(tmp_path))
        kwargs.setdefault("diretorio_base", str(tmp_path))
        kwargs.setdefault("diretorio_aplicacao", str(tmp_path))
        editor = ui_editor.EditorPerguntas(raiz_tk, banco, **kwargs)
        criados.append(editor)
        raiz_tk.update()
        return editor

    yield abrir

    for editor in criados:
        try:
            editor.destroy()
        except Exception:
            pass
    try:
        raiz_tk.update()
    except Exception:
        pass


def _digitar(editor, campo, valor):
    """Simula a digitação no formulário e dispara a notificação da UI."""
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
# Regra pura / integração sem Tk
# =========================================================
def test_rodada_em_andamento_regra_pura():
    assert not desafio.rodada_em_andamento(FASE_AGUARDANDO, False, False)
    assert desafio.rodada_em_andamento(FASE_AGUARDANDO, True, False)
    assert desafio.rodada_em_andamento(FASE_AGUARDANDO, False, True)
    assert desafio.rodada_em_andamento(FASE_AGUARDANDO, False, False, True)
    assert desafio.rodada_em_andamento(FASE_RESPONDENDO, False, False)


def test_hash_e_recarga_apos_editor(tmp_path):
    caminho = tmp_path / "banco.json"
    caminho.write_text("[]", encoding="utf-8")
    hash_antes = desafio.DueloDeConhecimento._hash_arquivo(str(caminho))
    assert hash_antes
    assert desafio.DueloDeConhecimento._hash_arquivo(str(tmp_path / "nada")) == ""

    recarregados = []
    avisos = []
    fake = SimpleNamespace(
        jogo=SimpleNamespace(perguntas=[1]),
        carregar_perguntas=lambda c: recarregados.append(c),
        proxima_pergunta=lambda forcar=False: None,
        render=lambda: None,
        avisar=lambda texto: avisos.append(texto),
    )
    fake._hash_arquivo = desafio.DueloDeConhecimento._hash_arquivo

    # Sem mudança de hash: não recarrega.
    desafio.DueloDeConhecimento._recarregar_apos_editor(
        fake, str(caminho), hash_antes
    )
    assert recarregados == []

    # Com mudança: recarrega e avisa.
    caminho.write_text("[{}]", encoding="utf-8")
    desafio.DueloDeConhecimento._recarregar_apos_editor(
        fake, str(caminho), hash_antes
    )
    assert recarregados == [str(caminho)]
    assert avisos

    # Caminho ausente: ignora.
    desafio.DueloDeConhecimento._recarregar_apos_editor(
        fake, str(tmp_path / "sumiu.json"), hash_antes
    )
    assert recarregados == [str(caminho)]


# =========================================================
# Editor: abertura e responsividade
# =========================================================
@pytest.mark.parametrize(
    "largura,esperado",
    [(1920, 360), (1366, 360), (1100, 320), (900, 250)],
)
def test_editor_responsivo_em_resolucoes(
    abrir_editor, raiz_tk, largura, esperado
):
    editor = abrir_editor()
    editor.geometry(f"{largura}x768")
    raiz_tk.update()
    editor._ao_redimensionar(SimpleNamespace(widget=editor, width=largura))

    assert editor.lista.winfo_exists()
    assert editor.formulario.winfo_exists()
    assert editor.lista.largura == esperado
    assert editor.winfo_width() > 0


def test_editor_banco_novo_e_selecao(abrir_editor):
    editor = abrir_editor(em.criar_banco_novo())
    assert editor.banco.perguntas == []
    assert editor.formulario.pergunta is None
    assert "Banco novo" in editor.lbl_banco.cget("text")
    assert editor.banco.pode_desfazer is False

    editor._ao_novo()
    assert len(editor.banco.perguntas) == 1
    assert editor.formulario.pergunta is not None
    assert editor.banco.perguntas[0].texto == "Nova pergunta"
    assert editor.banco.perguntas[0].categoria == "Geral"

    editor.desfazer()
    assert editor.banco.perguntas == []
    assert editor.formulario.pergunta is None


# =========================================================
# Editor: busca, filtro e seleção
# =========================================================
def test_busca_filtro_e_selecao(abrir_editor, raiz_tk):
    editor = abrir_editor()
    lista = editor.lista
    assert len(lista._indices_filtrados) == 3
    assert lista._item_selecionado == 0

    lista.var_busca.set("Pergunta 2")
    raiz_tk.update()
    assert len(lista._indices_filtrados) == 1
    assert lista._item_selecionado is None
    lista.selecionar_indice_banco(1)
    raiz_tk.update()
    assert editor.formulario.pergunta.texto.startswith("Pergunta 2")

    lista.var_busca.set("não existe")
    raiz_tk.update()
    assert lista._indices_filtrados == []
    assert lista._item_selecionado is None
    assert editor.formulario.pergunta is None

    assert lista._limpar_busca() == "break"
    lista.var_categoria.set("Beta")
    lista._aplicar_filtros()
    raiz_tk.update()
    assert all(
        editor.banco.perguntas[i].categoria == "Beta"
        for i in lista._indices_filtrados
    )

    # Categoria que deixa de existir volta para "Todas".
    lista.var_categoria.set("Categoria fantasma")
    lista._atualizar_categorias()
    assert lista.var_categoria.get() == ""

    lista.var_categoria.set("Beta")
    assert lista._limpar_categoria() == "break"
    assert lista.var_categoria.get() == ""


def test_selecionar_por_id_e_limpar(abrir_editor):
    editor = abrir_editor()
    alvo = editor.banco.perguntas[2]
    editor.lista.selecionar_por_id(alvo.id_interno)
    assert editor.formulario.pergunta is alvo
    assert editor.lista.indice_selecionado() == 2

    editor.lista.selecionar_por_id("id-que-nao-existe")
    assert editor.formulario.pergunta is alvo

    editor.lista.limpar_selecao()
    assert editor.lista.indice_selecionado() is None
    assert editor.formulario.pergunta is None
    editor.lista.limpar_selecao()  # idempotente

    editor.lista.on_banco_alterado()
    assert len(editor.lista._indices_filtrados) == 3


def test_scroll_e_foco(abrir_editor, raiz_tk):
    editor = abrir_editor()
    editor.lista.focus_busca()
    editor.lista._scroll_para_posicao(2)
    editor.lista._scroll_para_posicao(-1)
    editor.lista._scroll_para_posicao(999)
    raiz_tk.update()

    assert editor.lista.rolar(SimpleNamespace(delta=120)) == "break"
    assert editor.lista.rolar(SimpleNamespace(delta=-120)) == "break"
    assert editor.lista.rolar(SimpleNamespace(delta=0, num=4)) == "break"
    assert editor.lista.rolar(SimpleNamespace(delta=0, num=5)) == "break"

    assert editor.formulario.rolar(SimpleNamespace(delta=120)) == "break"
    assert editor.formulario.rolar(
        SimpleNamespace(delta=0, num=4)
    ) == "break"
    editor.formulario.focar_primeiro_campo()
    assert editor._ao_rolar(
        SimpleNamespace(widget=editor.lista.entry_busca)
    ) == "break"
    assert editor._ao_rolar(
        SimpleNamespace(widget=editor.formulario.container)
    ) == "break"
    assert editor._descende_de(editor.formulario.container, editor.formulario)
    assert not editor._descende_de(None, editor.formulario)


# =========================================================
# Editor: edição, validação e undo/redo
# =========================================================
def test_editar_campos_com_debounce(abrir_editor, raiz_tk):
    editor = abrir_editor()
    assert editor._pendente is None

    _digitar(editor, "pergunta", "Pergunta alterada pelo formulário")
    assert editor._pendente is not None
    editor._aplicar_pendente()
    raiz_tk.update()
    assert (
        editor.banco.perguntas[0].texto
        == "Pergunta alterada pelo formulário"
    )
    assert editor.banco.pode_desfazer

    _digitar(editor, "explicacao", "Nova explicação")
    editor._aplicar_pendente()
    assert editor.banco.perguntas[0].explicacao == "Nova explicação"

    _digitar(editor, "categoria", "Beta")
    editor._aplicar_pendente()
    assert editor.banco.perguntas[0].categoria == "Beta"

    _digitar(editor, "correta", 1)
    editor._aplicar_pendente()
    assert editor.banco.perguntas[0].correta == 1

    _digitar(
        editor,
        "alternativas",
        ["A", "B", "C", "D"],
    )
    editor._aplicar_pendente()
    assert editor.banco.perguntas[0].alternativas == ["A", "B", "C", "D"]

    _digitar(editor, "alternativas", ["A", "B", "", ""])
    editor._aplicar_pendente()
    assert editor.banco.perguntas[0].alternativas == ["A", "B"]

    editor.desfazer()
    raiz_tk.update()
    assert editor.formulario.pergunta is not None
    editor.refazer()
    raiz_tk.update()
    assert editor.formulario.pergunta is not None


def test_validacao_inline_e_salvamento_bloqueado(
    abrir_editor, mensagens
):
    editor = abrir_editor()
    _digitar(editor, "pergunta", "")
    erros = editor.formulario.validar_tempo_real()
    assert any(e.campo == "pergunta" for e in erros)
    assert editor.formulario.tem_erros_bloqueantes()
    assert editor.formulario.erros_bloqueantes()

    assert str(editor.btn_salvar.cget("state")) == "disabled"
    assert editor.salvar() is False
    assert "showwarning" in mensagens.tipos()
    assert editor.banco.alterado

    # A mensagem de erro do campo fica visível no label.
    label = editor.formulario._labels_erro["pergunta"]
    assert "❌" in label.cget("text")

    _digitar(editor, "pergunta", "Pergunta válida de novo")
    assert not editor.formulario.tem_erros_bloqueantes()
    assert str(editor.btn_salvar.cget("state")) == "normal"


def test_erros_por_alternativa_destacam_entry(abrir_editor):
    editor = abrir_editor()
    _digitar(editor, "alternativas", ["A", "", "C", "D"])
    erros = editor.formulario.validar_tempo_real()
    assert any(e.alternativa == 1 for e in erros)
    entry = editor.formulario._entry_alts[1]
    assert str(entry.cget("highlightbackground")) == ui_editor_form.Cor.ERRO
    label = editor.formulario._labels_erro["alternativas"]
    assert "vazia" in label.cget("text")


# =========================================================
# Editor: CRUD, reordenação e arrastar
# =========================================================
def test_novo_duplicar_excluir_e_desfazer(abrir_editor, mensagens):
    editor = abrir_editor()
    total = len(editor.banco.perguntas)

    editor._ao_novo()
    assert len(editor.banco.perguntas) == total + 1
    assert editor.formulario.pergunta.texto == "Nova pergunta"

    editor._ao_duplicar(editor.formulario.pergunta)
    assert len(editor.banco.perguntas) == total + 2
    assert "(cópia)" in editor.formulario.pergunta.texto

    mensagens.yes = False
    assert editor._ao_excluir(editor.formulario.pergunta) is False
    assert len(editor.banco.perguntas) == total + 2

    mensagens.yes = True
    assert editor._ao_excluir(editor.formulario.pergunta) is True
    assert len(editor.banco.perguntas) == total + 1

    editor.desfazer()
    assert len(editor.banco.perguntas) == total + 2


def test_reordenar_por_botoes_e_arrastar(abrir_editor, monkeypatch, raiz_tk):
    editor = abrir_editor()
    lista = editor.lista
    id_primeira = editor.banco.perguntas[0].id_interno

    lista._mover_item(0, 1)
    raiz_tk.update()
    assert editor.banco.perguntas[1].id_interno == id_primeira
    assert editor.formulario.pergunta.id_interno == id_primeira

    editor.desfazer()
    raiz_tk.update()
    assert editor.banco.perguntas[0].id_interno == id_primeira

    # Limites não movem.
    editor._ao_mover(0, -1)
    editor._ao_mover(0, len(editor.banco.perguntas))

    # Arrastar: o card de destino é encontrado pelas coordenadas.
    card_destino = next(
        c for c in lista._cards if getattr(c, "pos_lista", None) == 2
    )
    monkeypatch.setattr(
        lista, "winfo_containing", lambda x, y: card_destino
    )
    lista._drag_origem = 0
    lista._soltar_drag(SimpleNamespace(x_root=10, y_root=10))
    raiz_tk.update()
    assert editor.banco.perguntas[2].id_interno == id_primeira

    # Arrastar para fora/nulo não quebra.
    lista._drag_origem = 0
    monkeypatch.setattr(lista, "winfo_containing", lambda x, y: None)
    lista._soltar_drag(SimpleNamespace(x_root=10, y_root=10))
    lista._soltar_drag(SimpleNamespace(x_root=10, y_root=10))


def test_arrastar_scroll_automatico(abrir_editor, monkeypatch):
    editor = abrir_editor()
    lista = editor.lista
    lista._drag_origem = 0
    monkeypatch.setattr(
        lista.canvas_lista, "winfo_rooty", lambda: 100
    )
    monkeypatch.setattr(lista.canvas_lista, "winfo_height", lambda: 200)
    lista._arrastar(SimpleNamespace(y_root=105))
    lista._arrastar(SimpleNamespace(y_root=295))
    lista._arrastar(SimpleNamespace(y_root=200))
    lista._drag_origem = None
    lista._arrastar(SimpleNamespace(y_root=105))


# =========================================================
# Editor: salvamento
# =========================================================
def test_salvar_em_disco_e_backup(abrir_editor, raiz_tk):
    editor = abrir_editor()
    caminho = Path(editor.banco.caminho_origem)

    _digitar(editor, "pergunta", "Pergunta gravada pelo editor")
    assert editor.salvar() is True
    assert editor.banco.alterado is False
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["perguntas"][0]["pergunta"] == "Pergunta gravada pelo editor"
    assert "Salvo em" in editor.lbl_status.cget("text")

    _digitar(editor, "pergunta", "Segunda gravação")
    assert editor.salvar() is True
    assert Path(str(caminho) + ".bak").exists()


def test_salvar_como_copia_e_conflito(
    abrir_editor, tmp_path, mensagens, raiz_tk
):
    editor = abrir_editor()
    original = Path(editor.banco.caminho_origem)
    antes = original.read_text(encoding="utf-8")
    copias = tmp_path / "copias"
    copias.mkdir()
    editor.pasta_config = str(copias)

    _digitar(editor, "pergunta", "Versão da cópia")
    assert editor.salvar_como_copia() is True
    destino = Path(editor.banco.caminho_origem)
    assert destino.parent == copias
    assert destino.exists()
    assert original.read_text(encoding="utf-8") == antes

    # Conflito de nome: a UI pergunta e re-salva com sobrescrita.
    destino.write_text("{}", encoding="utf-8")
    _digitar(editor, "pergunta", "Sobrescreve a cópia")
    mensagens.yes = True
    assert editor.salvar_como_copia() is True
    assert json.loads(destino.read_text(encoding="utf-8"))["perguntas"][0][
        "pergunta"
    ] == "Sobrescreve a cópia"


def test_salvar_banco_somente_leitura_vai_para_copia(
    abrir_editor, tmp_path, raiz_tk
):
    banco, caminho = criar_banco(tmp_path, somente_leitura=True)
    copias = tmp_path / "copias"
    copias.mkdir()
    editor = abrir_editor(banco, pasta_config=str(copias))
    assert "SOMENTE LEITURA" in editor.lbl_aviso_leitura.cget("text")
    assert "somente leitura" in editor.lbl_status.cget("text")

    _digitar(editor, "pergunta", "Cópia de banco distribuído")
    assert editor.salvar() is True
    assert editor.banco.somente_leitura is False
    assert Path(editor.banco.caminho_origem).parent == copias
    assert Path(editor.banco.caminho_origem) != caminho


def test_salvar_invalida_partida_salva(
    abrir_editor, tmp_path, mensagens, raiz_tk
):
    banco, caminho = criar_banco(tmp_path)
    estado = tmp_path / "estado_partida.json"
    estado.write_text(
        json.dumps(
            {
                "caminho_perguntas": str(caminho),
                "hash_perguntas": "hash-antigo",
            }
        ),
        encoding="utf-8",
    )
    editor = abrir_editor(banco, estado_path=str(estado))
    _digitar(editor, "pergunta", "Edição que invalida a partida")
    mensagens.yes = True

    assert editor.salvar() is True
    assert not estado.exists()
    invalidados = list(tmp_path.glob("estado_partida.invalida-*.json"))
    assert len(invalidados) == 1
    assert "showinfo" in mensagens.tipos()


def test_cancelar_invalidacao_mantem_partida(
    abrir_editor, tmp_path, mensagens
):
    banco, caminho = criar_banco(tmp_path)
    estado = tmp_path / "estado_partida.json"
    estado.write_text(
        json.dumps({"caminho_perguntas": str(caminho)}),
        encoding="utf-8",
    )
    editor = abrir_editor(banco, estado_path=str(estado))
    _digitar(editor, "pergunta", "Edição cancelada")
    mensagens.yes = False

    assert editor.salvar() is False
    assert estado.exists()


def test_processar_resultado_conflito_e_erro(
    abrir_editor, mensagens, monkeypatch
):
    editor = abrir_editor()
    conflito = em.ResultadoSalvamento(
        ok=False,
        conflito=True,
        caminho=str(Path(editor.banco.caminho_origem)),
        erro="Já existe um banco com esse nome.",
    )
    mensagens.yes = False
    assert editor._processar_resultado(conflito, salvar_como=False) is False

    chamadas = []

    def retentar(resultado, **kwargs):
        chamadas.append(kwargs)
        return True

    monkeypatch.setattr(editor, "_retentar_salvamento", retentar)
    mensagens.yes = True
    assert editor._processar_resultado(conflito, salvar_como=False) is True
    assert chamadas and chamadas[0]["sobrescrever"] is True

    erro = em.ResultadoSalvamento(ok=False, erro="Falha de disco")
    assert editor._processar_resultado(erro, salvar_como=False) is False
    assert "showerror" in mensagens.tipos()

    somente_leitura = em.ResultadoSalvamento(
        ok=False,
        conflito=True,
        somente_leitura=True,
        erro="Somente leitura.",
    )
    assert (
        editor._processar_resultado(
            somente_leitura,
            salvar_como=True,
            permitir_reconfirmar=False,
        )
        is False
    )


# =========================================================
# Editor: fechamento
# =========================================================
def test_fechar_pede_confirmacao_e_salva(
    abrir_editor, mensagens, raiz_tk, tmp_path
):
    editor = abrir_editor()
    fechados = []
    editor.ao_fechar = fechados.append
    _digitar(editor, "pergunta", "Pergunta antes de fechar")

    mensagens.yesnocancel = None
    editor._confirmar_fechar()
    assert editor._fechado is False
    assert editor._pendente is None

    mensagens.yesnocancel = False
    editor._confirmar_fechar()
    raiz_tk.update()
    assert editor._fechado is True
    assert fechados == [editor.banco]

    # Fechar aceitando salvar grava no disco antes de sair.
    banco, caminho = criar_banco(tmp_path / "outro")
    editor2 = abrir_editor(banco)
    _digitar(editor2, "pergunta", "Salva ao fechar")
    mensagens.yesnocancel = True
    editor2._confirmar_fechar()
    raiz_tk.update()
    assert editor2._fechado is True
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    assert dados["perguntas"][0]["pergunta"] == "Salva ao fechar"


def test_fechar_sem_alteracoes_e_helper(abrir_editor, raiz_tk, tmp_path):
    banco, _ = criar_banco(tmp_path / "outro")
    fechados = []
    editor = ui_editor.abrir_editor(
        raiz_tk,
        banco,
        ao_fechar=fechados.append,
        diretorio_base=str(tmp_path),
        diretorio_aplicacao=str(tmp_path),
        pasta_config=str(tmp_path),
    )
    raiz_tk.update()
    editor._confirmar_fechar()
    raiz_tk.update()
    assert editor._fechado
    assert fechados


# =========================================================
# Integração com desafio.py (F3)
# =========================================================
def _app_falso(raiz_tk, caminho, tmp_path):
    app = object.__new__(desafio.DueloDeConhecimento)
    app.root = raiz_tk
    app.arquivo_atual = str(caminho)
    app.jogo = SimpleNamespace(
        timer_ativo=False,
        contagem_ativa=False,
        estado=SimpleNamespace(fase=FASE_AGUARDANDO),
        perguntas=[1],
    )
    app._contagem_visual = None
    app._janela_editor = None
    app._avisos = []
    app.avisar = lambda texto: app._avisos.append(texto)
    app.carregar_perguntas = lambda caminho=None: None
    app.proxima_pergunta = lambda forcar=False: None
    app.render = lambda: None
    return app


def test_f3_abre_editor_e_bloqueia_rodada(
    raiz_tk, tmp_path, mensagens, monkeypatch
):
    banco, caminho = criar_banco(tmp_path)
    app = _app_falso(raiz_tk, caminho, tmp_path)
    monkeypatch.setattr(desafio, "PASTA_PERGUNTAS", str(tmp_path))
    monkeypatch.setattr(
        desafio.persistencia, "localizar_estado", lambda *a, **k: None
    )
    mensagens.yes = True

    app.abrir_editor_perguntas()
    raiz_tk.update()
    editor = app._janela_editor
    assert isinstance(editor, ui_editor.EditorPerguntas)

    editor._fechar()
    raiz_tk.update()
    assert app._janela_editor is None

    app.jogo.timer_ativo = True
    app.abrir_editor_perguntas()
    raiz_tk.update()
    assert app._janela_editor is None
    assert app._avisos


def test_abrir_editor_perguntas_erro_de_banco(
    raiz_tk, tmp_path, mensagens, monkeypatch
):
    caminho = tmp_path / "quebrado.json"
    caminho.write_text("isto não é json", encoding="utf-8")
    app = _app_falso(raiz_tk, caminho, tmp_path)
    monkeypatch.setattr(desafio, "PASTA_PERGUNTAS", str(tmp_path))
    monkeypatch.delenv("DESAFIO_AUTO_FECHAR", raising=False)
    mensagens.yes = True

    app.abrir_editor_perguntas()
    raiz_tk.update()
    assert app._janela_editor is None
    assert "showerror" in mensagens.tipos()


# =========================================================
# Componentes isolados: lista e formulário
# =========================================================
class ListaFalsa:
    def __init__(self):
        self.eventos = []

    def selecionar(self, pergunta):
        self.eventos.append(("selecionar", pergunta))

    def novo(self):
        self.eventos.append(("novo", None))

    def duplicar(self, pergunta):
        self.eventos.append(("duplicar", pergunta))

    def excluir(self, pergunta):
        self.eventos.append(("excluir", pergunta))
        return True

    def mover(self, origem, destino):
        self.eventos.append(("mover", origem, destino))


def test_lista_isolada_callbacks(raiz_tk):
    banco = em.BancoEditavel(perguntas=[_pergunta(1), _pergunta(2)])
    falsa = ListaFalsa()
    lista = ui_editor_lista.ListaPerguntasEditor(
        raiz_tk,
        banco,
        ao_selecionar=falsa.selecionar,
        ao_novo=falsa.novo,
        ao_duplicar=falsa.duplicar,
        ao_excluir=falsa.excluir,
        ao_mover=falsa.mover,
    )
    raiz_tk.update()
    try:
        lista._cb_novo()
        lista.selecionar_indice_banco(1)
        lista._cb_duplicar()
        lista._cb_excluir()
        lista._mover_item(0, 1)
        assert ("novo", None) in falsa.eventos
        assert any(e[0] == "duplicar" for e in falsa.eventos)
        assert any(e[0] == "excluir" for e in falsa.eventos)
        assert ("mover", 0, 1) in falsa.eventos

        lista.limpar_bindings()
        lista.limpar_selecao()
        assert lista.indice_selecionado() is None
    finally:
        lista.destroy()


def test_formulario_isolado_alternativas_e_selecionar_tudo(raiz_tk):
    banco = em.BancoEditavel(perguntas=[_pergunta(1)])
    eventos = []
    atalhos = []
    form = ui_editor_form.FormularioPergunta(
        raiz_tk,
        banco,
        ao_alterar=lambda campo, valor: eventos.append((campo, valor)),
        ao_desfazer=lambda: atalhos.append("desfazer"),
        ao_refazer=lambda: atalhos.append("refazer"),
    )
    raiz_tk.update()
    try:
        form.carregar(banco.perguntas[0])
        form._vars_alternativas[2].set("Terceira")
        form._vars_alternativas[3].set("Quarta")
        form._ao_digitar("alternativas")
        assert eventos[-1][0] == "alternativas"
        assert len(eventos[-1][1]) == 4

        form._var_correta.set(2)
        form._ao_digitar("correta")
        assert eventos[-1] == ("correta", 2)

        form._var_categoria.set("Nova categoria")
        form._ao_digitar("categoria")
        assert eventos[-1] == ("categoria", "Nova categoria")

        form._set_texto("explicacao", "Explicação nova")
        form._ao_digitar("explicacao")
        assert eventos[-1] == ("explicacao", "Explicação nova")

        assert form._atalho_desfazer() == "break"
        assert form._atalho_refazer() == "break"
        assert atalhos == ["desfazer", "refazer"]

        texto = form._widgets_campos["pergunta"]["widget"]
        texto.tag_add("sel", "1.0", "2.0")
        assert form._selecionar_tudo(SimpleNamespace(widget=texto)) == "break"
        assert texto.tag_ranges("sel")

        entry = form._entry_alts[0]
        assert form._selecionar_tudo(SimpleNamespace(widget=entry)) == "break"
        assert entry.selection_present()

        form._ao_digitar("alternativas")
        form._coletar_dados_para_validacao()
        form._campo_do_erro(ErroCampo("alternativas[0]", "x"))
        form._campo_do_erro(ErroCampo("pergunta", "x"))
        form._mostrar_erros([ErroCampo("alternativas[0]", "vazia")])
        form.limpar_erros()
        form.atualizar_categorias()
        form.limpar_bindings()
        form.limpar()
        assert form.pergunta is None
    finally:
        form.destroy()

# =========================================================
# Cobertura adicional de ramos
# =========================================================
def test_editor_ramos_de_estado_e_erros(
    abrir_editor, mensagens, monkeypatch, raiz_tk, tmp_path
):
    import copy

    editor = abrir_editor()
    banco = editor.banco

    # Índice por id (objeto diferente, mesmo id).
    copia = copy.copy(banco.perguntas[0])
    assert editor._indice_pergunta(copia) == 0
    assert editor._indice_pergunta(em.PerguntaEditavel(id_interno="nao-existe")) is None

    # Alteração com formulário sem pergunta / pergunta fora do banco.
    editor.formulario.pergunta = None
    editor._ao_alterar_campo("pergunta", "x")
    editor.formulario.pergunta = em.PerguntaEditavel(id_interno="fora")
    editor._ao_alterar_campo("pergunta", "x")
    editor.formulario.carregar(banco.perguntas[0])

    # Pendência inválida e campo desconhecido.
    editor._pendente = (99, {"pergunta": "x"})
    editor._aplicar_pendente()
    editor._pendente = (0, {"campo_desconhecido": 1})
    editor._aplicar_pendente()
    editor._pendente = None

    # Aplicar pendência ao trocar de seleção.
    editor._pendente = (0, {"texto": "Pendente aplicada"})
    editor._ao_selecionar(banco.perguntas[1])
    assert banco.perguntas[0].texto == "Pendente aplicada"

    # Duplicar/excluir com objeto fora do banco.
    fora = em.PerguntaEditavel(id_interno="fora")
    editor._ao_duplicar(fora)
    assert editor._ao_excluir(fora) is False
    editor._ao_mover(-1, 0)
    editor._ao_mover(0, 99)

    # Exclusão de pergunta que tem vizinha à frente.
    editor.lista.selecionar_indice_banco(0)
    mensagens.yes = True
    assert editor._ao_excluir(banco.perguntas[0]) is True

    # Categoria padrão sem categorias e banco inválido (mínimo 1).
    vazio = em.criar_banco_novo()
    editor2 = abrir_editor(vazio)
    assert editor2._categoria_padrao() == "Geral"
    assert editor2.formulario.pergunta is None
    assert editor2.salvar() is False
    assert "showwarning" in mensagens.tipos()

    # Mais de 8 erros no aviso.
    erros = [ErroCampo(f"campo{i}", "erro") for i in range(10)]
    editor2._avisar_erros(erros)

    # Salvar como cópia bloqueado por validação.
    editor2._ao_novo()
    editor2.formulario._set_texto("pergunta", "")
    editor2.formulario._ao_digitar("pergunta")
    assert editor2.salvar_como_copia() is False

    # Fallback de centralização quando o pai ainda não tem tamanho.
    monkeypatch.setattr(raiz_tk, "winfo_width", lambda: 1)
    monkeypatch.setattr(raiz_tk, "winfo_height", lambda: 1)
    editor._centralizar()
    assert "+" in editor.geometry()

    # Fechar duas vezes é seguro.
    editor._fechar()
    editor._fechar()
    editor._confirmar_fechar()
    assert editor._fechado


def test_processar_resultado_somente_leitura_e_conflito_sem_reconfirmar(
    abrir_editor, mensagens, monkeypatch
):
    editor = abrir_editor()
    resultado = em.ResultadoSalvamento(
        ok=False, conflito=True, somente_leitura=True, erro="Somente leitura"
    )

    chamadas = []
    monkeypatch.setattr(
        editor, "salvar_como_copia", lambda: chamadas.append(True) or True
    )
    mensagens.yes = False
    assert editor._processar_resultado(resultado, salvar_como=False) is False
    assert chamadas == []

    mensagens.yes = True
    assert editor._processar_resultado(resultado, salvar_como=False) is True
    assert chamadas == [True]

    assert (
        editor._processar_resultado(
            resultado, salvar_como=False, permitir_reconfirmar=False
        )
        is False
    )
    assert "showerror" in mensagens.tipos()

    conflito = em.ResultadoSalvamento(
        ok=False, conflito=True, erro="Já existe"
    )
    assert (
        editor._processar_resultado(
            conflito, salvar_como=False, permitir_reconfirmar=False
        )
        is False
    )


def test_retentar_salvar_como_copia(abrir_editor, tmp_path):
    editor = abrir_editor()
    copias = tmp_path / "retentativa"
    copias.mkdir()
    editor.pasta_config = str(copias)
    _digitar(editor, "pergunta", "Retentativa de cópia")
    resultado = em.ResultadoSalvamento(
        ok=False, conflito=True, caminho=str(copias / "x.json"), erro="conflito"
    )
    assert editor._retentar_salvamento(
        resultado, salvar_como=True, sobrescrever=True, invalidar=False
    ) is True


def test_fechar_aceitando_salvar_mas_invalido_nao_fecha(
    abrir_editor, mensagens, raiz_tk
):
    editor = abrir_editor()
    _digitar(editor, "pergunta", "")
    mensagens.yesnocancel = True
    editor._confirmar_fechar()
    raiz_tk.update()
    assert editor._fechado is False
    assert "showwarning" in mensagens.tipos()


def test_lista_ramos_extras(abrir_editor, monkeypatch, raiz_tk):
    editor = abrir_editor()
    lista = editor.lista

    # Texto longo no card.
    editor.banco.perguntas[0].texto = "x" * 120
    lista.on_banco_alterado()
    raiz_tk.update()

    # Seleção inválida / repetida.
    lista._selecionar_por_posicao(-1)
    lista.selecionar_indice_banco(0)
    lista._selecionar_por_posicao(0)

    # Filtro suspenso não recalcula.
    lista._suspender_filtros = True
    lista._ao_mudar_filtro()
    lista._suspender_filtros = False

    # Lista vazia: visual ignora o label e não há seleção.
    lista.var_busca.set("sem resultado")
    raiz_tk.update()
    lista._atualizar_visual_selecao()
    lista._scroll_para_posicao(0)
    lista.var_busca.set("")
    raiz_tk.update()

    # Limites de mover.
    lista._mover_item(-1, 1)
    lista._mover_item(0, -1)
    lista._mover_item(0, 99)

    # Selecionar índice fora do filtro limpa os filtros.
    lista.selecionar_indice_banco(0)
    lista.var_categoria.set("Beta")
    raiz_tk.update()
    assert 0 not in lista._indices_filtrados
    lista.selecionar_indice_banco(0)
    assert lista.var_categoria.get() == ""
    assert lista.indice_selecionado() == 0

    lista.selecionar_indice_banco(-1)
    lista.selecionar_indice_banco(999)

    # Erros de Tk nos métodos de arrasto.
    lista._drag_origem = 0
    monkeypatch.setattr(
        lista.canvas_lista,
        "winfo_rooty",
        lambda: (_ for _ in ()).throw(__import__("tkinter").TclError("x")),
    )
    lista._arrastar(SimpleNamespace(y_root=10))
    monkeypatch.undo()
    lista._drag_origem = 0
    monkeypatch.setattr(
        lista,
        "winfo_containing",
        lambda *a: (_ for _ in ()).throw(__import__("tkinter").TclError("x")),
    )
    lista._soltar_drag(SimpleNamespace(x_root=1, y_root=1))
    monkeypatch.undo()

    # Caminhada pelo master até o card.
    card = next(c for c in lista._cards if hasattr(c, "pos_lista"))
    filho = SimpleNamespace(master=card)
    lista._drag_origem = 0
    monkeypatch.setattr(lista, "winfo_containing", lambda *a: filho)
    lista._soltar_drag(SimpleNamespace(x_root=1, y_root=1))
    monkeypatch.undo()

    # Card sem winfo_y e erro de Tk no container.
    lista._cards.insert(0, SimpleNamespace())
    lista._scroll_para_posicao(0)
    lista._cards.pop(0)
    monkeypatch.setattr(
        lista.container_itens,
        "winfo_height",
        lambda: (_ for _ in ()).throw(__import__("tkinter").TclError("x")),
    )
    lista._scroll_para_posicao(0)
    monkeypatch.undo()

    # Clique no card dispara seleção (evento Tk real).
    lista.selecionar_indice_banco(0)
    cards = [c for c in lista._cards if hasattr(c, "pos_lista")]
    if len(cards) > 1:
        cards[1].event_generate("<Button-1>", x=5, y=5)
        raiz_tk.update()


def test_formulario_ramos_extras(raiz_tk):
    banco = em.BancoEditavel(perguntas=[_pergunta(1)])
    form = ui_editor_form.FormularioPergunta(
        raiz_tk, banco, ao_alterar=lambda c, v: None
    )
    raiz_tk.update()
    try:
        invalida = em.PerguntaEditavel(
            texto="Pergunta inválida?",
            alternativas=["A", "B"],
            correta="abc",
            categoria="Alfa",
        )
        form.carregar(invalida)
        assert form._var_correta.get() == -1
        assert form._get_texto("categoria") == ""

        form.limpar()
        form._ao_digitar("pergunta")
        form._notificar_alteracao("pergunta")
        form._notificar_alteracao("campo_desconhecido")
        assert form.validar_tempo_real() == []
        form._mostrar_erros([ErroCampo("campo_inexistente", "x")])
        form._coletar_dados_para_validacao()
    finally:
        form.destroy()


def test_atalhos_adicionais_do_editor(abrir_editor, mensagens):
    editor = abrir_editor()
    editor.lista.selecionar_indice_banco(0)
    editor._duplicar_selecionada()
    assert len(editor.banco.perguntas) == 4

    editor.lista.limpar_selecao()
    editor._duplicar_selecionada()
    assert len(editor.banco.perguntas) == 4

    dentro = SimpleNamespace(widget=editor.lista.entry_busca, keysym="Down")
    assert editor._atalho_setas(dentro) == "break"
    dentro_up = SimpleNamespace(widget=editor.lista.canvas_lista, keysym="Up")
    assert editor._atalho_setas(dentro_up) == "break"
    fora = SimpleNamespace(widget=editor.formulario, keysym="Down")
    assert editor._atalho_setas(fora) is None

    assert editor._atalho_duplicar(dentro) is None
    editor.lista.selecionar_indice_banco(0)
    assert editor._atalho_duplicar(dentro_up) == "break"
    assert editor.lista.indice_selecionado() is not None

    assert editor._atalho_enter(dentro) == "break"
    assert editor._atalho_enter(fora) is None

    assert editor._atalho_excluir(dentro) is None
    assert editor._atalho_excluir(fora) is None

    editor.lista.selecionar_indice_banco(0)
    mensagens.yes = True
    antes = len(editor.banco.perguntas)
    assert editor._atalho_excluir(
        SimpleNamespace(widget=editor.lista.canvas_lista)
    ) == "break"
    assert len(editor.banco.perguntas) == antes - 1


def test_lista_navegacao_e_mover_selecionado(abrir_editor, raiz_tk):
    editor = abrir_editor()
    lista = editor.lista
    ids = [p.id_interno for p in editor.banco.perguntas]

    lista.selecionar_indice_banco(0)
    lista.mover_selecionado(1)
    assert [p.id_interno for p in editor.banco.perguntas][:2] == [ids[1], ids[0]]
    lista.mover_selecionado(-1)
    assert [p.id_interno for p in editor.banco.perguntas][:2] == [ids[0], ids[1]]

    lista.limpar_selecao()
    lista.mover_selecionado(1)

    lista._item_selecionado = 99
    lista.mover_selecionado(1)
    lista._item_selecionado = None

    lista.var_busca.set("sem resultado nenhum")
    raiz_tk.update()
    assert lista._indices_filtrados == []
    lista.selecionar_relativo(1)
    lista.selecionar_relativo(-1)
    lista.var_busca.set("")
    raiz_tk.update()

    lista.limpar_selecao()
    lista.selecionar_relativo(1)
    assert lista.indice_selecionado() == 0
    lista.selecionar_relativo(-1)
    assert lista.indice_selecionado() == 0
    lista.selecionar_relativo(1)
    assert lista.indice_selecionado() == 1
    lista.selecionar_relativo(999)
    assert lista.indice_selecionado() == len(editor.banco.perguntas) - 1


def test_fechar_tolera_erros_de_tk(abrir_editor, monkeypatch):
    import tkinter as tk

    editor = abrir_editor()
    for metodo in ("grab_release", "destroy"):
        monkeypatch.setattr(
            editor,
            metodo,
            lambda *a, **k: (_ for _ in ()).throw(tk.TclError("x")),
        )
    editor._fechar()
    assert editor._fechado is True
