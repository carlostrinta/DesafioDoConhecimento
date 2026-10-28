"""
Testes de `audio.py` (Etapas 3.3 e 4.5).

Provas principais:

1. Os bytes WAV dos efeitos sintetizados são **idênticos** aos da v2.2
   (sha256 fixado abaixo). O pacote externo em `sons/` não altera esse
   fallback.
2. Cada evento procura o arquivo correspondente em `sons/`, aceita WAV/OGG e
   cai no som sintetizado com WARNING único se o arquivo faltar ou estiver
   corrompido.
3. O áudio é opcional: sem pygame, `Som` fica inativo e nada levanta exceção.

Nada aqui toca a placa de som de verdade.
"""

import hashlib
import logging
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
        self.arquivo = None
        self.volume = 1.0
        if hasattr(file, "read"):
            self.dados = file.read()
        elif file is not None:
            self.arquivo = str(file)
            self.dados = Path(self.arquivo).read_bytes()
            if self.dados.startswith(b"CORROMPIDO"):
                raise ValueError("formato de áudio inválido")
        else:
            self.dados = b""

    def set_volume(self, valor):
        self.volume = valor

    def get_length(self):
        if self.dados == b"LONGO":
            return 6.0
        return 0.5


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
        self.pre_init_kwargs = None
        self.init_kwargs = None
        self.num_channels = None
        self.canais = {}
        self.sons = []
        self.quit_chamado = False

    def pre_init(self, **kw):
        self.pre_init_kwargs = kw

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


@pytest.fixture
def pasta_sons(tmp_path):
    pasta = tmp_path / audio.PASTA_SONS
    pasta.mkdir()
    return pasta


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
        """O volume usado em `_gerar_wav` é parte da identidade sonora."""
        capturado = {}
        original = audio._gerar_wav

        def espiao(notas, taxa=22050, volume=0.55):
            capturado["volume"] = volume
            capturado["taxa"] = taxa
            return original(notas, taxa=taxa, volume=volume)

        monkeypatch.setattr(audio, "_gerar_wav", espiao)
        audio.Som().nova_pergunta()

        assert capturado == {"volume": 0.42, "taxa": 22050}


