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
`pygame` instalado o jogo também inicia, mas sem som (aviso no log). Os sons
personalizados são opcionais: a pasta `sons/` pode estar vazia (veja
[Pacote de sons](#pacote-de-sons-etapa-45)).

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

Durante a **contagem de largada**, `A`/`B` são ignorados e `R`, `1`/`2` e `N`
mostram um aviso para aguardar o `JÁ!` (veja
[Contagem de largada](#contagem-de-largada-etapa-46)).

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
| `jogo.contagem_largada` | inteiro (s) | `3` | `0` a `10`; `0` desativa a contagem |
| `jogo.mostrar_pergunta_na_contagem` | booleano | `false` | `true` exibe a pergunta e as alternativas durante a contagem |
| `nomes_equipes.A` … `.D` | texto | `Competidor A` … `D` | 1 a 24 caracteres, não vazio |
| `serial.porta` | texto | `"auto"` | `auto`, `COMx` ou `VID:PID` (ex.: `1A86:7523`) |
| `serial.baud_rate` | inteiro | `9600` | `1200` a `115200` |
| `serial.timeout_pronto` | número (s) | `3.0` | `0.1` a `30` |
| `perguntas.pasta` | texto | `"."` | relativa à pasta da aplicação ou absoluta; se não existir, volta para a pasta da aplicação |
| `perguntas.arquivo_padrao` | texto | `conhecimentos_gerais.json` | nome de arquivo `.json`, sem pasta |
| `audio.ativo` | booleano | `true` | `true`/`false` (estado inicial do som) |
| `audio.volume` | número | `1.0` | `0.0` a `1.0`; aplica-se aos sons externos e sintetizados (`0.0` mudo) |
| `audio.buffer` | inteiro | `512` | `128` a `2048` amostras; buffer do mixer (menor = menos latência) |
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

## Contagem de largada (Etapa 4.6)

Cada pergunta nova entra na fase **CONTAGEM** antes de ficar valendo — inclusive
a primeira depois da escolha do tema e a pergunta retomada de uma partida salva.
A tela mostra **3, 2, 1, JÁ!** em um overlay central grande, que escala com a
janela e fica dentro do palco: os cartões de placar das equipes continuam
visíveis. O relógio de **30 s para apertar** só começa no **JÁ!**; durante a
contagem, a barra de tempo acompanha a contagem regressiva e o rodapé avisa para
aguardar.

- `jogo.contagem_largada` define a duração em segundos (padrão `3`, faixa de
  `0` a `10`). Com **`0`**, a contagem é desativada e a pergunta já entra
  valendo, como nas versões anteriores.
- Por padrão, a pergunta e as alternativas ficam **ocultas** durante a
  contagem. Com `jogo.mostrar_pergunta_na_contagem: true`, elas aparecem desde
  o início.
- As teclas **A**/**B** e os eventos `BTN_A`/`BTN_B` da serial são **ignorados**
  durante a contagem. **R**, **1**/**2** e **N** são recusados com o aviso
  `Aguarde o JÁ! da contagem de largada.`
- Ao entrar em **AGUARDANDO**, os eventos de botão de equipe que ainda
  estivessem na fila serial são descartados: um aperto durante a contagem não
  ganha a rodada. Os demais eventos da fila são preservados.
- Sons: `contagem` toca um tick a cada número e `largada` toca no **JÁ!**; os
  dois têm fallbacks sintetizados distintos (veja
  [Pacote de sons](#pacote-de-sons-etapa-45)).
- Sem mudança de firmware nem de protocolo serial.

## Persistência da partida (Etapa 4.3)

O jogo grava **`estado_partida.json`** ao lado do executável (rodando pelo
fonte, na pasta do projeto). Se essa pasta não for gravável, usa a pasta do
script. A gravação é atômica: escreve um arquivo `*.tmp` e troca com
`os.replace`; uma falha de disco/permissão não derruba o app (fica um
`WARNING` no log). `estado_partida.json`, `*.tmp` e `estado_partida.lock`
estão no `.gitignore`.

São salvos: versão do formato, tema e arquivo de perguntas, placar por equipe,
nomes, índice/rodada, a ordem do baralho e o **hash SHA-256 do banco de
perguntas**. A pontuação é gravada **imediatamente** (sem debounce, para não
perder o ponto se o app fechar em seguida). Nova pergunta, troca de tema e
zerar o placar usam debounce de **0,5 s**; fechar pelo X, pelo Esc dos modais
ou pelo seletor inicial também faz o flush do que estiver pendente.

O hash detecta alteração no conteúdo do banco mesmo quando a quantidade de
perguntas continua igual. O formato atual é a **versão 2**; estados da versão
1 (sem hash) ou de versão desconhecida são recusados e geram partida nova,
com `WARNING` no log.

O app usa `estado_partida.lock` para detectar duas instâncias na mesma pasta.
A segunda instância **não é bloqueada** (requisito da Etapa 4.3), mas registra
um `WARNING` avisando que as duas podem sobrescrever o estado. Travas órfãs de
processos mortos são recuperadas na abertura seguinte. O caminho normal de
fechamento (X, Esc nos modais e modal inicial) chama `fechar()` e **remove** o
`estado_partida.lock`; o teste `tests/test_fechamento.py` usa uma trava real em
`tmp_path` para provar isso.

**Limitação conhecida (PID reaproveitado):** a trava guarda o PID do processo e
considera o dono "vivo" enquanto esse PID existir. O Windows pode reutilizar o
PID de um processo que morreu; nesse caso, uma abertura seguinte pode ver a
trava como ativa e emitir um `WARNING` falso, sem bloquear o app. A trava é
cooperativa e serve para avisar, não para garantir exclusão mútua. Se o aviso
aparecer sem outra instância aberta, feche o app, apague
`estado_partida.lock` e abra de novo.

Ao abrir:

- com estado válido, aparece o modal **“Continuar partida salva?”** com o
  tema, o placar e a rodada, e os botões **Continuar** / **Nova partida**;
- com `persistencia.continuar_automatico: true`, a partida é retomada sem o
  modal;
- **Nova partida** apaga o estado salvo e abre o seletor de temas;
- fechar o modal de continuar pelo X ou pelo Esc **não apaga nem sobrescreve**
  a partida salva: o app apenas encerra;
- estado ausente, vazio, corrompido, com versão desconhecida, tema removido,
  quantidade de perguntas diferente ou hash diferente → `WARNING` no log,
  aviso na tela e partida nova (o app nunca quebra).

A pergunta atual volta em **CONTAGEM** (ou em **AGUARDANDO** com o tempo cheio,
se `jogo.contagem_largada` for `0`). Fase intermediária e tempo restante **não**
são restaurados de propósito; a contagem recomeça com a configuração atual.

## Testes

```powershell
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

A suíte cobre a máquina de estados, o placar, o carregador de perguntas, o
timer e a contagem de largada (com relógio injetável — nenhum teste usa
`sleep`) e o protocolo serial em modo headless. Nenhum teste exige Arduino.
Abrem uma janela Tk de verdade os testes visuais e de entrypoint abaixo; todos
são pulados em ambiente headless:

- o **golden visual** dos componentes (Etapa 3.5), **opt-in** porque as
  métricas de fonte variam entre PCs — guarda local de refatoração, não de CI:

```powershell
$env:DESAFIO_GOLDEN_UI=1
python -m pytest tests/test_ui_componentes.py -q
```

> **Regra de divergência do golden:** uma diferença só é aceita depois de
> identificar o commit de origem por bisseção (`git bisect` ou execução do
> golden em worktrees dos candidatos). Nunca classifique a diferença como
> “deriva de ambiente” sem essa prova. Identificado o commit, corrija o código
> ou o teste; regravar o golden é um commit separado, com a justificativa e
> apenas os casos afetados.

- o teste de **regressão do entrypoint**, que executa `python main.py` como
  subprocesso com `DESAFIO_AUTO_FECHAR=1` (a janela se fecha após 1 s) e exige
  código de saída 0;
- o **smoke da contagem de largada**, que usa `DESAFIO_AUTO_INICIAR=1` para
  pular o seletor, iniciar o banco padrão e só fechar depois de chegar em
  `AGUARDANDO` — assim o overlay é desenhado no caminho real do entrypoint;
- os testes de `tests/test_contagem_ui.py`, que montam a interface de verdade
  e percorrem o modal de tema → primeira pergunta → contagem → `AGUARDANDO`
  para `contagem_largada` `0`, `1`, `3` e `10`, com a pergunta visível ou não
  e com redimensionamento no meio da contagem.

O teste de `desafio.py` é headless: apenas confere o aviso e o código 1. O
logging (rotação, níveis, fallback e captura de exceções) é testado em
`tests/test_logging.py`, também sem abrir janela. A configuração (leitura,
validação, fallback e caso do `.exe` congelado) fica em `tests/test_config.py`.
A persistência (ida e volta, gravação atômica, falha de disco/permissão,
estado inválido, hash, trava de instância e debounce), o fechamento dos modais
e a lista de VID/PID ficam em `tests/test_persistencia.py`,
`tests/test_jogo_persistencia.py`, `tests/test_fechamento.py` e
`tests/test_dispositivos.py`; nenhum desses testes abre janela. A seleção de
porta e a fila de placa são testadas com portas falsas em
`tests/test_serial_comm.py`. A contagem de largada tem dois níveis:
`tests/test_contagem.py` cobre a regra (sequência 3-2-1-JÁ!, desativação com
`0`, duração inválida, recusas de `R`/`1`/`2`/`N`, descarte da fila serial e
restauração) com relógio falso; `tests/test_contagem_ui.py` cobre o caminho
visual em Tk real.

## Estrutura do projeto

| Arquivo | Papel |
| --- | --- |
| `main.py` | ponto de entrada: logging, monta a janela e inicia o loop do Tk |
| `logging_conf.py` | log rotativo em `logs/`, níveis e captura de exceções |
| `desafio.py` | interface tkinter: telas, teclado e ligação com o jogo |
| `ui_componentes.py` | componentes Canvas: paleta, tipografia, widgets visuais e overlay da contagem (sem lógica de jogo) |
| `ui_selecao.py` | modal de escolha do banco de perguntas (widgets Tk clássicos) |
| `serial_comm.py` | thread serial, detecção de porta, reconexão e fila de eventos |
| `dispositivos.py` | lista única de VID/PID, prioridade e nome da placa (puro) |
| `audio.py` | sons externos em `sons/` + fallback sintetizado (pygame opcional; sem ele fica mudo) |
| `jogo.py` | regra de jogo pura: estado, placar, timer e contagem de largada |
| `perguntas.py` | modelo, carregador/validador, listagem e nomes de tema (puro) |
| `persistencia.py` | estado da partida em JSON, hash, trava de instância e debounce (puro) |
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

**Como o app escolhe a porta (Etapa 4.4):** a regra é aplicada nesta ordem:

1. `serial.porta` no `config.json`, quando for `COMx` ou `VID:PID`
   (ex.: `1A86:7523`) — a porta/par indicado é tentado primeiro;
2. VID oficial de Arduino (`2341` ou `2A03`);
3. par VID:PID exato da tabela abaixo (inclui o clone CH340/CH341);
4. outro PID de um VID de adaptador compatível;
5. descrição que contenha `arduino`, `ch340` ou `ch341`.

Dentro da mesma faixa, a ordem de enumeração do sistema é preservada. Portas
Bluetooth/virtuais sem VID/PID ficam de fora. A escolha é registrada em
`DEBUG` no log, com a porta, a placa e a prioridade. A porta só é
considerada conectada depois de receber `PRONTO` dentro de
`serial.timeout_pronto` (padrão 3 s); enquanto isso não acontece, o app fecha a
porta e varre de novo a cada 3 s. A barra de status mostra a porta e a placa,
por exemplo `Arduino conectado (COM7) · CH340/CH341 (clone Arduino)
(1A86:7523)`.

**Porta configurada que não existe (decisão da Etapa 4.4):** o app **continua
tentando** a porta/par explícito primeiro e, se ele não estiver disponível,
cai na **detecção automática** — mas não em silêncio. A primeira ausência gera
um `WARNING` no log e um aviso persistente na barra de status:
`Porta COM9 não encontrada; usando detecção automática.` Se uma placa for
conectada em outra porta, o status mostra `Arduino conectado (COM5) · porta
COM9 não encontrada`; quando a porta configurada aparece, o aviso é limpo. A
mensagem é encurtada com reticências em janelas estreitas (teste em
`tests/test_ui_componentes.py`). O aviso é emitido **uma vez por ausência**,
não a cada varredura de 3 s.

A **lista única de VID/PID** fica em `dispositivos.py`:

| VID:PID | Nome exibido |
| --- | --- |
| `2341:0043` | Arduino Uno |
| `2341:0001` | Arduino Uno (bootloader) |
| `2341:0243` | Arduino Uno WiFi |
| `2341:0042` | Arduino Mega 2560 |
| `2341:0010` | Arduino Mega 2560 (bootloader) |
| `2341:8036` | Arduino Leonardo |
| `2341:8037` | Arduino Micro |
| `2A03:0043` | Arduino Uno (arduino.org) |
| `2A03:0042` | Arduino Mega 2560 (arduino.org) |
| `1A86:7523` | **CH340/CH341 (clone Arduino)** |
| `1A86:5523` | CH341 (clone) |
| `10C4:EA60` | CP2102 |
| `0403:6001` | FTDI FT232R |
| `067B:2303` | PL2303 |

Além desses pares, os VIDs de compatibilidade `1B4F`, `239A`, `03EB`, `04D8`
e `1209` são aceitos com qualquer PID; a lista e as prioridades não são
duplicadas em `serial_comm.py` nem na UI.

## Pacote de sons (Etapa 4.5)

Os efeitos são **opcionais e externos**: o jogo procura os arquivos na pasta
`sons/` ao lado do executável (rodando pelo fonte, na pasta do projeto). Se um
arquivo não existir, estiver corrompido, passar de **5 segundos** ou de
**5 MB**, usa o efeito sintetizado equivalente e registra **um único
`WARNING` por arquivo**; o app nunca cai por causa de áudio.

- Os arquivos existentes são carregados **uma vez na abertura** e mantidos em
  memória como objetos `Sound`; cada evento reutiliza o cache e **não lê o
  disco de novo**.
- Formatos: **WAV PCM 16 bits** e **OGG Vorbis**; se os dois existirem, o WAV
  tem preferência.
- Nomes e durações sugeridas: [`sons/README.md`](sons/README.md).
- Registro de autor/licença: [`sons/LICENCAS.md`](sons/LICENCAS.md).
- Botões A–D têm sons distintos e devem ter **menos de 1 s**.
- Volume geral em `audio.volume` (`0.0`–`1.0`), aplicado também ao fallback.
- O mixer usa `pre_init` com buffer de **512** amostras por padrão (ajustável
  em `audio.buffer`, `128`–`2048`) e mantém `set_num_channels(4)`.
- Contagem de largada: `contagem` toca um tick por número (3, 2, 1) e
  `largada` toca no **JÁ!**, com timbres sintetizados distintos.
- **O evento de vitória/fim de partida só dispara na Etapa 5.** O som
  `vitoria` já está mapeado, mas o jogo atual não o dispara; a tela de campeão
  e o fluxo de fim de partida pertencem àquela etapa. A troca de tema toca o
  som ao carregar um banco.

Nenhum áudio é baixado ou incluído no repositório. A pasta `sons/` contém
apenas a documentação; copie os arquivos licenciados para ela.

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
pasta do projeto rodando pelo fonte. Por isso os bancos de perguntas, o
`config.json` e a pasta `sons/` ficam sempre ao lado do executável. A chave
`perguntas.pasta` permite manter os bancos numa subpasta, sem recompilar; se a
pasta não existir, o app usa a pasta do executável. O comentário no `.spec`
lembra que `sons/` é externo e **não** deve entrar em `datas` (isso a colocaria
em `_MEIPASS`, fora do alcance do usuário).

**Pendência D6 (distribuição):** o `.exe` ainda não tem um script de
empacotamento de pasta. A distribuição precisa sair com o executável, o
`config.exemplo.json`, a pasta de perguntas (`perguntas.pasta` ou os JSONs ao
lado do `.exe`), a pasta `sons/` (com `README.md` e `LICENCAS.md`, mesmo sem
áudio) e o `README.md`. O script de empacotamento será feito depois da Etapa
4.5; até lá, copie esses itens manualmente para a pasta de distribuição.

## Roadmap (próximas etapas)

Ordem combinada: **3.6**, **3.7**, **4.x** (com a **4.6 antes da Etapa 5**) e
depois a **Etapa 5**. A **Etapa 4.6** está concluída; a próxima é a **Etapa 5**.

### Etapa 4.6 — Contagem de largada (implementada)

- Fase `CONTAGEM` no `Jogo`, antes de `AGUARDANDO`, com relógio injetável e
  duração configurável (`jogo.contagem_largada`, padrão 3 s; `0` desativa).
- Overlay com números grandes (3, 2, 1, JÁ!) em `ui_componentes.py`, escalando
  com a janela e sem cobrir os cartões de placar.
- Botões das equipes ignorados durante a contagem; eventos de botão acumulados
  na fila serial são descartados ao entrar em `AGUARDANDO`.
- O tempo de 30 s só começa no "JÁ!"; a pergunta fica oculta por padrão
  (`jogo.mostrar_pergunta_na_contagem`).
- Sons `contagem` (tick por número) e `largada`, com fallbacks sintetizados
  distintos.
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
- A partida salva retoma a pergunta atual em `CONTAGEM` (ou em `AGUARDANDO`,
  com a contagem desativada); fase e tempo restante não são restaurados.
- O firmware usa `delay()` no bipe e será revisado junto com o protocolo v2.
- **Pendência de hardware:** validar com clone **CH340**; se o `PRONTO`
  demorar mais de 3 s após o reset por DTR, aumentar
  `serial.timeout_pronto` no `config.json` (padrão 3 s).
- A validação com hardware real usou uma **Mega 2560** (VID `2341:0042`).
  A Etapa 5 deve validar o mapeamento de pinos do firmware em uma **Uno** e
  documentar a diferença Mega × Uno.
