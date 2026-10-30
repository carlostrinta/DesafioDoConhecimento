"""Caracterização do caminho serial v1 antes da limpeza do protocolo v2.

Estes testes congelam a saída do adaptador legado: cada evento de domínio do
Jogo, o reacendimento do LED no `PRONTO` e o `RESET` enviado ao fechar a porta.
Eles devem continuar passando depois da separação em `protocolo_v1.py`.
"""

import queue

import pytest

import protocolo_v1
import serial_comm
from apoio_serial import ModuloSerialFalso, Porta, criar_comm, esperar
from jogo import Jogo


COMANDOS_POR_EVENTO = {
    "apertou:A": ["LED_A_ON", "BEEP"],
    "apertou:B": ["LED_B_ON", "BEEP"],
    "apertou:C": ["LED_C_ON", "BEEP"],
    "apertou:D": ["LED_D_ON", "BEEP"],
    "pontuou:A": ["BEEP_LONG"],
    "pontuou:B": ["BEEP_LONG"],
    "pontuou:C": ["BEEP_LONG"],
    "pontuou:D": ["BEEP_LONG"],
    "tempo_esgotado": ["BEEP"],
    "proxima_pergunta": ["RESET"],
    "reiniciou_banco": [],
    "reiniciou_placar": [],
    "revelou": [],
    "contagem:3": [],
    "contagem:2": [],
    "contagem:1": [],
    "largada": [],
    "recusado:contagem": [],
    "recusado:avancar": [],
    "recusado:revelar_aguardando": [],
    "recusado:acerto_fase": [],
    "recusado:acerto_sem_quem": [],
    "recusado:acerto_outra_equipe": [],
    "recusado:acerto_tempo": [],
}


@pytest.mark.parametrize("evento, esperado", COMANDOS_POR_EVENTO.items())
def test_comandos_v1_por_evento_de_dominio(evento, esperado):
    assert protocolo_v1.comandos_para_arduino([evento]) == esperado


@pytest.mark.parametrize("equipe", ["A", "B", "C", "D"])
def test_comandos_v1_preservam_ordem_de_multiplos_eventos(equipe):
    assert protocolo_v1.comandos_para_arduino(
        [f"apertou:{equipe}", f"pontuou:{equipe}"]
    ) == [f"LED_{equipe}_ON", "BEEP", "BEEP_LONG"]


@pytest.mark.parametrize("equipe", ["A", "B", "C", "D"])
def test_pronto_reacende_led_da_equipe_na_caracterizacao(
    perguntas_exemplo, equipe
):
    jogo = Jogo(perguntas_exemplo, num_equipes=4, contagem_largada=0)
    assert jogo.apertar_botao(equipe) == [f"apertou:{equipe}"]

    eventos = protocolo_v1.mapear_evento_arduino("PRONTO", jogo)
    assert eventos == [f"led_reacender:{equipe}"]
    assert protocolo_v1.comandos_para_arduino(eventos) == [f"LED_{equipe}_ON"]


def test_pronto_sem_aperto_nao_gera_comando(perguntas_exemplo):
    jogo = Jogo(perguntas_exemplo, num_equipes=4, contagem_largada=0)
    assert protocolo_v1.mapear_evento_arduino("PRONTO", jogo) == []


def test_v1_envia_reset_byte_a_byte_ao_fechar_a_porta():
    modulo = ModuloSerialFalso()
    modulo.portas = [Porta("COM6", "Arduino Uno", 0x2341, 0x0043)]
    modulo.manda_pronto = {"COM6"}
    comm = criar_comm(queue.Queue(), modulo)
    comm.definir_protocolo("v1")
    comm.iniciar()
    try:
        assert esperar(lambda: comm.serial is not None)
        aberta = comm.serial
        comm.parar(timeout=1.0)
        assert aberta.escritas == [b"RESET\n"]
        assert aberta.fechado is True
    finally:
        comm.rodando = False
        comm.fechar()
