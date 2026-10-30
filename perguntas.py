"""
Perguntas: modelo, carregador/validador único, listagem e nomes de tema.

Módulo puro — sem tkinter, serial, pygame ou pygame.mixer. Pode ser importado
em qualquer ambiente (inclusive nos testes headless) e não importa `jogo`
para não criar dependência circular: é `jogo.py` que importa daqui.

A apresentação (emoji do tema, cores, fontes) não mora aqui — `obter_icone_tema`
continua na UI.
"""

from __future__ import annotations

import json
import logging
import os

from dataclasses import dataclass, field

log = logging.getLogger("desafio.perguntas")


@dataclass
class Pergunta:
    categoria: str
    texto: str
    alternativas: list[str]
    correta: int
    explicacao: str = ""


# ─────────────────────────────────────────────────────────
# Carregador/validador ÚNICO de perguntas do projeto.
# ─────────────────────────────────────────────────────────
@dataclass
class CargaPerguntas:
    tema: str
    perguntas: list[Pergunta] = field(default_factory=list)
    erro: str = ""
    ignoradas: list[str] = field(default_factory=list)


ENCODINGS_PERGUNTAS = ("utf-8-sig", "utf-8", "latin-1")


def ler_conteudo_banco(caminho: str) -> tuple[object | None, str]:
    """
    Lê o JSON de um banco usando a mesma ordem de codificações do carregador.

    Devolve `(conteudo, "")` em caso de sucesso ou `(None, mensagem)` quando
    todas as codificações falham. É a única rotina de leitura de banco; o
    carregador e o editor usam esta função.
    """
    nome_arquivo = os.path.basename(caminho)
    for enc in ENCODINGS_PERGUNTAS:
        try:
            with open(caminho, "r", encoding=enc) as f:
                return json.load(f), ""
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        except OSError as e:
            return None, f"Não foi possível ler {nome_arquivo}: {e}"

    return (
        None,
        f"Não foi possível ler {nome_arquivo}: arquivo inválido ou "
        "codificação incompatível.",
    )


def ler_banco_perguntas(
    caminho: str,
    tema_padrao: str = "",
    aceitar_tema_do_arquivo: bool = True,
) -> CargaPerguntas:
    """
    Lê e valida um banco de perguntas.

    Formato aceito: lista de perguntas, ou objeto com a chave "perguntas"
    (opcionalmente com "tema"). Cada pergunta precisa de 2 a 4 alternativas e
    "correta" dentro do intervalo; o texto pode vir em "pergunta" ou "texto".

    Nunca levanta exceção por conteúdo inválido: devolve `erro` (falha de
    leitura/estrutura) e `ignoradas` (perguntas descartadas, com o motivo).
    """
    nome_arquivo = os.path.basename(caminho)
    carga = CargaPerguntas(tema=tema_padrao or nome_arquivo)

    conteudo, erro_leitura = ler_conteudo_banco(caminho)
    if erro_leitura:
        carga.erro = erro_leitura
        return carga

    if conteudo is None:
        carga.erro = (
            f"Não foi possível ler {nome_arquivo}: arquivo inválido ou "
            "codificação incompatível."
        )
        return carga

    if isinstance(conteudo, dict):
        if aceitar_tema_do_arquivo:
            tema_arquivo = conteudo.get("tema") or conteudo.get("titulo")
            if tema_arquivo:
                carga.tema = str(tema_arquivo)
        bruto = conteudo.get("perguntas", [])
    elif isinstance(conteudo, list):
        bruto = conteudo
    else:
        carga.erro = (
            f"Não foi possível ler {nome_arquivo}: o arquivo deve conter uma "
            "lista de perguntas ou objeto com 'perguntas'."
        )
        return carga

    if not isinstance(bruto, list):
        # Ex.: config.json, cujo "perguntas" é um objeto com pasta/arquivo padrão
        carga.erro = (
            f"Não foi possível ler {nome_arquivo}: o campo 'perguntas' deve ser uma lista."
        )
        return carga

    for i, q in enumerate(bruto, 1):
        try:
            alts = [str(a) for a in q["alternativas"]]
            correta = int(q["correta"])
            if not 2 <= len(alts) <= 4:
                raise ValueError("use de 2 a 4 alternativas")
            if not 0 <= correta < len(alts):
                raise ValueError("'correta' fora do intervalo")
            texto = q.get("pergunta")
            if texto is None:
                texto = q.get("texto")
            if texto is None:
                raise ValueError("campo 'pergunta' ausente")
            carga.perguntas.append(
                Pergunta(
                    categoria=str(q.get("categoria", carga.tema or "Geral")),
                    texto=str(texto),
                    alternativas=alts,
                    correta=correta,
                    explicacao=str(q.get("explicacao", "")),
                )
            )
        except Exception as e:
            carga.ignoradas.append(f"Pergunta #{i} ignorada: {e}")
            log.warning("Pergunta #%d ignorada em %s: %s", i, nome_arquivo, e)

    return carga


