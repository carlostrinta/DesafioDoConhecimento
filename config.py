"""
Configuração do Desafio do Conhecimento — Etapa 4.2.

O `config.json` fica ao lado do executável (rodando pelo fonte, na pasta do
projeto); se não existir, tenta a pasta do script. Sem o arquivo, valem os
padrões históricos — o comportamento é idêntico ao da versão anterior.

A leitura é tolerante: JSON inválido, chave desconhecida ou valor fora da
regra nunca derrubam o jogo. Cada valor inválido volta ao padrão com WARNING
no log e um aviso na tela (via `Configuracao.avisos`); chave desconhecida só
gera WARNING no log.

Sem dependência de tkinter, pygame ou serial: pode ser importado em qualquer
ambiente, inclusive nos testes headless.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field

from recursos import obter_diretorio_base

log = logging.getLogger("desafio.config")

# ─── Arquivos ───
NOME_ARQUIVO_CONFIG = "config.json"
NOME_ARQUIVO_EXEMPLO = "config.exemplo.json"

# ─── Identidade (não configurável nesta etapa) ───
TITULO = "Desafio de Conhecimento"
EQUIPES = ("A", "B", "C", "D")

# ─── Padrões (idênticos aos da Etapa 3.1) ───
TEMPO_PERGUNTA_PADRAO = 30
TEMPO_RESPOSTA_PADRAO = 15
PONTUAR_APOS_TEMPO_PADRAO = False
NUM_EQUIPES_PADRAO = 2
NOMES_EQUIPES_PADRAO = {
    "A": "Competidor A",
    "B": "Competidor B",
    "C": "Competidor C",
    "D": "Competidor D",
}
PORTA_SERIAL_PADRAO = None          # None = autodetectar
TIMEOUT_PRONTO_PADRAO = 3.0         # s esperando "PRONTO" depois de abrir a porta
BAUD_RATE_PADRAO = 9600
PASTA_PERGUNTAS_PADRAO = "."        # relativa à pasta da aplicação
ARQUIVO_PERGUNTAS_PADRAO = "conhecimentos_gerais.json"
SOM_ATIVO_PADRAO = True
VOLUME_AUDIO_PADRAO = 1.0
BUFFER_AUDIO_PADRAO = 512
CONTAGEM_LARGADA_PADRAO = 3
MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO = False
DURACAO_OVERLAY_JA_PADRAO = 1.0
CONTINUAR_AUTOMATICO_PADRAO = False

# ─── Limites de validação ───
MAX_NOME_EQUIPE = 24
BAUD_MINIMO = 1200
BAUD_MAXIMO = 115200
TIMEOUT_PRONTO_MINIMO = 0.1
TIMEOUT_PRONTO_MAXIMO = 30.0
VOLUME_AUDIO_MINIMO = 0.0
VOLUME_AUDIO_MAXIMO = 1.0
BUFFER_AUDIO_MINIMO = 128
BUFFER_AUDIO_MAXIMO = 2048
CONTAGEM_LARGADA_MINIMO = 0
CONTAGEM_LARGADA_MAXIMO = 10
DURACAO_OVERLAY_JA_MINIMO = 0.3
DURACAO_OVERLAY_JA_MAXIMO = 3.0

_SECOES = {
    "tempos": {"tempo_pergunta", "tempo_resposta"},
    "jogo": {
        "num_equipes",
        "pontuar_apos_tempo",
        "contagem_largada",
        "mostrar_pergunta_na_contagem",
    },
    "nomes_equipes": set(EQUIPES),
    "ui": {"duracao_overlay_ja"},
    "serial": {"porta", "baud_rate", "timeout_pronto"},
    "perguntas": {"pasta", "arquivo_padrao"},
    "audio": {"ativo", "volume", "buffer"},
    "persistencia": {"continuar_automatico"},
}

_RE_COM = re.compile(r"^COM\d+$", re.IGNORECASE)
_RE_VID_PID = re.compile(r"^[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}$")


@dataclass(frozen=True)
class Configuracao:
    """Valores validados em uso pelo jogo."""

    tempo_pergunta: int = TEMPO_PERGUNTA_PADRAO
    tempo_resposta: int = TEMPO_RESPOSTA_PADRAO
    pontuar_apos_tempo: bool = PONTUAR_APOS_TEMPO_PADRAO
    num_equipes: int = NUM_EQUIPES_PADRAO
    num_equipes_configurado: int = NUM_EQUIPES_PADRAO
    contagem_largada: int = CONTAGEM_LARGADA_PADRAO
    mostrar_pergunta_na_contagem: bool = MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO
    duracao_overlay_ja: float = DURACAO_OVERLAY_JA_PADRAO
    nomes_equipes: dict[str, str] = field(
        default_factory=lambda: dict(NOMES_EQUIPES_PADRAO)
    )
    porta_serial: str | None = PORTA_SERIAL_PADRAO
    timeout_pronto: float = TIMEOUT_PRONTO_PADRAO
    baud_rate: int = BAUD_RATE_PADRAO
    pasta_perguntas: str = ""
    arquivo_perguntas: str = ARQUIVO_PERGUNTAS_PADRAO
    som_ativo: bool = SOM_ATIVO_PADRAO
    volume_audio: float = VOLUME_AUDIO_PADRAO
    buffer_audio: int = BUFFER_AUDIO_PADRAO
    continuar_automatico: bool = CONTINUAR_AUTOMATICO_PADRAO
    avisos: tuple[str, ...] = ()
    caminho_config: str | None = None
    encontrado: bool = False

    @property
    def buffer(self) -> int:
        """Alias curto para `buffer_audio` (nome da chave no config.json)."""
        return self.buffer_audio

    @property
    def caminho_perguntas_padrao(self) -> str:
        return os.path.join(self.pasta_perguntas, self.arquivo_perguntas)


# -----------------------------------------------------
# Leitura e localização
# -----------------------------------------------------
def localizar_config(diretorio_base=None):
    """Caminho do `config.json` ao lado da aplicação ou, na falta, do script."""
    base = os.path.abspath(diretorio_base or obter_diretorio_base())
    candidatos = [base]
    script = os.path.dirname(os.path.abspath(__file__))
    if script not in candidatos:
        candidatos.append(script)

    for pasta in candidatos:
        caminho = os.path.join(pasta, NOME_ARQUIVO_CONFIG)
        if os.path.isfile(caminho):
            return caminho
    return None


def carregar(caminho=None, diretorio_base=None) -> Configuracao:
    """
    Lê e valida o `config.json`, devolvendo uma `Configuracao`.

    `caminho` explícito serve aos testes; sem ele, procura ao lado do
    executável e depois na pasta do script. Arquivo ausente = padrões.
    """
    base = os.path.abspath(diretorio_base or obter_diretorio_base())
    avisos: list[str] = []

    if caminho is None:
        caminho = localizar_config(base)
        if caminho is None:
            log.info(
                "config.json não encontrado em %s; usando os padrões.", base
            )
    else:
        caminho = os.path.abspath(caminho)
        if not os.path.isfile(caminho):
            log.info(
                "config.json não encontrado em %s; usando os padrões.", caminho
            )
            caminho = None

    encontrado = caminho is not None
    dados = {}

    if encontrado:
        try:
            with open(caminho, "r", encoding="utf-8-sig") as arquivo:
                dados = json.load(arquivo)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            _aviso(avisos, "config.json inválido; usando os padrões.")
            log.error("config.json inválido (%s): %s", caminho, e)
            dados = {}

    if not isinstance(dados, dict):
        _aviso(avisos, "config.json deve conter um objeto JSON; usando os padrões.")
        dados = {}

    if dados:
        _chaves_desconhecidas(dados, set(_SECOES), "")

    tempos = _secao(dados, "tempos", avisos)
    jogo = _secao(dados, "jogo", avisos)
    ui = _secao(dados, "ui", avisos)
    nomes = _secao(dados, "nomes_equipes", avisos)
    serial = _secao(dados, "serial", avisos)
    perguntas = _secao(dados, "perguntas", avisos)
    audio = _secao(dados, "audio", avisos)
    persistencia = _secao(dados, "persistencia", avisos)

    tempo_pergunta = _ler_inteiro(
        tempos, "tempo_pergunta", "tempos.tempo_pergunta",
        TEMPO_PERGUNTA_PADRAO, avisos, minimo=1,
    )
    tempo_resposta = _ler_inteiro(
        tempos, "tempo_resposta", "tempos.tempo_resposta",
        TEMPO_RESPOSTA_PADRAO, avisos, minimo=1,
    )
    pontuar_apos_tempo = _ler_booleano(
        jogo, "pontuar_apos_tempo", "jogo.pontuar_apos_tempo",
        PONTUAR_APOS_TEMPO_PADRAO, avisos,
    )
    num_pedido = _ler_inteiro(
        jogo, "num_equipes", "jogo.num_equipes",
        NUM_EQUIPES_PADRAO, avisos, minimo=2, maximo=4,
    )

    contagem_largada = _ler_inteiro(
        jogo, "contagem_largada", "jogo.contagem_largada",
        CONTAGEM_LARGADA_PADRAO, avisos,
        minimo=CONTAGEM_LARGADA_MINIMO, maximo=CONTAGEM_LARGADA_MAXIMO,
    )
    mostrar_pergunta_na_contagem = _ler_booleano(
        jogo,
        "mostrar_pergunta_na_contagem",
        "jogo.mostrar_pergunta_na_contagem",
        MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO,
        avisos,
    )
    duracao_overlay_ja = _ler_duracao_overlay_ja(ui, avisos)

    nomes_equipes = _ler_nomes(nomes, avisos)
    porta_serial = _ler_porta(serial, avisos)
    baud_rate = _ler_inteiro(
        serial, "baud_rate", "serial.baud_rate",
        BAUD_RATE_PADRAO, avisos, minimo=BAUD_MINIMO, maximo=BAUD_MAXIMO,
    )
    timeout_pronto = _ler_timeout(serial, avisos)
    pasta_perguntas = _resolver_pasta(perguntas, base, avisos)
    arquivo_perguntas = _ler_arquivo(perguntas, avisos)
    caminho_padrao = os.path.join(pasta_perguntas, arquivo_perguntas)
    if not os.path.isfile(caminho_padrao):
        log.warning(
            "perguntas.arquivo_padrao %r não existe em %s; "
            "o seletor de temas será aberto.",
            arquivo_perguntas,
            pasta_perguntas,
        )
    som_ativo = _ler_booleano(
        audio, "ativo", "audio.ativo", SOM_ATIVO_PADRAO, avisos,
    )
    volume_audio = _ler_volume(audio, avisos)
    buffer_audio = _ler_inteiro(
        audio, "buffer", "audio.buffer",
        BUFFER_AUDIO_PADRAO, avisos,
        minimo=BUFFER_AUDIO_MINIMO, maximo=BUFFER_AUDIO_MAXIMO,
    )
    continuar_automatico = _ler_booleano(
        persistencia,
        "continuar_automatico",
        "persistencia.continuar_automatico",
        CONTINUAR_AUTOMATICO_PADRAO,
        avisos,
    )

    return Configuracao(
        tempo_pergunta=tempo_pergunta,
        tempo_resposta=tempo_resposta,
        pontuar_apos_tempo=pontuar_apos_tempo,
        num_equipes=num_pedido,
        num_equipes_configurado=num_pedido,
        contagem_largada=contagem_largada,
        mostrar_pergunta_na_contagem=mostrar_pergunta_na_contagem,
        duracao_overlay_ja=duracao_overlay_ja,
        nomes_equipes=nomes_equipes,
        porta_serial=porta_serial,
        timeout_pronto=timeout_pronto,
        baud_rate=baud_rate,
        pasta_perguntas=pasta_perguntas,
        arquivo_perguntas=arquivo_perguntas,
        som_ativo=som_ativo,
        volume_audio=volume_audio,
        buffer_audio=buffer_audio,
        continuar_automatico=continuar_automatico,
        avisos=tuple(avisos),
        caminho_config=caminho,
        encontrado=encontrado,
    )


def modelo_padrao() -> dict:
    """Conteúdo de um `config.json` com todos os padrões (para criar do zero)."""
    return {
        "tempos": {
            "tempo_pergunta": TEMPO_PERGUNTA_PADRAO,
            "tempo_resposta": TEMPO_RESPOSTA_PADRAO,
        },
        "jogo": {
            "num_equipes": NUM_EQUIPES_PADRAO,
            "pontuar_apos_tempo": PONTUAR_APOS_TEMPO_PADRAO,
            "contagem_largada": CONTAGEM_LARGADA_PADRAO,
            "mostrar_pergunta_na_contagem": MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO,
        },
        "ui": {
            "duracao_overlay_ja": DURACAO_OVERLAY_JA_PADRAO,
        },
        "nomes_equipes": dict(NOMES_EQUIPES_PADRAO),
        "serial": {
            "porta": (
                "auto" if PORTA_SERIAL_PADRAO is None else PORTA_SERIAL_PADRAO
            ),
            "baud_rate": BAUD_RATE_PADRAO,
            "timeout_pronto": TIMEOUT_PRONTO_PADRAO,
        },
        "perguntas": {
            "pasta": PASTA_PERGUNTAS_PADRAO,
            "arquivo_padrao": ARQUIVO_PERGUNTAS_PADRAO,
        },
        "audio": {
            "ativo": SOM_ATIVO_PADRAO,
            "volume": VOLUME_AUDIO_PADRAO,
            "buffer": BUFFER_AUDIO_PADRAO,
        },
        "persistencia": {
            "continuar_automatico": CONTINUAR_AUTOMATICO_PADRAO,
        },
    }


def criar_config_exemplo(destino=None, diretorio_base=None) -> bool:
    """
    Cria `config.json` a partir do `config.exemplo.json` (opcional).

    Não é chamado automaticamente. Devolve False se o destino já existir.
    """
    base = os.path.abspath(diretorio_base or obter_diretorio_base())
    destino = os.path.abspath(destino or os.path.join(base, NOME_ARQUIVO_CONFIG))
    if os.path.exists(destino):
        return False

    exemplo = None
    for pasta in (base, os.path.dirname(os.path.abspath(__file__))):
        candidato = os.path.join(pasta, NOME_ARQUIVO_EXEMPLO)
        if os.path.isfile(candidato):
            exemplo = candidato
            break

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if exemplo:
        shutil.copyfile(exemplo, destino)
    else:
        with open(destino, "w", encoding="utf-8") as arquivo:
            json.dump(modelo_padrao(), arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
    return True


def texto_avisos(avisos) -> str:
    """Mensagem única para a tela (sem detalhes técnicos)."""
    return "Configuração:\n\n" + "\n".join(f"• {aviso}" for aviso in avisos)


# -----------------------------------------------------
# Validação (cada problema vira WARNING no log)
# -----------------------------------------------------
def _aviso(avisos, mensagem):
    log.warning("config.json: %s", mensagem)
    avisos.append(mensagem)


def _chaves_desconhecidas(dados, conhecidas, prefixo):
    for chave in dados:
        if chave not in conhecidas:
            log.warning(
                "config.json: chave desconhecida %s%s (ignorada)", prefixo, chave
            )


def _secao(dados, nome, avisos):
    if nome not in dados:
        return {}
    valor = dados[nome]
    if not isinstance(valor, dict):
        _aviso(avisos, f"{nome}: deve ser um objeto JSON; usando os padrões.")
        return {}
    _chaves_desconhecidas(valor, _SECOES[nome], f"{nome}.")
    return valor


def _ler_inteiro(secao, chave, nome, padrao, avisos, *, minimo, maximo=None):
    if chave not in secao:
        return padrao
    valor = secao[chave]
    fora = isinstance(valor, bool) or not isinstance(valor, int)
    if not fora and valor < minimo:
        fora = True
    if not fora and maximo is not None and valor > maximo:
        fora = True
    if fora:
        faixa = (
            f"entre {minimo} e {maximo}" if maximo is not None else f">= {minimo}"
        )
        _aviso(
            avisos,
            f"{nome}: valor inválido {valor!r}; use inteiro {faixa}; "
            f"usando {padrao}.",
        )
        return padrao
    return valor


def _ler_booleano(secao, chave, nome, padrao, avisos):
    if chave not in secao:
        return padrao
    valor = secao[chave]
    if not isinstance(valor, bool):
        _aviso(
            avisos,
            f"{nome}: valor inválido {valor!r}; use true ou false; "
            f"usando {str(padrao).lower()}.",
        )
        return padrao
    return valor


def _ler_volume(secao, avisos):
    chave = "volume"
    nome = "audio.volume"
    if chave not in secao:
        return VOLUME_AUDIO_PADRAO
    valor = secao[chave]
    valido = (
        not isinstance(valor, bool)
        and isinstance(valor, (int, float))
        and VOLUME_AUDIO_MINIMO <= valor <= VOLUME_AUDIO_MAXIMO
    )
    if not valido:
        _aviso(
            avisos,
            f"{nome}: valor inválido {valor!r}; use número entre "
            f"{VOLUME_AUDIO_MINIMO:g} e {VOLUME_AUDIO_MAXIMO:g}; "
            f"usando {VOLUME_AUDIO_PADRAO:g}.",
        )
        return VOLUME_AUDIO_PADRAO
    return float(valor)


def _ler_timeout(secao, avisos):
    chave = "timeout_pronto"
    nome = "serial.timeout_pronto"
    if chave not in secao:
        return TIMEOUT_PRONTO_PADRAO
    valor = secao[chave]
    valido = (
        not isinstance(valor, bool)
        and isinstance(valor, (int, float))
        and TIMEOUT_PRONTO_MINIMO <= valor <= TIMEOUT_PRONTO_MAXIMO
    )
    if not valido:
        _aviso(
            avisos,
            f"{nome}: valor inválido {valor!r}; use número entre "
            f"{TIMEOUT_PRONTO_MINIMO} e {TIMEOUT_PRONTO_MAXIMO:g}; "
            f"usando {TIMEOUT_PRONTO_PADRAO:g}.",
        )
        return TIMEOUT_PRONTO_PADRAO
    return float(valor)


def _ler_duracao_overlay_ja(secao, avisos):
    chave = "duracao_overlay_ja"
    nome = "ui.duracao_overlay_ja"
    if chave not in secao:
        return DURACAO_OVERLAY_JA_PADRAO
    valor = secao[chave]
    valido = (
        not isinstance(valor, bool)
        and isinstance(valor, (int, float))
        and DURACAO_OVERLAY_JA_MINIMO <= valor <= DURACAO_OVERLAY_JA_MAXIMO
    )
    if not valido:
        _aviso(
            avisos,
            f"{nome}: valor inválido {valor!r}; use número entre "
            f"{DURACAO_OVERLAY_JA_MINIMO:g} e {DURACAO_OVERLAY_JA_MAXIMO:g}; "
            f"usando {DURACAO_OVERLAY_JA_PADRAO:g}.",
        )
        return DURACAO_OVERLAY_JA_PADRAO
    return float(valor)


def _ler_nomes(secao, avisos):
    nomes = dict(NOMES_EQUIPES_PADRAO)
    for equipe, valor in secao.items():
        if equipe not in EQUIPES:
            continue  # chave desconhecida já registrada por _secao()
        if not isinstance(valor, str):
            _aviso(
                avisos,
                f"nomes_equipes.{equipe}: valor inválido {valor!r}; "
                f"usando {NOMES_EQUIPES_PADRAO[equipe]!r}.",
            )
            continue
        nome = valor.strip()
        if not nome or len(nome) > MAX_NOME_EQUIPE:
            _aviso(
                avisos,
                f"nomes_equipes.{equipe}: use texto de 1 a {MAX_NOME_EQUIPE} "
                f"caracteres; usando {NOMES_EQUIPES_PADRAO[equipe]!r}.",
            )
            continue
        nomes[equipe] = nome
    return nomes


def _ler_porta(secao, avisos):
    if "porta" not in secao:
        return PORTA_SERIAL_PADRAO
    valor = secao["porta"]
    if valor is None:
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.lower() == "auto":
            return None
        if _RE_COM.match(texto):
            return texto.upper()
        if _RE_VID_PID.match(texto):
            return texto.upper()
    _aviso(
        avisos,
        f"serial.porta: valor inválido {valor!r}; use \"auto\", COMx ou "
        "VID:PID (ex.: 1A86:7523); usando auto.",
    )
    return None


def _resolver_pasta(secao, base, avisos):
    valor = secao.get("pasta", PASTA_PERGUNTAS_PADRAO)
    if not isinstance(valor, str) or not valor.strip():
        _aviso(
            avisos,
            f"perguntas.pasta: valor inválido {valor!r}; use um caminho de "
            "pasta; usando a pasta da aplicação.",
        )
        return base

    texto = os.path.expanduser(valor.strip())
    caminho = texto if os.path.isabs(texto) else os.path.join(base, texto)
    caminho = os.path.abspath(caminho)
    if not _pasta_utilizavel(caminho):
        _aviso(
            avisos,
            f"perguntas.pasta: pasta não encontrada ou sem permissão "
            f"({caminho}); usando a pasta da aplicação.",
        )
        return base
    return caminho


def _pasta_utilizavel(caminho):
    """True se a pasta existe, pode ser lida e listada (checagem real)."""
    try:
        if not os.path.isdir(caminho):
            return False
        if not os.access(caminho, os.R_OK | os.X_OK):
            return False
        os.listdir(caminho)
    except OSError:
        return False
    return True


def _ler_arquivo(secao, avisos):
    if "arquivo_padrao" not in secao:
        return ARQUIVO_PERGUNTAS_PADRAO
    valor = secao["arquivo_padrao"]
    texto = valor.strip() if isinstance(valor, str) else ""
    valido = (
        texto
        and texto == os.path.basename(texto)
        and texto.lower().endswith(".json")
    )
    if not valido:
        _aviso(
            avisos,
            f"perguntas.arquivo_padrao: valor inválido {valor!r}; use o nome "
            f"de um arquivo .json (sem pasta); usando "
            f"{ARQUIVO_PERGUNTAS_PADRAO!r}.",
        )
        return ARQUIVO_PERGUNTAS_PADRAO
    return texto


# -----------------------------------------------------
# Valores em uso (compatibilidade com quem importa `config`)
# -----------------------------------------------------
CONFIG = carregar()

TEMPO_PERGUNTA = CONFIG.tempo_pergunta
TEMPO_RESPOSTA = CONFIG.tempo_resposta
PONTUAR_APOS_TEMPO = CONFIG.pontuar_apos_tempo
NUM_EQUIPES = CONFIG.num_equipes
CONTAGEM_LARGADA = CONFIG.contagem_largada
MOSTRAR_PERGUNTA_NA_CONTAGEM = CONFIG.mostrar_pergunta_na_contagem
DURACAO_OVERLAY_JA = CONFIG.duracao_overlay_ja
NOMES_EQUIPES = dict(CONFIG.nomes_equipes)
PORTA_FORCADA = CONFIG.porta_serial
TIMEOUT_PRONTO = CONFIG.timeout_pronto
BAUD_RATE = CONFIG.baud_rate
PASTA_PERGUNTAS = CONFIG.pasta_perguntas
ARQUIVO_PERGUNTAS = CONFIG.arquivo_perguntas
SOM_ATIVO = CONFIG.som_ativo
VOLUME_AUDIO = CONFIG.volume_audio
BUFFER_AUDIO = CONFIG.buffer_audio
CONTINUAR_AUTOMATICO = CONFIG.continuar_automatico
AVISOS_CONFIG = CONFIG.avisos
