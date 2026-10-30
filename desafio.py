"""
Duelo de Conhecimento — Aplicação Windows
Versão 2.1 — interface de palco + máquina de estados + serial robusta + áudio

Requisitos: Python 3.12+ (validado em 3.12.15), pyserial.
Protocolo serial: v1 preservado; v2 detectado por `PRONTO` + `VERSAO 2`,
com `CONFIG_TEAMS N` e ACK `EQUIPES N`.

Atalhos de teclado (modo simulação, funcionam junto com o Arduino):
    A / B / C / D   apertar o botão da equipe
    R               revelar resposta
    1 / 2 / 3 / 4   acerto da equipe A / B / C / D
    N               próxima pergunta
    S               ligar/desligar som
    F1              tela Sobre
    F11             tela cheia  (Esc sai)
    Ctrl+R          zerar o placar
"""

import logging
import math
import os
import queue
import time
import tkinter as tk
from tkinter import messagebox

import persistencia
import ui_componentes
from audio import Som
from config import (
    ARQUIVO_PERGUNTAS,
    BUFFER_AUDIO,
    CONFIG,
    CONTAGEM_LARGADA,
    CONTINUAR_AUTOMATICO,
    DURACAO_OVERLAY_JA,
    MOSTRAR_PERGUNTA_NA_CONTAGEM,
    NOMES_EQUIPES,
    NUM_EQUIPES,
    PASTA_PERGUNTAS,
    PONTUAR_APOS_TEMPO,
    SOM_ATIVO,
    TEMPO_PERGUNTA,
    TEMPO_RESPOSTA,
    TIMEOUT_PRONTO,
    TITULO,
    VOLUME_AUDIO,
    texto_avisos,
)
from jogo import (
    Jogo,
    FASE_AGUARDANDO,
    FASE_RESPONDENDO,
    FASE_REVELADA,
    FASE_PONTUADA,
    FASE_CONTAGEM,
    MOTIVO_ACERTO_FASE,
    MOTIVO_ACERTO_OUTRA_EQUIPE,
    MOTIVO_ACERTO_SEM_QUEM,
    MOTIVO_ACERTO_TEMPO,
    MOTIVO_AVANCAR,
    MOTIVO_CONTAGEM,
    MOTIVO_REVELAR_AGUARDANDO,
    PREFIXO_RECUSA,
    TIMER_MOTIVO_REVELADA,
)
from perguntas import (
    formatar_nome_tema,
    ler_banco_perguntas,
    listar_arquivos_perguntas,
)
from protocolo import (
    comando_config_equipes,
    equipes_confirmadas,
    mapear_evento_arduino,
)
from protocolo_v1 import (
    comandos_para_arduino,
    mapear_evento_arduino as mapear_evento_arduino_v1,
)
from recursos import caminho_recurso
from serial_comm import SERIAL_DISPONIVEL, ComunicacaoSerial
from ui_componentes import (
    BarraTempo,
    BarraTopo,
    CartaoAlt,
    CartaoExplicacao,
    CartaoPergunta,
    CartaoPlacar,
    Cor,
    CORES_EQUIPES,
    OverlayContagem,
    Rodape,
    escolher_fonte,
)
from ui_selecao import ModalContinuarPartida, ModalSelecaoPerguntas
from ui_sobre import TelaSobre

log = logging.getLogger("desafio")

if not SERIAL_DISPONIVEL:
    log.warning("pyserial não instalado. Modo teclado ativo.")

# =========================================================
# CONFIGURAÇÕES
# Os valores (título, equipes, tempos, serial) vêm de config.py, que lê e
# valida o config.json na Etapa 4.2.
# =========================================================
NOME_A = NOMES_EQUIPES["A"]
NOME_B = NOMES_EQUIPES["B"]


# =========================================================
# FASES DA RODADA (definidas em jogo.py — fonte única)
# =========================================================
# Mensagens das recusas do Jogo. A regra mora no Jogo; aqui só o texto.
MENSAGENS_RECUSA = {
    MOTIVO_CONTAGEM: "Aguarde o JÁ! da contagem de largada.",
    MOTIVO_AVANCAR: "Resolva a pergunta atual (revele ou pontue) antes de avançar.",
    MOTIVO_REVELAR_AGUARDANDO: "Ninguém apertou ainda. REVELAR só funciona depois que uma equipe apertar.",
    MOTIVO_ACERTO_FASE: "Revele a resposta (botão REVELAR) antes de pontuar.",
    MOTIVO_ACERTO_SEM_QUEM: "Ninguém apertou nesta rodada: não há ponto para dar.",
    MOTIVO_ACERTO_OUTRA_EQUIPE: "Só quem apertou pode pontuar (apertou: {equipe}).",
    MOTIVO_ACERTO_TEMPO: "O tempo de resposta esgotou: sem ponto nesta rodada.",
}


def mensagem_ignoradas(quantidade, nome_arquivo):
    """
    Texto do aviso de perguntas descartadas na carga.
    Devolve None quando nada foi ignorado.
    """
    if quantidade <= 0:
        return None
    substantivo = "pergunta ignorada" if quantidade == 1 else "perguntas ignoradas"
    return f"{quantidade} {substantivo} em {nome_arquivo}."


def escolher_arquivo_inicial(arquivos, arquivo_atual, pasta, arquivo_padrao):
    """
    Item pré-selecionado no seletor de temas.

    Prioridade: arquivo atual da partida, arquivo padrão do `config.json` e,
    por fim, o primeiro da lista. Devolve None se não houver arquivos.
    """
    if arquivo_atual:
        alvo = os.path.abspath(arquivo_atual)
        for arq in arquivos:
            if os.path.abspath(arq["caminho"]) == alvo:
                return arq

    alvo = os.path.abspath(os.path.join(pasta, arquivo_padrao))
    for arq in arquivos:
        if os.path.abspath(arq["caminho"]) == alvo:
            return arq

    return arquivos[0] if arquivos else None


