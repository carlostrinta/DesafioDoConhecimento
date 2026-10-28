# Pacote de sons — Desafio do Conhecimento

Esta pasta fica **ao lado do executável** (ou na pasta do projeto, rodando pelo
código-fonte). O jogo **não inclui áudio por padrão**: se um arquivo não
existir, ele usa o efeito sintetizado equivalente e registra um único
`WARNING` no log. O jogo continua normalmente.

## Como usar

1. Coloque os arquivos nesta pasta com os nomes exatos da tabela abaixo.
2. Use **WAV PCM 16 bits** ou **OGG Vorbis**; se os dois existirem, o WAV tem
   preferência.
3. Reinicie o jogo depois de trocar/adicionar arquivos: os arquivos existentes
   são carregados **uma vez na abertura** e ficam em memória.
4. O volume geral vem de `audio.volume` no `config.json` (`0.0` a `1.0`).
5. Cada arquivo pode ter no máximo **5 segundos** e **5 MB**. Acima disso, o
   jogo registra um `WARNING` e usa o som sintetizado.

Formatos recomendados:

- WAV: mono, 22.050 Hz ou 44.100 Hz, PCM 16 bits, sem clipping.
- OGG: mono, taxa de bits moderada (ex.: 96–128 kbps).
- Botões A–D: **menos de 1 segundo**.
- Evite silêncio no começo: o som é disparado no instante do evento.
- Normalize os picos perto de -6 dBFS; o volume final é ajustado pelo jogo.

## Arquivos esperados

| Evento | Arquivo (sem extensão fixa) | Duração sugerida | Observações |
| --- | --- | --- | --- |
| Nova pergunta | `nova_pergunta.wav` ou `.ogg` | 0,3–0,8 s | Sinal curto de “próxima pergunta”. |
| Botão da equipe A | `botao_a.wav` ou `.ogg` | < 1 s | Timbres diferentes para A, B, C e D. |
| Botão da equipe B | `botao_b.wav` ou `.ogg` | < 1 s |  |
| Botão da equipe C | `botao_c.wav` ou `.ogg` | < 1 s |  |
| Botão da equipe D | `botao_d.wav` ou `.ogg` | < 1 s |  |
| Revelar resposta | `revelar.wav` ou `.ogg` | 0,3–1 s |  |
| Acerto | `acerto.wav` ou `.ogg` | 0,5–1,2 s |  |
| Tempo esgotado | `tempo_esgotado.wav` ou `.ogg` | 0,5–1,5 s |  |
| Tick normal | `tick.wav` ou `.ogg` | 30–80 ms | Deve ser discreto e não competir com a fala. |
| Tick final | `tick_final.wav` ou `.ogg` | 40–100 ms | Últimos 3 segundos; mais urgente que o tick normal. |
| Vitória / fim de partida | `vitoria.wav` ou `.ogg` | 1–3 s | Também usado por `fim_partida()`. |
| Troca de tema | `troca_tema.wav` ou `.ogg` | 0,3–1 s | Tocado ao carregar um tema. |

> **Vitória/fim de partida só dispara na Etapa 5.** A tela de campeão e o
> fluxo de fim de partida ainda não existem; o arquivo `vitoria` já fica
> mapeado para quando essa tela chamar `Som.vitoria()` ou
> `Som.fim_partida()`.

## Onde conseguir sons livres

Sugestões de bancos com licenças permissivas (confira a licença de **cada**
arquivo antes de usar):

- [Kenney — Audio](https://kenney.nl/assets?q=audio) — CC0.
- [OpenGameArt](https://opengameart.org/) — procure a licença CC0 no item.
- [Freesound](https://freesound.org/) — use o filtro de licença CC0.
- [Pixabay — Sound Effects](https://pixabay.com/sound-effects/) — licença
  Pixabay; leia os termos.
- [Mixkit — Free Sound Effects](https://mixkit.co/free-sound-effects/) —
  licença Mixkit; leia os termos.
- [Bfxr](https://www.bfxr.net/) / [jsfxr](https://sfxr.me/) — geradores de
  efeitos 8-bit; os sons gerados são seus, mas confira os termos da ferramenta.

Evite material sem licença clara, músicas comerciais e sons copiados de jogos.

## Licenças dos arquivos adicionados

Registre autor, fonte, licença e data em [`LICENCAS.md`](LICENCAS.md). Sem esse
registro, a distribuição do `.exe` fica com a licença do áudio indefinida.