def carregar_perguntas_json(caminho: str) -> list[Pergunta]:
    """Atalho de compatibilidade: só a lista de perguntas do carregador único."""
    return ler_banco_perguntas(caminho).perguntas


# ─────────────────────────────────────────────────────────
# Validação por campo (editor) — mesmas regras do carregador
# ─────────────────────────────────────────────────────────
LIMITE_ENUNCIADO_MIN = 5
LIMITE_ENUNCIADO_MAX = 500
LIMITE_ALTERNATIVA_MIN = 1
LIMITE_ALTERNATIVA_MAX = 300
LIMITE_EXPLICACAO_MAX = 1000
LIMITE_CATEGORIA_MIN = 1
LIMITE_CATEGORIA_MAX = 80
MIN_ALTERNATIVAS = 2
MAX_ALTERNATIVAS = 4
MIN_PERGUNTAS = 1
MAX_PERGUNTAS_PRATICO = 5000

SEVERIDADE_ERRO = "erro"
SEVERIDADE_AVISO = "aviso"


@dataclass(frozen=True)
class ErroCampo:
    """Resultado de validação de um campo, pronto para a UI."""

    campo: str
    mensagem: str
    severidade: str = SEVERIDADE_ERRO
    indice: int | None = None
    alternativa: int | None = None

    @property
    def bloqueante(self) -> bool:
        return self.severidade == SEVERIDADE_ERRO

    def __str__(self) -> str:
        prefixo = f"Pergunta {self.indice + 1}: " if self.indice is not None else ""
        return prefixo + self.mensagem


def normalizar_texto_duplicata(texto: object) -> str:
    """Normaliza para comparar duplicatas: strip, espaços e caixa."""
    return " ".join(str(texto or "").split()).casefold()


def _validar_texto(
    dados: dict,
    campo: str,
    *,
    indice: int | None,
    obrigatorio: bool,
    minimo: int,
    maximo: int,
    rotulo: str,
) -> list[ErroCampo]:
    erros: list[ErroCampo] = []
    valor = dados.get(campo)
    if valor is None:
        if obrigatorio:
            mensagem = (
                "Escreva o enunciado da pergunta."
                if campo == "pergunta"
                else f"Informe {rotulo}."
            )
            erros.append(
                ErroCampo(
                    campo,
                    mensagem,
                    indice=indice,
                )
            )
        return erros

    if not isinstance(valor, str):
        erros.append(
            ErroCampo(
                campo,
                f"{rotulo.capitalize()} deve ser um texto.",
                indice=indice,
            )
        )
        return erros

    limpo = valor.strip()
    if obrigatorio and not limpo:
        erros.append(
            ErroCampo(
                campo,
                f"Escreva {rotulo}." if campo == "pergunta" else f"Informe {rotulo}.",
                indice=indice,
            )
        )
        return erros
    if len(limpo) < minimo:
        erros.append(
            ErroCampo(
                campo,
                f"{rotulo.capitalize()} precisa ter pelo menos {minimo} caracteres.",
                indice=indice,
            )
        )
    if len(limpo) > maximo:
        erros.append(
            ErroCampo(
                campo,
                f"{rotulo.capitalize()} passa do limite de {maximo} caracteres.",
                indice=indice,
            )
        )
    return erros


