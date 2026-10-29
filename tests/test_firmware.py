"""Checagens estáticas dos sketches que não podem ser testados sem o Uno.

A validação física continua sendo obrigatória; estes testes só evitam que a
bancada e o firmware de produção percam pinos, eventos ou o debounce de 60 ms.
"""

import hashlib
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
V1 = RAIZ / "firmware" / "v1" / "duelo_arduino_v1" / "duelo_arduino_v1.ino"
BANCADA = RAIZ / "firmware" / "bancada_botoes" / "bancada_botoes.ino"
V2 = RAIZ / "firmware" / "v2" / "duelo_arduino_v2" / "duelo_arduino_v2.ino"

HASH_V1 = "761CAF1BA38765DE458B1458D898AFAA60E07794CF45C65908D864B80FCB351A"

EVENTOS = (
    "BTN_A",
    "BTN_B",
    "BTN_AVANCAR",
    "BTN_ACERTO_A",
    "BTN_ACERTO_B",
    "BTN_REVELAR",
    "BTN_C",
    "BTN_D",
    "BTN_ACERTO_C",
    "BTN_ACERTO_D",
)


def _texto(caminho):
    return caminho.read_text(encoding="utf-8")


def test_v1_fica_somente_em_firmware_e_mantem_o_hash():
    assert V1.exists()
    assert not (RAIZ / "duelo_arduino.ino").exists()
    # O Git pode materializar o arquivo com CRLF no Windows; o hash de
    # referência é o do blob normalizado com LF.
    conteudo = V1.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(conteudo).hexdigest().upper() == HASH_V1


def test_bancada_tem_os_10_botoes_e_debounce_de_60ms():
    texto = _texto(BANCADA)

    for evento in EVENTOS:
        assert f'"{evento}"' in texto

    assert "DEBOUNCE_MS = 60" in texto
    assert 'Serial.println(F("BANCADA_BOTOES"))' in texto
    assert 'Serial.println(F("ERRO EQUIPES"))' in texto
    assert 'strncmp(cmd, "CONFIG_TEAMS", prefixo)' in texto


def test_v2_faz_handshake_e_aceita_config_teams():
    texto = _texto(V2)

    assert 'Serial.println(F("PRONTO"))' in texto
    assert 'Serial.println(F("VERSAO 2"))' in texto
    assert 'Serial.println(F("ERRO EQUIPES"))' in texto
    assert 'strncmp(cmd, "CONFIG_TEAMS", prefixo)' in texto
    assert "DEBOUNCE_MS = 60" in texto

    for evento in EVENTOS:
        assert f'"{evento}"' in texto


def test_v2_usa_d2_a_d11_sem_saidas_fisicas():
    texto = _texto(V2)

    for pino in range(2, 12):
        assert f"= {pino};" in texto

    assert "pinMode(botoes[i].pino, INPUT_PULLUP)" in texto
    assert "pinMode(LED" not in texto
    assert "pinMode(BUZZER" not in texto
