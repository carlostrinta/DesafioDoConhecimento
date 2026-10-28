# Desafio do Conhecimento

Jogo de perguntas e respostas para **2 a 4 equipes**, com interface desktop
(tkinter) e botões físicos opcionais via **Arduino**. A equipe que apertar
primeiro tem a vez de responder; o tempo controla a rodada e o placar fica na
tela.

O projeto está em evolução por etapas. Esta versão (`v2.2-logica-integrada`)
já tem toda a regra de jogo isolada em `jogo.py`, testada sem interface, e a
interface apenas desenha e encaminha ações.

---

## Requisitos

| Item | Versão |
| --- | --- |
| Python | **3.12.x** (versão fixada do projeto) |
| Sistema | Windows 10/11 (testado), Linux/macOS devem funcionar |
| Arduino | opcional — o jogo roda 100% no teclado |

> **Por que 3.12?** É a versão estável de referência dos laboratórios onde o
> jogo é usado. O código também roda em 3.13/3.14/3.15, mas a suíte de testes
> é validada oficialmente em **3.12.15**. Se você usa `uv`:
> `uv python install 3.12`.

---

## Instalação

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Dependências:

- `pyserial` — comunicação com o Arduino;
- `pygame` — sons.

Sem Arduino conectado o jogo inicia normalmente em **modo teclado**. Sem
`pygame` instalado o jogo também inicia, mas sem som (aviso no log).

## Execução

```powershell
python main.py
```

