"""
Prova de equivalência com o protótipo (tag v2.1-prototipo).

Cada teste cobre EXPLICITAMENTE uma regra que existia em
`git show v2.1-prototipo:desafio.py`, com a linha original citada.
Nada aqui depende de tkinter, serial ou pygame.
"""

from pathlib import Path

import pytest

from jogo import (
    Jogo,
    FASE_AGUARDANDO,
    FASE_RESPONDENDO,
    FASE_REVELADA,
    FASE_PONTUADA,
    TIMER_MOTIVO_REVELADA,
    TIMER_MOTIVO_TEMPO_ESGOTADO,
)
from protocolo import comandos_para_arduino, mapear_evento_arduino

RAIZ = Path(__file__).resolve().parent.parent


class Relogio:
    """Relógio fake: o teste move o tempo à mão."""

    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def jogo(perguntas_exemplo, relogio):
    return Jogo(
        perguntas_exemplo,
        num_equipes=2,
        tempo_pergunta=30,
        tempo_resposta=15,
        clock=relogio,
        contagem_largada=0,
    )


# ─────────────────────────────────────────────────────────
# 1. Estouro do tempo em AGUARDANDO (ninguém apertou)
#    Original: _tempo_esgotado, linhas 1704-1707
# ─────────────────────────────────────────────────────────
class TestEstouroEmAguardando:
    def test_fase_vai_para_revelada_sem_autor(self, jogo, relogio):
        relogio.avancar(31)
        assert jogo.tick_timer() == ["tempo_esgotado"]

        assert jogo.estado.fase == FASE_REVELADA
        assert jogo.estado.quem_apertou is None
        assert jogo.estado.tempo_estourou is False
        assert jogo.timer_motivo == TIMER_MOTIVO_TEMPO_ESGOTADO
        assert jogo.timer_restante_visual() == 0
        assert jogo.timer_restante() == 0
        assert jogo.timer_rotulo == "Tempo esgotado"
        assert jogo.timer_ativo is False

    def test_estouro_nao_repete(self, jogo, relogio):
        relogio.avancar(31)
        assert jogo.tick_timer() == ["tempo_esgotado"]
        relogio.avancar(5)
        assert jogo.tick_timer() == []


# ─────────────────────────────────────────────────────────
# 2. ACERTO sem ninguém ter apertado
#    Original: confirmar_acerto, linhas 1869-1871
# ─────────────────────────────────────────────────────────
class TestAcertoSemAutor:
    def test_apos_estouro_em_aguardando_nao_pontua(self, jogo, relogio):
        relogio.avancar(31)
        jogo.tick_timer()  # AGUARDANDO -> REVELADA sem quem_apertou
        assert jogo.estado.fase == FASE_REVELADA

        assert jogo.confirmar_acerto("A") == ["recusado:acerto_sem_quem"]
        assert jogo.confirmar_acerto("B") == ["recusado:acerto_sem_quem"]
        assert jogo.placar == {"A": 0, "B": 0}
        assert jogo.estado.fase == FASE_REVELADA


# ─────────────────────────────────────────────────────────
# 3. REVELAR durante AGUARDANDO
#    Original: revelar_resposta, linhas 1852-1854
# ─────────────────────────────────────────────────────────
class TestRevelarEmAguardando:
    def test_recusa_e_nao_muda_de_fase(self, jogo, relogio):
        assert jogo.revelar_resposta() == ["recusado:revelar_aguardando"]
        assert jogo.estado.fase == FASE_AGUARDANDO
        assert jogo.estado.quem_apertou is None
        # O prazo continua correndo
        assert jogo.timer_ativo is True
        assert jogo.timer_restante() == pytest.approx(30)

    def test_revelar_depois_de_pontuar_e_ignorado_em_silencio(self, jogo):
        jogo.apertar_botao("A")
        jogo.revelar_resposta()
        jogo.confirmar_acerto("A")
        assert jogo.estado.fase == FASE_PONTUADA
        assert jogo.revelar_resposta() == []


