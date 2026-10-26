"""
Duelo de Conhecimento — Aplicação Windows
Versão 2.1 — interface de palco + máquina de estados + serial robusta + áudio

Requisitos: Python 3.9+, pyserial  (pip install pyserial)
Protocolo serial: IDÊNTICO ao da v1.1 (o firmware do Arduino não muda).

Atalhos de teclado (modo simulação, funcionam junto com o Arduino):
    A / B      apertar o botão do competidor
    R          revelar resposta
    1 / 2      acerto do A / acerto do B
    N          próxima pergunta
    S          ligar/desligar som
    F11        tela cheia  (Esc sai)
    Ctrl+R     zerar o placar
"""

import math
import os
import queue
import traceback
import tkinter as tk
from tkinter import messagebox

import ui_componentes
from audio import Som
from config import (
    ARQUIVO_PERGUNTAS,
    NOMES_EQUIPES,
    NUM_EQUIPES,
    PONTUAR_APOS_TEMPO,
    TEMPO_PERGUNTA,
    TEMPO_RESPOSTA,
    TITULO,
)
from jogo import (
    Jogo,
    FASE_AGUARDANDO,
    FASE_RESPONDENDO,
    FASE_REVELADA,
    FASE_PONTUADA,
    MOTIVO_ACERTO_FASE,
    MOTIVO_ACERTO_OUTRA_EQUIPE,
    MOTIVO_ACERTO_SEM_QUEM,
    MOTIVO_ACERTO_TEMPO,
    MOTIVO_AVANCAR,
    MOTIVO_REVELAR_AGUARDANDO,
    PREFIXO_RECUSA,
    TIMER_MOTIVO_REVELADA,
)
from perguntas import (
    formatar_nome_tema,
    ler_banco_perguntas,
    listar_arquivos_perguntas,
)
from protocolo import comandos_para_arduino, mapear_evento_arduino
from recursos import caminho_recurso, obter_diretorio_base
from serial_comm import SERIAL_DISPONIVEL, ComunicacaoSerial
from ui_componentes import (
    BarraTempo,
    BarraTopo,
    CartaoAlt,
    CartaoExplicacao,
    CartaoPergunta,
    CartaoPlacar,
    Cor,
    Rodape,
    escolher_fonte,
)
from ui_selecao import ModalSelecaoPerguntas

if not SERIAL_DISPONIVEL:
    print("AVISO: pyserial não instalado. Modo teclado ativo.")

# =========================================================
# CONFIGURAÇÕES
# Os valores (título, equipes, tempos, serial) ficam em config.py.
# Este módulo ainda NÃO lê config.json — isso entra na Etapa 4.2.
# =========================================================
NOME_A = NOMES_EQUIPES["A"]
NOME_B = NOMES_EQUIPES["B"]