# =========================================================
# APLICAÇÃO PRINCIPAL
# =========================================================
class DueloDeConhecimento:
    def __init__(self, root, *, clock=None):
        self.root = root
        self._clock = clock or time.monotonic
        self.root.title(TITULO)
        self.root.geometry("1280x800")
        self.root.minsize(900, 600)
        self.root.configure(bg=Cor.FUNDO)
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

        ui_componentes.FAMILIAS["display"] = escolher_fonte(["Bahnschrift", "Segoe UI Semibold", "Segoe UI", "Arial"])
        ui_componentes.FAMILIAS["corpo"] = escolher_fonte(["Segoe UI", "Calibri", "Arial"])

        # ---------- Estado ----------
        # O Jogo é o dono único das regras, do placar e do tempo.
        # A UI lê o estado por propriedades (placar_a/b, fase, ...) e não
        # reimplementa nenhuma regra.
        self.arquivo_atual = None
        self.tema_atual = ""
        self.erro_carga = ""
        self._equipes_configuradas = NUM_EQUIPES
        self.protocolo_arduino = None
        self._job_versao = None
        self._versao_prazo = 0.0
        self._job_equipes = None
        self._equipes_prazo = 0.0
        self._equipes_tentativas = 0
        self._equipes_alvo = 0
        self._equipes_confirmado = False
        self._janela_sobre = None
        self._aviso_protocolo_mostrado = False
        self._geracao_conexao = 0
        self._geracao_fallback = 0
        self._fallback_equipes = False
        self.jogo = Jogo(
            [],
            num_equipes=NUM_EQUIPES,
            tempo_pergunta=TEMPO_PERGUNTA,
            tempo_resposta=TEMPO_RESPOSTA,
            pontuar_apos_tempo=PONTUAR_APOS_TEMPO,
            nomes_equipes=dict(NOMES_EQUIPES),
            contagem_largada=CONTAGEM_LARGADA,
            mostrar_pergunta_na_contagem=MOSTRAR_PERGUNTA_NA_CONTAGEM,
        )

        # Avisa (sem bloquear) se já houver outra instância usando esta pasta.
        self._trava = persistencia.TravaInstancia()
        self._trava.adquirir()

        # Estado salvo é lido antes da interface; a decisão de continuar é
        # tomada em `_iniciar_fluxo_inicial`, depois que a janela existe.
        self._resultado_salvo = persistencia.carregar(
            PASTA_PERGUNTAS,
            nomes_equipes=dict(NOMES_EQUIPES),
            tempo_pergunta=TEMPO_PERGUNTA,
            tempo_resposta=TEMPO_RESPOSTA,
            pontuar_apos_tempo=PONTUAR_APOS_TEMPO,
            num_equipes=NUM_EQUIPES,
            contagem_largada=CONTAGEM_LARGADA,
            mostrar_pergunta_na_contagem=MOSTRAR_PERGUNTA_NA_CONTAGEM,
        )
        self._partida_salva = self._resultado_salvo.partida
        self._motivo_estado = self._resultado_salvo.motivo

        self.aviso = None
        self._aviso_carga = None

        self._job_timer = None
        self._job_aviso = None
        self._job_escala = None
        self._job_contagem_visual = None
        self._contagem_visual = None
        # Duração puramente visual do "JÁ!" (config.ui.duracao_overlay_ja).
        # O Jogo já está em AGUARDANDO e os botões já valem neste instante.
        self._duracao_overlay_ja = DURACAO_OVERLAY_JA
        self._salvador = persistencia.AgendadorSalvamento(
            self._salvar_estado,
            self.root.after,
            self.root.after_cancel,
        )

        self.rodando = True
        self.fila = queue.Queue()
        self.serial_comm = ComunicacaoSerial(self.fila, log=log.debug)

        # Ícone da janela principal
        ico_path = caminho_recurso("desafio.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        # ---------- Áudio ----------
        self.som = Som(
            ativo=SOM_ATIVO,
            volume=VOLUME_AUDIO,
            buffer=BUFFER_AUDIO,
        )
        self._ultimo_seg_tick = None

        # ---------- Inicialização ----------
        self.montar_interface()
        self.iniciar_thread_serial()

        self.root.bind("<Key>", self.tecla_pressionada)
        self.root.bind("<F1>", lambda e: self.abrir_sobre())
        self.root.bind("<F11>", lambda e: self.alternar_tela_cheia())
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<Control-r>", lambda e: self.reiniciar_placar())
        self.root.bind("<Control-R>", lambda e: self.reiniciar_placar())
        self.root.bind("<Control-t>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Control-T>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Control-o>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Control-O>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<F2>", lambda e: self.abrir_seletor_tema(inicial=False))
        self.root.bind("<Configure>", self._ao_redimensionar)
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)

        self._avisar_config()

        self.root.after(20, self.drenar_fila)
        self.render()

        # Decide entre continuar a partida salva ou abrir o seletor de temas.
        self.root.after(100, self._iniciar_fluxo_inicial)

    # -----------------------------------------------------
    # LEITURA DO ESTADO (compatibilidade: a UI antiga continua
    # usando os mesmos nomes; a verdade está no Jogo)
    # -----------------------------------------------------
    @property
    def perguntas(self):
        return self.jogo.perguntas_base

    @property
    def pergunta_atual(self):
        return self.jogo.estado.pergunta_atual

    @property
    def indice(self):
        return self.jogo.estado.indice_pergunta

    @property
    def numero(self):
        return self.jogo.estado.numero_pergunta

    @property
    def fase(self):
        return self.jogo.estado.fase

    @property
    def quem_apertou(self):
        return self.jogo.estado.quem_apertou

    @property
    def tempo_estourou(self):
        return self.jogo.estado.tempo_estourou

    @property
    def placar_a(self):
        return self.jogo.placar.get("A", 0)

    @placar_a.setter
    def placar_a(self, valor):
        self.jogo.placar["A"] = valor

    @property
    def placar_b(self):
        return self.jogo.placar.get("B", 0)

    @placar_b.setter
    def placar_b(self, valor):
        self.jogo.placar["B"] = valor

    # -----------------------------------------------------
    # PERGUNTAS E TEMAS
    # -----------------------------------------------------
    def carregar_perguntas(self, caminho=None, nome_tema=None):
        self._cancelar_job_timer()
        if caminho is None:
            caminho = os.path.join(PASTA_PERGUNTAS, ARQUIVO_PERGUNTAS)

        self.arquivo_atual = caminho
        nome_arquivo = os.path.basename(caminho)

        # Carregador/validador único do projeto (perguntas.ler_banco_perguntas)
        carga = ler_banco_perguntas(
            caminho,
            tema_padrao=nome_tema or formatar_nome_tema(nome_arquivo),
            aceitar_tema_do_arquivo=not nome_tema,
        )
        self.tema_atual = carga.tema
        self.erro_carga = carga.erro
        if carga.erro:
            log.error("%s", carga.erro)

        self.jogo.recarregar_perguntas(carga.perguntas)
        log.info(
            "[%s] %d perguntas carregadas de %s.",
            self.tema_atual,
            len(carga.perguntas),
            nome_arquivo,
        )
        if carga.ignoradas:
            log.warning(
                "%d pergunta(s) ignorada(s) em %s (detalhes acima).",
                len(carga.ignoradas),
                nome_arquivo,
            )
        # Aviso na tela; o detalhe de cada pergunta ignorada fica no log.
        self._aviso_carga = mensagem_ignoradas(len(carga.ignoradas), nome_arquivo)

        if hasattr(self, "topo"):
            self.topo.tema = self.tema_atual
            self.topo.desenhar()

        # O arquivo de "troca de tema" é opcional; sem ele, o fallback
        # sintetizado mantém o app funcionando.
        som = getattr(self, "som", None)
        if som is not None and carga.perguntas and not carga.erro:
            som.troca_tema()

    # -----------------------------------------------------
    # PARTIDA SALVA (Etapa 4.3)
    # -----------------------------------------------------
    def _iniciar_fluxo_inicial(self):
        if os.environ.get("DESAFIO_AUTO_INICIAR"):
            # Gancho do smoke test: pula seletor/estado salvo e começa a
            # contagem pelo banco padrão. Não grava estado por cima da
            # partida salva do usuário.
            self.carregar_perguntas()
            self.proxima_pergunta(forcar=True)
            self.arquivo_atual = None
            return

        if self._partida_salva is not None:
            if CONTINUAR_AUTOMATICO:
                log.info("Continuando partida salva automaticamente.")
                self._aplicar_partida_salva(self._partida_salva)
            else:
                ModalContinuarPartida(
                    self.root,
                    self._partida_salva.resumo,
                    self._escolher_partida_inicial,
                    ao_fechar=self.fechar,
                )
            return

        if self._motivo_estado:
            self._avisar_estado_invalido()
            persistencia.remover_estado()
            self._motivo_estado = ""

        self.abrir_seletor_tema(inicial=True)

    def _avisar_estado_invalido(self):
        log.warning(
            "Partida salva não pôde ser continuada: %s", self._motivo_estado
        )
        if not os.environ.get("DESAFIO_AUTO_FECHAR"):
            messagebox.showwarning(
                TITULO,
                "Não foi possível continuar a partida salva:\n\n"
                f"{self._motivo_estado}\n\n"
                "Iniciando uma nova partida.",
                parent=self.root,
            )

    def _escolher_partida_inicial(self, continuar):
        if continuar and self._partida_salva is not None:
            self._aplicar_partida_salva(self._partida_salva)
            return

        persistencia.remover_estado()
        self._partida_salva = None
        self.abrir_seletor_tema(inicial=True)

    def _aplicar_partida_salva(self, partida):
        self.jogo = partida.jogo
        self.arquivo_atual = partida.caminho_perguntas
        self.tema_atual = partida.tema
        self.erro_carga = ""
        self._aviso_carga = None
        self._ultimo_seg_tick = None
        self._ocultar_contagem(renderizar=False)
        if self.fase == FASE_AGUARDANDO:
            # Contagem desativada (0): a partida retomada já está valendo,
            # então botões enfileirados não podem ganhar a rodada.
            self.descartar_botoes_fila()

        if hasattr(self, "topo"):
            self.topo.tema = self.tema_atual
            self.topo.desenhar()

        self.render()
        self._atualizar_barra()
        self._reiniciar_loop_timer()
        log.info(
            "Partida salva continuada: tema=%s, rodada=%d.",
            self.tema_atual,
            self.numero,
        )

    def _salvar_estado(self):
        if not self.arquivo_atual:
            return
        caminho = persistencia.salvar(
            self.jogo,
            self.tema_atual,
            self.arquivo_atual,
        )
        if caminho:
            log.debug("Estado da partida salvo em %s.", caminho)

    def abrir_seletor_tema(self, inicial=False):
        """Abre a tela modal para escolha de tema/arquivo de perguntas."""
        if self._job_timer:
            self._cancelar_job_timer()

        diretorio = PASTA_PERGUNTAS
        arquivos = listar_arquivos_perguntas(diretorio)

        atual = escolher_arquivo_inicial(
            arquivos, self.arquivo_atual, PASTA_PERGUNTAS, ARQUIVO_PERGUNTAS
        )

        def ao_confirmar(info_escolhida):
            if not info_escolhida:
                return
            mesmo_arquivo = self.arquivo_atual and (os.path.abspath(info_escolhida["caminho"]) == os.path.abspath(self.arquivo_atual))

            if not inicial and not mesmo_arquivo and any(self.jogo.placar.values()):
                if messagebox.askyesno(TITULO, f"Zerar o placar das equipes para '{info_escolhida['titulo']}'?", parent=self.root):
                    for equipe in self.jogo.equipes_ativas:
                        self.jogo.placar[equipe] = 0

            self.carregar_perguntas(info_escolhida["caminho"], info_escolhida["titulo"])
            self.proxima_pergunta(forcar=True)

        modal = ModalSelecaoPerguntas(
            parent=self.root,
            lista_arquivos=arquivos,
            arquivo_atual=atual,
            ao_confirmar=ao_confirmar,
            permitir_cancelar=True,
            inicial=inicial,
            diretorio=diretorio,
            ao_sair=self.fechar,
        )

    def abrir_sobre(self):
        """
        Abre a tela "Sobre" (F1) sem cobrir placar, topo ou contagem.

        Durante a contagem (inclusive enquanto o "JÁ!" está visível) a janela
        não é aberta: o overlay precisa continuar legível. O F1 nunca abre
        uma segunda janela; se ela já existe, apenas recebe o foco.
        """
        if self.jogo.contagem_ativa or self._contagem_visual is not None:
            self.avisar("Aguarde o JÁ! da contagem de largada.")
            return

        janela = getattr(self, "_janela_sobre", None)
        if janela is not None:
            try:
                if janela.winfo_exists():
                    janela.lift()
                    janela.focus_force()
                    return
            except tk.TclError:
                pass
            self._janela_sobre = None

        self._janela_sobre = TelaSobre(
            self.root, ao_fechar=self._sobre_fechada
        )

    def _sobre_fechada(self):
        self._janela_sobre = None
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def proxima_pergunta(self, forcar=False):
        # A regra de bloqueio e o avanço do baralho são do Jogo.
        self._despachar(self.jogo.proxima_pergunta(forcar))

    # -----------------------------------------------------
    # INTERFACE
    # -----------------------------------------------------
    def montar_interface(self):
        r = self.root
        r.columnconfigure(0, weight=2, uniform="lado")
        r.columnconfigure(1, weight=5)
        r.columnconfigure(2, weight=2, uniform="lado")
        r.rowconfigure(0, minsize=64)
        r.rowconfigure(1, weight=1)
        r.rowconfigure(2, minsize=84)
        P = 16

        self.topo = BarraTopo(r, height=64)
        self.topo.grid(row=0, column=0, columnspan=3, sticky="ew", padx=P, pady=(10, 0))

        # As colunas laterais são fixas; os cartões dentro delas são
        # reconstruídos conforme `jogo.equipes_ativas` (2, 3 ou 4 equipes).
        self.coluna_placar_esq = tk.Frame(r, bg=Cor.FUNDO)
        self.coluna_placar_esq.grid(
            row=1, column=0, sticky="nsew", padx=(P, 8), pady=10
        )
        self.coluna_placar_dir = tk.Frame(r, bg=Cor.FUNDO)
        self.coluna_placar_dir.grid(
            row=1, column=2, sticky="nsew", padx=(8, P), pady=10
        )

        palco = tk.Frame(r, bg=Cor.FUNDO)
        palco.grid(row=1, column=1, sticky="nsew", padx=8, pady=10)
        palco.columnconfigure(0, weight=1)
        palco.rowconfigure(0, minsize=56)
        palco.rowconfigure(1, weight=5)
        for i in range(2, 6):
            palco.rowconfigure(i, weight=2, uniform="alt")
        palco.rowconfigure(6, weight=2)

        self.barra = BarraTempo(palco, height=56)
        self.barra.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.cartao_pergunta = CartaoPergunta(palco)
        self.cartao_pergunta.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        self.cartoes_alt = []
        for i in range(4):
            c = CartaoAlt(palco)
            c.grid(row=2 + i, column=0, sticky="nsew", pady=3)
            self.cartoes_alt.append(c)
        self.cartao_explic = CartaoExplicacao(palco)
        self.cartao_explic.grid(row=6, column=0, sticky="nsew", pady=(6, 0))

        # Overlay fica dentro do palco central: os cartões de placar das
        # equipes (colunas laterais) continuam visíveis durante a contagem.
        self.overlay_contagem = OverlayContagem(palco)

        self.rodape = Rodape(r, height=84)
        self.rodape.grid(row=2, column=0, columnspan=3, sticky="ew", padx=P, pady=(0, 14))

        self._montar_cartoes()

    def _montar_cartoes(self):
        """Cria um cartão por equipe ativa, alternando as colunas A/C e B/D."""
        for coluna in (self.coluna_placar_esq, self.coluna_placar_dir):
            for filho in coluna.winfo_children():
                filho.destroy()
            coluna.grid_columnconfigure(0, weight=1)
            for linha in range(4):
                coluna.grid_rowconfigure(linha, weight=0)

        esquerda = list(self.jogo.equipes_ativas[0::2])
        direita = list(self.jogo.equipes_ativas[1::2])
        self.cartoes_placar = {}

        for coluna, equipes in (
            (self.coluna_placar_esq, esquerda),
            (self.coluna_placar_dir, direita),
        ):
            for linha, equipe in enumerate(equipes):
                cartao = CartaoPlacar(
                    coluna,
                    self.jogo.nomes_equipes.get(equipe, f"Competidor {equipe}"),
                    CORES_EQUIPES[equipe],
                )
                cartao.grid(row=linha, column=0, sticky="nsew", pady=4)
                coluna.grid_rowconfigure(linha, weight=1)
                self.cartoes_placar[equipe] = cartao

        # Nomes históricos usados por testes e por trechos antigos da UI.
        self.cartao_a = self.cartoes_placar.get("A")
        self.cartao_b = self.cartoes_placar.get("B")
        self.telas = self._lista_de_telas()

    def _lista_de_telas(self):
        cartoes = [
            self.cartoes_placar[equipe]
            for equipe in self.jogo.equipes_ativas
            if equipe in self.cartoes_placar
        ]
        return [
            self.topo,
            *cartoes,
            self.barra,
            self.cartao_pergunta,
            *self.cartoes_alt,
            self.cartao_explic,
            self.rodape,
            self.overlay_contagem,
        ]

    def _reconstruir_cartoes(self):
        """Recria os cartões quando o número de equipes muda."""
        self._montar_cartoes()
        self.render()

    def _nome(self, letra):
        return self.jogo.nomes_equipes.get(letra, f"Competidor {letra}")

    def _cor(self, letra):
        return CORES_EQUIPES.get(letra, Cor.APOIO)

    def _status_padrao(self):
        if self.pergunta_atual is None:
            if not self.perguntas:
                return (self.erro_carga or "Aguardando seleção de tema de perguntas.", Cor.SUAVE)
            return (self.erro_carga or "Nenhuma pergunta válida carregada.", Cor.ERRO)
        q = self.quem_apertou
        if self.fase == FASE_CONTAGEM:
            return ("Contagem de largada: aguarde o JÁ! para apertar.", Cor.APOIO)
        if self.fase == FASE_AGUARDANDO:
            return ("Valendo! O primeiro a apertar o botão responde.", Cor.APOIO)
        if self.fase == FASE_RESPONDENDO:
            return (f"{self._nome(q)} apertou. Monitor: revele a resposta.", self._cor(q))
        if self.fase == FASE_REVELADA:
            if q is None:
                return ("Ninguém apertou. Aperte AVANÇAR.", Cor.SUAVE)
            if self.tempo_estourou and not PONTUAR_APOS_TEMPO:
                return (f"Tempo esgotado para {self._nome(q)}. Aperte AVANÇAR.", Cor.ERRO)
            return (f"{self._nome(q)} acertou? Pontue ou aperte AVANÇAR.", Cor.TEXTO)
        return (f"Ponto para {self._nome(q)}! Aperte AVANÇAR.", self._cor(q))

    def render(self):
        """Desenha a tela inteira a partir do estado atual."""
        p = self.pergunta_atual
        revelado = self.fase in (FASE_REVELADA, FASE_PONTUADA)
        em_contagem = self.fase == FASE_CONTAGEM
        mostrar_pergunta = (
            not em_contagem or self.jogo.mostrar_pergunta_na_contagem
        )

        for letra in self.jogo.equipes_ativas:
            cartao = self.cartoes_placar.get(letra)
            if cartao is None:
                continue
            pts = self.jogo.placar.get(letra, 0)
            outros = [
                self.jogo.placar.get(outra, 0)
                for outra in self.jogo.equipes_ativas
                if outra != letra
            ]
            outro = max(outros, default=0)
            cartao.pontos = pts
            cartao.ativo = (self.quem_apertou == letra)
            cartao.rotulo = "Apertou primeiro" if cartao.ativo else ("Na frente" if pts > outro else "")
            cartao.desenhar()

        cp = self.cartao_pergunta
        if p:
            cp.categoria, cp.texto, cp.numero = p.categoria, p.texto, self.numero
        else:
            cp.categoria, cp.texto, cp.numero = "", "Nenhuma pergunta carregada.", 0
        if mostrar_pergunta:
            cp.grid()
            cp.desenhar()
        else:
            cp.grid_remove()

        for i, c in enumerate(self.cartoes_alt):
            if p and i < len(p.alternativas) and mostrar_pergunta:
                c.grid()
                if revelado:
                    estado = "correta" if i == p.correta else "apagada"
                else:
                    estado = "normal"
                c.definir(chr(65 + i), p.alternativas[i], estado)
                c.desenhar()
            else:
                c.grid_remove()

        self.cartao_explic.texto = p.explicacao if (p and revelado) else ""
        self.cartao_explic.desenhar()

        self._sincronizar_contagem()

        msg, cor = (self.aviso, Cor.AVISO) if self.aviso else self._status_padrao()
        # -1 desmarca todos os passos: CONTAGEM é uma fase anterior a
        # AGUARDANDO e não deve acender o passo "Aguardando".
        passo = -1 if self.fase == FASE_CONTAGEM else self.fase + 1
        self.rodape.msg, self.rodape.cor_msg, self.rodape.passo = msg, cor, passo
        self.rodape.desenhar()

    def avisar(self, texto):
        """Aviso temporário no rodapé (some sozinho, não altera o estado)."""
        self._limpar_aviso()
        self.aviso = texto
        self._job_aviso = self.root.after(3500, self._expirar_aviso)
        self.render()

    def _avisar_config(self):
        """Mostra uma vez os problemas do config.json (detalhe fica no log).

        No modo `DESAFIO_AUTO_FECHAR` (teste/smoke) o diálogo é omitido para o
        fechamento automático não ficar preso esperando um clique.
        """
        if CONFIG.avisos and not os.environ.get("DESAFIO_AUTO_FECHAR"):
            messagebox.showwarning(
                TITULO, texto_avisos(CONFIG.avisos), parent=self.root
            )

    def _expirar_aviso(self):
        self._job_aviso = None
        self.aviso = None
        self.render()

    def _limpar_aviso(self):
        if self._job_aviso:
            self.root.after_cancel(self._job_aviso)
            self._job_aviso = None
        self.aviso = None

    # -----------------------------------------------------
    # CONTAGEM DE LARGADA — overlay e sons (a regra é do Jogo)
    # -----------------------------------------------------
    def _cancelar_contagem_visual(self):
        job = getattr(self, "_job_contagem_visual", None)
        if job:
            self.root.after_cancel(job)
            self._job_contagem_visual = None

    def _mostrar_contagem(self, valor):
        """Exibe o número no overlay central (sem cobrir o placar lateral)."""
        self._cancelar_contagem_visual()
        self._contagem_visual = str(valor)
        overlay = self.overlay_contagem
        overlay.valor = str(valor)
        overlay.place(
            relx=0.5,
            rely=0.60,
            anchor="center",
            relwidth=0.72,
            relheight=0.54,
        )
        # Em Canvas, `lift`, `tkraise` e `tag_raise` são o MESMO método e
        # exigem item/tag do canvas. Para elevar o widget acima dos irmãos do
        # palco, chamamos o comando Tcl de widget diretamente.
        overlay.tk.call("raise", overlay._w)
        overlay.desenhar()
        if str(valor) == "JÁ!":
            atraso_ms = int(round(self._duracao_overlay_ja * 1000))
            self._job_contagem_visual = self.root.after(
                atraso_ms, self._ocultar_contagem
            )

    def _ocultar_contagem(self, renderizar=True):
        self._cancelar_contagem_visual()
        self._contagem_visual = None
        if hasattr(self, "overlay_contagem"):
            self.overlay_contagem.place_forget()
        if renderizar and getattr(self, "rodando", False):
            self.render()

    def _sincronizar_contagem(self):
        """Mantém o overlay coerente com a fase (chamado pelo render)."""
        if self.fase == FASE_CONTAGEM:
            valor = str(self.jogo.contagem_numero())
            if self._contagem_visual != valor:
                self._mostrar_contagem(valor)
        elif self._contagem_visual == "JÁ!":
            # O "JÁ!" fica visível por alguns instantes; o job o remove e
            # redesenha a pergunta.
            pass
        elif self._contagem_visual is not None:
            self._ocultar_contagem(renderizar=False)

    def piscar(self, letra, n=5):
        cartao = self.cartoes_placar.get(letra)
        if cartao is None:
            return

        def passo(i):
            cartao.brilho = (i % 2 == 1)
            cartao.desenhar()
            if i < n:
                self.root.after(110, passo, i + 1)
        passo(0)

    def alternar_tela_cheia(self):
        atual = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not atual)

    def _ao_redimensionar(self, ev):
        if ev.widget is not self.root:
            return
        if self._job_escala:
            self.root.after_cancel(self._job_escala)
        self._job_escala = self.root.after(60, self._aplicar_escala)

    def _aplicar_escala(self):
        self._job_escala = None
        w, h = self.root.winfo_width(), self.root.winfo_height()
        nova = max(0.6, min(w / 1280, h / 800, 2.2))
        if abs(nova - ui_componentes.ESCALA) > 0.02:
            ui_componentes.definir_escala(nova)
            for t in self.telas:
                t.desenhar()

    # -----------------------------------------------------
    # TIMER — o prazo é do Jogo; a UI só agenda o after(),
    # consulta timer_restante()/timer_fracao() e desenha.
    # -----------------------------------------------------
    def _cancelar_job_timer(self):
        if self._job_timer:
            self.root.after_cancel(self._job_timer)
            self._job_timer = None

    def _reiniciar_loop_timer(self):
        self._cancelar_job_timer()
        if self.jogo.contagem_ativa or self.jogo.timer_ativo:
            self._tick()

    def _tick(self):
        self._job_timer = None

        if self.jogo.contagem_ativa:
            eventos = self.jogo.tick_contagem()
            if eventos:
                self._despachar(eventos)  # número novo ou "largada"
                return
            self._atualizar_barra()
            self._job_timer = self.root.after(100, self._tick)
            return

        if not self.jogo.timer_ativo:
            return

        eventos = self.jogo.tick_timer()
        if eventos:
            self._despachar(eventos)   # estouro: o Jogo já fez a transição
            return

        self._atualizar_barra()
        restante = self.jogo.timer_restante()
        seg = math.ceil(restante)
        if seg != self._ultimo_seg_tick:
            self._ultimo_seg_tick = seg
            self.som.tick(seg, self.fase)
        self._job_timer = self.root.after(100, self._tick)

    def _atualizar_barra(self):
        j = self.jogo
        if j.estado.pergunta_atual is None:
            return
        b = self.barra
        if j.estado.fase == FASE_CONTAGEM:
            b.rotulo = "Contagem de largada"
            b.frac = j.contagem_fracao()
            b.segundos = math.ceil(max(0.0, j.contagem_restante()))
            b.cor = Cor.APOIO
            b.desenhar()
            return
        b.rotulo = j.timer_rotulo
        b.frac = j.timer_fracao()
        b.segundos = math.ceil(max(0.0, j.timer_restante_visual()))
        if j.timer_motivo == TIMER_MOTIVO_REVELADA:
            b.cor = Cor.APAGADO
        elif b.frac <= 0.34:
            b.cor = Cor.ERRO
        elif j.timer_cor:
            b.cor = self._cor(j.timer_cor)
        else:
            b.cor = Cor.APOIO
        b.desenhar()

    # -----------------------------------------------------
    # EVENTOS DO JOGO -> serial v1, som e tela (nenhuma regra aqui)
    # -----------------------------------------------------
    def _despachar(self, eventos):
        if eventos and eventos[0].startswith(PREFIXO_RECUSA):
            self.avisar(self._texto_recusa(eventos[0]))
            return

        if self.protocolo_arduino == "v2" and "proxima_pergunta" in eventos:
            # O firmware pode ter perdido a configuração; reenvia a cada
            # pergunta nova, sem esperar uma reconexão.
            self._solicitar_configuracao_equipes(motivo="pergunta")

        if self.protocolo_arduino != "v2":
            # LEDs, buzzer e RESET existem apenas no adaptador legado.
            for cmd in comandos_para_arduino(eventos):
                self.enviar_serial(cmd)

        quem_piscar = None
        for ev in eventos:
            if ev.startswith("apertou:"):
                quem_piscar = ev.split(":", 1)[1]
                self._limpar_aviso()
                self.som.apertou(quem_piscar)
            elif ev == "revelou":
                self._limpar_aviso()
                self.som.revelou()
            elif ev.startswith("pontuou:"):
                self._limpar_aviso()
                self.som.acertou()
            elif ev == "tempo_esgotado":
                self._limpar_aviso()
                self.som.tempo_esgotado()
            elif ev == "proxima_pergunta":
                self._limpar_aviso()
                self._ultimo_seg_tick = None
                self._ocultar_contagem(renderizar=False)
                self.som.nova_pergunta()
                if self.jogo.estado.fase == FASE_AGUARDANDO:
                    # Contagem desativada: já estamos valendo; botões que
                    # ficaram na fila da rodada anterior não podem ganhar.
                    self.descartar_botoes_fila(time.monotonic())
            elif ev.startswith("contagem:"):
                self._mostrar_contagem(ev.split(":", 1)[1])
                self.som.contagem()
            elif ev == "largada":
                # Fronteira da rodada: tudo que a thread serial recebeu antes
                # deste instante é aperto da contagem e não vale. Eventos
                # recebidos depois do corte seguem para o Jogo.
                corte = time.monotonic()
                self._limpar_aviso()
                self._ultimo_seg_tick = None
                self._mostrar_contagem("JÁ!")
                self.som.largada()
                # Aperto durante a contagem não vale: remove os BTN_A/B/C/D
                # recebidos antes do "JÁ!".
                self.descartar_botoes_fila(corte)
            elif ev == "reiniciou_placar":
                self._limpar_aviso()
            # "reiniciou_banco" e "led_reacender:*" só têm efeito serial/tela

        self.render()
        self._atualizar_barra()
        if quem_piscar:
            self.piscar(quem_piscar)
        self._reiniciar_loop_timer()
        self._mostrar_aviso_carga()

        # Mudanças relevantes para continuar a partida. Pontuação é gravada
        # na hora (o operador pode fechar logo depois); o resto usa debounce.
        if any(ev.startswith("pontuou:") for ev in eventos):
            self._salvador.pedir_imediato()
        elif any(
            ev in ("proxima_pergunta", "reiniciou_placar", "reiniciou_banco")
            for ev in eventos
        ):
            self._salvador.pedir()

    def _mostrar_aviso_carga(self):
        if self._aviso_carga:
            texto, self._aviso_carga = self._aviso_carga, None
            self.avisar(texto)

    def _texto_recusa(self, evento):
        motivo = evento.split(":", 1)[1]
        texto = MENSAGENS_RECUSA.get(motivo, "")
        if motivo == MOTIVO_ACERTO_OUTRA_EQUIPE:
            quem = self.quem_apertou
            texto = texto.format(equipe=self._nome(quem) if quem else "?")
        return texto

    # -----------------------------------------------------
    # SERIAL
    # -----------------------------------------------------
    def iniciar_thread_serial(self):
        self.serial_comm.iniciar()

    def enviar_serial(self, cmd):
        self.serial_comm.enviar(cmd)

    def drenar_fila(self):
        try:
            while True:
                # Itens de evento trazem o timestamp de recepção como terceiro
                # campo; os demais itens da fila continuam com dois campos.
                item = self.fila.get_nowait()
                tipo, valor = item[0], item[1]
                try:
                    if tipo == "evento":
                        self.processar_evento(valor)
                    elif tipo == "conexao":
                        if valor is None:
                            self.topo.placa = ""
                        self.topo.conexao = valor
                        self.topo.desenhar()
                    elif tipo == "placa":
                        self.topo.placa = valor or ""
                        self.topo.desenhar()
                    elif tipo == "porta_ausente":
                        self.topo.aviso_porta = valor or ""
                        self.topo.desenhar()
                    elif tipo == "protocolo":
                        self._aplicar_protocolo(valor)
                except Exception:
                    log.exception("Falha ao processar item da fila serial")
        except queue.Empty:
            pass
        if self.rodando:
            self.root.after(20, self.drenar_fila)

    def descartar_botoes_fila(self, corte=None):
        """
        Remove da fila os BTN_A/B/C/D recebidos antes do corte.

        O corte é o instante em que a UI processa a entrada em AGUARDANDO
        (no "JÁ!" ou com a contagem desativada). Cada evento da thread serial
        carrega `time.monotonic()` do instante de recepção no PC; só os
        apertos anteriores a esse instante são descartados. Itens sem
        timestamp (fila de teste/legado) são tratados como antigos. Outros
        eventos (conexão, placa, revelar, avançar) são preservados na mesma
        ordem. Devolve quantos foram descartados.
        """
        if corte is None:
            corte = time.monotonic()

        mantidos = []
        descartados = 0
        while True:
            try:
                item = self.fila.get_nowait()
            except queue.Empty:
                break

            if (
                isinstance(item, tuple)
                and len(item) >= 2
                and item[0] == "evento"
                and item[1] in ("BTN_A", "BTN_B", "BTN_C", "BTN_D")
            ):
                recebido_em = item[2] if len(item) >= 3 else None
                if recebido_em is None or recebido_em < corte:
                    descartados += 1
                    continue

            mantidos.append(item)

        for item in mantidos:
            self.fila.put(item)

        if descartados:
            log.info(
                "Descartado(s) %d evento(s) de botão de equipe recebido(s) "
                "antes do corte da contagem.",
                descartados,
            )
        return descartados

    def processar_evento(self, evento):
        # Mapeamento linha-da-serial -> ação é uma função pura (protocolo.py)
        log.debug("Evento serial recebido: %s", evento)
        if evento == "VERSAO 2":
            self._aplicar_protocolo("v2")
            return
        if evento == "ERRO EQUIPES" or evento.startswith("EQUIPES "):
            self._receber_equipes(evento)
            return
        if evento == "PRONTO":
            log.info("Arduino reiniciado.")
            self._geracao_conexao += 1
            # O reset por DTR invalida qualquer ACK pendente. O VERSAO 2 que
            # vem logo depois dispara uma nova configuração imediatamente.
            self._cancelar_solicitacao_equipes()
            self._equipes_tentativas = 0
            self._equipes_alvo = 0
            self._equipes_confirmado = False
            self._agendar_verificacao_versao()
        if self.protocolo_arduino == "v2":
            eventos = mapear_evento_arduino(evento, self.jogo)
        else:
            eventos = mapear_evento_arduino_v1(evento, self.jogo)
        self._despachar(eventos)

    # -----------------------------------------------------
    # PROTOCOLO / NÚMERO DE EQUIPES
    # -----------------------------------------------------
    def _agendar_verificacao_versao(self):
        """Firmware v1 só manda PRONTO; o v2 manda VERSAO 2 logo depois."""
        if self.protocolo_arduino == "v2":
            return
        if self._job_versao:
            self.root.after_cancel(self._job_versao)
        self._versao_prazo = self._clock() + TIMEOUT_PRONTO
        atraso_ms = max(1, int(math.ceil(TIMEOUT_PRONTO * 1000)))
        self._job_versao = self.root.after(
            atraso_ms, self._confirmar_protocolo_v1
        )

    def _confirmar_protocolo_v1(self):
        self._job_versao = None
        if self.protocolo_arduino == "v2":
            return
        restante = self._versao_prazo - self._clock()
        if restante > 0.0005:
            # O `after` do Tk pode disparar um pouco antes; o relógio é a
            # autoridade, então reagenda o que faltar.
            self._job_versao = self.root.after(
                max(1, int(math.ceil(restante * 1000))),
                self._confirmar_protocolo_v1,
            )
            return
        self._versao_prazo = 0.0
        self._aplicar_protocolo("v1")

    def _cancelar_solicitacao_equipes(self):
        """Cancela a janela do ACK sem alterar o protocolo detectado."""
        job = getattr(self, "_job_equipes", None)
        if job:
            self.root.after_cancel(job)
            self._job_equipes = None
        self._equipes_prazo = 0.0

    def _definir_protocolo_serial(self, protocolo):
        definir = getattr(self.serial_comm, "definir_protocolo", None)
        if definir is not None:
            definir(protocolo)

    def _solicitar_configuracao_equipes(
        self, *, retentativa=False, motivo="handshake"
    ):
        """
        Pede ao firmware v2 para ativar exatamente as equipes do jogo.

        Cada solicitação abre uma janela não bloqueante. Uma falha gera no
        máximo uma retentativa; a segunda falha vira aviso visível e fallback.
        """
        if self.protocolo_arduino != "v2":
            return

        if retentativa:
            if self._equipes_tentativas >= 2:
                return
            self._equipes_tentativas += 1
        else:
            self._equipes_tentativas = 1

        quantidade = self.jogo.num_equipes
        self._equipes_alvo = quantidade
        self._equipes_confirmado = False
        self._cancelar_solicitacao_equipes()
        self.enviar_serial(comando_config_equipes(quantidade))
        self._equipes_prazo = self._clock() + TIMEOUT_PRONTO
        atraso_ms = max(1, int(math.ceil(TIMEOUT_PRONTO * 1000)))
        self._job_equipes = self.root.after(
            atraso_ms, self._confirmar_equipes
        )
        log.debug(
            "Arduino v2: CONFIG_TEAMS %d (tentativa %d/2, %s).",
            quantidade,
            self._equipes_tentativas,
            motivo,
        )

    def _confirmar_equipes(self):
        """Timeout do ACK `EQUIPES N`; sem ACK, tenta uma vez e avisa."""
        self._job_equipes = None
        if self.protocolo_arduino != "v2":
            return
        restante = self._equipes_prazo - self._clock()
        if restante > 0.0005:
            self._job_equipes = self.root.after(
                max(1, int(math.ceil(restante * 1000))),
                self._confirmar_equipes,
            )
            return

        self._equipes_prazo = 0.0
        self._falhar_equipes("não enviou ACK")

    def _falhar_equipes(self, motivo):
        """WARNING + uma retentativa; na segunda falha, aviso e fallback."""
        alvo = self._equipes_alvo or self.jogo.num_equipes
        tentativa = self._equipes_tentativas
        log.warning(
            "Arduino v2 %s para CONFIG_TEAMS %d (tentativa %d/2).",
            motivo,
            alvo,
            tentativa,
        )

        if tentativa < 2:
            self._solicitar_configuracao_equipes(
                retentativa=True, motivo=motivo
            )
            return

        mensagem = f"Arduino não confirmou {alvo} equipes"
        log.warning("%s; usando 2 equipes para continuar.", mensagem)
        self._aplicar_fallback_equipes(mensagem)

    def _aplicar_fallback_equipes(self, mensagem):
        """Reduz para 2 equipes, mantém o protocolo v2 e deixa o aviso visível."""
        self._cancelar_solicitacao_equipes()
        self._equipes_tentativas = 0
        self._equipes_confirmado = False

        if self.jogo.num_equipes > 2:
            self.jogo.reduzir_equipes(2)
            self._fallback_equipes = True
            self._geracao_fallback = self._geracao_conexao
            self._reconstruir_cartoes()
            self._atualizar_barra()
            self._salvador.pedir_imediato()

        self._equipes_alvo = self.jogo.num_equipes
        # Melhor esforço: deixa o firmware alinhado ao modo seguro. Não abre
        # uma terceira janela de ACK; a próxima pergunta reenvia normalmente.
        self.enviar_serial(comando_config_equipes(self.jogo.num_equipes))

        self.topo.aviso_protocolo = mensagem
        self.topo.desenhar()
        self.avisar(mensagem)

    def _receber_equipes(self, evento):
        """Processa `EQUIPES N`/`ERRO EQUIPES` devolvido pelo firmware v2."""
        if self.protocolo_arduino != "v2":
            log.debug("ACK de equipes ignorado fora do protocolo v2: %s", evento)
            return

        pendente = self._job_equipes is not None and self._equipes_tentativas > 0
        if not pendente:
            log.debug("ACK de equipes sem solicitação pendente: %s", evento)
            return

        if evento == "ERRO EQUIPES":
            self._cancelar_solicitacao_equipes()
            self._falhar_equipes("rejeitou CONFIG_TEAMS")
            return

        confirmadas = equipes_confirmadas(evento)
        if confirmadas is None:
            self._cancelar_solicitacao_equipes()
            self._falhar_equipes(f"enviou ACK inválido ({evento!r})")
            return

        alvo = self._equipes_alvo or self.jogo.num_equipes
        if confirmadas != alvo:
            self._cancelar_solicitacao_equipes()
            self._falhar_equipes(
                f"confirmou {confirmadas} equipes em vez de {alvo}"
            )
            return

        self._cancelar_solicitacao_equipes()
        self._equipes_confirmado = True
        self._equipes_tentativas = 0
        log.debug("Arduino v2 confirmou %d equipes.", confirmadas)

    def _aplicar_protocolo(self, protocolo):
        if self._job_versao:
            self.root.after_cancel(self._job_versao)
            self._job_versao = None
        self._versao_prazo = 0.0
        self._cancelar_solicitacao_equipes()

        if protocolo == "v2":
            self.protocolo_arduino = "v2"
            self._definir_protocolo_serial("v2")
            if (
                self._fallback_equipes
                and self._geracao_conexao <= self._geracao_fallback
            ):
                # V2 chegou atrasado na mesma conexão que já caiu para 2.
                # Não expande a partida no meio da rodada; a próxima
                # reconexão (novo PRONTO) poderá restaurar 3/4.
                log.warning(
                    "VERSAO 2 tardio após o fallback; mantendo 2 equipes "
                    "até a próxima reconexão."
                )
                return

            if self._fallback_equipes:
                self._restaurar_equipes_pos_fallback()
            else:
                log.info("Arduino confirmou protocolo v2.")
                self.topo.aviso_protocolo = ""
                self.topo.desenhar()
            self._solicitar_configuracao_equipes(motivo="handshake")
            return

        if protocolo not in ("v1", "sem_handshake"):
            return

        self.protocolo_arduino = protocolo
        self._definir_protocolo_serial(protocolo)
        self._equipes_tentativas = 0
        self._equipes_alvo = 0
        self._equipes_confirmado = False
        if protocolo == "v1":
            motivo = "Arduino v1 não suporta 3/4 equipes"
            aviso = (
                "Arduino v1: usando 2 equipes; "
                "pontos de C/D guardados nesta sessão."
            )
        else:
            motivo = "Arduino não confirmou o handshake"
            aviso = (
                "Sem handshake do Arduino: usando 2 equipes; "
                "pontos de C/D guardados nesta sessão."
            )

        if self.jogo.num_equipes > 2:
            self.jogo.reduzir_equipes(2)
            self._fallback_equipes = True
            self._geracao_fallback = self._geracao_conexao
            self._reconstruir_cartoes()
            self._atualizar_barra()
            self._salvador.pedir_imediato()
            log.warning(
                "%s; partida limitada a 2 equipes; pontos de C/D guardados.",
                motivo,
            )

        if self._equipes_configuradas > 2 and not self._aviso_protocolo_mostrado:
            self._aviso_protocolo_mostrado = True
            self.topo.aviso_protocolo = aviso
            self.topo.desenhar()
            self.avisar(aviso)
        else:
            log.info("%s; mantendo 2 equipes.", motivo)

    def _restaurar_equipes_pos_fallback(self):
        """Volta a 3/4 equipes quando o v2 retorna em uma nova conexão."""
        alvo = self._equipes_configuradas
        if alvo <= self.jogo.num_equipes:
            self._fallback_equipes = False
            self.topo.aviso_protocolo = ""
            self.topo.desenhar()
            return
        if not self.jogo.restaurar_equipes(alvo):
            return

        self._fallback_equipes = False
        self._geracao_fallback = 0
        self._aviso_protocolo_mostrado = False
        self._reconstruir_cartoes()
        self._atualizar_barra()
        self._salvador.pedir_imediato()
        self.topo.aviso_protocolo = ""
        self.topo.desenhar()
        aviso = (
            f"Arduino v2: {alvo} equipes restauradas; "
            "pontos de C/D recuperados."
        )
        self.avisar(aviso)
        log.info(
            "Arduino v2 reconectado; partida restaurada para %d equipes.",
            alvo,
        )

    # -----------------------------------------------------
    # AÇÕES DA UI (só delegam ao Jogo e despacham os eventos)
    # AGUARDANDO -> RESPONDENDO -> REVELADA -> PONTUADA
    # -----------------------------------------------------
    def apertar_botao(self, quem):
        self._despachar(self.jogo.apertar_botao(quem))

    def revelar_resposta(self):
        self._despachar(self.jogo.revelar_resposta())

    def confirmar_acerto(self, quem):
        self._despachar(self.jogo.confirmar_acerto(quem))

    def reiniciar_placar(self):
        n = self.jogo.num_equipes
        alvo = "das duas equipes" if n == 2 else f"das {n} equipes"
        if messagebox.askyesno(TITULO, f"Zerar o placar {alvo}?"):
            self._despachar(self.jogo.reiniciar_placar())

    
    def alternar_som(self):
        if not self.som.disponivel:
            self.avisar("Áudio indisponível. Verifique a instalação do pygame.")
            return

        self.som.ativo = not self.som.ativo

        if self.som.ativo:
            self.som.tocar_ja(("C5", 80), ("E5", 110))

        self.avisar(
            "Som ativado." if self.som.ativo else "Som silenciado."
        )


    # -----------------------------------------------------
    # TECLADO (simulação)
    # -----------------------------------------------------
    def tecla_pressionada(self, event):
        # Ctrl/Alt não podem virar aperto de equipe: em alguns teclados o
        # Tk entrega `event.char` mesmo com o modificador pressionado. Shift
        # e Caps Lock continuam valendo (o `lower()` normaliza a letra).
        if event.state & (0x4 | 0x8 | 0x20000):
            return

        k = (event.char or "").lower()
        if not k:
            # Fallback para Num Lock desligado em alguns layouts: o numpad
            # pode chegar sem `event.char`. O comportamento 1/2 é preservado.
            k = {
                "KP_1": "1", "KP_2": "2", "KP_3": "3", "KP_4": "4",
            }.get(event.keysym, "")

        if k in ("a", "b", "c", "d"):
            self.apertar_botao(k.upper())
        elif k in ("1", "2", "3", "4"):
            self.confirmar_acerto(("A", "B", "C", "D")[int(k) - 1])
        elif k == "n":
            self.proxima_pergunta()
        elif k == "r":
            self.revelar_resposta()
        elif k == "s":
            self.alternar_som()

    def fechar(self):
        # Fechar normalmente preserva a partida: grava o que estiver pendente.
        # Na tela "Continuar partida salva?" ainda não há jogo/arquivo atual,
        # então este flush é no-op e não sobrescreve o estado salvo.
        self._salvador.executar_agora()
        self.rodando = False
        self._cancelar_contagem_visual()
        job_versao = getattr(self, "_job_versao", None)
        if job_versao:
            self.root.after_cancel(job_versao)
            self._job_versao = None
        self._versao_prazo = 0.0
        self._cancelar_solicitacao_equipes()
        self.serial_comm.parar()
        self.som.parar()
        trava = getattr(self, "_trava", None)
        if trava is not None:
            trava.liberar()
        janela_sobre = getattr(self, "_janela_sobre", None)
        if janela_sobre is not None:
            try:
                janela_sobre.destroy()
            except tk.TclError:
                pass
            self._janela_sobre = None
        self.root.destroy()


# -----------------------------------------------------
# ENTRADA ERRADA
# Este arquivo é só a interface; a montagem fica em main.py.
# Rodá-lo direto antes terminava em silêncio (código 0), parecendo sucesso.
# -----------------------------------------------------
if __name__ == "__main__":
    print("Use: python main.py")
    raise SystemExit(1)