# ─────────────────────────────────────────────────────────
# 4. Estouro em RESPONDENDO e congelamento da barra ao revelar
#    Original: _tempo_esgotado 1708-1711 / _congelar_barra 1699-1702
# ─────────────────────────────────────────────────────────
class TestEstouroEmRespondendo:
    def test_marca_tempo_estourado(self, jogo, relogio):
        jogo.apertar_botao("A")
        relogio.avancar(16)
        assert jogo.tick_timer() == ["tempo_esgotado"]

        assert jogo.estado.fase == FASE_REVELADA
        assert jogo.estado.quem_apertou == "A"
        assert jogo.estado.tempo_estourou is True
        assert jogo.timer_motivo == TIMER_MOTIVO_TEMPO_ESGOTADO
        assert jogo.timer_restante_visual() == 0


class TestCongelamentoDaBarra:
    def test_revelar_congela_no_restante(self, jogo, relogio):
        jogo.apertar_botao("A")          # timer de resposta = 15s
        relogio.avancar(5)
        assert jogo.revelar_resposta() == ["revelou"]

        assert jogo.timer_restante() == 0           # prazo parou
        assert jogo.timer_ativo is False
        assert jogo.timer_restante_visual() == pytest.approx(10)  # barra preservada
        assert jogo.timer_fracao() == pytest.approx(10 / 15)
        assert jogo.timer_motivo == TIMER_MOTIVO_REVELADA
        assert jogo.timer_rotulo == "Resposta revelada"

    def test_barra_cheia_na_nova_pergunta(self, jogo, relogio):
        jogo.apertar_botao("A")
        relogio.avancar(5)
        jogo.revelar_resposta()
        jogo.confirmar_acerto("A")
        jogo.proxima_pergunta()

        assert jogo.timer_restante() == pytest.approx(30)
        assert jogo.timer_restante_visual() == pytest.approx(30)
        assert jogo.timer_fracao() == pytest.approx(1.0)
        assert jogo.timer_motivo == ""
        assert jogo.timer_rotulo == "Tempo para apertar"


# ─────────────────────────────────────────────────────────
# 4b. ACERTO fora de hora / repetido
#     Original: confirmar_acerto, linhas 1864-1868
# ─────────────────────────────────────────────────────────
class TestAcertoForaDeHora:
    def test_acerto_em_aguardando(self, jogo):
        assert jogo.confirmar_acerto("A") == ["recusado:acerto_fase"]
        assert jogo.estado.fase == FASE_AGUARDANDO

    def test_acerto_em_respondendo(self, jogo):
        jogo.apertar_botao("A")
        assert jogo.confirmar_acerto("A") == ["recusado:acerto_fase"]
        assert jogo.placar["A"] == 0
        assert jogo.estado.fase == FASE_RESPONDENDO

    def test_acerto_repetido_apos_pontuar_e_ignorado(self, jogo):
        jogo.apertar_botao("A")
        jogo.revelar_resposta()
        assert jogo.confirmar_acerto("A") == ["pontuou:A"]
        assert jogo.confirmar_acerto("A") == []          # em PONTUADA: silêncio
        assert jogo.placar["A"] == 1


# ─────────────────────────────────────────────────────────
# 4c. Estouro fora das fases com prazo (o original dava return)
#     Original: _tempo_esgotado, linhas 1712-1713
# ─────────────────────────────────────────────────────────
class TestEstouroForaDeHora:
    def test_tick_apos_revelar_nao_faz_nada(self, jogo, relogio):
        jogo.apertar_botao("A")
        jogo.revelar_resposta()
        relogio.avancar(60)
        assert jogo.tick_timer() == []
        assert jogo.estado.fase == FASE_REVELADA
        assert jogo.estado.tempo_estourou is False

    def test_tick_apos_pontuar_nao_faz_nada(self, jogo, relogio):
        jogo.apertar_botao("A")
        jogo.revelar_resposta()
        jogo.confirmar_acerto("A")
        relogio.avancar(60)
        assert jogo.tick_timer() == []
        assert jogo.estado.fase == FASE_PONTUADA