# =========================================================
# FASES DA RODADA (definidas em jogo.py — fonte única)
# =========================================================
# Mensagens das recusas do Jogo. A regra mora no Jogo; aqui só o texto.
MENSAGENS_RECUSA = {
    MOTIVO_AVANCAR: "Resolva a pergunta atual (revele ou pontue) antes de avançar.",
    MOTIVO_REVELAR_AGUARDANDO: "Ninguém apertou ainda. REVELAR só funciona depois que A ou B apertar.",
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


# =========================================================
# APLICAÇÃO PRINCIPAL
# =========================================================
class DueloDeConhecimento:
    def __init__(self, root):
        self.root = root
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
        self.jogo = Jogo(
            [],
            num_equipes=NUM_EQUIPES,
            tempo_pergunta=TEMPO_PERGUNTA,
            tempo_resposta=TEMPO_RESPOSTA,
            pontuar_apos_tempo=PONTUAR_APOS_TEMPO,
            nomes_equipes=dict(NOMES_EQUIPES),
        )

        self.aviso = None
        self._aviso_carga = None

        self._job_timer = None
        self._job_aviso = None
        self._job_escala = None

        self.rodando = True
        self.fila = queue.Queue()
        self.serial_comm = ComunicacaoSerial(self.fila)

        # Ícone da janela principal
        ico_path = caminho_recurso("desafio.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        # ---------- Áudio ----------
        self.som = Som()
        self._ultimo_seg_tick = None

        # ---------- Inicialização ----------
        self.montar_interface()
        self.iniciar_thread_serial()

        self.root.bind("<Key>", self.tecla_pressionada)
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

        self.root.after(20, self.drenar_fila)
        self.render()

        # Abre o seletor de temas na inicialização da aplicação
        self.root.after(100, lambda: self.abrir_seletor_tema(inicial=True))

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
            caminho = caminho_recurso(ARQUIVO_PERGUNTAS)

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
            print(carga.erro)
        for linha in carga.ignoradas:
            print(linha)

        self.jogo.recarregar_perguntas(carga.perguntas)
        print(f"[{self.tema_atual}] {len(carga.perguntas)} perguntas carregadas de {nome_arquivo}.")
        # Aviso na tela (o detalhe de cada pergunta vai para o log na Etapa 4.1)
        self._aviso_carga = mensagem_ignoradas(len(carga.ignoradas), nome_arquivo)

        if hasattr(self, "topo"):
            self.topo.tema = self.tema_atual
            self.topo.desenhar()

    def abrir_seletor_tema(self, inicial=False):
        """Abre a tela modal para escolha de tema/arquivo de perguntas."""
        if self._job_timer:
            self._cancelar_job_timer()

        diretorio = obter_diretorio_base()
        arquivos = listar_arquivos_perguntas(diretorio)

        atual = None
        if self.arquivo_atual:
            for arq in arquivos:
                if os.path.abspath(arq["caminho"]) == os.path.abspath(self.arquivo_atual):
                    atual = arq
                    break
        if atual is None and arquivos:
            atual = arquivos[0]

        def ao_confirmar(info_escolhida):
            if not info_escolhida:
                return
            mesmo_arquivo = self.arquivo_atual and (os.path.abspath(info_escolhida["caminho"]) == os.path.abspath(self.arquivo_atual))

            if not inicial and not mesmo_arquivo and (self.placar_a > 0 or self.placar_b > 0):
                if messagebox.askyesno(TITULO, f"Zerar o placar dos competidores para '{info_escolhida['titulo']}'?", parent=self.root):
                    self.placar_a = self.placar_b = 0

            self.carregar_perguntas(info_escolhida["caminho"], info_escolhida["titulo"])
            self.proxima_pergunta(forcar=True)

        modal = ModalSelecaoPerguntas(
            parent=self.root,
            lista_arquivos=arquivos,
            arquivo_atual=atual,
            ao_confirmar=ao_confirmar,
            permitir_cancelar=True,
            inicial=inicial
        )

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

        self.cartao_a = CartaoPlacar(r, NOME_A, Cor.A)
        self.cartao_a.grid(row=1, column=0, sticky="nsew", padx=(P, 8), pady=10)
        self.cartao_b = CartaoPlacar(r, NOME_B, Cor.B)
        self.cartao_b.grid(row=1, column=2, sticky="nsew", padx=(8, P), pady=10)

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

        self.rodape = Rodape(r, height=84)
        self.rodape.grid(row=2, column=0, columnspan=3, sticky="ew", padx=P, pady=(0, 14))

        self.telas = [self.topo, self.cartao_a, self.cartao_b, self.barra,
                      self.cartao_pergunta, *self.cartoes_alt, self.cartao_explic, self.rodape]

    def _nome(self, letra):
        return NOME_A if letra == "A" else NOME_B

    def _cor(self, letra):
        return Cor.A if letra == "A" else Cor.B

    def _status_padrao(self):
        if self.pergunta_atual is None:
            if not self.perguntas:
                return (self.erro_carga or "Aguardando seleção de tema de perguntas.", Cor.SUAVE)
            return (self.erro_carga or "Nenhuma pergunta válida carregada.", Cor.ERRO)
        q = self.quem_apertou
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

        for cartao, letra, pts, outro in ((self.cartao_a, "A", self.placar_a, self.placar_b),
                                          (self.cartao_b, "B", self.placar_b, self.placar_a)):
            cartao.pontos = pts
            cartao.ativo = (self.quem_apertou == letra)
            cartao.rotulo = "Apertou primeiro" if cartao.ativo else ("Na frente" if pts > outro else "")
            cartao.desenhar()

        cp = self.cartao_pergunta
        if p:
            cp.categoria, cp.texto, cp.numero = p.categoria, p.texto, self.numero
        else:
            cp.categoria, cp.texto, cp.numero = "", "Nenhuma pergunta carregada.", 0
        cp.desenhar()

        for i, c in enumerate(self.cartoes_alt):
            if p and i < len(p.alternativas):
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

        msg, cor = (self.aviso, Cor.AVISO) if self.aviso else self._status_padrao()
        self.rodape.msg, self.rodape.cor_msg, self.rodape.passo = msg, cor, self.fase
        self.rodape.desenhar()

    def avisar(self, texto):
        """Aviso temporário no rodapé (some sozinho, não altera o estado)."""
        self._limpar_aviso()
        self.aviso = texto
        self._job_aviso = self.root.after(3500, self._expirar_aviso)
        self.render()

    def _expirar_aviso(self):
        self._job_aviso = None
        self.aviso = None
        self.render()

    def _limpar_aviso(self):
        if self._job_aviso:
            self.root.after_cancel(self._job_aviso)
            self._job_aviso = None
        self.aviso = None

    def piscar(self, letra, n=5):
        cartao = self.cartao_a if letra == "A" else self.cartao_b

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
        if self.jogo.timer_ativo:
            self._tick()

    def _tick(self):
        self._job_timer = None
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
    # EVENTOS DO JOGO -> LED, som e tela (nenhuma regra aqui)
    # -----------------------------------------------------
    def _despachar(self, eventos):
        if eventos and eventos[0].startswith(PREFIXO_RECUSA):
            self.avisar(self._texto_recusa(eventos[0]))
            return

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
                self.som.nova_pergunta()
            elif ev == "reiniciou_placar":
                self._limpar_aviso()
            # "reiniciou_banco" e "led_reacender:*" só têm efeito serial/tela

        self.render()
        self._atualizar_barra()
        if quem_piscar:
            self.piscar(quem_piscar)
        self._reiniciar_loop_timer()
        self._mostrar_aviso_carga()

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
                tipo, valor = self.fila.get_nowait()
                try:
                    if tipo == "evento":
                        self.processar_evento(valor)
                    elif tipo == "conexao":
                        self.topo.conexao = valor
                        self.topo.desenhar()
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        if self.rodando:
            self.root.after(20, self.drenar_fila)

    def processar_evento(self, evento):
        # Mapeamento linha-da-serial -> ação é uma função pura (protocolo.py)
        if evento == "PRONTO":
            print("Arduino reiniciado.")
        self._despachar(mapear_evento_arduino(evento, self.jogo))

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
        if messagebox.askyesno(TITULO, "Zerar o placar dos dois competidores?"):
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
        k = event.char.lower()
        if k == "a":
            self.apertar_botao("A")
        elif k == "b":
            self.apertar_botao("B")
        elif k == "n":
            self.proxima_pergunta()
        elif k == "1":
            self.confirmar_acerto("A")
        elif k == "2":
            self.confirmar_acerto("B")
        elif k == "r":
            self.revelar_resposta()
        elif k == "s":
            self.alternar_som()
        elif k == "t" and (event.state & 0x4):
            self.abrir_seletor_tema(inicial=False)

    def fechar(self):
        self.rodando = False
        self.serial_comm.parar()
        self.som.parar()
        self.root.destroy()

