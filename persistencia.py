"""
Persistência da partida — Etapa 4.3.

Módulo puro (sem tkinter, serial ou áudio). Grava `estado_partida.json` de
forma atômica ao lado do executável e, se essa pasta não for gravável, na
pasta do script.

O arquivo guarda apenas o necessário para continuar a partida: versão do
formato, tema/arquivo, placar, nomes, índice/rodada e a ordem do baralho.
Fase e timer NÃO são restaurados: a pergunta atual volta em AGUARDANDO com o
tempo cheio.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from jogo import Jogo, TODAS_EQUIPES, _ordem_valida
from perguntas import ler_banco_perguntas
from recursos import obter_diretorio_base

log = logging.getLogger("desafio.persistencia")

VERSAO_FORMATO = 1
NOME_ARQUIVO = "estado_partida.json"
ATRASO_SALVAMENTO_MS = 500


@dataclass
class PartidaSalva:
    """Resultado de uma carga válida, pronto para a UI aplicar."""

    jogo: Jogo
    tema: str
    arquivo: str
    caminho_perguntas: str
    resumo: str


@dataclass
class ResultadoCarga:
    """Carga de estado: `partida` é None quando não há nada para continuar."""

    partida: PartidaSalva | None = None
    motivo: str = ""
    caminho: str = ""


# ─────────────────────────────────────────────────────────
# Localização e gravação atômica
# ─────────────────────────────────────────────────────────
def _diretorio_script() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def diretorios_candidatos(diretorio_base: str | None = None) -> list[str]:
    """Pasta do executável primeiro; pasta do script como fallback."""
    base = os.path.abspath(diretorio_base) if diretorio_base else os.path.abspath(obter_diretorio_base())
    candidatos = [base]
    script = _diretorio_script()
    if script not in candidatos:
        candidatos.append(script)
    return candidatos


def localizar_estado(diretorio_base: str | None = None) -> str | None:
    """Caminho do estado existente, ou None."""
    for pasta in diretorios_candidatos(diretorio_base):
        caminho = os.path.join(pasta, NOME_ARQUIVO)
        if os.path.isfile(caminho):
            return caminho
    return None


def _remover_arquivo_silencioso(caminho: str) -> None:
    try:
        if os.path.exists(caminho):
            os.remove(caminho)
    except OSError:
        pass


def _gravar(dados: dict[str, Any], caminho: str) -> bool:
    """Grava `.tmp` e troca com `os.replace`; nunca levanta OSError."""
    temporario = caminho + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8", newline="\n") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        return True
    except (OSError, TypeError, ValueError) as exc:
        log.warning(
            "Não foi possível gravar o estado da partida em %s: %s",
            caminho,
            exc,
        )
        _remover_arquivo_silencioso(temporario)
        return False


def montar_estado(jogo: Jogo, tema: str, arquivo: str) -> dict[str, Any]:
    """Monta o dicionário versionado que vai para o JSON."""
    caminho = os.path.abspath(str(arquivo)) if arquivo else ""
    return {
        "versao": VERSAO_FORMATO,
        "salvo_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tema": str(tema or ""),
        "arquivo": os.path.basename(caminho),
        "caminho_perguntas": caminho,
        "total_perguntas": len(jogo.perguntas_base),
        "jogo": jogo.to_dict(),
    }


def salvar(
    jogo: Jogo,
    tema: str,
    arquivo: str | None,
    *,
    diretorio_base: str | None = None,
    caminho: str | None = None,
) -> str | None:
    """
    Salva o estado e devolve o caminho usado, ou None em caso de falha.

    Sem `caminho` explícito: usa o estado já existente (para manter a mesma
    pasta em que foi salvo antes) ou a pasta do executável, com fallback para
    a pasta do script. Falha de disco/permissão não derruba a aplicação.
    """
    if not arquivo:
        return None
    if not getattr(jogo, "perguntas", None):
        return None
    if jogo.estado.indice_pergunta < 1:
        return None

    dados = montar_estado(jogo, tema, arquivo)

    if caminho:
        alvo = os.path.abspath(caminho)
        return alvo if _gravar(dados, alvo) else None

    alvos: list[str] = []
    existente = localizar_estado(diretorio_base)
    if existente:
        alvos.append(existente)
    for pasta in diretorios_candidatos(diretorio_base):
        alvo = os.path.join(pasta, NOME_ARQUIVO)
        if alvo not in alvos:
            alvos.append(alvo)

    for alvo in alvos:
        if _gravar(dados, alvo):
            return alvo
    return None


def remover_estado(
    *,
    diretorio_base: str | None = None,
    caminho: str | None = None,
) -> bool:
    """Remove o estado salvo (e eventual `.tmp`); True se removeu algo."""
    if caminho:
        alvos = [os.path.abspath(caminho)]
    else:
        alvos = [
            os.path.join(pasta, NOME_ARQUIVO)
            for pasta in diretorios_candidatos(diretorio_base)
        ]

    removeu = False
    for alvo in alvos:
        for nome in (alvo, alvo + ".tmp"):
            try:
                if os.path.exists(nome):
                    os.remove(nome)
                    removeu = True
            except OSError as exc:
                log.warning("Não foi possível remover %s: %s", nome, exc)
    return removeu


# ─────────────────────────────────────────────────────────
# Leitura e validação
# ─────────────────────────────────────────────────────────
def _falha(motivo: str, caminho: str) -> ResultadoCarga:
    log.warning("Estado da partida ignorado (%s): %s", caminho, motivo)
    return ResultadoCarga(partida=None, motivo=motivo, caminho=caminho)


def _inteiro(valor: Any) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def resumo_partida(dados: dict[str, Any]) -> str:
    """Texto curto para o modal: tema, placar e rodada."""
    tema = dados.get("tema")
    tema = tema.strip() if isinstance(tema, str) and tema.strip() else "?"

    jogo = dados.get("jogo")
    jogo = jogo if isinstance(jogo, dict) else {}
    placar = jogo.get("placar")
    placar = placar if isinstance(placar, dict) else {}
    nomes = jogo.get("nomes_equipes")
    nomes = nomes if isinstance(nomes, dict) else {}

    def nome(equipe: str) -> str:
        valor = nomes.get(equipe)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
        return f"Competidor {equipe}"

    equipes = [eq for eq in TODAS_EQUIPES if eq in placar] or ["A", "B"]

    def pontos(equipe):
        valor = _inteiro(placar.get(equipe))
        return valor if valor is not None else 0

    if len(equipes) == 2:
        placar_txt = (
            f"{nome(equipes[0])} {pontos(equipes[0])} x "
            f"{pontos(equipes[1])} {nome(equipes[1])}"
        )
    else:
        placar_txt = " x ".join(
            f"{nome(equipe)} {pontos(equipe)}" for equipe in equipes
        )

    rodada = _inteiro(jogo.get("numero_pergunta"))
    if rodada is None:
        rodada = 0
    return f"Tema: {tema}\nPlacar: {placar_txt}\nRodada: {rodada}"


def carregar(
    diretorio_perguntas: str,
    *,
    nomes_equipes: dict[str, str] | None = None,
    tempo_pergunta: int | None = None,
    tempo_resposta: int | None = None,
    pontuar_apos_tempo: bool | None = None,
    num_equipes: int | None = None,
    diretorio_base: str | None = None,
    caminho: str | None = None,
) -> ResultadoCarga:
    """
    Lê e valida o estado salvo.

    Não levanta exceção por arquivo ausente, vazio, corrompido, versão
    desconhecida, tema removido ou baralho alterado: devolve
    `ResultadoCarga(partida=None, motivo="...")` e registra WARNING.
    """
    caminho_estado = os.path.abspath(caminho) if caminho else localizar_estado(diretorio_base)
    if not caminho_estado or not os.path.isfile(caminho_estado):
        return ResultadoCarga()

    try:
        with open(caminho_estado, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _falha(f"não foi possível ler o arquivo ({exc})", caminho_estado)

    try:
        return _validar_e_montar(
            dados,
            caminho_estado,
            diretorio_perguntas,
            nomes_equipes=nomes_equipes,
            tempo_pergunta=tempo_pergunta,
            tempo_resposta=tempo_resposta,
            pontuar_apos_tempo=pontuar_apos_tempo,
            num_equipes=num_equipes,
        )
    except Exception as exc:  # robustez: estado malformado nunca derruba o app
        return _falha(f"estado salvo inválido ({exc})", caminho_estado)


def _validar_e_montar(
    dados: Any,
    caminho_estado: str,
    diretorio_perguntas: str,
    *,
    nomes_equipes: dict[str, str] | None,
    tempo_pergunta: int | None,
    tempo_resposta: int | None,
    pontuar_apos_tempo: bool | None,
    num_equipes: int | None,
) -> ResultadoCarga:
    if not isinstance(dados, dict):
        return _falha("o arquivo não contém um objeto JSON válido", caminho_estado)

    versao = _inteiro(dados.get("versao"))
    if versao != VERSAO_FORMATO:
        return _falha(
            f"versão do formato desconhecida ({dados.get('versao')!r}); "
            f"esperada {VERSAO_FORMATO}",
            caminho_estado,
        )

    tema = dados.get("tema")
    if not isinstance(tema, str) or not tema.strip():
        return _falha("estado sem tema válido", caminho_estado)
    tema = tema.strip()

    arquivo = dados.get("arquivo")
    if not isinstance(arquivo, str) or not arquivo.strip():
        return _falha("estado sem arquivo de perguntas válido", caminho_estado)
    arquivo = os.path.basename(arquivo.strip())

    jogo_dados = dados.get("jogo")
    if not isinstance(jogo_dados, dict):
        return _falha("estado sem os dados do jogo", caminho_estado)

    total = _inteiro(dados.get("total_perguntas"))
    if total is None or total < 1:
        return _falha("estado sem o total de perguntas", caminho_estado)

    num_salvo = _inteiro(jogo_dados.get("num_equipes", 2))
    if num_salvo not in (2, 3, 4):
        return _falha("número de equipes inválido no estado", caminho_estado)
    num = num_equipes if num_equipes in (2, 3, 4) else num_salvo

    indice = _inteiro(jogo_dados.get("indice_pergunta"))
    if indice is None or not 1 <= indice <= total:
        return _falha("índice da pergunta atual inválido", caminho_estado)

    numero = _inteiro(jogo_dados.get("numero_pergunta"))
    if numero is None or numero < 1:
        return _falha("número da rodada inválido", caminho_estado)

    ordem = jogo_dados.get("ordem")
    if not _ordem_valida(ordem, total):
        return _falha("ordem do baralho inválida", caminho_estado)

    placar = jogo_dados.get("placar")
    if not isinstance(placar, dict):
        return _falha("placar inválido no estado", caminho_estado)
    for equipe, valor in placar.items():
        if equipe not in TODAS_EQUIPES:
            continue
        pontos = _inteiro(valor)
        if pontos is None or pontos < 0:
            return _falha(f"placar inválido para a equipe {equipe}", caminho_estado)

    caminho_salvo = dados.get("caminho_perguntas")
    candidatos: list[str] = []
    if isinstance(caminho_salvo, str) and caminho_salvo.strip():
        candidatos.append(os.path.abspath(os.path.expanduser(caminho_salvo.strip())))
    candidatos.append(os.path.abspath(os.path.join(diretorio_perguntas, arquivo)))

    caminho_banco = next((c for c in candidatos if os.path.isfile(c)), None)
    if not caminho_banco:
        return _falha(
            f"o arquivo '{arquivo}' do tema '{tema}' não existe mais",
            caminho_estado,
        )

    carga = ler_banco_perguntas(
        caminho_banco,
        tema_padrao=tema,
        aceitar_tema_do_arquivo=False,
    )
    if carga.erro or not carga.perguntas:
        return _falha(
            f"não foi possível carregar o banco '{arquivo}': "
            f"{carga.erro or 'nenhuma pergunta válida'}",
            caminho_estado,
        )
    if len(carga.perguntas) != total:
        return _falha(
            f"o banco '{arquivo}' tem {len(carga.perguntas)} pergunta(s), "
            f"mas o estado salvo tem {total}",
            caminho_estado,
        )

    dados_jogo = dict(jogo_dados)
    dados_jogo["num_equipes"] = num

    kwargs: dict[str, Any] = {}
    if nomes_equipes is not None:
        kwargs["nomes_equipes"] = dict(nomes_equipes)
    if tempo_pergunta is not None:
        kwargs["tempo_pergunta"] = tempo_pergunta
    if tempo_resposta is not None:
        kwargs["tempo_resposta"] = tempo_resposta
    if pontuar_apos_tempo is not None:
        kwargs["pontuar_apos_tempo"] = pontuar_apos_tempo

    jogo = Jogo.from_dict(dados_jogo, carga.perguntas, **kwargs)
    if jogo.estado.pergunta_atual is None:
        return _falha("estado sem pergunta atual", caminho_estado)

    return ResultadoCarga(
        partida=PartidaSalva(
            jogo=jogo,
            tema=tema,
            arquivo=arquivo,
            caminho_perguntas=caminho_banco,
            resumo=resumo_partida(dados),
        ),
        caminho=caminho_estado,
    )


# ─────────────────────────────────────────────────────────
# Debounce para a UI (sem depender de tkinter)
# ─────────────────────────────────────────────────────────
class AgendadorSalvamento:
    """
    Debounce simples e injetável.

    A UI passa `root.after`/`root.after_cancel`; os testes passam funções
    falsas. Cada `pedir()` cancela o agendamento anterior e agenda um novo,
    evitando gravações em excesso.
    """

    def __init__(
        self,
        salvar: Callable[[], Any],
        agendar: Callable[[int, Callable[[], Any]], Any],
        cancelar: Callable[[Any], Any],
        atraso_ms: int = ATRASO_SALVAMENTO_MS,
    ):
        self._salvar = salvar
        self._agendar = agendar
        self._cancelar = cancelar
        self._atraso_ms = atraso_ms
        self._job: Any = None

    @property
    def pendente(self) -> bool:
        return self._job is not None

    def pedir(self) -> None:
        if self._job is not None:
            self._cancelar(self._job)
        self._job = self._agendar(self._atraso_ms, self._executar)

    def _executar(self) -> None:
        self._job = None
        self._salvar()

    def executar_agora(self) -> None:
        """Cancela o pendente e grava imediatamente (usado ao fechar)."""
        if self._job is not None:
            self._cancelar(self._job)
            self._job = None
        self._salvar()
