"""
Testes de `audio.py` (Etapa 3.3).

Duas provas principais:

1. Os bytes WAV de cada evento são **idênticos** aos gerados pelo código da
   v2.2 (sha256 fixado abaixo, capturado de `v2.2-logica-integrada` antes da
   movimentação). Se qualquer nota, frequência, duração, volume ou envelope
   mudar, o teste falha.
2. O áudio é opcional: sem pygame, `Som` fica inativo e nada levanta exceção;
   com um pygame falso, dá para verificar qual som cada evento pede.

Nada aqui toca a placa de som de verdade.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import audio
from jogo import FASE_AGUARDANDO, FASE_RESPONDENDO

RAIZ = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────
# pygame falso (só o suficiente para o Som funcionar)
# ─────────────────────────────────────────────────────────
class FakeSound:
    def __init__(self, file=None, buffer=None):
        self.dados = file.read() if file is not None else b""


class FakeCanal:
    def __init__(self):
        self.tocados = []
        self.paradas = 0
        self._busy = False

    def stop(self):
        self.paradas += 1
        self._busy = False

    def play(self, som):
        self.tocados.append(som.dados)
        self._busy = True
        return True

    def get_busy(self):
        return self._busy


class FakeMixer:
    def __init__(self):
        self.init_kwargs = None
        self.num_channels = None
        self.canais = {}
        self.sons = []
        self.quit_chamado = False

    def init(self, **kw):
        self.init_kwargs = kw

    def set_num_channels(self, n):
        self.num_channels = n

    def Channel(self, indice):
        return self.canais.setdefault(indice, FakeCanal())

    def Sound(self, file=None, buffer=None):
        som = FakeSound(file=file, buffer=buffer)
        self.sons.append(som)
        return som

    def quit(self):
        self.quit_chamado = True


class FakePygame:
    def __init__(self):
        self.mixer = FakeMixer()


@pytest.fixture
def pygame_falso(monkeypatch):
    fake = FakePygame()
    monkeypatch.setitem(sys.modules, "pygame", fake)
    return fake


# ─────────────────────────────────────────────────────────
# 1. Bytes WAV idênticos aos da v2.2
#    (hashes capturados de v2.2-logica-integrada:desafio.py)
# ─────────────────────────────────────────────────────────
EVENTOS_V22 = [
    (
        "nova_pergunta",
        lambda s: s.nova_pergunta(),
        (("E5", 90), ("G5", 90), ("C6", 140)),
        "65fc02f8e433c0761bc9b9832577ff36a242204613899fa65d5c84728f8ed3cc",
    ),
    (
        "apertou_A",
        lambda s: s.apertou("A"),
        (("A4", 90), ("C5", 110)),
        "55e2ddd71d3f24319e85982d83f358a97dff0ce21c148445c10bc8d169887fa2",
    ),
    (
        "apertou_B",
        lambda s: s.apertou("B"),
        (("G4", 90), ("D5", 110)),
        "92d5cc1d60907b577d330c0938bce2011fa589b05d54a08cd23946f867f3da6c",
    ),
    (
        "revelou",
        lambda s: s.revelou(),
        (("C5", 80), ("E5", 80), ("G5", 130)),
        "293e60d31eaecda376248ec0e768e9548e01b5958412b887fcdc3f2f917101d6",
    ),
    (
        "acertou",
        lambda s: s.acertou(),
        (("C5", 90), ("E5", 90), ("G5", 90), ("C6", 220)),
        "a2aa09a4f9761f83f487c5a879b0754bb44b976e43b77aabe0374aaf9c02a085",
    ),
    (
        "tempo_esgotado",
        lambda s: s.tempo_esgotado(),
        (("E4", 200), ("C4", 220), ("A3", 320)),
        "601dc368a634ba3864602525c8a9ec13f8c0183886cb1ec6b45f5b0e0558cb0c",
    ),
    (
        "tick_aguardando_9s",
        lambda s: s.tick(9, FASE_AGUARDANDO),
        ((587, 35),),
        "99f55e6fad9d99423f44bd8d7176a48bbac30224cf322dedcd220d2b717099bd",
    ),
    (
        "tick_aguardando_3s",
        lambda s: s.tick(3, FASE_AGUARDANDO),
        ((880, 45),),
        "f50ca282af9546b2ad49551b61af67a9ef09b8f21a82473ec20197202b5cb684",
    ),
    (
        "tick_respondendo_8s",
        lambda s: s.tick(8, FASE_RESPONDENDO),
        ((740, 40),),
        "6e92e10b013ecd1186efee8d9a090062d997c08ba95707613444f99a50c6f4ac",
    ),
    (
        "tick_respondendo_3s",
        lambda s: s.tick(3, FASE_RESPONDENDO),
        ((988, 55),),
        "7623eddbc374dd0b595ddb4b4361088fc262b030bc88d4afd6e28927973ed6dc",
    ),
]


class TestBytesIdenticosV22:
    @pytest.mark.parametrize(
        "nome, acao, notas, sha_esperado",
        EVENTOS_V22,
        ids=[e[0] for e in EVENTOS_V22],
    )
    def test_wav_do_evento(self, nome, acao, notas, sha_esperado, pygame_falso):
        som = audio.Som()
        acao(som)

        assert list(som._cache) == [notas], nome
        dados = som._cache[notas].dados
        assert hashlib.sha256(dados).hexdigest() == sha_esperado, nome

    def test_volume_do_efeito_continua_042(self, monkeypatch, pygame_falso):
        """O volume usado em `_wav` é parte da identidade sonora."""
        capturado = {}
        original = audio._gerar_wav

        def espiao(notas, taxa=22050, volume=0.55):
            capturado["volume"] = volume
            capturado["taxa"] = taxa
            return original(notas, taxa=taxa, volume=volume)

        monkeypatch.setattr(audio, "_gerar_wav", espiao)
        audio.Som().nova_pergunta()

        assert capturado == {"volume": 0.42, "taxa": 22050}


class TestSemSom:
    def test_tick_sem_som_nao_gera_nada(self, pygame_falso):
        som = audio.Som()
        som.tick(0, FASE_AGUARDANDO)       # zerado
        som.tick(10, FASE_RESPONDENDO)     # fora da janela
        som.tick(9, FASE_RESPONDENDO)      # fora da janela
        assert som._cache == {}
        assert pygame_falso.mixer.canais[0].tocados == []


class TestSemPygame:
    def test_import_indisponivel_nao_levanta(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pygame", None)  # faz import pygame falhar
        som = audio.Som()
        assert som.ativo is False
        assert som.disponivel is False
        assert som._pygame is None
        assert som._canal is None

    def test_eventos_viram_noop_sem_pygame(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pygame", None)
        som = audio.Som()
        for _, acao, _, _ in EVENTOS_V22:
            acao(som)  # não pode levantar
        som.parar()
        assert som._cache == {}


class TestPygameFalso:
    def test_inicializacao_do_mixer_inalterada(self, pygame_falso):
        som = audio.Som()
        assert som.disponivel is True
        assert som.ativo is True
        assert pygame_falso.mixer.init_kwargs == {
            "frequency": 22050,
            "size": -16,
            "channels": 1,
            "buffer": 512,
        }
        assert pygame_falso.mixer.num_channels == 4
        assert 0 in pygame_falso.mixer.canais  # Channel(0)

    def test_tocar_ja_corta_o_anterior_e_toca(self, pygame_falso):
        som = audio.Som()
        canal = pygame_falso.mixer.canais[0]
        som.nova_pergunta()
        som.revelou()
        assert canal.paradas == 2
        assert len(canal.tocados) == 2
        assert canal.tocados[0] != canal.tocados[1]

    def test_tocar_respeita_prioridade(self, pygame_falso):
        som = audio.Som()
        canal = pygame_falso.mixer.canais[0]
        som.nova_pergunta()          # tocar_ja: canal ocupado
        assert len(canal.tocados) == 1

        som.tick(1, FASE_AGUARDANDO)  # baixa prioridade: não interrompe
        assert len(canal.tocados) == 1

        canal.stop()                  # canal livre
        som.tick(1, FASE_AGUARDANDO)
        assert len(canal.tocados) == 2

    def test_mudo_e_reativacao(self, pygame_falso):
        som = audio.Som(ativo=False)
        canal = pygame_falso.mixer.canais[0]

        som.nova_pergunta()
        assert canal.tocados == []

        # Reativação (tecla S): a UI chama exatamente este bipe
        som.ativo = True
        som.tocar_ja(("C5", 80), ("E5", 110))
        assert len(canal.tocados) == 1

    def test_apertou_a_e_b_diferentes(self, pygame_falso):
        som_a = audio.Som()
        som_a.apertou("A")
        som_b = audio.Som()
        som_b.apertou("B")
        assert som_a._cache != som_b._cache
        (dados_a,) = [s.dados for s in som_a._cache.values()]
        (dados_b,) = [s.dados for s in som_b._cache.values()]
        assert dados_a != dados_b

    def test_parar_encerra_o_mixer(self, pygame_falso):
        som = audio.Som()
        som.parar()
        assert som.disponivel is False
        assert pygame_falso.mixer.quit_chamado is True


class TestModuloPuro:
    def test_importa_sem_tkinter_serial_ou_pygame(self):
        codigo = (
            "import sys; import audio; "
            "proibidos = {'tkinter', 'serial', 'pygame'}; "
            "achados = proibidos & set(sys.modules); "
            "assert not achados, achados"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            cwd=str(RAIZ),
        )
        assert saida.returncode == 0, saida.stderr

    def test_ui_usa_a_mesma_classe(self):
        desafio = pytest.importorskip("desafio")
        assert desafio.Som is audio.Som