O ponto de entrada é **`main.py`**. O aplicativo abre em tela cheia e, na
primeira execução, pede o tema (arquivo de perguntas). Se houver uma partida
salva, pergunta antes se você quer continuá-la (veja
[Persistência da partida](#persistência-da-partida-etapa-43)).

> `desafio.py` contém apenas a interface (a classe `DueloDeConhecimento`); ele
> **não é** um entrypoint. Rodá-lo direto imprime `Use: python main.py` e sai
> com código 1, em vez de terminar em silêncio.

Para ver o log detalhado também no console:

```powershell
python main.py --debug
```

## Logs

O jogo grava tudo em **`logs/desafio.log`**, na pasta da aplicação (ao lado do
`.exe`; rodando pelo fonte, na pasta do projeto). Se não houver permissão de
escrita ali, o arquivo vai para a pasta do script.

- Rotação automática: no máximo **1 MB por arquivo** e **3 backups**
  (`desafio.log.1` … `desafio.log.3`).
- Sem `--debug`, **nada** é impresso no console; o arquivo recebe `INFO`,
  `WARNING` e `ERROR`.
- Com `--debug`, o console mostra também `DEBUG` (portas seriais, cada evento
  recebido etc.).
- O nível pode ser trocado por `DESAFIO_LOG_NIVEL` (`DEBUG`, `INFO`, `WARNING`
  ou `ERROR`); o padrão é `INFO` (`DEBUG` com `--debug`).
- Cada **pergunta ignorada** na carga do banco é registrada com o número, o
  arquivo e o motivo; a tela mostra apenas o resumo.
- Exceções não tratadas (globais e em callbacks do Tk) vão com traceback para o
  log; o usuário vê uma mensagem curta com o caminho do arquivo.

A pasta `logs/` não é versionada (veja `.gitignore`).

## Controles de teclado

| Tecla | Ação |
| --- | --- |
| `A` | equipe A aperta o botão |
| `B` | equipe B aperta o botão |
| `R` | revela a resposta |
| `1` | ponto para a equipe A |
| `2` | ponto para a equipe B |
| `N` | próxima pergunta |
| `S` | liga/desliga o som |
| `F11` | alterna tela cheia |
| `Esc` | sai da tela cheia |
| `Ctrl+R` | reinicia o placar (com confirmação) |
| `Ctrl+T`, `Ctrl+O`, `F2` | abre o seletor de tema |

No seletor de tema: `↑`/`↓` movem a seleção, `Enter` confirma e `Esc`
cancela. Clique simples seleciona; clique duplo escolhe o tema.

## Perguntas e temas

Os bancos de perguntas são arquivos JSON na pasta do jogo. O formato aceito é
uma **lista** de perguntas ou um **objeto** com a chave `perguntas`:

```json
[
  {
    "pergunta": "Qual é a capital do Brasil?",
    "alternativas": ["Rio de Janeiro", "Brasília", "São Paulo"],
    "correta": 1,
    "categoria": "Geografia",
    "explicacao": "Brasília é a capital desde 1960."
  }
]
```

Regras de validação (aplicadas por `perguntas.ler_banco_perguntas`, o
carregador único do projeto):

- `pergunta` (ou `texto`) obrigatório e não vazio;
- `alternativas`: lista de **2 a 4** itens, todos não vazios;
- `correta`: índice inteiro válido dentro de `alternativas`;
- campo `tema`/`titulo` no objeto define o nome do tema (opcional).

Perguntas inválidas são **ignoradas** e o motivo (arquivo, número e causa) vai
para o log; a interface mostra um aviso como `1 pergunta ignorada em tema.json.`
e continua carregando as demais.

Bancos incluídos: `conhecimentos_gerais.json` (97 perguntas),
`eletrotecnica.json` (20) e `radiologia.json` (20).

> ⚠️ **Cuidado com os temas curtos.** `eletrotecnica.json` e
> `radiologia.json` têm apenas **20 perguntas** cada. O baralho é embaralhado
> a cada carga e, quando acaba, **recomeça do início** — numa partida longa as
> mesmas perguntas voltam cedo. **Pendência da Etapa 4:** ampliar esses bancos
> e/ou avisar na tela quando o tema escolhido for curto para o número de
> equipes/alvo de pontos.

## Configuração — `config.json` (Etapa 4.2)

O jogo lê **`config.json`** ao lado do executável (rodando pelo fonte, na pasta
do projeto). Se não existir ali, procura na pasta do script; se também não
houver, usa os padrões históricos — o comportamento fica **idêntico** ao da
versão anterior. O jogo **nunca falha** por causa da configuração.

Para começar, copie o modelo:

```powershell
Copy-Item config.exemplo.json config.json
```

> Opcional: `python -c "import config; config.criar_config_exemplo()"` cria o
> `config.json` a partir do exemplo (não sobrescreve um arquivo existente).

| Chave | Tipo | Padrão | Regra |
| --- | --- | --- | --- |
| `tempos.tempo_pergunta` | inteiro (s) | `30` | `> 0` |
| `tempos.tempo_resposta` | inteiro (s) | `15` | `> 0` |
| `jogo.num_equipes` | inteiro | `2` | `2` a `4`; `3`/`4` avisam e a UI usa `2` até a Etapa 5 |
| `jogo.pontuar_apos_tempo` | booleano | `false` | `true`/`false` |
| `nomes_equipes.A` … `.D` | texto | `Competidor A` … `D` | 1 a 24 caracteres, não vazio |
| `serial.porta` | texto | `"auto"` | `auto`, `COMx` ou `VID:PID` (ex.: `1A86:7523`) |
| `serial.baud_rate` | inteiro | `9600` | `1200` a `115200` |
| `serial.timeout_pronto` | número (s) | `3.0` | `0.1` a `30` |
| `perguntas.pasta` | texto | `"."` | relativa à pasta da aplicação ou absoluta; se não existir, volta para a pasta da aplicação |
| `perguntas.arquivo_padrao` | texto | `conhecimentos_gerais.json` | nome de arquivo `.json`, sem pasta |
| `audio.ativo` | booleano | `true` | `true`/`false` (estado inicial do som) |
| `persistencia.continuar_automatico` | booleano | `false` | `true` retoma a partida salva sem o modal de confirmação |

O que acontece com arquivo problemático:

- **Chave desconhecida** → `WARNING` no log e a chave é ignorada (sem aviso na
  tela).
- **Valor inválido** (tipo ou faixa) → volta ao padrão, com `WARNING` no log e
  um aviso único na tela ao abrir o jogo.
- **JSON corrompido/vazio** ou raiz que não é objeto → padrões + aviso na tela;
  o app continua abrindo.
- **Arquivo ausente** → padrões, sem erro.
- **`perguntas.pasta` inexistente ou sem permissão** → `WARNING` no log, aviso
  na tela e uso da pasta da aplicação.
- **`perguntas.arquivo_padrao` inexistente** → `WARNING` no log; o seletor de
  temas abre normalmente, sem tela vazia.
- `config.json` é local e **não** é versionado (veja `.gitignore`); o modelo
  versionado é `config.exemplo.json`.

## Persistência da partida (Etapa 4.3)

O jogo grava **`estado_partida.json`** ao lado do executável (rodando pelo
fonte, na pasta do projeto). Se essa pasta não for gravável, usa a pasta do
script. A gravação é atômica: escreve `estado_partida.json.tmp` e troca com
`os.replace`; uma falha de disco/permissão não derruba o app (fica um
`WARNING` no log).

São salvos: versão do formato, tema e arquivo de perguntas, placar por equipe,
nomes, índice/rodada e a ordem do baralho. O estado é atualizado após
pontuação, nova pergunta, troca de tema e ao zerar o placar, com debounce de
0,5 s. Fechar normalmente também grava o que estiver pendente.

Ao abrir:

- com estado válido, aparece o modal **“Continuar partida salva?”** com o
  tema, o placar e a rodada, e os botões **Continuar** / **Nova partida**;
- com `persistencia.continuar_automatico: true`, a partida é retomada sem o
  modal;
- **Nova partida** apaga o estado salvo e abre o seletor de temas;
- estado ausente, vazio, corrompido, com versão desconhecida, tema removido ou
  quantidade de perguntas diferente → `WARNING` no log, aviso na tela e
  partida nova (o app nunca quebra).

A pergunta atual volta em **AGUARDANDO com o tempo cheio**. Fase intermediária
e tempo restante **não** são restaurados de propósito.

## Testes

```powershell
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

A suíte cobre a máquina de estados, o placar, o carregador de perguntas, o
timer (com relógio injetável — nenhum teste usa `sleep`) e o protocolo serial
em modo headless. Nenhum teste exige Arduino. Abrem uma janela Tk de verdade
apenas dois testes, e ambos são pulados em ambiente headless:

- o **golden visual** dos componentes (Etapa 3.5), **opt-in** porque as
  métricas de fonte variam entre PCs — guarda local de refatoração, não de CI:

```powershell
$env:DESAFIO_GOLDEN_UI=1
python -m pytest tests/test_ui_componentes.py -q
```

- o teste de **regressão do entrypoint**, que executa `python main.py` como
  subprocesso com `DESAFIO_AUTO_FECHAR=1` (a janela se fecha após 1 s) e exige
  código de saída 0.

O teste de `desafio.py` é headless: apenas confere o aviso e o código 1. O
logging (rotação, níveis, fallback e captura de exceções) é testado em
`tests/test_logging.py`, também sem abrir janela. A configuração (leitura,
validação, fallback e caso do `.exe` congelado) fica em `tests/test_config.py`.
A persistência (ida e volta, gravação atômica, falha de disco/permissão,
estado inválido e debounce) fica em `tests/test_persistencia.py` e
`tests/test_jogo_persistencia.py`; nenhum desses testes abre janela.

## Estrutura do projeto

| Arquivo | Papel |
| --- | --- |
| `main.py` | ponto de entrada: logging, monta a janela e inicia o loop do Tk |
| `logging_conf.py` | log rotativo em `logs/`, níveis e captura de exceções |
| `desafio.py` | interface tkinter: telas, teclado e ligação com o jogo |
| `ui_componentes.py` | componentes Canvas: paleta, tipografia e widgets visuais (sem lógica de jogo) |
| `ui_selecao.py` | modal de escolha do banco de perguntas (widgets Tk clássicos) |
| `serial_comm.py` | thread serial, detecção de porta, reconexão e fila de eventos |
| `audio.py` | efeitos sonoros sintetizados (pygame opcional; sem ele fica mudo) |
| `jogo.py` | regra de jogo pura: estado, placar e timer |
| `perguntas.py` | modelo, carregador/validador, listagem e nomes de tema (puro) |
| `persistencia.py` | estado da partida em JSON, gravação atômica e debounce (puro) |
| `recursos.py` | pasta da aplicação (código-fonte ou `.exe`) — puro |
| `protocolo.py` | tradução pura entre linhas da serial e ações/eventos |
| `config.py` | lê e valida `config.json`; expõe os valores em uso e os avisos |
| `tests/` | suíte pytest |
| `duelo_arduino.ino/` | firmware do Arduino (protocolo v1) |
| `config.exemplo.json` | modelo versionado da configuração (copie para `config.json`) |
| `Desafio do Conhecimento.spec` | receita de build com PyInstaller |
| `ROTEIRO_SERIAL_HARDWARE.md` | checklist de validação com Arduino real |

## Protocolo serial (v1)

Arduino → PC (uma linha por evento, 9600 baud):

| Linha | Efeito |
| --- | --- |
| `BTN_A` / `BTN_B` | equipe A/B aperta |
| `BTN_AVANCAR` | próxima pergunta |
| `BTN_REVELAR` | revela a resposta |
| `BTN_ACERTO_A` / `BTN_ACERTO_B` | ponto para A/B |
| `PRONTO` | Arduino reiniciou e está pronto |

PC → Arduino:

| Comando | Efeito |
| --- | --- |
| `LED_A_ON` / `LED_A_OFF` | LED da equipe A |
| `LED_B_ON` / `LED_B_OFF` | LED da equipe B |
| `BEEP` | bipe curto |
| `BEEP_LONG` | bipe longo (ponto confirmado) |
| `BUZZER_ON` / `BUZZER_OFF` | buzzer contínuo |
| `RESET` | apaga LEDs e reinicia a rodada no Arduino |

O protocolo **não muda** sem aprovação: a tabela acima é a referência
congelada da v1. A versão 2 (4 equipes, `VERSAO 2`) será definida na Etapa 5.

**Como o app escolhe a porta (3.4-B):** só entram na varredura portas com
VID/PID de Arduino (2341, 2A03) ou de adaptador USB-serial conhecido (CH340/
CH341, CP210x, FTDI, PL2303 e compatíveis) ou, sem VID/PID, com descrição de
Arduino/CH340. Portas Bluetooth/virtuais (VID/PID `None`) ficam de fora. A
porta só é considerada conectada depois de receber `PRONTO` dentro de
`serial.timeout_pronto` (padrão 3 s); enquanto isso não acontece, o app fecha a
porta e varre de novo a cada 3 s. `serial.porta` (config.json) pode ser `auto`,
`COMx` ou `VID:PID` (ex.: `1A86:7523`); a porta indicada é tentada primeiro,
mas também precisa do `PRONTO`.

## Gerar o executável

```powershell
pyinstaller "Desafio do Conhecimento.spec"
```

O `.exe` sai em `dist/`. Ele **não** é versionado (veja `.gitignore`); os
arquivos JSON de perguntas e, se usado, o `config.json` precisam ficar ao lado
do executável. Na primeira execução, a pasta `logs/` é criada ali mesmo (ou na
pasta do script, se o local não permitir escrita).

Nada é empacotado dentro do `.exe` (`datas=[]` no `.spec`): os recursos são
procurados na **pasta da aplicação** — a pasta do `.exe` quando congelado, ou a
pasta do projeto rodando pelo fonte. Por isso os bancos de perguntas (e, no
futuro, a pasta `sons/`) ficam sempre ao lado do executável. A chave
`perguntas.pasta` permite manter os bancos numa subpasta, sem recompilar; se a
pasta não existir, o app usa a pasta do executável.

## Roadmap (próximas etapas)

Ordem combinada: **3.6**, **3.7**, **4.x** (com a **4.6 antes da Etapa 5**) e
depois a **Etapa 5**.

### Etapa 4.6 — Contagem de largada (não implementada)

- Nova fase `CONTAGEM` no `Jogo`, antes de `AGUARDANDO`, com relógio
  injetável e duração configurável (padrão 3 s; `0` desativa).
- Overlay com números grandes (3, 2, 1, JÁ!), desenhado em
  `ui_componentes.py`.
- Botões das equipes ignorados durante a contagem; descartar eventos de
  botão acumulados na fila serial ao entrar em `AGUARDANDO`.
- O tempo de 30 s só começa no "JÁ!"; pergunta oculta ou desfocada durante a
  contagem (configurável).
- Sons: tick por número e som distinto para o "JÁ!" (junto da 4.5).
- Vale também para a primeira pergunta e para a partida restaurada.
- Sem mudança de firmware nem de protocolo serial.

### Melhorias futuras (sem etapa definida)

- **Renomear `desafio.py`** para um nome que reflita seu papel (ex.:
  `ui_jogo.py`): hoje o arquivo contém a classe `DueloDeConhecimento` e toda a
  interface, mas o nome sugere um ponto de entrada. A troca precisa acompanhar
  imports, `.spec` de build e testes.

## Limitações conhecidas (em evolução)

- A interface ainda mostra **2 equipes**; a lógica já suporta 2, 3 ou 4. Se
  `jogo.num_equipes` for 3 ou 4, o app avisa e continua com 2 até a Etapa 5.
- `config.json` ainda não cobre cores, modo de jogo nem alvo de pontos.
- `eletrotecnica.json` e `radiologia.json` têm só 20 perguntas: o baralho
  reinicia rápido (pendência da Etapa 4).
- A partida salva retoma a pergunta atual em `AGUARDANDO`; fase e tempo
  restante não são restaurados.
- O firmware usa `delay()` no bipe e será revisado junto com o protocolo v2.
- **Pendência de hardware:** validar com clone **CH340**; se o `PRONTO`
  demorar mais de 3 s após o reset por DTR, aumentar
  `serial.timeout_pronto` no `config.json` (padrão 3 s).
- A validação com hardware real usou uma **Mega 2560** (VID `2341:0042`).
  A Etapa 5 deve validar o mapeamento de pinos do firmware em uma **Uno** e
  documentar a diferença Mega × Uno.
