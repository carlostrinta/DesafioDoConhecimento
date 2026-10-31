"""Modelo puro do editor de perguntas (Etapa E1).

Sem tkinter, pygame ou serial. O módulo concentra o banco editável, as
operações de CRUD/reordenação/busca, a pilha de undo/redo, a serialização
compatível com o carregador e a gravação segura.

A validação é a de `perguntas.py`; não existe uma segunda regra aqui.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import unicodedata
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import perguntas
import persistencia
from recursos import obter_diretorio_base

log = logging.getLogger("desafio.editor_modelo")

BANCOS_DISTRIBUIDOS = (
    "conhecimentos_gerais.json",
    "eletrotecnica.json",
    "radiologia.json",
)

ORDEM_CHAVES_PERGUNTA = (
    "categoria",
    "pergunta",
    "alternativas",
    "correta",
    "explicacao",
)
CHAVES_PERGUNTA = frozenset(ORDEM_CHAVES_PERGUNTA) | {"texto"}

ORDEM_CHAVES_ENVELOPE = (
    "versao_formato",
    "tema",
    "autor",
    "licenca",
    "perguntas",
)
CHAVES_ENVELOPE = frozenset(ORDEM_CHAVES_ENVELOPE)

LIMITE_HISTORICO = 100
EXTENSAO_JSON = ".json"
NOME_ESTADO = persistencia.NOME_ARQUIVO


def _texto_seguro(valor: object) -> str:
    return "" if valor is None else str(valor)


def _normalizar_busca(texto: object) -> str:
    """Busca sem diferenciar caixa/acentos e com espaços colapsados."""
    decomposto = unicodedata.normalize("NFKD", _texto_seguro(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def _caminho_abs(caminho: str | os.PathLike[str] | None) -> str | None:
    if not caminho:
        return None
    return os.path.abspath(os.fspath(caminho))


def _remover_silencioso(caminho: str) -> None:
    try:
        if os.path.exists(caminho):
            os.remove(caminho)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────
# Pergunta editável
# ─────────────────────────────────────────────────────────
@dataclass
class PerguntaEditavel:
    """Pergunta em memória; `id_interno` nunca é gravado no JSON."""

    texto: str = ""
    alternativas: list[str] = field(default_factory=list)
    correta: int | None = 0
    categoria: str = ""
    explicacao: str = ""
    extras: dict[str, Any] = field(default_factory=dict)
    ordem_chaves: tuple[str, ...] = field(
        default_factory=lambda: ORDEM_CHAVES_PERGUNTA
    )
    id_interno: str = field(
        default_factory=lambda: uuid.uuid4().hex,
        repr=False,
        compare=False,
    )

    @classmethod
    def from_dict(cls, dados: object) -> "PerguntaEditavel":
        if not isinstance(dados, dict):
            return cls(
                texto="",
                alternativas=[],
                correta=None,
                categoria="",
                explicacao="",
                extras={},
                ordem_chaves=(),
            )

        texto = dados.get("pergunta")
        if texto is None:
            texto = dados.get("texto", "")
        alternativas = dados.get("alternativas")
        if not isinstance(alternativas, list):
            alternativas = []
        correta = dados.get("correta")
        # Valores inválidos são preservados para o validador apontar o campo.
        return cls(
            texto=texto,  # type: ignore[arg-type]
            alternativas=list(alternativas),
            correta=correta,  # type: ignore[arg-type]
            categoria=dados.get("categoria", ""),  # type: ignore[arg-type]
            explicacao=dados.get("explicacao", ""),  # type: ignore[arg-type]
            extras={
                chave: deepcopy(valor)
                for chave, valor in dados.items()
                if chave not in CHAVES_PERGUNTA
            },
            ordem_chaves=tuple(dados.keys()),
        )

    def para_dict(self) -> dict[str, Any]:
        valores = {
            "pergunta": self.texto,
            "alternativas": list(self.alternativas),
            "correta": self.correta,
            "categoria": self.categoria,
            "explicacao": self.explicacao,
        }
        resultado: dict[str, Any] = {}

        for chave in self.ordem_chaves:
            if chave == "texto":
                if "pergunta" not in resultado:
                    resultado["pergunta"] = deepcopy(valores["pergunta"])
            elif chave in valores:
                resultado[chave] = deepcopy(valores[chave])
            elif chave in self.extras:
                resultado[chave] = deepcopy(self.extras[chave])

        for chave in ORDEM_CHAVES_PERGUNTA:
            if chave not in resultado:
                resultado[chave] = deepcopy(valores[chave])

        for chave, valor in self.extras.items():
            if chave not in resultado:
                resultado[chave] = deepcopy(valor)

        return resultado

    def para_pergunta(self) -> perguntas.Pergunta:
        """Converte para o modelo do jogo. Use só depois de validar."""
        return perguntas.Pergunta(
            categoria=_texto_seguro(self.categoria),
            texto=_texto_seguro(self.texto),
            alternativas=[_texto_seguro(a) for a in self.alternativas],
            correta=int(self.correta or 0),
            explicacao=_texto_seguro(self.explicacao),
        )

    def clonar(self, *, sufixo: str = "") -> "PerguntaEditavel":
        copia = deepcopy(self)
        copia.id_interno = uuid.uuid4().hex
        if sufixo:
            copia.texto = _texto_seguro(copia.texto) + sufixo
        return copia

    def validar(self, indice: int | None = None) -> list[perguntas.ErroCampo]:
        return perguntas.validar_pergunta(self.para_dict(), indice=indice)


# ─────────────────────────────────────────────────────────
# Banco editável
# ─────────────────────────────────────────────────────────
@dataclass
class BancoEditavel:
    """
    Banco em memória.

    `caminho_origem` é o arquivo de onde o banco veio; `somente_leitura` é
    ligado para os bancos distribuídos. O caminho não é alterado por edições
    em memória.
    """

    perguntas: list[PerguntaEditavel] = field(default_factory=list)
    tema: str = ""
    autor: str = ""
    licenca: str = ""
    versao_formato: int = 1
    caminho_origem: str | None = None
    somente_leitura: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    ordem_chaves_envelope: tuple[str, ...] = field(default_factory=tuple)
    formato_origem: str = "lista"
    hash_origem: str = ""
    _undo: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _redo: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _estado_salvo: dict[str, Any] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.perguntas = [
            p if isinstance(p, PerguntaEditavel) else PerguntaEditavel.from_dict(p)
            for p in self.perguntas
        ]

    @classmethod
    def novo(
        cls,
        *,
        tema: str = "",
        autor: str = "",
        licenca: str = "CC BY 4.0",
        perguntas: Iterable[PerguntaEditavel] | None = None,
    ) -> "BancoEditavel":
        banco = cls(
            perguntas=list(perguntas or []),
            tema=tema,
            autor=autor,
            licenca=licenca,
            versao_formato=1,
            formato_origem="envelope",
            ordem_chaves_envelope=ORDEM_CHAVES_ENVELOPE,
        )
        banco._marcar_salvo()
        return banco

    # ── estado interno / undo ─────────────────────────────
    def _snapshot(self) -> dict[str, Any]:
        return {
            "perguntas": [deepcopy(p) for p in self.perguntas],
            "tema": self.tema,
            "autor": self.autor,
            "licenca": self.licenca,
            "versao_formato": self.versao_formato,
            "extras": deepcopy(self.extras),
            "ordem_chaves_envelope": self.ordem_chaves_envelope,
            "formato_origem": self.formato_origem,
        }

    def _restaurar(self, snapshot: dict[str, Any]) -> None:
        self.perguntas = [deepcopy(p) for p in snapshot["perguntas"]]
        self.tema = snapshot["tema"]
        self.autor = snapshot["autor"]
        self.licenca = snapshot["licenca"]
        self.versao_formato = snapshot["versao_formato"]
        self.extras = deepcopy(snapshot["extras"])
        self.ordem_chaves_envelope = snapshot["ordem_chaves_envelope"]
        self.formato_origem = snapshot["formato_origem"]

    def _commit(self, antes: dict[str, Any]) -> bool:
        if self._snapshot() == antes:
            return False
        self._undo.append(antes)
        if len(self._undo) > LIMITE_HISTORICO:
            self._undo.pop(0)
        self._redo.clear()
        return True

    def _marcar_salvo(self) -> None:
        self._estado_salvo = self._snapshot()

    @property
    def alterado(self) -> bool:
        if self._estado_salvo is None:
            return True
        return self._snapshot() != self._estado_salvo

    @property
    def pode_desfazer(self) -> bool:
        return bool(self._undo)

    @property
    def pode_refazer(self) -> bool:
        return bool(self._redo)

    def limpar_historico(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def desfazer(self) -> bool:
        if not self._undo:
            return False
        atual = self._snapshot()
        anterior = self._undo.pop()
        self._redo.append(atual)
        if len(self._redo) > LIMITE_HISTORICO:
            self._redo.pop(0)
        self._restaurar(anterior)
        return True

    def refazer(self) -> bool:
        if not self._redo:
            return False
        atual = self._snapshot()
        proximo = self._redo.pop()
        self._undo.append(atual)
        if len(self._undo) > LIMITE_HISTORICO:
            self._undo.pop(0)
        self._restaurar(proximo)
        return True

    # ── CRUD / ordenação ──────────────────────────────────
    @staticmethod
    def _coerce(pergunta: PerguntaEditavel | dict[str, Any]) -> PerguntaEditavel:
        if isinstance(pergunta, PerguntaEditavel):
            return pergunta
        if isinstance(pergunta, dict):
            return PerguntaEditavel.from_dict(pergunta)
        raise TypeError("pergunta deve ser PerguntaEditavel ou dict")

    def adicionar(
        self,
        pergunta: PerguntaEditavel | dict[str, Any] | None = None,
        *,
        indice: int | None = None,
        texto: str = "",
        alternativas: Iterable[str] | None = None,
        correta: int = 0,
        categoria: str = "",
        explicacao: str = "",
    ) -> PerguntaEditavel:
        antes = self._snapshot()
        if pergunta is None:
            pergunta = PerguntaEditavel(
                texto=texto,
                alternativas=list(alternativas or []),
                correta=correta,
                categoria=categoria,
                explicacao=explicacao,
            )
        else:
            pergunta = self._coerce(pergunta)

        if indice is None:
            self.perguntas.append(pergunta)
        else:
            if indice < 0 or indice > len(self.perguntas):
                raise IndexError("índice fora da faixa")
            self.perguntas.insert(indice, pergunta)
        self._commit(antes)
        return pergunta

    def editar(self, indice: int, **campos: Any) -> PerguntaEditavel:
        pergunta = self.perguntas[indice]
        if "pergunta" in campos:
            campos["texto"] = campos.pop("pergunta")
        permitidos = {
            "texto",
            "alternativas",
            "correta",
            "categoria",
            "explicacao",
            "extras",
            "ordem_chaves",
        }
        desconhecidos = set(campos) - permitidos
        if desconhecidos:
            raise ValueError(f"campo desconhecido: {sorted(desconhecidos)[0]}")

        antes = self._snapshot()
        for campo, valor in campos.items():
            if campo == "alternativas":
                valor = list(valor)
            elif campo == "extras":
                valor = dict(valor)
            elif campo == "ordem_chaves":
                valor = tuple(valor)
            elif campo == "correta":
                if valor is not None and (
                    isinstance(valor, bool) or not isinstance(valor, int)
                ):
                    raise ValueError("correta deve ser inteiro ou None")
            setattr(pergunta, campo, valor)
        self._commit(antes)
        return pergunta

    def substituir(
        self,
        indice: int,
        pergunta: PerguntaEditavel | dict[str, Any],
    ) -> PerguntaEditavel:
        antes = self._snapshot()
        nova = self._coerce(pergunta)
        self.perguntas[indice] = nova
        self._commit(antes)
        return nova

    def excluir(self, indice: int) -> PerguntaEditavel:
        antes = self._snapshot()
        removida = self.perguntas.pop(indice)
        self._commit(antes)
        return removida

    def duplicar(self, indice: int) -> PerguntaEditavel:
        antes = self._snapshot()
        copia = self.perguntas[indice].clonar(sufixo=" (cópia)")
        self.perguntas.insert(indice + 1, copia)
        self._commit(antes)
        return copia

    def mover(self, indice: int, novo_indice: int) -> int:
        if not 0 <= indice < len(self.perguntas):
            raise IndexError("índice fora da faixa")
        if not 0 <= novo_indice < len(self.perguntas):
            raise IndexError("índice de destino fora da faixa")
        if indice == novo_indice:
            return indice
        antes = self._snapshot()
        pergunta = self.perguntas.pop(indice)
        self.perguntas.insert(novo_indice, pergunta)
        self._commit(antes)
        return novo_indice

    def mover_cima(self, indice: int) -> int:
        if indice <= 0:
            return 0
        return self.mover(indice, indice - 1)

    def mover_baixo(self, indice: int) -> int:
        if indice >= len(self.perguntas) - 1:
            return max(0, len(self.perguntas) - 1)
        return self.mover(indice, indice + 1)

    # ── busca / filtro ────────────────────────────────────
    def indices_filtrados(
        self,
        texto: str = "",
        categoria: str | None = None,
    ) -> list[int]:
        termo = _normalizar_busca(texto)
        alvo_categoria = (
            _normalizar_busca(categoria) if categoria is not None else None
        )
        indices: list[int] = []
        for i, pergunta in enumerate(self.perguntas):
            if alvo_categoria is not None:
                if _normalizar_busca(pergunta.categoria) != alvo_categoria:
                    continue
            if termo:
                campos = [
                    pergunta.texto,
                    pergunta.categoria,
                    pergunta.explicacao,
                    *pergunta.alternativas,
                ]
                if not any(termo in _normalizar_busca(campo) for campo in campos):
                    continue
            indices.append(i)
        return indices

    def filtrar(
        self,
        texto: str = "",
        categoria: str | None = None,
    ) -> list[PerguntaEditavel]:
        return [self.perguntas[i] for i in self.indices_filtrados(texto, categoria)]

    def buscar(self, texto: str) -> list[PerguntaEditavel]:
        return self.filtrar(texto=texto)

    def categorias(self) -> list[str]:
        vistas: dict[str, str] = {}
        for pergunta in self.perguntas:
            nome = _texto_seguro(pergunta.categoria).strip()
            if nome and _normalizar_busca(nome) not in vistas:
                vistas[_normalizar_busca(nome)] = nome
        return sorted(vistas.values(), key=_normalizar_busca)

    # ── validação / serialização ──────────────────────────
    def validar(self) -> list[perguntas.ErroCampo]:
        return perguntas.validar_banco(
            [p.para_dict() for p in self.perguntas],
            metadados={
                "tema": self.tema,
                "autor": self.autor,
                "licenca": self.licenca,
                "versao_formato": self.versao_formato,
            },
        )

    def erros_bloqueantes(self) -> list[perguntas.ErroCampo]:
        return perguntas.erros_bloqueantes(self.validar())

    def avisos(self) -> list[perguntas.ErroCampo]:
        return perguntas.avisos_de_validacao(self.validar())

    def para_dict(self, formato: str = "envelope") -> Any:
        if formato == "lista":
            return [p.para_dict() for p in self.perguntas]
        if formato != "envelope":
            raise ValueError("formato deve ser 'lista' ou 'envelope'")

        valores = {
            "versao_formato": int(self.versao_formato or 1),
            "tema": _texto_seguro(self.tema),
            "autor": _texto_seguro(self.autor),
            "licenca": _texto_seguro(self.licenca),
            "perguntas": [p.para_dict() for p in self.perguntas],
        }
        resultado: dict[str, Any] = {}
        ordem = self.ordem_chaves_envelope or ORDEM_CHAVES_ENVELOPE
        for chave in ordem:
            if chave in valores:
                resultado[chave] = deepcopy(valores[chave])
            elif chave in self.extras:
                resultado[chave] = deepcopy(self.extras[chave])
        for chave in ORDEM_CHAVES_ENVELOPE:
            if chave not in resultado:
                resultado[chave] = deepcopy(valores[chave])
        for chave, valor in self.extras.items():
            if chave not in resultado:
                resultado[chave] = deepcopy(valor)
        return resultado

    def para_json(self, formato: str = "envelope") -> str:
        return (
            json.dumps(
                self.para_dict(formato),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )

    def hash_serializado(self) -> str:
        """Hash do JSON em memória; o jogo usa o hash do arquivo salvo."""
        return hashlib.sha256(self.para_json().encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────
# Leitura
# ─────────────────────────────────────────────────────────
def _eh_distribuido(
    caminho: str,
    *,
    diretorio_aplicacao: str | None = None,
    distribuidos: Iterable[str] | None = None,
) -> bool:
    alvo = os.path.abspath(caminho)
    if distribuidos is not None:
        for item in distribuidos:
            if os.path.abspath(str(item)) == alvo:
                return True
            if os.path.basename(str(item)).casefold() == os.path.basename(
                alvo
            ).casefold():
                return True
        return False

    base = os.path.abspath(diretorio_aplicacao or obter_diretorio_base())
    nomes = {nome.casefold() for nome in BANCOS_DISTRIBUIDOS}
    return (
        os.path.dirname(alvo) == base
        and os.path.basename(alvo).casefold() in nomes
    )


def _meta_texto(metadados: dict[str, Any], chave: str, padrao: str = "") -> str:
    valor = metadados.get(chave, padrao)
    return valor if isinstance(valor, str) else padrao


def _meta_versao(metadados: dict[str, Any]) -> int:
    valor = metadados.get("versao_formato", 1)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 1
    return valor


def carregar_banco(
    caminho: str,
    *,
    somente_leitura: bool | None = None,
    diretorio_aplicacao: str | None = None,
    distribuidos: Iterable[str] | None = None,
) -> BancoEditavel:
    """Lê lista legada ou envelope e devolve o modelo editável."""
    alvo = os.path.abspath(caminho)
    if not os.path.isfile(alvo):
        raise FileNotFoundError(alvo)

    conteudo, erro = perguntas.ler_conteudo_banco(alvo)
    if erro:
        raise ValueError(erro)
    if conteudo is None:
        raise ValueError(
            f"Não foi possível ler {os.path.basename(alvo)}: arquivo inválido "
            "ou codificação incompatível."
        )

    if isinstance(conteudo, dict):
        if "perguntas" not in conteudo:
            raise ValueError(
                f"Não foi possível ler {os.path.basename(alvo)}: o envelope "
                "precisa do campo 'perguntas'."
            )
        brutas = conteudo["perguntas"]
        if not isinstance(brutas, list):
            raise ValueError(
                f"Não foi possível ler {os.path.basename(alvo)}: o campo "
                "'perguntas' deve ser uma lista."
            )
        metadados = dict(conteudo)
        metadados.pop("perguntas", None)
        formato = "envelope"
        ordem_envelope = tuple(conteudo.keys())
        tema = _meta_texto(metadados, "tema") or _meta_texto(metadados, "titulo")
        autor = _meta_texto(metadados, "autor")
        licenca = _meta_texto(metadados, "licenca")
        versao = _meta_versao(metadados)
        extras = {
            chave: deepcopy(valor)
            for chave, valor in metadados.items()
            if chave not in CHAVES_ENVELOPE
        }
    elif isinstance(conteudo, list):
        brutas = conteudo
        formato = "lista"
        ordem_envelope = ORDEM_CHAVES_ENVELOPE
        tema = ""
        autor = ""
        licenca = ""
        versao = 1
        extras = {}
    else:
        raise ValueError(
            f"Não foi possível ler {os.path.basename(alvo)}: o arquivo deve "
            "conter uma lista de perguntas ou objeto com 'perguntas'."
        )

    banco = BancoEditavel(
        perguntas=[PerguntaEditavel.from_dict(q) for q in brutas],
        tema=tema,
        autor=autor,
        licenca=licenca,
        versao_formato=versao,
        caminho_origem=alvo,
        somente_leitura=(
            _eh_distribuido(
                alvo,
                diretorio_aplicacao=diretorio_aplicacao,
                distribuidos=distribuidos,
            )
            if somente_leitura is None
            else bool(somente_leitura)
        ),
        extras=extras,
        ordem_chaves_envelope=ordem_envelope,
        formato_origem=formato,
    )
    try:
        banco.hash_origem = persistencia.hash_arquivo(alvo)
    except OSError:
        banco.hash_origem = ""
    banco._marcar_salvo()
    return banco


def criar_banco_novo(
    *,
    tema: str = "",
    autor: str = "",
    licenca: str = "CC BY 4.0",
    perguntas: Iterable[PerguntaEditavel] | None = None,
) -> BancoEditavel:
    return BancoEditavel.novo(
        tema=tema,
        autor=autor,
        licenca=licenca,
        perguntas=perguntas,
    )


# ─────────────────────────────────────────────────────────
# Gravação segura
# ─────────────────────────────────────────────────────────
@dataclass
class ResultadoSalvamento:
    ok: bool = False
    caminho: str = ""
    backup: str = ""
    erro: str = ""
    conflito: bool = False
    somente_leitura: bool = False
    partida_salva_afetada: bool = False
    estado_invalidado: str = ""
    erros: list[perguntas.ErroCampo] = field(default_factory=list)

    @property
    def precisa_confirmar(self) -> bool:
        return self.conflito


def _gravar_arquivo(
    destino: str,
    dados: bytes,
    *,
    fazer_backup: bool,
) -> tuple[bool, str, str]:
    """Grava `.tmp`, faz `.bak` e troca com `os.replace`. Nunca perde o original."""
    temporario = destino + ".tmp"
    backup = destino + ".bak"
    try:
        with open(temporario, "wb") as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())

        backup_criado = ""
        if fazer_backup and os.path.exists(destino):
            backup_tmp = backup + ".tmp"
            shutil.copyfile(destino, backup_tmp)
            os.replace(backup_tmp, backup)
            backup_criado = backup

        os.replace(temporario, destino)
        return True, backup_criado, ""
    except OSError as exc:
        _remover_silencioso(temporario)
        _remover_silencioso(backup + ".tmp")
        log.warning("Não foi possível gravar o banco em %s: %s", destino, exc)
        return False, "", str(exc)


def _ler_estado(estado_path: str | None, diretorio_base: str | None) -> dict | None:
    caminho = _caminho_abs(estado_path) or persistencia.localizar_estado(
        diretorio_base
    )
    if not caminho or not os.path.isfile(caminho):
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


@dataclass
class RelacaoPartida:
    estado_path: str = ""
    caminho_salvo: str = ""
    hash_salvo: str = ""
    caminho_atual: str = ""
    hash_atual: str = ""

    @property
    def mesmo_caminho(self) -> bool:
        return bool(
            self.caminho_salvo
            and self.caminho_atual
            and os.path.normcase(self.caminho_salvo)
            == os.path.normcase(self.caminho_atual)
        )

    @property
    def hash_confere(self) -> bool:
        return bool(
            self.hash_salvo
            and self.hash_salvo.casefold() == self.hash_atual.casefold()
        )

    @property
    def mesmo_banco(self) -> bool:
        return self.mesmo_caminho and self.hash_confere


def relacao_com_partida_salva(
    banco: BancoEditavel,
    *,
    estado_path: str | None = None,
    diretorio_base: str | None = None,
) -> RelacaoPartida:
    dados = _ler_estado(estado_path, diretorio_base)
    if dados is None:
        return RelacaoPartida()

    caminho_salvo = _caminho_abs(dados.get("caminho_perguntas")) or ""
    hash_salvo = dados.get("hash_perguntas")
    hash_salvo = hash_salvo if isinstance(hash_salvo, str) else ""
    caminho_atual = _caminho_abs(banco.caminho_origem) or ""
    hash_atual = ""
    if caminho_atual and os.path.isfile(caminho_atual):
        try:
            hash_atual = persistencia.hash_arquivo(caminho_atual)
        except OSError:
            hash_atual = ""

    estado = _caminho_abs(estado_path) or persistencia.localizar_estado(
        diretorio_base
    )
    return RelacaoPartida(
        estado_path=estado or "",
        caminho_salvo=caminho_salvo,
        hash_salvo=hash_salvo,
        caminho_atual=caminho_atual,
        hash_atual=hash_atual,
    )


def banco_e_da_partida_salva(
    banco: BancoEditavel,
    *,
    estado_path: str | None = None,
    diretorio_base: str | None = None,
) -> bool:
    """True quando caminho e hash batem com a partida salva."""
    return relacao_com_partida_salva(
        banco,
        estado_path=estado_path,
        diretorio_base=diretorio_base,
    ).mesmo_banco


def _salvamento_afeta_partida(
    destino: str,
    *,
    estado_path: str | None = None,
    diretorio_base: str | None = None,
) -> bool:
    dados = _ler_estado(estado_path, diretorio_base)
    if dados is None:
        return False
    caminho_salvo = _caminho_abs(dados.get("caminho_perguntas"))
    if not caminho_salvo:
        return False
    return os.path.normcase(caminho_salvo) == os.path.normcase(destino)


def invalidar_partida_salva(
    *,
    estado_path: str | None = None,
    diretorio_base: str | None = None,
    data: str | date | None = None,
) -> str | None:
    """
    Renomeia `estado_partida.json` para
    `estado_partida.invalida-AAAA-MM-DD.json` (decisão nº 8).
    """
    caminho = _caminho_abs(estado_path) or persistencia.localizar_estado(
        diretorio_base
    )
    if not caminho or not os.path.isfile(caminho):
        return None

    data_txt = (
        data.isoformat()
        if isinstance(data, date)
        else str(data or date.today().isoformat())
    )
    pasta = os.path.dirname(caminho)
    base_estado = os.path.splitext(NOME_ESTADO)[0]
    alvo = os.path.join(pasta, f"{base_estado}.invalida-{data_txt}.json")
    contador = 2
    while os.path.exists(alvo):
        alvo = os.path.join(
            pasta,
            f"{base_estado}.invalida-{data_txt}-{contador}.json",
        )
        contador += 1

    try:
        os.replace(caminho, alvo)
    except OSError as exc:
        log.warning("Não foi possível invalidar a partida salva %s: %s", caminho, exc)
        return None
    return alvo


def salvar_banco(
    banco: BancoEditavel,
    caminho: str | None = None,
    *,
    formato: str = "envelope",
    permitir_sobrescrever: bool = False,
    confirmar_invalidacao: bool = False,
    validar: bool = True,
    estado_path: str | None = None,
    diretorio_base: str | None = None,
    diretorio_aplicacao: str | None = None,
    distribuidos: Iterable[str] | None = None,
) -> ResultadoSalvamento:
    """
    Salva de forma atômica. Devolve conflito (sem gravar) quando a UI precisa
    confirmar sobrescrita, banco somente leitura ou invalidação da partida.
    """
    if validar:
        bloqueantes = banco.erros_bloqueantes()
        if bloqueantes:
            return ResultadoSalvamento(
                ok=False,
                caminho=_caminho_abs(caminho) or "",
                erro="Corrija os erros antes de salvar.",
                erros=banco.validar(),
            )

    origem = _caminho_abs(banco.caminho_origem)
    destino = _caminho_abs(caminho) or origem
    if not destino:
        return ResultadoSalvamento(
            ok=False,
            erro="Informe o caminho de destino.",
            conflito=True,
            somente_leitura=banco.somente_leitura,
        )

    if (banco.somente_leitura and destino == origem) or _eh_distribuido(
        destino,
        diretorio_aplicacao=diretorio_aplicacao,
        distribuidos=distribuidos,
    ):
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro="Banco distribuído é somente leitura. Use 'Salvar como'.",
            conflito=True,
            somente_leitura=True,
        )

    if os.path.isdir(destino):
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro="O destino é uma pasta, não um arquivo.",
        )

    if (
        os.path.exists(destino)
        and destino != origem
        and not permitir_sobrescrever
    ):
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro="Já existe um banco com esse nome. Confirme para sobrescrever.",
            conflito=True,
        )

    afeta_partida = _salvamento_afeta_partida(
        destino,
        estado_path=estado_path,
        diretorio_base=diretorio_base,
    )
    if afeta_partida and not confirmar_invalidacao:
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro="A partida salva será invalidada. Confirme para continuar.",
            conflito=True,
            partida_salva_afetada=True,
        )

    pasta_destino = os.path.dirname(destino) or "."
    if not os.path.isdir(pasta_destino):
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro="A pasta de destino não existe.",
        )
    if not _pasta_gravavel(pasta_destino):
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro="A pasta de destino não tem permissão de escrita.",
        )

    try:
        dados = banco.para_json(formato).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro=f"Não foi possível serializar o banco: {exc}",
        )

    trava = persistencia.TravaInstancia(caminho=destino + ".lock")
    if not trava.adquirir():
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro=(
                "Este banco está aberto em outra instância. Feche o outro "
                "editor ou use 'Salvar como'."
            ),
            conflito=True,
            somente_leitura=True,
        )

    try:
        ok, backup, erro = _gravar_arquivo(
            destino,
            dados,
            fazer_backup=os.path.exists(destino),
        )
    finally:
        trava.liberar()

    if not ok:
        return ResultadoSalvamento(
            ok=False,
            caminho=destino,
            erro=f"Não foi possível gravar o banco: {erro}",
        )

    banco.caminho_origem = destino
    banco.somente_leitura = False
    try:
        banco.hash_origem = persistencia.hash_arquivo(destino)
    except OSError:
        banco.hash_origem = ""
    banco._marcar_salvo()

    estado_invalidado = ""
    if afeta_partida:
        estado_invalidado = (
            invalidar_partida_salva(
                estado_path=estado_path,
                diretorio_base=diretorio_base,
            )
            or ""
        )

    return ResultadoSalvamento(
        ok=True,
        caminho=destino,
        backup=backup,
        partida_salva_afetada=afeta_partida,
        estado_invalidado=estado_invalidado,
    )


# ─────────────────────────────────────────────────────────
# Salvar como cópia / nomes
# ─────────────────────────────────────────────────────────
def sanitizar_nome_arquivo(nome: str) -> str:
    """Gera um nome `.json` seguro para Windows, sem pastas."""
    base = _texto_seguro(nome).strip()
    # Troca separadores de pasta por "_" ANTES de basename, evitando perda
    # silenciosa do prefixo (ex.: "a/b" não vira "b.json").
    base = base.replace(os.sep, "_").replace("/", "_").replace("\\", "_")
    base = os.path.basename(base)
    if base.casefold().endswith(EXTENSAO_JSON):
        base = base[: -len(EXTENSAO_JSON)]
    decomposto = unicodedata.normalize("NFKD", base)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    permitido = []
    for caractere in sem_acento.casefold():
        if caractere.isalnum() or caractere in "-_":
            permitido.append(caractere)
        else:
            permitido.append("_")
    slug = "".join(permitido).strip("._-")
    while "__" in slug:
        slug = slug.replace("__", "_")
    if not slug:
        slug = "banco"

    reservados = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    if slug in reservados:
        slug = f"banco_{slug}"
    slug = slug[:100].rstrip("._-") or "banco"
    return slug + EXTENSAO_JSON


def nome_sugerido_copia(banco: BancoEditavel) -> str:
    base = _texto_seguro(banco.tema).strip()
    if not base and banco.caminho_origem:
        base = os.path.splitext(os.path.basename(banco.caminho_origem))[0]
    return sanitizar_nome_arquivo(base or "meu_banco")


def pastas_salvamento_candidatas(
    pasta_config: str | None = None,
    *,
    diretorio_aplicacao: str | None = None,
) -> list[str]:
    """Ordem da decisão nº 2, sem gravar ao lado do executável."""
    app = os.path.abspath(diretorio_aplicacao or obter_diretorio_base())
    candidatas: list[str] = []

    def adicionar(caminho: str | None) -> None:
        if not caminho:
            return
        alvo = os.path.abspath(os.path.expanduser(caminho))
        if os.path.normcase(alvo) == os.path.normcase(app):
            return
        if alvo not in candidatas:
            candidatas.append(alvo)

    if pasta_config:
        adicionar(pasta_config)
    adicionar(
        os.path.join(
            str(Path.home()),
            "Documents",
            "Desafio do Conhecimento",
            "perguntas",
        )
    )

    appdata = os.environ.get("APPDATA")
    if appdata:
        adicionar(os.path.join(appdata, "DesafioDoConhecimento", "perguntas"))
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = xdg or os.path.join(str(Path.home()), ".config")
        adicionar(os.path.join(base, "DesafioDoConhecimento", "perguntas"))

    return candidatas or [app]


def _pasta_gravavel(caminho: str) -> bool:
    try:
        if not os.path.isdir(caminho):
            return False
        if not os.access(caminho, os.W_OK | os.X_OK):
            return False
        teste = os.path.join(
            caminho,
            f".desafio_escrita_{os.getpid()}_{uuid.uuid4().hex}.tmp",
        )
        with open(teste, "wb") as arquivo:
            arquivo.write(b"x")
        os.remove(teste)
        return True
    except OSError:
        return False


def resolver_pasta_salvamento(
    pasta_config: str | None = None,
    *,
    diretorio_aplicacao: str | None = None,
) -> str:
    candidatas = pastas_salvamento_candidatas(
        pasta_config,
        diretorio_aplicacao=diretorio_aplicacao,
    )
    for pasta in candidatas:
        try:
            os.makedirs(pasta, exist_ok=True)
        except OSError:
            continue
        if _pasta_gravavel(pasta):
            return pasta
    return candidatas[-1]


def salvar_como_copia(
    banco: BancoEditavel,
    *,
    nome: str | None = None,
    pasta_config: str | None = None,
    diretorio_aplicacao: str | None = None,
    permitir_sobrescrever: bool = False,
    confirmar_invalidacao: bool = False,
    validar: bool = True,
    estado_path: str | None = None,
    diretorio_base: str | None = None,
) -> ResultadoSalvamento:
    """Escolhe a pasta da decisão nº 2 e delega para `salvar_banco`."""
    pasta = resolver_pasta_salvamento(
        pasta_config,
        diretorio_aplicacao=diretorio_aplicacao,
    )
    nome_final = sanitizar_nome_arquivo(nome or nome_sugerido_copia(banco))
    return salvar_banco(
        banco,
        os.path.join(pasta, nome_final),
        permitir_sobrescrever=permitir_sobrescrever,
        confirmar_invalidacao=confirmar_invalidacao,
        validar=validar,
        estado_path=estado_path,
        diretorio_base=diretorio_base,
        diretorio_aplicacao=diretorio_aplicacao,
    )
