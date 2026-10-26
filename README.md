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
`pygame` instalado o jogo também inicia, mas sem som (aviso no console).

## Execução

```powershell
python desafio.py
```

O aplicativo abre em tela cheia. Na primeira execução ele pede o tema
(arquivo de perguntas).

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

Regras de validação (aplicadas por `jogo.ler_banco_perguntas`, o carregador
único do projeto):

- `pergunta` (ou `texto`) obrigatório e não vazio;
- `alternativas`: lista de **2 a 4** itens, todos não vazios;
- `correta`: índice inteiro válido dentro de `alternativas`;
- campo `tema`/`titulo` no objeto define o nome do tema (opcional).

Perguntas inválidas são **ignoradas** e o motivo vai para o console; a
interface mostra um aviso como `1 pergunta ignorada em tema.json.` e continua
carregando as demais.

Bancos incluídos: `conhecimentos_gerais.json` (97 perguntas),
`eletrotecnica.json` (20) e `radiologia.json` (20).

## Testes

```powershell
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

A suíte cobre a máquina de estados, o placar, o carregador de perguntas, o
timer (com relógio injetável — nenhum teste usa `sleep`) e o protocolo serial
em modo headless. Nenhum teste abre janela ou exige Arduino.

## Estrutura do projeto

| Arquivo | Papel |
| --- | --- |
| `desafio.py` | interface tkinter: desenho, teclado, serial e sons |
| `jogo.py` | regra de jogo pura: estado, placar, timer, perguntas |
| `protocolo.py` | tradução pura entre linhas da serial e ações/eventos |
| `tests/` | suíte pytest |
| `duelo_arduino.ino/` | firmware do Arduino (protocolo v1) |
| `config.exemplo.json` | modelo de configuração (lido a partir da Etapa 4.2) |
| `Desafio do Conhecimento.spec` | receita de build com PyInstaller |

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

## Gerar o executável

```powershell
pyinstaller "Desafio do Conhecimento.spec"
```

O `.exe` sai em `dist/`. Ele **não** é versionado (veja `.gitignore`); os
arquivos JSON de perguntas precisam ficar ao lado do executável.

## Limitações conhecidas (em evolução)

- A interface ainda mostra **2 equipes**; a lógica já suporta 2, 3 ou 4.
- `config.json` ainda não é lido (Etapa 4.2) — os tempos estão no código.
- Sem log em arquivo e sem retomada automática de partida (Etapa 4).
- O firmware usa `delay()` no bipe e será revisado junto com o protocolo v2.