def validar_pergunta(
    dados: object,
    indice: int | None = None,
) -> list[ErroCampo]:
    """
    Valida uma pergunta por campo, acumulando erros e avisos.

    Usa os mesmos limites e a mesma representação do carregador único. O
    carregador continua aceitando arquivos antigos como antes; esta função é a
    camada estrita usada pelo editor antes de salvar.
    """
    if not isinstance(dados, dict):
        return [
            ErroCampo(
                "pergunta",
                "A pergunta precisa ser um objeto JSON.",
                indice=indice,
            )
        ]

    erros: list[ErroCampo] = []

    # Enunciado: aceita "pergunta" (formato atual) e "texto" (alias legado).
    texto = dados.get("pergunta")
    if texto is None:
        texto = dados.get("texto")
    dados_texto = dict(dados)
    dados_texto["pergunta"] = texto
    erros.extend(
        _validar_texto(
            dados_texto,
            "pergunta",
            indice=indice,
            obrigatorio=True,
            minimo=LIMITE_ENUNCIADO_MIN,
            maximo=LIMITE_ENUNCIADO_MAX,
            rotulo="o enunciado",
        )
    )

    alternativas = dados.get("alternativas")
    if not isinstance(alternativas, list):
        erros.append(
            ErroCampo(
                "alternativas",
                "Informe as alternativas da pergunta.",
                indice=indice,
            )
        )
        alternativas = []
    elif len(alternativas) < MIN_ALTERNATIVAS:
        erros.append(
            ErroCampo(
                "alternativas",
                f"Informe pelo menos {MIN_ALTERNATIVAS} alternativas.",
                indice=indice,
            )
        )
    elif len(alternativas) > MAX_ALTERNATIVAS:
        erros.append(
            ErroCampo(
                "alternativas",
                f"Informe no máximo {MAX_ALTERNATIVAS} alternativas.",
                indice=indice,
            )
        )

    vistos: dict[str, int] = {}
    for i, alternativa in enumerate(alternativas):
        campo = f"alternativas[{i}]"
        if not isinstance(alternativa, str):
            erros.append(
                ErroCampo(
                    campo,
                    f"A alternativa {i + 1} deve ser um texto.",
                    indice=indice,
                    alternativa=i,
                )
            )
            continue
        limpa = alternativa.strip()
        if len(limpa) < LIMITE_ALTERNATIVA_MIN:
            erros.append(
                ErroCampo(
                    campo,
                    f"A alternativa {i + 1} está vazia.",
                    indice=indice,
                    alternativa=i,
                )
            )
        if len(limpa) > LIMITE_ALTERNATIVA_MAX:
            erros.append(
                ErroCampo(
                    campo,
                    f"A alternativa {i + 1} passa do limite de "
                    f"{LIMITE_ALTERNATIVA_MAX} caracteres.",
                    indice=indice,
                    alternativa=i,
                )
            )
        chave = normalizar_texto_duplicata(limpa)
        if chave and chave in vistos:
            erros.append(
                ErroCampo(
                    "alternativas",
                    f"As alternativas {vistos[chave] + 1} e {i + 1} são iguais.",
                    severidade=SEVERIDADE_AVISO,
                    indice=indice,
                    alternativa=i,
                )
            )
        elif chave:
            vistos[chave] = i

    correta = dados.get("correta")
    if correta is None:
        erros.append(
            ErroCampo(
                "correta",
                "Marque qual alternativa é a correta.",
                indice=indice,
            )
        )
    elif isinstance(correta, bool) or not isinstance(correta, int):
        erros.append(
            ErroCampo(
                "correta",
                "Marque uma alternativa correta válida.",
                indice=indice,
            )
        )
    elif not 0 <= correta < len(alternativas):
        erros.append(
            ErroCampo(
                "correta",
                "Marque uma alternativa correta válida.",
                indice=indice,
            )
        )

    categoria = dados.get("categoria")
    if categoria is None or (isinstance(categoria, str) and not categoria.strip()):
        erros.append(
            ErroCampo(
                "categoria",
                "Informe a categoria.",
                indice=indice,
            )
        )
    elif not isinstance(categoria, str):
        erros.append(
            ErroCampo(
                "categoria",
                "A categoria deve ser um texto.",
                indice=indice,
            )
        )
    elif len(categoria.strip()) > LIMITE_CATEGORIA_MAX:
        erros.append(
            ErroCampo(
                "categoria",
                f"A categoria passa do limite de {LIMITE_CATEGORIA_MAX} caracteres.",
                indice=indice,
            )
        )

    explicacao = dados.get("explicacao")
    if explicacao is not None and not isinstance(explicacao, str):
        erros.append(
            ErroCampo(
                "explicacao",
                "A explicação deve ser um texto.",
                indice=indice,
            )
        )
    elif isinstance(explicacao, str) and len(explicacao) > LIMITE_EXPLICACAO_MAX:
        erros.append(
            ErroCampo(
                "explicacao",
                f"A explicação passa do limite de "
                f"{LIMITE_EXPLICACAO_MAX:,} caracteres.".replace(",", "."),
                indice=indice,
            )
        )

    return erros


def validar_banco(
    perguntas: object,
    metadados: dict | None = None,
) -> list[ErroCampo]:
    """
    Valida a lista inteira e sinaliza duplicatas como aviso, nunca como erro.

    `metadados` é aceito para a UI, mas não bloqueia a gravação nesta etapa.
    """
    del metadados  # reservado para validações futuras de envelope

    if not isinstance(perguntas, list):
        return [
            ErroCampo(
                "perguntas",
                "O banco precisa conter uma lista de perguntas.",
            )
        ]

    erros: list[ErroCampo] = []
    if len(perguntas) < MIN_PERGUNTAS:
        erros.append(
            ErroCampo(
                "perguntas",
                f"O banco precisa ter pelo menos {MIN_PERGUNTAS} pergunta.",
            )
        )
    if len(perguntas) > MAX_PERGUNTAS_PRATICO:
        erros.append(
            ErroCampo(
                "perguntas",
                f"O banco passa do limite prático de "
                f"{MAX_PERGUNTAS_PRATICO:,} perguntas.".replace(",", "."),
            )
        )

    vistos: dict[str, int] = {}
    for i, pergunta in enumerate(perguntas):
        erros.extend(validar_pergunta(pergunta, indice=i))
        if not isinstance(pergunta, dict):
            continue
        texto = pergunta.get("pergunta")
        if texto is None:
            texto = pergunta.get("texto")
        chave = normalizar_texto_duplicata(texto)
        if not chave:
            continue
        if chave in vistos:
            erros.append(
                ErroCampo(
                    "pergunta",
                    f"A pergunta {i + 1} repete a pergunta {vistos[chave] + 1}.",
                    severidade=SEVERIDADE_AVISO,
                    indice=i,
                )
            )
        else:
            vistos[chave] = i

    return erros


