"""
Lógica pura do Duelo de Conhecimento — sem dependências de UI, serial ou áudio.
Parametrizável para 2, 3 ou 4 equipes.
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass, field
from typing import Any

# ─── Estados da rodada ───
FASE_AGUARDANDO = 0
FASE_RESPONDENDO = 1
FASE_REVELADA = 2
FASE_PONTUADA = 3

# ─── Equipes suportadas ───
TODAS_EQUIPES = ("A", "B", "C", "D")


@dataclass
class Pergunta:
    categoria: str
    texto: str
    alternativas: list[str]
    correta: int
    explicacao: str = ""


@dataclass
class EstadoRodada:
    fase: int = FASE_AGUARDANDO
    quem_apertou: str | None = None
    tempo_estourou: bool = False
    indice_pergunta: int = 0
    numero_pergunta: int = 0
    pergunta_atual: Pergunta | None = None


class Jogo:
    """
    Máquina de estados do jogo.
    Não conhece tkinter, serial, áudio — apenas recebe eventos e expõe estado.
    """

    def __init__(
        self,
        perguntas: list[Pergunta],
        num_equipes: int = 2,
        tempo_pergunta: int = 30,
        tempo_resposta: int = 15,
        pontuar_apos_tempo: bool = False,
        nomes_equipes: dict[str, str] | None = None,
    ):
        if not 2 <= num_equipes <= 4:
            raise ValueError("num_equipes deve ser 2, 3 ou 4")
        self.num_equipes = num_equipes
        self.equipes_ativas = TODAS_EQUIPES[:num_equipes]

        self.perguntas_base = list(perguntas)
        self.tempo_pergunta = tempo_pergunta
        self.tempo_resposta = tempo_resposta
        self.pontuar_apos_tempo = pontuar_apos_tempo

        self.nomes_equipes = nomes_equipes or {
            "A": "Competidor A",
            "B": "Competidor B",
            "C": "Competidor C",
            "D": "Competidor D",
        }

        # Estado mutável
        self.placar: dict[str, int] = {eq: 0 for eq in self.equipes_ativas}
        self.perguntas: list[Pergunta] = []
        self.estado = EstadoRodada()
        self.timer_fim: float = 0.0
        self.timer_rotulo: str = ""
        self.timer_cor: str = ""

        self._embaralhar_e_preparar()
        # Inicia a primeira pergunta e timer
        self.proxima_pergunta(forcar=True)

    # ─── Carregamento / embaralhamento ───
    def _embaralhar_e_preparar(self) -> None:
        self.perguntas = self.perguntas_base.copy()
        random.shuffle(self.perguntas)
        self.estado.indice_pergunta = 0
        self.estado.numero_pergunta = 0

    def recarregar_perguntas(self, novas: list[Pergunta]) -> None:
        self.perguntas_base = novas
        self._embaralhar_e_preparar()
        self.estado = EstadoRodada()
        self.placar = {eq: 0 for eq in self.equipes_ativas}

    # ─── Timer (usa time.monotonic) ───
    def _iniciar_timer(self, segundos: int, rotulo: str, cor: str) -> None:
        self.timer_fim = time.monotonic() + segundos
        self.timer_rotulo = rotulo
        self.timer_cor = cor

    def _parar_timer(self) -> None:
        self.timer_fim = 0.0

    def timer_restante(self) -> float:
        if self.timer_fim <= 0:
            return 0.0
        return max(0.0, self.timer_fim - time.monotonic())

    def timer_fracao(self) -> float:
        total = self.tempo_pergunta if self.estado.fase == FASE_AGUARDANDO else self.tempo_resposta
        if total <= 0:
            return 0.0
        return max(0.0, self.timer_restante() / total)

    def tick_timer(self) -> bool:
        """Chamado a cada frame. Retorna True se timer estourou agora."""
        if self.timer_fim <= 0:
            return False
        if time.monotonic() >= self.timer_fim:
            self._parar_timer()
            self._tempo_esgotado()
            return True
        return False

    # ─── Eventos de botão (chamados pela UI/Serial) ───
    def apertar_botao(self, equipe: str) -> bool:
        """Retorna True se o botão foi aceito (primeiro a apertar)."""
        if equipe not in self.equipes_ativas:
            return False
        if self.estado.fase != FASE_AGUARDANDO:
            return False
        if self.estado.pergunta_atual is None:
            return False

        self.estado.fase = FASE_RESPONDENDO
        self.estado.quem_apertou = equipe
        self.estado.tempo_estourou = False
        self._iniciar_timer(self.tempo_resposta, f"{self.nomes_equipes[equipe]} respondendo", "")
        return True

    def revelar_resposta(self) -> bool:
        if self.estado.fase != FASE_RESPONDENDO:
            return False
        self.estado.fase = FASE_REVELADA
        self._parar_timer()
        return True

    def confirmar_acerto(self, equipe: str) -> bool:
        if self.estado.fase != FASE_REVELADA:
            return False
        if self.estado.quem_apertou is None:
            return False
        if equipe != self.estado.quem_apertou:
            return False
        if self.estado.tempo_estourou and not self.pontuar_apos_tempo:
            return False

        self.estado.fase = FASE_PONTUADA
        self.placar[equipe] += 1
        return True

    def proxima_pergunta(self, forcar: bool = False) -> bool:
        if not forcar and self.estado.pergunta_atual is not None and self.estado.fase not in (FASE_REVELADA, FASE_PONTUADA):
            return False

        if not self.perguntas:
            self.estado.pergunta_atual = None
            return False

        if self.estado.indice_pergunta >= len(self.perguntas):
            random.shuffle(self.perguntas)
            self.estado.indice_pergunta = 0

        self.estado.pergunta_atual = self.perguntas[self.estado.indice_pergunta]
        self.estado.indice_pergunta += 1
        self.estado.numero_pergunta += 1

        self.estado.fase = FASE_AGUARDANDO
        self.estado.quem_apertou = None
        self.estado.tempo_estourou = False
        self._iniciar_timer(self.tempo_pergunta, "Tempo para apertar", "")
        return True

    def reiniciar_placar(self) -> None:
        for eq in self.equipes_ativas:
            self.placar[eq] = 0

    def _tempo_esgotado(self) -> None:
        if self.estado.fase == FASE_AGUARDANDO:
            # Ninguém apertou: vai para REVELADA sem quem_apertou
            self.estado.fase = FASE_REVELADA
            self.estado.quem_apertou = None
            self.timer_rotulo = "Tempo esgotado"
        elif self.estado.fase == FASE_RESPONDENDO:
            # Quem apertou não respondeu a tempo
            self.estado.fase = FASE_REVELADA
            self.estado.tempo_estourou = True
            self.timer_rotulo = "Tempo esgotado"

    # ─── Serial / estado para persistência ───
    def to_dict(self) -> dict[str, Any]:
        return {
            "placar": self.placar,
            "num_equipes": self.num_equipes,
            "indice_pergunta": self.estado.indice_pergunta,
            "numero_pergunta": self.estado.numero_pergunta,
            "fase": self.estado.fase,
            "quem_apertou": self.estado.quem_apertou,
            "timer_restante": self.timer_restante(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], perguntas: list[Pergunta], **kwargs) -> "Jogo":
        jogo = cls(perguntas, num_equipes=data.get("num_equipes", 2), **kwargs)
        jogo.placar = data.get("placar", {eq: 0 for eq in jogo.equipes_ativas})
        jogo.estado.indice_pergunta = data.get("indice_pergunta", 0)
        jogo.estado.numero_pergunta = data.get("numero_pergunta", 0)
        jogo.estado.fase = data.get("fase", FASE_AGUARDANDO)
        jogo.estado.quem_apertou = data.get("quem_apertou")
        # Nota: timer e fase intermediária NÃO são restaurados (regra da Etapa 4.3)
        jogo.estado.fase = FASE_AGUARDANDO
        jogo._parar_timer()
        if jogo.estado.indice_pergunta > 0 and jogo.estado.indice_pergunta <= len(jogo.perguntas):
            jogo.estado.pergunta_atual = jogo.perguntas[jogo.estado.indice_pergunta - 1]
        return jogo


# ─── Carregamento de perguntas (formato JSON) ───
def carregar_perguntas_json(caminho: str) -> list[Pergunta]:
    import json
    import os

    with open(caminho, "r", encoding="utf-8-sig") as f:
        conteudo = json.load(f)

    bruto = conteudo.get("perguntas", conteudo) if isinstance(conteudo, dict) else conteudo

    resultado = []
    for q in bruto:
        alts = [str(a) for a in q["alternativas"]]
        correta = int(q["correta"])
        if not 2 <= len(alts) <= 4:
            continue
        if not 0 <= correta < len(alts):
            continue
        # Suporta tanto "pergunta" (JSON original) quanto "texto" (serialização de Pergunta)
        texto = q.get("pergunta") or q.get("texto")
        if texto is None:
            continue
        resultado.append(Pergunta(
            categoria=str(q.get("categoria", "Geral")),
            texto=str(texto),
            alternativas=alts,
            correta=correta,
            explicacao=str(q.get("explicacao", "")),
        ))
    return resultado