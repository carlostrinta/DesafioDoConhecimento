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

    conteudo = None
    for enc in ENCODINGS_PERGUNTAS:
        try:
            with open(caminho, "r", encoding=enc) as f:
                conteudo = json.load(f)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        except OSError as e:
            carga.erro = f"Não foi possível ler {nome_arquivo}: {e}"
            return carga

    if conteudo is None:
        carga.erro = f"Não foi possível ler {nome_arquivo}: arquivo inválido ou codificação incompatível."
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