def erros_bloqueantes(erros: list[ErroCampo]) -> list[ErroCampo]:
    """Somente os erros que impedem a gravação (avisos ficam de fora)."""
    return [erro for erro in erros if erro.bloqueante]


def avisos_de_validacao(erros: list[ErroCampo]) -> list[ErroCampo]:
    """Somente os avisos (por exemplo, perguntas duplicadas)."""
    return [erro for erro in erros if not erro.bloqueante]


# ─────────────────────────────────────────────────────────
# Temas: nome legível, inspeção e listagem
# ─────────────────────────────────────────────────────────
def formatar_nome_tema(nome_arquivo):
    """Converte o nome do arquivo em um título legível e amigável."""
    base = os.path.splitext(os.path.basename(nome_arquivo))[0]
    mapa_termos = {
        "conhecimentos_gerais": "Conhecimentos Gerais",
        "conhecimento_gerais": "Conhecimentos Gerais",
        "conhecimentos gerais": "Conhecimentos Gerais",
        "conhecimento gerais": "Conhecimentos Gerais",
        "eletrotecnica": "Eletrotécnica",
        "eletrotécnica": "Eletrotécnica",
        "radiologia": "Radiologia",
        "ti": "Tecnologia da Informação",
        "tecnologia_da_informacao": "Tecnologia da Informação",
        "mecanica": "Mecânica",
        "mecânica": "Mecânica",
        "enfermagem": "Enfermagem",
        "seguranca_do_trabalho": "Segurança do Trabalho",
        "perguntas": "Perguntas Gerais",
    }
    chave = base.strip().lower()
    if chave in mapa_termos:
        return mapa_termos[chave]
    limpo = base.replace("_", " ").replace("-", " ")
    palavras = [p.capitalize() for p in limpo.split()]
    return " ".join(palavras) if palavras else base


def inspecionar_arquivo_perguntas(caminho):
    """
    Analisa um arquivo .json e retorna metadados se for um banco de perguntas válido.
    Usa o mesmo carregador/validador do jogo (perguntas.ler_banco_perguntas).
    """
    try:
        if not os.path.isfile(caminho):
            return None
        nome_arquivo = os.path.basename(caminho)
        carga = ler_banco_perguntas(caminho, tema_padrao=formatar_nome_tema(nome_arquivo))
        if carga.erro or not carga.perguntas:
            return None

        categorias = {p.categoria for p in carga.perguntas}
        return {
            "caminho": os.path.abspath(caminho),
            "arquivo": nome_arquivo,
            "titulo": str(carga.tema),
            "total": len(carga.perguntas),
            "categorias": sorted(categorias),
        }
    except Exception as e:
        log.warning("Erro ao inspecionar %s: %s", caminho, e)
        return None


def listar_arquivos_perguntas(diretorio_base):
    """
    Lista todos os arquivos JSON de perguntas na pasta da aplicação e subpastas comuns.
    """
    arquivos = []
    if not os.path.exists(diretorio_base):
        return arquivos

    candidatos = []
    try:
        for f in os.listdir(diretorio_base):
            if f.lower().endswith(".json"):
                candidatos.append(os.path.join(diretorio_base, f))
    except Exception as e:
        log.warning("Erro ao listar pasta base %s: %s", diretorio_base, e)

    # Também inspeciona subpasta 'perguntas' caso exista
    subpasta = os.path.join(diretorio_base, "perguntas")
    if os.path.isdir(subpasta):
        try:
            for f in os.listdir(subpasta):
                if f.lower().endswith(".json"):
                    candidatos.append(os.path.join(subpasta, f))
        except Exception:
            pass

    candidatos_unicos = []
    vistos = set()
    for c in candidatos:
        abs_c = os.path.abspath(c)
        if abs_c not in vistos:
            vistos.add(abs_c)
            candidatos_unicos.append(c)

    for caminho in candidatos_unicos:
        info = inspecionar_arquivo_perguntas(caminho)
        if info:
            arquivos.append(info)

    arquivos.sort(key=lambda x: x["titulo"].lower())
    return arquivos
