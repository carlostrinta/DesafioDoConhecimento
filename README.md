# Desafio do Conhecimento

Jogo de perguntas e respostas para **2 a 4 equipes**, com interface desktop em
Python/tkinter e botões físicos opcionais no **Arduino Uno ou Mega 2560**. A
equipe que apertar primeiro ganha a vez de responder; o tempo controla a rodada
e o placar fica visível na tela.

**Versão atual: 2.8.1** — os metadados oficiais ficam em
[`versao.py`](versao.py). A tela **Sobre** pode ser aberta com `F1`.

> **Estado do hardware:** o firmware v2 é o **recomendado** e foi validado no
> **Arduino Uno e no Mega 2560**, com 2 a 4 equipes e 10 botões. O **clone CH340
> ainda não foi testado com o v2** — é uma pendência explícita. Se o `PRONTO`
> demorar mais de 3 s após o reset por DTR, aumente `serial.timeout_pronto` no
> `config.json`. O firmware v1 continua disponível como caminho legado para
> 2 equipes com LEDs e buzzer.

---

## Sumário

- [Como rodar](#como-rodar)
- [Controles do teclado](#controles-do-teclado)
- [Hardware opcional](#hardware-opcional)
- [Gerar o executável](#gerar-o-executável)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Configuração e logs](#configuração-e-logs)
- [Testes](#testes)
- [Limitações conhecidas](#limitações-conhecidas)
- [Como contribuir](#como-contribuir)
- [Licenças e créditos](#licenças-e-créditos)
- [Documentação adicional](#documentação-adicional)

---

## Como rodar

### Requisitos

| Item | Versão |
| --- | --- |
| Python | **3.12.x** (versão de referência; também roda em 3.13–3.15) |
| Sistema | Windows 10/11 (testado); Linux/macOS devem funcionar |
| Arduino | opcional — o jogo roda 100% no teclado |

O projeto é validado oficialmente com **Python 3.12.15**. Se você usa `uv`:

```powershell
uv python install 3.12
```

### Instalação e execução

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Dependências:

- `pyserial` — comunicação com o Arduino;
- `pygame` — áudio.

Sem Arduino conectado, o jogo inicia em **modo teclado**. Sem `pygame`, o jogo
também inicia, mas fica sem som. Os arquivos de áudio são opcionais: veja
[`sons/README.md`](sons/README.md).

Na primeira execução o jogo pede o **tema** (banco de perguntas `.json`). Se
houver uma partida salva, ele pergunta antes se você quer continuá-la.

Para ver o log detalhado também no console:

```powershell
python main.py --debug
```

O ponto de entrada é **`main.py`**. O arquivo `desafio.py` contém a interface
(a classe `DueloDeConhecimento`) e **não** deve ser executado diretamente.

---

## Controles do teclado

| Tecla | Ação |
| --- | --- |
| `A` / `B` / `C` / `D` | a equipe correspondente aperta o botão |
| `R` | revela a resposta |
| `1` / `2` / `3` / `4` | ponto para a equipe A / B / C / D |
| `N` | próxima pergunta |
| `S` | liga/desliga o som |
| `F1` | abre a tela Sobre |
| `F11` | alterna tela cheia |
| `Esc` | sai da tela cheia |
| `Ctrl+R` | reinicia o placar (com confirmação) |
| `Ctrl+T`, `Ctrl+O`, `F2` | abre o seletor de tema |

No seletor de tema, `↑`/`↓` movem a seleção, `Enter` confirma e `Esc` cancela.
Clique simples seleciona; clique duplo escolhe o tema.

As teclas de equipe e de ponto respeitam `jogo.num_equipes`: com 2 equipes,
`C`/`D` e `3`/`4` são ignorados; com 3, `D`/`4` são ignorados; com 4, todas
valem. Durante a contagem de largada, as teclas de equipe ficam bloqueadas até
o `JÁ!`.

---

## Hardware opcional

O hardware é opcional: sem Arduino, o jogo funciona no teclado. Há três
caminhos, do recomendado ao legado.

### (a) Firmware v2 — recomendado

O v2 usa **somente botões** em `D2–D11`, sem LEDs, buzzer, resistores ou fonte
externa. O feedback visual e sonoro fica no aplicativo. Foi validado no
**Arduino Uno** e no **Mega 2560**; o clone CH340 ainda é pendência.

#### Lista de materiais do v2

- 1 **Arduino Uno** ou **Arduino Mega 2560**;
- **6, 8 ou 10 botões** de pressão momentâneos, conforme o modo de equipes;
- 1 protoboard grande ou placa de montagem;
- jumpers macho-macho;
- cabo USB.

> **Alimentação:** use o Arduino alimentado pelo USB. Não ligue os botões em
> tensões externas. Os pinos digitais do Uno e do Mega trabalham em 5 V.
>
> **Clone CH340:** ainda não validado com o v2. Se o `PRONTO` demorar mais de
> 3 s após o reset por DTR, aumente `serial.timeout_pronto` no `config.json`.

#### Botões necessários por modo

| Modo | Botões | Pinos usados |
| --- | ---: | --- |
| 2 equipes | 6 | `D2`–`D7` |
| 3 equipes | 8 | `D2`–`D8` + `D10` (`D9`/`D11` ficam livres) |
| 4 equipes | 10 | `D2`–`D11` |

Você pode montar os 10 botões de uma vez: o firmware só ativa os botões das
equipes configuradas em `CONFIG_TEAMS`.

#### Mapa de pinos (Uno e Mega 2560)

Os dois modelos usam os **mesmos pinos D2–D11**. O mapa abaixo serve para
qualquer um deles:

| Pino | Evento | Função | 2 eq. | 3 eq. | 4 eq. |
| --- | --- | --- | :---: | :---: | :---: |
| `D2` | `BTN_A` | botão da equipe A | sim | sim | sim |
| `D3` | `BTN_B` | botão da equipe B | sim | sim | sim |
| `D4` | `BTN_AVANCAR` | próxima pergunta | sim | sim | sim |
| `D5` | `BTN_ACERTO_A` | ponto da equipe A | sim | sim | sim |
| `D6` | `BTN_ACERTO_B` | ponto da equipe B | sim | sim | sim |
| `D7` | `BTN_REVELAR` | revelar resposta | sim | sim | sim |
| `D8` | `BTN_C` | botão da equipe C | — | sim | sim |
| `D9` | `BTN_D` | botão da equipe D | — | — | sim |
| `D10` | `BTN_ACERTO_C` | ponto da equipe C | — | sim | sim |
| `D11` | `BTN_ACERTO_D` | ponto da equipe D | — | — | sim |

Cada botão fica entre o pino indicado e o **GND**, usando o resistor interno
de pull-up (`INPUT_PULLUP`). Em repouso o pino lê `HIGH`; ao apertar, lê `LOW`.
Não use resistores externos de pull-up.

```text
Arduino Uno/Mega 2560              Botão
D2  ───────────────────────────────[ A ]──────── GND
D3  ───────────────────────────────[ B ]──────── GND
D4  ───────────────────────────────[ Avançar ]── GND
D5  ───────────────────────────────[ Acerto A ]─ GND
D6  ───────────────────────────────[ Acerto B ]─ GND
D7  ───────────────────────────────[ Revelar ]── GND
D8  ───────────────────────────────[ C ]──────── GND
D9  ───────────────────────────────[ D ]──────── GND
D10 ───────────────────────────────[ Acerto C ]─ GND
D11 ───────────────────────────────[ Acerto D ]─ GND
```

Diagrama visual em SVG:
[`docs/ligacao_v2.svg`](docs/ligacao_v2.svg).

#### Pinos livres e reservados

- **Livres no Uno:** `A0`–`A5`, `D12` e `D13`.
- **Mega 2560:** usa os mesmos `D2`–`D11`; os demais pinos digitais ficam
  disponíveis. O I2C em `D20`/`D21` **não é usado** pelo firmware v2.
- **Reservados:** `D0`/`D1` são a serial/USB. Não ligue botões neles.

#### Handshake do v2

1. Ao iniciar, o Arduino envia `PRONTO`.
2. Em seguida envia `VERSAO 2`.
3. O PC envia `CONFIG_TEAMS 2`, `3` ou `4`.
4. O Arduino responde `EQUIPES N` para confirmar o número ativo.

O firmware começa com **2 equipes**. Se o ACK não chegar, o PC faz uma
retentativa e, na segunda falha, avisa e cai para 2 equipes. O roteiro completo
está em [`firmware/v2/ROTEIRO_VALIDACAO.md`](firmware/v2/ROTEIRO_VALIDACAO.md).

### (b) Firmware v1 — legado (2 equipes, LEDs e buzzer)

O firmware original está em
[`firmware/v1/duelo_arduino_v1/duelo_arduino_v1.ino`](firmware/v1/duelo_arduino_v1/duelo_arduino_v1.ino)
(cópia idêntica, mantida como ponto de retorno). Ele atende **2 equipes** e
continua disponível para quem já tem a montagem antiga.

#### Lista de materiais do v1

- 1 **Arduino Uno**;
- 6 botões de pressão momentâneos;
- 2 LEDs;
- 2 resistores de **220 Ω** ou **330 Ω** para os LEDs;
- 1 buzzer ativo de 5 V;
- protoboard ou placa de montagem, jumpers e cabo USB.

#### Mapa de pinos do v1

| Pino | Função |
| --- | --- |
| `D2` | botão A |
| `D3` | botão B |
| `D4` | avançar pergunta |
| `D5` | acerto A |
| `D6` | acerto B |
| `D7` | revelar resposta |
| `D8` | LED da equipe A (com resistor de 220–330 Ω para GND) |
| `D9` | LED da equipe B (com resistor de 220–330 Ω para GND) |
| `D10` | buzzer ativo (positivo no pino, negativo no GND) |
| `D11` | livre no firmware v1 |

O v1 envia `BTN_*` e `PRONTO` pela serial em **9600 baud** e recebe comandos
de LED/buzzer. A interface Python detecta o v1 e limita a partida a 2 equipes,
preservando o caminho legado.

### (c) Sketch de bancada

O sketch [`firmware/bancada_botoes/bancada_botoes.ino`](firmware/bancada_botoes/bancada_botoes.ino)
valida apenas os 10 botões, sem LEDs e sem buzzer. Ele responde no Monitor
Serial a 9600 baud: `CONFIG_TEAMS 2|3|4` devolve `EQUIPES N` e
`CONFIG_TEAMS 5|X|22` (ou vazio) devolve `ERRO EQUIPES`. Use o aplicativo
**fechado** enquanto o Monitor Serial estiver aberto. O procedimento completo
está em [`firmware/bancada_botoes/README.md`](firmware/bancada_botoes/README.md).

Para gravar qualquer um dos sketches: abra o `.ino` na Arduino IDE, selecione
a placa (**Arduino Uno** ou **Mega 2560**) e a porta correta, clique em
**Upload** e feche o Monitor Serial antes de abrir o jogo.

---

## Gerar o executável

Instale o PyInstaller (apenas para o build) e use o `.spec` versionado:

```powershell
pip install pyinstaller
pyinstaller "Desafio do Conhecimento.spec"
```

O executável sai em `dist/Desafio do Conhecimento.exe`. Ele **não** é
versionado. O arquivo de versão do PyInstaller (`versao_info.txt`) lê os dados
de `versao.py` e grava no `.exe`:

- nome do produto: **Desafio do Conhecimento**;
- versão: **2.8.1**;
- autor/empresa: **Carlos Santos**;
- copyright: **Copyright (c) 2026 Carlos Santos**.

Nada é empacotado dentro do `.exe` (`datas=[]` no `.spec`). Os recursos são
procurados na pasta da aplicação. Para distribuir, copie para a mesma pasta do
executável:

- os bancos de perguntas `.json` (ou a subpasta configurada em
  `perguntas.pasta`);
- `config.exemplo.json` (o usuário pode copiar para `config.json`);
- a pasta `sons/` (mesmo que só com `README.md` e `LICENCAS.md`);
- `README.md`, `LICENSE` e `LICENCA_PERGUNTAS.md`.

A pasta `logs/` é criada automaticamente ao lado do `.exe` (ou na pasta do
script, se não houver permissão de escrita).

---

## Estrutura do projeto

| Arquivo/pasta | Papel |
| --- | --- |
| `main.py` | ponto de entrada: logging, janela e loop do Tk |
| `versao.py` | fonte única de nome, versão, autor, URL e licença |
| `desafio.py` | interface tkinter: telas, teclado e ligação com o jogo |
| `ui_componentes.py` | componentes Canvas: paleta, tipografia, widgets e overlay da contagem |
| `ui_selecao.py` | modal de escolha do banco de perguntas |
| `ui_sobre.py` | tela Sobre (F1) |
| `jogo.py` | regra de jogo pura: estado, placar, timer e contagem |
| `perguntas.py` | modelo, carregador/validador e listagem dos bancos |
| `persistencia.py` | partida salva em JSON, hash, trava de instância e debounce |
| `serial_comm.py` | thread serial, detecção de porta, reconexão e fila |
| `protocolo.py` | protocolo v2: botões, `CONFIG_TEAMS` e ACK de equipes |
| `protocolo_v1.py` | adaptador legado v1: LEDs, buzzer, `RESET` e reacendimento |
| `dispositivos.py` | lista única de VID/PID e nomes de placas |
| `audio.py` | sons externos em `sons/` e fallback sintetizado |
| `config.py` | leitura e validação de `config.json` |
| `recursos.py` | localização da pasta da aplicação (fonte ou `.exe`) |
| `logging_conf.py` | log rotativo, níveis e captura de exceções |
| `conhecimentos_gerais.json`, `eletrotecnica.json`, `radiologia.json` | bancos de perguntas |
| `firmware/README.md` | índice dos sketches e ordem de validação |
| `firmware/v1/duelo_arduino_v1/` | firmware v1 congelado (ponto de retorno) |
| `firmware/bancada_botoes/` | sketch e roteiro de validação dos 10 botões |
| `firmware/v2/duelo_v2/` | firmware v2 validado no Uno/Mega (10 botões, 4 equipes, sem LEDs/buzzer) |
| `sons/` | documentação de áudio e registro de licenças |
| `tests/` | suíte de testes pytest |
| `Desafio do Conhecimento.spec` | receita de build do PyInstaller |
| `versao_info.txt` | metadados de versão/autor gravados no `.exe` |
| `config.exemplo.json` | modelo versionado de configuração |
| `ROTEIRO_SERIAL_HARDWARE.md` | checklist de validação com Arduino real |
| `docs/ligacao_v2.svg` | diagrama de ligação dos 10 botões (Uno e Mega) |
| `docs/PLANO_EDITOR_PERGUNTAS.md` | plano do editor de perguntas (sem código) |

---

## Configuração e logs

Copie `config.exemplo.json` para `config.json` e edite os valores desejados. O
arquivo fica ao lado do executável (ou na pasta do projeto, rodando pelo
código-fonte). Sem ele, valem os padrões históricos. JSON inválido ou valor
fora da regra não derruba o jogo: o aplicativo usa o padrão, registra um
`WARNING` e mostra um aviso curto.

Configurações principais:

| Seção | Exemplos |
| --- | --- |
| `tempos` | tempo de pergunta e tempo de resposta |
| `jogo` | número de equipes, pontuação após o tempo e contagem de largada |
| `perguntas` | pasta e arquivo padrão do banco inicial |
| `audio` | volume, buffer e ativação do som |
| `serial` | porta fixa, `VID:PID`, baud rate e timeout do `PRONTO` |
| `ui` | duração do overlay `JÁ!` e exibição da pergunta durante a contagem |
| `nomes_equipes` | nomes exibidos para as equipes A–D |
| `persistencia` | continuar a partida salva automaticamente |

O log fica em `logs/desafio.log`, com rotação de 1 MB e 3 backups. Sem
`--debug`, nada é impresso no console. O nível pode ser trocado por
`DESAFIO_LOG_NIVEL` (`DEBUG`, `INFO`, `WARNING` ou `ERROR`). Exceções não
tratadas vão com traceback para o log; o usuário vê uma mensagem curta.

---

## Testes

A suíte usa `pytest` e não precisa de Arduino nem de um display para a maior
parte dos testes. Instale as dependências de desenvolvimento e rode:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Alguns testes abrem uma janela Tk real; em ambiente **headless** eles são
pulados automaticamente. O golden visual é opt-in:

```powershell
$env:DESAFIO_GOLDEN_UI=1
python -m pytest tests/test_ui_componentes.py -q
```

O golden serve como guarda de refatoração local. Se o layout mudar de propósito,
regrave **apenas os casos afetados** em um commit separado e justificado.

---

## Como contribuir

Contribuições são bem-vindas, principalmente testes com hardware real,
revisão de perguntas e melhorias de acessibilidade.

1. Abra uma **issue** descrevendo o problema ou a ideia, com a versão do jogo e
   o trecho relevante de `logs/desafio.log`.
2. Faça um fork, crie uma branch curta (`fix/...` ou `feat/...`) e mantenha o
   estilo e os nomes já usados no projeto.
3. Rode `python -m pytest -q` antes de abrir o pull request.
4. Para mudanças de hardware/firmware, valide no **Arduino Uno ou Mega 2560**
   usando `firmware/bancada_botoes` e descreva a placa, o driver e a porta
   testada.
5. No pull request, explique **o que mudou**, **como testar** e quais
   limitações permanecem.

Não envie para o repositório:

- `config.json` pessoal;
- `logs/`, `build/`, `dist/` ou arquivos `.exe`;
- áudio sem licença registrada em `sons/LICENCAS.md`;
- segredos, caminhos absolutos da sua máquina ou dados pessoais.

Mudanças no protocolo serial ou nos pinos precisam de discussão prévia: o
firmware v1 é uma referência congelada para não quebrar placas já montadas.

---

## Licenças e créditos

- **Código-fonte:** licença **MIT**, `Copyright (c) 2026 Carlos Santos`.
  Texto oficial em [`LICENSE`](LICENSE).
- **Bancos de perguntas:** licença **Creative Commons Atribuição 4.0
  Internacional (CC BY 4.0)**, autor **Carlos Santos**. O aviso de atribuição
  está em [`LICENCA_PERGUNTAS.md`](LICENCA_PERGUNTAS.md). Isso vale para
  `conhecimentos_gerais.json`, `eletrotecnica.json`, `radiologia.json` e os
  demais bancos `.json` distribuídos com o jogo.
- **Sons:** o projeto não inclui áudio por padrão. Cada arquivo de áudio tem
  sua própria licença e crédito, registrados em
  [`sons/LICENCAS.md`](sons/LICENCAS.md).
- **Autor do projeto:** **Carlos Santos**.
- **Metadados:** nome, versão, autor, URL e licença ficam em
  [`versao.py`](versao.py) e são usados pela tela Sobre (`F1`), pelo log e pelo
  arquivo de versão do `.exe`.

Se você redistribuir o jogo, mantenha os arquivos `LICENSE`,
`LICENCA_PERGUNTAS.md` e `sons/LICENCAS.md` junto da distribuição.

---

## Documentação adicional

- [`ROTEIRO_SERIAL_HARDWARE.md`](ROTEIRO_SERIAL_HARDWARE.md) — checklist de
  validação com Arduino real (portas, drivers, reconexão e `.exe`).
- [`sons/README.md`](sons/README.md) — nomes, formatos e limites dos arquivos
  de áudio.
- [`sons/LICENCAS.md`](sons/LICENCAS.md) — registro obrigatório de licenças
  dos sons.
- [`firmware/README.md`](firmware/README.md) — índice dos sketches e ordem de
  validação.
- [`firmware/v1/README.md`](firmware/v1/README.md) — cópia do firmware
  original e seu hash.
- [`firmware/bancada_botoes/README.md`](firmware/bancada_botoes/README.md) —
  roteiro físico dos 10 botões, `CONFIG_TEAMS` e debounce.
- [`firmware/v2/README.md`](firmware/v2/README.md) — pinagem, protocolo e
  status do firmware v2.
- [`firmware/v2/ROTEIRO_VALIDACAO.md`](firmware/v2/ROTEIRO_VALIDACAO.md) —
  roteiro físico, matriz PC × firmware, placas validadas e pendência do CH340.
- [`LICENCA_PERGUNTAS.md`](LICENCA_PERGUNTAS.md) — licença dos bancos de
  perguntas.
- [`docs/PLANO_EDITOR_PERGUNTAS.md`](docs/PLANO_EDITOR_PERGUNTAS.md) — plano
  do editor de perguntas (escopo, formato, salvamento, UI, testes e etapas).

---

## Limitações conhecidas

- Com firmware v1 (ou sem handshake), a partida cai para **2 equipes** com
  aviso; 3/4 equipes com botões físicos usam o firmware v2.
- O firmware v2 foi validado no **Arduino Uno e no Mega 2560**. O clone CH340
  com v2 ainda é pendência; se o `PRONTO` demorar mais de 3 s após o reset por
  DTR, aumente `serial.timeout_pronto`.
- No modo teclado puro, 3/4 equipes já funcionam.
- `eletrotecnica.json` e `radiologia.json` têm 20 perguntas cada: o baralho
  reinicia rápido.
- A partida salva retoma a pergunta atual; fase e tempo restante não são
  restaurados.
- A ordem de chegada é definida pela **recepção no PC**; o firmware não envia
  timestamp de pressionamento. Em empates muito próximos, a ordem pode
  depender do buffer e da porta serial. Para um v3, a sugestão é enviar um
  contador de pressão por botão no firmware.
- O v1 continua na pasta `firmware/v1` como ponto de retorno.

---

**Autor:** Carlos Santos · **Versão:** 2.8.1 · **Licença do código:** MIT