# ─────────────────────────────────────────────────────────
# 4d. Sem banco de perguntas
#     Original: proxima_pergunta, linhas 1477-1480
# ─────────────────────────────────────────────────────────
class TestSemPerguntas:
    def test_proxima_pergunta_sem_banco(self, relogio):
        j = Jogo([], clock=relogio)
        assert j.proxima_pergunta(forcar=True) == []
        assert j.estado.pergunta_atual is None
        assert j.timer_ativo is False

    def test_apertar_sem_pergunta(self, relogio):
        j = Jogo([], clock=relogio)
        assert j.apertar_botao("A") == []
        assert j.estado.fase == FASE_AGUARDANDO


# ─────────────────────────────────────────────────────────
# 5. LEDs e serial em cada transição
#    Original: apertar_botao 1845-1846, confirmar_acerto 1885,
#              _tempo_esgotado 1715, proxima_pergunta 1495,
#              processar_evento/PRONTO 1829-1832
# ─────────────────────────────────────────────────────────
class TestLedsPorTransicao:
    def test_apertar_acende_led_e_bipa(self):
        assert comandos_para_arduino(["apertou:A"]) == ["LED_A_ON", "BEEP"]
        assert comandos_para_arduino(["apertou:B"]) == ["LED_B_ON", "BEEP"]

    def test_revelar_nao_mexe_no_led(self):
        assert comandos_para_arduino(["revelou"]) == []

    def test_pontuar_bipa_longo(self):
        assert comandos_para_arduino(["pontuou:A"]) == ["BEEP_LONG"]
        assert comandos_para_arduino(["pontuou:B"]) == ["BEEP_LONG"]

    def test_estouro_bipa(self):
        assert comandos_para_arduino(["tempo_esgotado"]) == ["BEEP"]

    def test_nova_pergunta_reseta_o_arduino(self):
        assert comandos_para_arduino(["proxima_pergunta"]) == ["RESET"]

    def test_reinicio_do_banco_nao_reseta_de_novo(self):
        # O RESET já vem de "proxima_pergunta"; "reiniciou_banco" é só informativo
        assert comandos_para_arduino(["reiniciou_banco", "proxima_pergunta"]) == ["RESET"]

    def test_pronto_reacende_led_de_quem_apertou(self, jogo):
        jogo.apertar_botao("A")
        assert mapear_evento_arduino("PRONTO", jogo) == ["led_reacender:A"]
        assert comandos_para_arduino(["led_reacender:A"]) == ["LED_A_ON"]

    def test_pronto_sem_aperto_nao_acende_nada(self, jogo):
        assert mapear_evento_arduino("PRONTO", jogo) == []

    def test_nenhuma_transicao_apaga_led(self, jogo):
        """No protótipo o LED só era aceso por LED_x_ON; o firmware nunca recebia LED_x_OFF."""
        todos_eventos = [
            ["apertou:A"],
            ["revelou"],
            ["pontuou:A"],
            ["tempo_esgotado"],
            ["proxima_pergunta"],
            ["reiniciou_banco"],
            ["reiniciou_placar"],
            ["led_reacender:A"],
        ]
        for eventos in todos_eventos:
            for cmd in comandos_para_arduino(eventos):
                assert not cmd.endswith("_OFF")


