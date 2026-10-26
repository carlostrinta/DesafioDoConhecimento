"""
Lógica pura do Duelo de Conhecimento — sem dependências de UI, serial ou áudio.
Parametrizável para 2, 3 ou 4 equipes.

Ações do Jogo devolvem uma lista de eventos de domínio; a camada de
apresentação apenas reage a eles (LED, som, serial, tela):

    apertou:X          equipe X apertou o botão (AGUARDANDO -> RESPONDENDO)
    revelou            resposta revelada (RESPONDENDO -> REVELADA)
    pontuou:X          equipe X pontuou (REVELADA -> PONTUADA)
    tempo_esgotado     prazo expirou (transição decidida pelo próprio Jogo)
    proxima_pergunta   nova pergunta carregada
    reiniciou_banco    baralho embaralhado (fim do banco)
    reiniciou_placar   placar zerado
    led_reacender:X    Arduino reiniciou; re-sincronizar o LED de X
    recusado:<motivo>  ação rejeitada; motivos em MOTIVOS_RECUSA
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

# `Pergunta` aparece só em anotações (avaliadas por `from __future__ import
# annotations`); o import fica em TYPE_CHECKING para não haver reexportação
# em tempo de execução (Etapa 3.6).
if TYPE_CHECKING:
    from perguntas import Pergunta


# ─── Estados da rodada ───
FASE_AGUARDANDO = 0
FASE_RESPONDENDO = 1
FASE_REVELADA = 2
FASE_PONTUADA = 3

# ─── Equipes suportadas ───
TODAS_EQUIPES = ("A", "B", "C", "D")

# ─── Motivos de recusa (texto fica na camada de apresentação) ───
MOTIVO_AVANCAR = "avancar"
MOTIVO_REVELAR_AGUARDANDO = "revelar_aguardando"
MOTIVO_ACERTO_FASE = "acerto_fase"
MOTIVO_ACERTO_SEM_QUEM = "acerto_sem_quem"
MOTIVO_ACERTO_OUTRA_EQUIPE = "acerto_outra_equipe"
MOTIVO_ACERTO_TEMPO = "acerto_tempo"

MOTIVOS_RECUSA = (
    MOTIVO_AVANCAR,
    MOTIVO_REVELAR_AGUARDANDO,
    MOTIVO_ACERTO_FASE,
    MOTIVO_ACERTO_SEM_QUEM,
    MOTIVO_ACERTO_OUTRA_EQUIPE,
    MOTIVO_ACERTO_TEMPO,
)

# ─── Motivos de parada do timer (usados para desenhar a barra) ───
TIMER_MOTIVO_REVELADA = "revelada"
TIMER_MOTIVO_TEMPO_ESGOTADO = "tempo_esgotado"

PREFIXO_RECUSA = "recusado:"


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
    Máquina de estados e dono único do tempo.

    Não conhece tkinter, serial nem áudio: recebe ações, devolve eventos de
    domínio e expõe o estado (fase, placar, prazo, fração restante).
    """

    def __init__(
        self,
        perguntas: list[Pergunta],
        num_equipes: int = 2,
        tempo_pergunta: int = 30,
        tempo_resposta: int = 15,
        pontuar_apos_tempo: bool = False,
        nomes_equipes: dict[str, str] | None = None,
        clock: Callable[[], float] | None = None,
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

        self._clock = clock or time.monotonic

        # Estado mutável
        self.placar: dict[str, int] = {eq: 0 for eq in self.equipes_ativas}
        self.perguntas: list[Pergunta] = []
        self.estado = EstadoRodada()

        self.timer_fim: float = 0.0
        self.timer_rotulo: str = ""
        self.timer_cor: str = ""          # "" = neutro | "A".."D" = cor da equipe
        self.timer_motivo: str = ""       # "" | "revelada" | "tempo_esgotado"
        self.timer_congelado: float = 0.0  # restante no instante da parada

        self._embaralhar_e_preparar()
        self.proxima_pergunta(forcar=True)

    # ─── Helpers ───
    @staticmethod
    def _recusa(motivo: str) -> list[str]:
        return [PREFIXO_RECUSA + motivo]

    # ─── Carregamento / embaralhamento ───
    def _embaralhar_e_preparar(self) -> None:
        self.perguntas = list(self.perguntas_base)
        random.shuffle(self.perguntas)
        self.estado.indice_pergunta = 0
        self.estado.numero_pergunta = 0

    def recarregar_perguntas(self, novas: list[Pergunta], zerar_placar: bool = False) -> list[str]:
        """
        Troca o banco de perguntas e deixa a rodada limpa (sem pergunta atual).
        O placar só é zerado se `zerar_placar=True` (a UI decide isso).
        A apresentação chama `proxima_pergunta(forcar=True)` em seguida.
        """
        self.perguntas_base = list(novas)
        self._embaralhar_e_preparar()
        self.estado = EstadoRodada()
        self._parar_timer()
        self.timer_rotulo = ""
        self.timer_cor = ""
        if zerar_placar:
            self.placar = {eq: 0 for eq in self.equipes_ativas}
        return ["reiniciou_banco"]

    # ─── Timer (usa clock injetável) ───
    @property
    def timer_ativo(self) -> bool:
        return self.timer_fim > 0

    def _iniciar_timer(self, segundos: int, rotulo: str, cor: str = "") -> None:
        self.timer_fim = self._clock() + segundos
        self.timer_rotulo = rotulo
        self.timer_cor = cor
        self.timer_motivo = ""
        self.timer_congelado = 0.0

    def _parar_timer(self, motivo: str = "") -> None:
        if self.timer_fim > 0:
            self.timer_congelado = max(0.0, self.timer_fim - self._clock())
        else:
            self.timer_congelado = 0.0
        self.timer_fim = 0.0
        self.timer_motivo = motivo

    def timer_restante(self) -> float:
        """Tempo restante. Zero quando o timer está parado."""
        if self.timer_fim <= 0:
            return 0.0
        return max(0.0, self.timer_fim - self._clock())

    def timer_restante_visual(self) -> float:
        """Valor que a barra deve mostrar (preserva o restante ao revelar)."""
        if self.timer_fim > 0:
            return self.timer_restante()
        return self.timer_congelado

    def timer_total(self) -> float:
        """Duração do timer vigente (para a fração da barra)."""
        if self.estado.fase == FASE_AGUARDANDO:
            return float(self.tempo_pergunta)
        return float(self.tempo_resposta)

    def timer_fracao(self) -> float:
        total = self.timer_total()
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, self.timer_restante_visual() / total))

    def tick_timer(self) -> list[str]:
        """
        Chamado pela UI a cada quadro.
        Devolve ["tempo_esgotado"] na transição de estouro, senão [].
        """
        if self.timer_fim <= 0:
            return []
        if self._clock() >= self.timer_fim:
            self._parar_timer(TIMER_MOTIVO_TEMPO_ESGOTADO)
            self._tempo_esgotado()
            return ["tempo_esgotado"]
        return []

    # ─── Eventos de botão (chamados pela UI / serial) ───
    def apertar_botao(self, equipe: str) -> list[str]:
        if equipe not in self.equipes_ativas:
            return []
        if self.estado.fase != FASE_AGUARDANDO:
            return []
        if self.estado.pergunta_atual is None:
            return []

        self.estado.fase = FASE_RESPONDENDO
        self.estado.quem_apertou = equipe
        self.estado.tempo_estourou = False
        self._iniciar_timer(
            self.tempo_resposta,
            f"{self.nomes_equipes[equipe]} respondendo",
            equipe,
        )
        return [f"apertou:{equipe}"]

    def revelar_resposta(self) -> list[str]:
        if self.estado.fase == FASE_AGUARDANDO:
            return self._recusa(MOTIVO_REVELAR_AGUARDANDO)
        if self.estado.fase != FASE_RESPONDENDO:
            return []
        self.estado.fase = FASE_REVELADA
        self._parar_timer(TIMER_MOTIVO_REVELADA)
        self.timer_rotulo = "Resposta revelada"
        return ["revelou"]

    def confirmar_acerto(self, equipe: str) -> list[str]:
        if self.estado.fase == FASE_PONTUADA:
            return []
        if self.estado.fase != FASE_REVELADA:
            return self._recusa(MOTIVO_ACERTO_FASE)
        if self.estado.quem_apertou is None:
            return self._recusa(MOTIVO_ACERTO_SEM_QUEM)
        if equipe != self.estado.quem_apertou:
            return self._recusa(MOTIVO_ACERTO_OUTRA_EQUIPE)
        if self.estado.tempo_estourou and not self.pontuar_apos_tempo:
            return self._recusa(MOTIVO_ACERTO_TEMPO)

        self.estado.fase = FASE_PONTUADA
        self.placar[equipe] += 1
        return [f"pontuou:{equipe}"]

    def proxima_pergunta(self, forcar: bool = False) -> list[str]:
        if not forcar and self.estado.pergunta_atual is not None and self.estado.fase not in (
            FASE_REVELADA,
            FASE_PONTUADA,
        ):
            return self._recusa(MOTIVO_AVANCAR)

        if not self.perguntas:
            self.estado.pergunta_atual = None
            return []

        eventos: list[str] = []
        if self.estado.indice_pergunta >= len(self.perguntas):
            random.shuffle(self.perguntas)
            self.estado.indice_pergunta = 0
            eventos.append("reiniciou_banco")

        self.estado.pergunta_atual = self.perguntas[self.estado.indice_pergunta]
        self.estado.indice_pergunta += 1
        self.estado.numero_pergunta += 1

        self.estado.fase = FASE_AGUARDANDO
        self.estado.quem_apertou = None
        self.estado.tempo_estourou = False
        self._iniciar_timer(self.tempo_pergunta, "Tempo para apertar", "")
        eventos.append("proxima_pergunta")
        return eventos

    def reiniciar_placar(self) -> list[str]:
        for eq in self.equipes_ativas:
            self.placar[eq] = 0
        return ["reiniciou_placar"]

    def _tempo_esgotado(self) -> None:
        if self.estado.fase == FASE_AGUARDANDO:
            # Ninguém apertou: revela sem autor (não há ponto possível)
            self.estado.fase = FASE_REVELADA
            self.estado.quem_apertou = None
            self.timer_rotulo = "Tempo esgotado"
        elif self.estado.fase == FASE_RESPONDENDO:
            # Quem apertou não respondeu a tempo
            self.estado.fase = FASE_REVELADA
            self.estado.tempo_estourou = True
            self.timer_rotulo = "Tempo esgotado"

    # ─── Persistência ───
    def to_dict(self) -> dict[str, Any]:
        return {
            "placar": dict(self.placar),
            "num_equipes": self.num_equipes,
            "indice_pergunta": self.estado.indice_pergunta,
            "numero_pergunta": self.estado.numero_pergunta,
            "fase": self.estado.fase,
            "quem_apertou": self.estado.quem_apertou,
            "tempo_estourou": self.estado.tempo_estourou,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], perguntas: list[Pergunta], **kwargs) -> "Jogo":
        jogo = cls(perguntas, num_equipes=data.get("num_equipes", 2), **kwargs)
        jogo.placar = dict(data.get("placar", {eq: 0 for eq in jogo.equipes_ativas}))
        jogo.estado.indice_pergunta = data.get("indice_pergunta", 0)
        jogo.estado.numero_pergunta = data.get("numero_pergunta", 0)
        # Regra da Etapa 4.3: não restaura timer nem fase intermediária
        jogo.estado.fase = FASE_AGUARDANDO
        jogo.estado.quem_apertou = None
        jogo.estado.tempo_estourou = False
        jogo._parar_timer()
        jogo.timer_rotulo = ""
        jogo.timer_cor = ""
        if 0 < jogo.estado.indice_pergunta <= len(jogo.perguntas):
            jogo.estado.pergunta_atual = jogo.perguntas[jogo.estado.indice_pergunta - 1]
        jogo._iniciar_timer(jogo.tempo_pergunta, "Tempo para apertar", "")
        return jogo