# ─────────────────────────────────────────────────────────
# 2. Pacote de sons externo
# ─────────────────────────────────────────────────────────
class TestPacoteDeSons:
    def test_tabela_cobre_todos_os_eventos(self):
        assert audio.ARQUIVOS_SOM == {
            "nova_pergunta": "nova_pergunta",
            "botao_a": "botao_a",
            "botao_b": "botao_b",
            "botao_c": "botao_c",
            "botao_d": "botao_d",
            "revelou": "revelar",
            "acertou": "acerto",
            "tempo_esgotado": "tempo_esgotado",
            "tick": "tick",
            "tick_final": "tick_final",
            "vitoria": "vitoria",
            "troca_tema": "troca_tema",
        }

    def test_arquivo_wav_tem_preferencia_e_substitui_o_sintetizado(
        self, pygame_falso, pasta_sons
    ):
        (pasta_sons / "nova_pergunta.wav").write_bytes(b"externo-wav")
        (pasta_sons / "nova_pergunta.ogg").write_bytes(b"externo-ogg")

        som = audio.Som(diretorio_sons=str(pasta_sons))
        som.nova_pergunta()

        externo = som._cache_arquivos["nova_pergunta"]
        assert externo.arquivo.endswith("nova_pergunta.wav")
        assert externo.dados == b"externo-wav"
        assert som._cache == {}

    def test_ogg_e_aceito_quando_nao_ha_wav(
        self, pygame_falso, pasta_sons
    ):
        (pasta_sons / "botao_c.ogg").write_bytes(b"externo-ogg")

        som = audio.Som(diretorio_sons=str(pasta_sons))
        som.apertou("C")

        externo = som._cache_arquivos["botao_c"]
        assert externo.arquivo.endswith("botao_c.ogg")

    def test_arquivo_ausente_cai_no_sintetizado_com_um_warning(
        self, pygame_falso, pasta_sons, caplog
    ):
        som = audio.Som(diretorio_sons=str(pasta_sons))

        with caplog.at_level(logging.WARNING, logger="desafio.audio"):
            som.nova_pergunta()
            som.nova_pergunta()

        assert list(som._cache) == [(("E5", 90), ("G5", 90), ("C6", 140))]
        avisos = [
            registro.getMessage()
            for registro in caplog.records
            if "não encontrado" in registro.getMessage()
        ]
        assert len(avisos) == 1

    def test_arquivo_corrompido_nao_derruba_e_usa_fallback(
        self, pygame_falso, pasta_sons, caplog
    ):
        (pasta_sons / "nova_pergunta.wav").write_bytes(b"CORROMPIDO")

        with caplog.at_level(logging.WARNING, logger="desafio.audio"):
            som = audio.Som(diretorio_sons=str(pasta_sons))
            som.nova_pergunta()
            som.nova_pergunta()

        assert som._cache_arquivos["nova_pergunta"] is None
        assert list(som._cache) == [(("E5", 90), ("G5", 90), ("C6", 140))]
        avisos = [
            registro.getMessage()
            for registro in caplog.records
            if "inválido/corrompido" in registro.getMessage()
        ]
        assert len(avisos) == 1

    def test_arquivos_existentes_sao_precarregados_uma_vez(
        self, pygame_falso, pasta_sons
    ):
        (pasta_sons / "nova_pergunta.wav").write_bytes(b"externo")
        (pasta_sons / "botao_a.wav").write_bytes(b"externo")

        som = audio.Som(diretorio_sons=str(pasta_sons))

        assert set(som._cache_arquivos) == {"nova_pergunta", "botao_a"}
        assert all(som._cache_arquivos[nome] is not None for nome in som._cache_arquivos)
        assert len(pygame_falso.mixer.sons) == 2

        for _ in range(3):
            som.nova_pergunta()
            som.apertou("A")

        assert len(pygame_falso.mixer.sons) == 2, "o disco/Sound não pode ser relido"

    def test_arquivo_acima_de_cinco_megabytes_usa_fallback(
        self, pygame_falso, pasta_sons, caplog, monkeypatch
    ):
        (pasta_sons / "nova_pergunta.wav").write_bytes(b"externo")
        monkeypatch.setattr(
            audio.os.path,
            "getsize",
            lambda _caminho: audio.LIMITE_ARQUIVO_BYTES + 1,
        )

        with caplog.at_level(logging.WARNING, logger="desafio.audio"):
            som = audio.Som(diretorio_sons=str(pasta_sons))
            som.nova_pergunta()

        assert som._cache_arquivos["nova_pergunta"] is None
        assert all(som_fake.arquivo is None for som_fake in pygame_falso.mixer.sons)
        assert any("limite" in r.getMessage() and "MB" in r.getMessage()
                   for r in caplog.records)

    def test_arquivo_acima_de_cinco_segundos_usa_fallback(
        self, pygame_falso, pasta_sons, caplog
    ):
        (pasta_sons / "nova_pergunta.wav").write_bytes(b"LONGO")

        with caplog.at_level(logging.WARNING, logger="desafio.audio"):
            som = audio.Som(diretorio_sons=str(pasta_sons))
            som.nova_pergunta()

        assert som._cache_arquivos["nova_pergunta"] is None
        assert pygame_falso.mixer.sons[0].dados == b"LONGO"
        assert any("limite" in r.getMessage() and " s" in r.getMessage()
                   for r in caplog.records)

    def test_volume_configuravel_chega_aos_sons_externos_e_sintetizados(
        self, pygame_falso, pasta_sons
    ):
        (pasta_sons / "nova_pergunta.wav").write_bytes(b"externo")
        (pasta_sons / "troca_tema.wav").write_bytes(b"externo")

        externo = audio.Som(diretorio_sons=str(pasta_sons), volume=0.25)
        externo.nova_pergunta()
        assert externo.volume == 0.25
        assert externo._cache_arquivos["nova_pergunta"].volume == 0.25

        sintetizado = audio.Som(diretorio_sons=str(pasta_sons), volume=0.5)
        sintetizado.vitoria()
        som = next(iter(sintetizado._cache.values()))
        assert som.volume == 0.5

    def test_eventos_de_botao_a_a_d_sao_distintos(
        self, pygame_falso, pasta_sons
    ):
        dados = []
        for equipe in ("A", "B", "C", "D"):
            som = audio.Som(diretorio_sons=str(pasta_sons))
            som.apertou(equipe)
            (som_sintetizado,) = som._cache.values()
            dados.append(som_sintetizado.dados)

        assert len(set(dados)) == 4

    def test_vitoria_e_troca_de_tema_tem_mapeamento(
        self, pygame_falso, pasta_sons
    ):
        for nome in ("vitoria.wav", "troca_tema.wav"):
            (pasta_sons / nome).write_bytes(b"externo")

        som = audio.Som(diretorio_sons=str(pasta_sons))
        som.vitoria()
        som.fim_partida()
        som.troca_tema()

        assert som._cache_arquivos["vitoria"] is not None
        assert som._cache_arquivos["troca_tema"] is not None

    def test_volume_invalido_direto_vira_um(self, pygame_falso, pasta_sons):
        assert audio.Som(diretorio_sons=str(pasta_sons), volume="x").volume == 1.0
        assert audio.Som(diretorio_sons=str(pasta_sons), volume=-2).volume == 0.0
        assert audio.Som(diretorio_sons=str(pasta_sons), volume=3).volume == 1.0

    def test_pasta_sons_padrao_fica_ao_lado_da_aplicacao(
        self, pygame_falso, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            audio, "obter_diretorio_base", lambda: str(tmp_path)
        )
        som = audio.Som()
        assert som._pasta_sons == str(tmp_path / audio.PASTA_SONS)


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
        som.vitoria()
        som.troca_tema()
        som.parar()
        assert som._cache == {}


class TestPygameFalso:
    def test_inicializacao_do_mixer_usa_buffer_padrao_512(
        self, pygame_falso
    ):
        som = audio.Som()
        assert som.disponivel is True
        assert som.ativo is True
        assert som.buffer == 512
        assert pygame_falso.mixer.pre_init_kwargs == {
            "frequency": 22050,
            "size": -16,
            "channels": 1,
            "buffer": 512,
        }
        assert pygame_falso.mixer.init_kwargs == {}
        assert pygame_falso.mixer.num_channels == 4
        assert 0 in pygame_falso.mixer.canais  # Channel(0)

    @pytest.mark.parametrize("valor", [128, 1024, 2048])
    def test_buffer_configuravel_chega_ao_pre_init(self, pygame_falso, valor):
        som = audio.Som(buffer=valor)

        assert som.buffer == valor
        assert pygame_falso.mixer.pre_init_kwargs["buffer"] == valor

    @pytest.mark.parametrize("valor", [127, 2049, "512", True, None])
    def test_buffer_invalido_direto_volta_ao_padrao(self, pygame_falso, valor):
        som = audio.Som(buffer=valor)

        assert som.buffer == 512
        assert pygame_falso.mixer.pre_init_kwargs["buffer"] == 512

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