# ─────────────────────────────────────────────────────────
# 6. Protocolo serial -> ação (função pura, usada pela UI)
#    Original: processar_evento, linhas 1816-1832
# ─────────────────────────────────────────────────────────
class TestProtocoloPuro:
    def test_btn_a(self, jogo):
        assert mapear_evento_arduino("BTN_A", jogo) == ["apertou:A"]
        assert jogo.estado.quem_apertou == "A"

    def test_btn_b(self, jogo):
        assert mapear_evento_arduino("BTN_B", jogo) == ["apertou:B"]
        assert jogo.estado.quem_apertou == "B"

    def test_segundo_aperto_e_ignorado(self, jogo):
        mapear_evento_arduino("BTN_A", jogo)
        assert mapear_evento_arduino("BTN_B", jogo) == []
        assert jogo.estado.quem_apertou == "A"

    def test_fluxo_completo_pelo_protocolo(self, jogo):
        assert mapear_evento_arduino("BTN_A", jogo) == ["apertou:A"]
        assert mapear_evento_arduino("BTN_REVELAR", jogo) == ["revelou"]
        assert mapear_evento_arduino("BTN_ACERTO_A", jogo) == ["pontuou:A"]
        assert mapear_evento_arduino("BTN_AVANCAR", jogo) == ["proxima_pergunta"]
        assert jogo.placar["A"] == 1
        assert jogo.estado.fase == FASE_AGUARDANDO

    def test_avancar_em_aguardando_e_recusado(self, jogo):
        assert mapear_evento_arduino("BTN_AVANCAR", jogo) == ["recusado:avancar"]
        assert jogo.estado.fase == FASE_AGUARDANDO

    def test_linha_desconhecida_nao_faz_nada(self, jogo):
        assert mapear_evento_arduino("QUALQUER_COISA", jogo) == []
        assert jogo.estado.fase == FASE_AGUARDANDO


# ─────────────────────────────────────────────────────────
# 7. Carregador único de perguntas
# ─────────────────────────────────────────────────────────
class TestCarregadorUnico:
    def test_desafio_usa_o_carregador_do_jogo(self):
        fonte = (RAIZ / "desafio.py").read_text(encoding="utf-8")
        assert "ler_banco_perguntas" in fonte
        # Não pode existir um segundo carregador no arquivo de UI
        assert "json.load(" not in fonte

    def test_erro_de_arquivo_inexistente_nao_levanta(self, tmp_path):
        from perguntas import ler_banco_perguntas

        carga = ler_banco_perguntas(str(tmp_path / "nao_existe.json"), tema_padrao="X")
        assert carga.perguntas == []
        assert carga.erro
        assert carga.tema == "X"

    def test_perguntas_que_nao_e_lista_nao_vira_ignoradas(self, tmp_path):
        """config.json tem "perguntas": {"pasta": ..., "arquivo_padrao": ...}."""
        import json

        from perguntas import ler_banco_perguntas

        arquivo = tmp_path / "config.json"
        arquivo.write_text(
            json.dumps({"perguntas": {"pasta": "perguntas", "arquivo_padrao": "x.json"}}),
            encoding="utf-8",
        )
        carga = ler_banco_perguntas(str(arquivo))
        assert carga.perguntas == []
        assert carga.ignoradas == []          # não inventa "pergunta ignorada"
        assert "deve ser uma lista" in carga.erro

    def test_aceita_pergunta_e_texto(self, tmp_path):
        import json

        from perguntas import ler_banco_perguntas

        arquivo = tmp_path / "banco.json"
        arquivo.write_text(
            json.dumps(
                {
                    "tema": "Tema do arquivo",
                    "perguntas": [
                        {"pergunta": "P1?", "alternativas": ["a", "b"], "correta": 0},
                        {"texto": "P2?", "alternativas": ["a", "b"], "correta": 1},
                        {"alternativas": ["a", "b"], "correta": 0},
                        {"pergunta": "P4?", "alternativas": ["a"], "correta": 0},
                        {"pergunta": "P5?", "alternativas": ["a", "b"], "correta": 9},
                    ],
                }
            ),
            encoding="utf-8",
        )
        carga = ler_banco_perguntas(str(arquivo))
        assert [p.texto for p in carga.perguntas] == ["P1?", "P2?"]
        assert carga.tema == "Tema do arquivo"
        assert len(carga.ignoradas) == 3
        assert all(p.categoria == "Tema do arquivo" for p in carga.perguntas)
