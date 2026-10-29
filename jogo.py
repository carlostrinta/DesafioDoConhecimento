"""
Lógica pura do Duelo de Conhecimento — sem dependências de UI, serial ou áudio.
Parametrizável para 2, 3 ou 4 equipes.

Ações do Jogo devolvem uma lista de eventos de domínio; a camada de
apresentação apenas reage a eles (LED, som, serial, tela):

    apertou:X          equipe X apertou o botão (AGUARDANDO -> RESPONDENDO)
    revelou            resposta revelada (RESPONDENDO -> REVELADA)
    pontuou:X          equipe X pontuou (REVELADA -> PONTUADA)
    tempo_esgotado     prazo expirou (transição decidida pelo próprio Jogo)
    proxima_pergunta   nova pergunta carregada (entra em CONTAGEM)
    contagem:N         número N deve aparecer no overlay (N, N-1, ..., 1)
    largada            contagem terminou; AGUARDANDO e timer de 30 s iniciados
    reiniciou_banco    baralho embaralhado (fim do banco)
    reiniciou_placar   placar zerado
    led_reacender:X    Arduino reiniciou; re-sincronizar o LED de X
    recusado:<motivo>  ação rejeitada; motivos em MOTIVOS_RECUSA
"""

from __future__ import annotations
import math
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
FASE_CONTAGEM = 4

# ─── Contagem de largada (Etapa 4.6) ───
CONTAGEM_LARGADA_PADRAO = 3
CONTAGEM_LARGADA_MINIMO = 0
CONTAGEM_LARGADA_MAXIMO = 10
MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO = False

# ─── Equipes suportadas ───
TODAS_EQUIPES = ("A", "B", "C", "D")

# ─── Motivos de recusa (texto fica na camada de apresentação) ───
MOTIVO_CONTAGEM = "contagem"
MOTIVO_AVANCAR = "avancar"
MOTIVO_REVELAR_AGUARDANDO = "revelar_aguardando"
MOTIVO_ACERTO_FASE = "acerto_fase"
MOTIVO_ACERTO_SEM_QUEM = "acerto_sem_quem"
MOTIVO_ACERTO_OUTRA_EQUIPE = "acerto_outra_equipe"
MOTIVO_ACERTO_TEMPO = "acerto_tempo"

