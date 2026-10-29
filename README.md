# Desafio do Conhecimento

Jogo de perguntas e respostas para **2 a 4 equipes**, com interface desktop em
Python/tkinter e botões físicos opcionais no **Arduino Uno**. A equipe que
apertar primeiro ganha a vez de responder; o tempo controla a rodada e o placar
fica visível na tela.

**Versão atual: 2.7.0** — os metadados oficiais ficam em
[`versao.py`](versao.py). A tela **Sobre** pode ser aberta com `F1`.

> **Estado do hardware:** a parte Python já aceita 2, 3 ou 4 equipes pelo
> teclado. O firmware/protocolo v1 do Arduino atende 2 equipes; o protocolo v2
> (4 equipes e botões C/D) foi **validado no Arduino Uno** e está disponível
> nesta versão. O sketch de bancada em
> [`firmware/bancada_botoes`](firmware/bancada_botoes/bancada_botoes.ino)
> registra o teste dos 10 botões e do parser de `CONFIG_TEAMS`.

---

## Sumário

- [Como rodar](#como-rodar)
- [Controles do teclado](#controles-do-teclado)
- [Hardware opcional](#hardware-opcional)
- [Gerar o executável](#gerar-o-executável)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Configuração e logs](#configuração-e-logs)
- [Testes](#testes)
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

### Lista de materiais

Para montar a bancada completa de **10 botões** (teclado físico para 4 equipes):

- 1 **Arduino Uno** (original ou clone CH340/CH341);
- 10 botões de pressão (push buttons) momentâneos;
- 1 protoboard grande ou placa de montagem;
- jumpers macho-macho;
- cabo USB;
- opcional para o firmware v1: 2 LEDs e 2 resistores de **220 Ω** ou
  **330 Ω**, além de 1 buzzer ativo de 5 V.

Para o firmware v1 original bastam **6 botões** (A, B, Avançar, Acerto A,
Acerto B e Revelar), 2 LEDs e o buzzer.

> **Alimentação:** use o Arduino alimentado pelo USB. Não ligue os botões em
> tensões externas. Os pinos digitais do Uno trabalham em 5 V.

### Diagrama de ligação dos botões (D2 a D11)

Todos os botões usam o resistor interno de pull-up do Arduino
(`INPUT_PULLUP`). A ligação é simples:

```text
Arduino Uno                        Botão
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

Cada botão fica entre o pino indicado e o **GND**. Em repouso o pino lê `HIGH`;
ao apertar, lê `LOW`. Não use resistores externos de pull-up.

Mapa dos 10 botões usado pelo sketch de bancada:

| Pino | Evento | Função |
| --- | --- | --- |
| `D2` | `BTN_A` | botão da equipe A |
| `D3` | `BTN_B` | botão da equipe B |
| `D4` | `BTN_AVANCAR` | próxima pergunta |
| `D5` | `BTN_ACERTO_A` | ponto da equipe A |
| `D6` | `BTN_ACERTO_B` | ponto da equipe B |
| `D7` | `BTN_REVELAR` | revelar resposta |
| `D8` | `BTN_C` | botão da equipe C |
| `D9` | `BTN_D` | botão da equipe D |
| `D10` | `BTN_ACERTO_C` | ponto da equipe C |
| `D11` | `BTN_ACERTO_D` | ponto da equipe D |

> `D0` e `D1` são usados pela serial/USB. Não ligue botões neles.

### Firmware v1 (2 equipes)

O firmware original está em
[`firmware/v1/duelo_arduino_v1/duelo_arduino_v1.ino`](firmware/v1/duelo_arduino_v1/duelo_arduino_v1.ino)
(cópia idêntica, mantida como ponto de retorno). Essa é agora a única cópia
versionada do v1.

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

O firmware v1 envia `BTN_*` e `PRONTO` pela serial em **9600 baud** e recebe
comandos de LED/buzzer. A interface Python detecta o firmware v1 e limita a
partida a 2 equipes, evitando enviar comandos que ele não conhece.

### Bancada de botões (validação do v2)

O sketch [`firmware/bancada_botoes/bancada_botoes.ino`](firmware/bancada_botoes/bancada_botoes.ino)
valida apenas os 10 botões, sem LEDs e sem buzzer. Ele responde no Monitor
Serial a 9600 baud: `CONFIG_TEAMS 2|3|4` devolve `EQUIPES N` e
`CONFIG_TEAMS 5|X|22` (ou vazio) devolve `ERRO EQUIPES`. Use o aplicativo
**fechado** enquanto o Monitor Serial estiver aberto. O procedimento completo
está em [`firmware/bancada_botoes/README.md`](firmware/bancada_botoes/README.md).

Para gravar: abra o `.ino` na Arduino IDE, selecione a placa **Arduino Uno** e
a porta correta e clique em **Upload**. Depois feche o Monitor Serial antes de
abrir o jogo.

### Firmware v2 de produção

O firmware v2 fica em
[`firmware/v2/duelo_arduino_v2/duelo_arduino_v2.ino`](firmware/v2/duelo_arduino_v2/duelo_arduino_v2.ino)
e usa o mesmo mapa de 10 botões em `D2–D11`. Ele **não usa LEDs nem buzzer**:
o feedback fica no aplicativo. O handshake é `PRONTO` + `VERSAO 2`; depois o
Python envia `CONFIG_TEAMS N` e espera o ACK `EQUIPES N`. A validação física
foi concluída no Arduino Uno em **29/10/2026**.

| Comando | Resposta |
| --- | --- |
| `CONFIG_TEAMS 2`, `3` ou `4` | `EQUIPES N` |
| `CONFIG_TEAMS 5`, `X`, `22` ou vazio | `ERRO EQUIPES` |
| `RESET` | reinicia o debounce, sem saída física |
| `LED_*`, `BEEP*`, `BUZZER_*` | ignorados |

O debounce é de **60 ms**. O roteiro da bancada e o teste do aplicativo com o
v2 foram concluídos antes da liberação; consulte
[`firmware/bancada_botoes/README.md`](firmware/bancada_botoes/README.md).

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
- versão: **2.7.0**;
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
| `protocolo.py` | tradução entre linhas da serial e ações/eventos |
| `dispositivos.py` | lista única de VID/PID e nomes de placas |
| `audio.py` | sons externos em `sons/` e fallback sintetizado |
| `config.py` | leitura e validação de `config.json` |
| `recursos.py` | localização da pasta da aplicação (fonte ou `.exe`) |
| `logging_conf.py` | log rotativo, níveis e captura de exceções |
| `conhecimentos_gerais.json`, `eletrotecnica.json`, `radiologia.json` | bancos de perguntas |
| `firmware/README.md` | índice dos sketches e ordem de validação |
| `firmware/v1/duelo_arduino_v1/` | firmware v1 congelado (ponto de retorno) |
| `firmware/bancada_botoes/` | sketch e roteiro de validação dos 10 botões |
| `firmware/v2/duelo_arduino_v2/` | firmware v2 (10 botões, 4 equipes, sem LEDs/buzzer) |
| `sons/` | documentação de áudio e registro de licenças |
| `tests/` | suíte de testes pytest |
| `Desafio do Conhecimento.spec` | receita de build do PyInstaller |
| `versao_info.txt` | metadados de versão/autor gravados no `.exe` |
| `config.exemplo.json` | modelo versionado de configuração |
| `ROTEIRO_SERIAL_HARDWARE.md` | checklist de validação com Arduino real |

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
4. Para mudanças de hardware/firmware, valide na **Arduino Uno** usando
   `firmware/bancada_botoes` e descreva a placa, o driver e a porta testada.
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
  validação do firmware v2.
- [`LICENCA_PERGUNTAS.md`](LICENCA_PERGUNTAS.md) — licença dos bancos de
  perguntas.

---

## Limitações conhecidas

- Com firmware v1 (ou sem handshake), a partida cai para **2 equipes** com
  aviso; 3/4 equipes com botões físicos usam o firmware v2 validado.
- No modo teclado puro, 3/4 equipes já funcionam.
- `eletrotecnica.json` e `radiologia.json` têm 20 perguntas cada: o baralho
  reinicia rápido.
- A partida salva retoma a pergunta atual; fase e tempo restante não são
  restaurados.
- O firmware v2 foi validado no Arduino Uno e está disponível; o v1 continua
  na pasta `firmware/v1` como ponto de retorno.

---

**Autor:** Carlos Santos · **Versão:** 2.7.0 · **Licença do código:** MIT