MOTIVOS_RECUSA = (
    MOTIVO_CONTAGEM,
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


def _ordem_valida(ordem, total: int) -> bool:
    """True se `ordem` é uma permutação de range(total)."""
    if total <= 0:
        return isinstance(ordem, list) and not ordem
    if not isinstance(ordem, list) or len(ordem) != total:
        return False
    vistos = set()
    for indice in ordem:
        if isinstance(indice, bool) or not isinstance(indice, int):
            return False
        if not 0 <= indice < total or indice in vistos:
            return False
        vistos.add(indice)
    return True


def _normalizar_contagem(valor) -> int:
    """Duração da contagem em 0..10; valor inválido volta ao padrão 3."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return CONTAGEM_LARGADA_PADRAO
    if not CONTAGEM_LARGADA_MINIMO <= valor <= CONTAGEM_LARGADA_MAXIMO:
        return CONTAGEM_LARGADA_PADRAO
    return valor


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
        contagem_largada: int = CONTAGEM_LARGADA_PADRAO,
        mostrar_pergunta_na_contagem: bool = MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO,
    ):
        if not 2 <= num_equipes <= 4:
            raise ValueError("num_equipes deve ser 2, 3 ou 4")
        self.num_equipes = num_equipes
        self.equipes_ativas = TODAS_EQUIPES[:num_equipes]

        self.perguntas_base = list(perguntas)
        self.tempo_pergunta = tempo_pergunta
        self.tempo_resposta = tempo_resposta
        self.pontuar_apos_tempo = pontuar_apos_tempo
        self.contagem_largada = _normalizar_contagem(contagem_largada)
        self.mostrar_pergunta_na_contagem = (
            mostrar_pergunta_na_contagem
            if isinstance(mostrar_pergunta_na_contagem, bool)
            else MOSTRAR_PERGUNTA_NA_CONTAGEM_PADRAO
        )

        self.nomes_equipes = nomes_equipes or {
            "A": "Competidor A",
            "B": "Competidor B",
            "C": "Competidor C",
            "D": "Competidor D",
        }

        self._clock = clock or time.monotonic

        # Estado mutável
        self.placar: dict[str, int] = {eq: 0 for eq in self.equipes_ativas}
        # Pontos de equipes temporariamente fora da partida (fallback para 2).
        # Ficam só em memória: uma reconexão v2 pode restaurá-los na mesma sessão.
        self._placar_reservado: dict[str, int] = {}
        self.perguntas: list[Pergunta] = []
        self.estado = EstadoRodada()

        self.timer_fim: float = 0.0
        self.timer_rotulo: str = ""
        self.timer_cor: str = ""          # "" = neutro | "A".."D" = cor da equipe
        self.timer_motivo: str = ""       # "" | "revelada" | "tempo_esgotado"
        self.timer_congelado: float = 0.0  # restante no instante da parada

        # Contagem de largada: relógio próprio, separado do timer de resposta.
        self.contagem_fim: float = 0.0
        self.contagem_duracao: float = 0.0
        self.contagem_ultimo: int = 0

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
        self._parar_contagem()
        self.timer_rotulo = ""
        self.timer_cor = ""
        if zerar_placar:
            self.placar = {eq: 0 for eq in self.equipes_ativas}
            self._placar_reservado = {}
        return ["reiniciou_banco"]

    def reduzir_equipes(self, num_equipes: int = 2) -> bool:
        """
        Reduz a partida para 2 equipes quando o protocolo não suporta 3/4.

        Preserva o placar de A/B e guarda os pontos de C/D para uma eventual
        reconexão v2 na mesma sessão. Se a equipe da vez for uma das removidas,
        a rodada volta para AGUARDANDO com o tempo cheio para A/B disputarem.
        Devolve True quando houve redução.
        """
        if not 2 <= num_equipes < self.num_equipes:
            return False

        removidas = [
            equipe for equipe in self.equipes_ativas
            if equipe not in TODAS_EQUIPES[:num_equipes]
        ]
        self._placar_reservado.update(
            {equipe: self.placar.get(equipe, 0) for equipe in removidas}
        )

        self.num_equipes = num_equipes
        self.equipes_ativas = TODAS_EQUIPES[:num_equipes]
        self.placar = {
            equipe: self.placar.get(equipe, 0) for equipe in self.equipes_ativas
        }

        if self.estado.quem_apertou not in self.equipes_ativas:
            self.estado.quem_apertou = None
            self.estado.tempo_estourou = False
            if self.estado.fase in (FASE_RESPONDENDO, FASE_REVELADA, FASE_PONTUADA):
                self.estado.fase = FASE_AGUARDANDO
                self._parar_timer()
                self.timer_rotulo = ""
                self.timer_cor = ""
                self.timer_motivo = ""
                self.timer_congelado = 0.0
                if self.estado.pergunta_atual is not None:
                    self._iniciar_timer(
                        self.tempo_pergunta, "Tempo para apertar", ""
                    )
        return True

    def restaurar_equipes(self, num_equipes: int) -> bool:
        """
        Volta ao modo v2 com 3/4 equipes e devolve os pontos guardados de C/D.

        Só aumenta a partida; nunca reduz. Devolve True quando restaurou.
        """
        if num_equipes not in (3, 4) or num_equipes <= self.num_equipes:
            return False

        self.num_equipes = num_equipes
        self.equipes_ativas = TODAS_EQUIPES[:num_equipes]
        for equipe in self.equipes_ativas:
            if equipe in self._placar_reservado:
                self.placar[equipe] = self._placar_reservado.pop(equipe)
            else:
                self.placar.setdefault(equipe, 0)
        return True

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

    # ─── Contagem de largada (usa o mesmo clock injetável) ───
    @property
    def contagem_ativa(self) -> bool:
        return self.estado.fase == FASE_CONTAGEM and self.contagem_fim > 0

    def _parar_contagem(self) -> None:
        self.contagem_fim = 0.0
        self.contagem_duracao = 0.0
        self.contagem_ultimo = 0

    def _iniciar_contagem(self) -> None:
        """
        Coloca a rodada em CONTAGEM ou, com duração 0, direto em AGUARDANDO.

        O timer de resposta só é iniciado no "JÁ!"; durante a contagem
        `timer_ativo` fica False e `timer_restante()` retorna 0.
        """
        self._parar_timer()
        self.timer_rotulo = ""
        self.timer_cor = ""
        self.timer_motivo = ""
        self.timer_congelado = 0.0

        if self.contagem_largada <= 0:
            self.estado.fase = FASE_AGUARDANDO
            self._parar_contagem()
            self._iniciar_timer(self.tempo_pergunta, "Tempo para apertar", "")
            return

        self.estado.fase = FASE_CONTAGEM
        agora = self._clock()
        self.contagem_fim = agora + self.contagem_largada
        self.contagem_duracao = float(self.contagem_largada)
        self.contagem_ultimo = 0

    def contagem_restante(self) -> float:
        """Segundos restantes da contagem; 0 quando ela não está ativa."""
        if not self.contagem_ativa:
            return 0.0
        return max(0.0, self.contagem_fim - self._clock())

    def contagem_numero(self) -> int:
        """Número que o overlay deve mostrar (3, 2, 1) ou 0 no "JÁ!"."""
        if not self.contagem_ativa:
            return 0
        restante = self.contagem_restante()
        if restante <= 0:
            return 0
        numero = math.ceil(restante - 1e-9)
        return max(1, min(int(self.contagem_duracao), numero))

    def contagem_fracao(self) -> float:
        """Fração restante da contagem, para a barra de tempo."""
        if self.contagem_duracao <= 0:
            return 0.0
        return max(0.0, min(1.0, self.contagem_restante() / self.contagem_duracao))

    def tick_contagem(self) -> list[str]:
        """
        Avança a contagem pelo relógio injetável.

        Devolve `["contagem:N"]` quando o número exibido muda e `["largada"]`
        na transição para AGUARDANDO (quando o timer de 30 s começa).
        """
        if not self.contagem_ativa:
            return []

        if self._clock() >= self.contagem_fim:
            self.estado.fase = FASE_AGUARDANDO
            self._parar_contagem()
            self._iniciar_timer(self.tempo_pergunta, "Tempo para apertar", "")
            return ["largada"]

        numero = self.contagem_numero()
        if numero != self.contagem_ultimo:
            self.contagem_ultimo = numero
            return [f"contagem:{numero}"]
        return []

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
        if self.estado.fase == FASE_CONTAGEM:
            return self._recusa(MOTIVO_CONTAGEM)
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
        if self.estado.fase == FASE_CONTAGEM:
            return self._recusa(MOTIVO_CONTAGEM)
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
        if not forcar and self.estado.fase == FASE_CONTAGEM:
            return self._recusa(MOTIVO_CONTAGEM)
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

        self.estado.quem_apertou = None
        self.estado.tempo_estourou = False
        self._iniciar_contagem()
        eventos.append("proxima_pergunta")
        return eventos

    def reiniciar_placar(self) -> list[str]:
        for eq in self.equipes_ativas:
            self.placar[eq] = 0
        self._placar_reservado = {}
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
    def _ordem_do_baralho(self) -> list[int]:
        """Índices da ordem atual em relação a `perguntas_base`."""
        posicoes = {id(q): i for i, q in enumerate(self.perguntas_base)}
        ordem = [posicoes.get(id(q)) for q in self.perguntas]
        if any(indice is None for indice in ordem):
            return list(range(len(self.perguntas)))
        return ordem

    def to_dict(self) -> dict[str, Any]:
        """
        Estado mínimo para continuar a partida.

        Não inclui fase, quem apertou nem o timer: a restauração recomeça a
        pergunta atual pela contagem de largada (Etapa 4.6), com o tempo cheio.
        """
        return {
            "placar": dict(self.placar),
            "num_equipes": self.num_equipes,
            "nomes_equipes": dict(self.nomes_equipes),
            "tempo_pergunta": self.tempo_pergunta,
            "tempo_resposta": self.tempo_resposta,
            "pontuar_apos_tempo": self.pontuar_apos_tempo,
            "indice_pergunta": self.estado.indice_pergunta,
            "numero_pergunta": self.estado.numero_pergunta,
            "ordem": self._ordem_do_baralho(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], perguntas: list[Pergunta], **kwargs) -> "Jogo":
        """
        Reconstrói o jogo a partir de `to_dict()`.

        Restaura placar, nomes, índice, rodada e a ordem do baralho. A fase
        intermediária não é restaurada: a pergunta atual volta em CONTAGEM
        (ou em AGUARDANDO com o tempo cheio, se a contagem estiver desativada).
        """
        dados = data if isinstance(data, dict) else {}

        num_equipes = dados.get("num_equipes", 2)
        if (
            isinstance(num_equipes, bool)
            or not isinstance(num_equipes, int)
            or num_equipes not in (2, 3, 4)
        ):
            num_equipes = 2

        nomes = dados.get("nomes_equipes")
        if "nomes_equipes" not in kwargs and isinstance(nomes, dict):
            limpos = {eq: f"Competidor {eq}" for eq in TODAS_EQUIPES}
            for eq in TODAS_EQUIPES:
                valor = nomes.get(eq)
                if isinstance(valor, str) and valor.strip():
                    limpos[eq] = valor.strip()
            kwargs["nomes_equipes"] = limpos

        for chave in ("tempo_pergunta", "tempo_resposta"):
            if chave not in kwargs:
                valor = dados.get(chave)
                if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0:
                    kwargs[chave] = valor
        if "pontuar_apos_tempo" not in kwargs:
            valor = dados.get("pontuar_apos_tempo")
            if isinstance(valor, bool):
                kwargs["pontuar_apos_tempo"] = valor

        jogo = cls(perguntas, num_equipes=num_equipes, **kwargs)

        ordem = dados.get("ordem")
        if _ordem_valida(ordem, len(perguntas)):
            jogo.perguntas = [perguntas[i] for i in ordem]

        placar = dados.get("placar")
        if isinstance(placar, dict):
            for eq in jogo.equipes_ativas:
                valor = placar.get(eq, 0)
                if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                    valor = 0
                jogo.placar[eq] = valor
        else:
            jogo.placar = {eq: 0 for eq in jogo.equipes_ativas}

        indice = dados.get("indice_pergunta", 0)
        if isinstance(indice, bool) or not isinstance(indice, int):
            indice = 0
        indice = max(0, min(indice, len(jogo.perguntas)))
        numero = dados.get("numero_pergunta", 0)
        if isinstance(numero, bool) or not isinstance(numero, int) or numero < 0:
            numero = 0

        jogo.estado.indice_pergunta = indice
        jogo.estado.numero_pergunta = numero
        # Não restaura fase intermediária nem tempo restante. A pergunta
        # atual entra na contagem de largada (Etapa 4.6); sem pergunta, a
        # rodada fica limpa em AGUARDANDO, sem timer.
        jogo.estado.quem_apertou = None
        jogo.estado.tempo_estourou = False
        jogo.estado.pergunta_atual = (
            jogo.perguntas[indice - 1]
            if 1 <= indice <= len(jogo.perguntas)
            else None
        )
        jogo._parar_timer()
        jogo._parar_contagem()
        jogo.timer_rotulo = ""
        jogo.timer_cor = ""
        if jogo.estado.pergunta_atual is not None:
            jogo._iniciar_contagem()
        else:
            jogo.estado.fase = FASE_AGUARDANDO
        return jogo
