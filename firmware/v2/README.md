# Firmware v2 — produção

**Status: EM VALIDAÇÃO.** O firmware só será liberado depois da validação
física no Arduino Uno e do teste do aplicativo com 4 equipes. O roteiro está
em [`ROTEIRO_VALIDACAO.md`](ROTEIRO_VALIDACAO.md).

O firmware v2 usa os **10 botões em D2–D11** e não usa LEDs nem buzzer. O
feedback visual e sonoro fica no aplicativo; isso libera todos os pinos
digitais para os botões e elimina a diferença de fiação entre a bancada e a
produção.

## Ligação

Cada botão fica entre o pino e o **GND**, com `INPUT_PULLUP`:

| Pino | Evento | Equipe |
| --- | --- | --- |
| `D2` | `BTN_A` | A |
| `D3` | `BTN_B` | B |
| `D4` | `BTN_AVANCAR` | — |
| `D5` | `BTN_ACERTO_A` | A |
| `D6` | `BTN_ACERTO_B` | B |
| `D7` | `BTN_REVELAR` | — |
| `D8` | `BTN_C` | C |
| `D9` | `BTN_D` | D |
| `D10` | `BTN_ACERTO_C` | C |
| `D11` | `BTN_ACERTO_D` | D |

`D0`/`D1` continuam reservados para a serial/USB. Não use resistores externos
de pull-up.

## Protocolo

Arduino → PC, uma vez por boot:

```text
PRONTO
VERSAO 2
```

PC → Arduino:

| Comando | Resposta | Efeito |
| --- | --- | --- |
| `CONFIG_TEAMS 2` | `EQUIPES 2` | ativa A/B |
| `CONFIG_TEAMS 3` | `EQUIPES 3` | ativa A/B/C |
| `CONFIG_TEAMS 4` | `EQUIPES 4` | ativa A/B/C/D |
| `CONFIG_TEAMS 5` | `EQUIPES <atual>` | inválido; não altera |
| `CONFIG_TEAMS X` | `EQUIPES <atual>` | inválido; não altera |
| `CONFIG_TEAMS 22` | `EQUIPES <atual>` | inválido; não altera |
| `CONFIG_TEAMS` (vazio) | `EQUIPES <atual>` | inválido; não altera |
| `LED_*`, `LED_ALL_OFF`, `BEEP`, `BEEP_LONG`, `BUZZER_*`, `RESET` | — | ignorados |
| comando desconhecido | — | ignorado |

O firmware começa com **2 equipes** (`EQUIPES 2`). Os eventos de C/D só são
enviados quando `CONFIG_TEAMS` ativou essas equipes. O debounce é um lockout de
**60 ms**: o evento sai na primeira descida, sem atraso; soltar ou manter o
botão pressionado não gera nova linha. O buffer serial é fixo de 32 bytes;
linhas que estouram o buffer são descartadas até o próximo `\n`.

## Compatibilidade PC × firmware

| PC | Firmware | Resultado |
| --- | --- | --- |
| v1 | v1 | 2 equipes, LEDs/buzzer ativos, protocolo v1 |
| v1 | v2 | PC v1 ignora `VERSAO 2`/`EQUIPES N`; o firmware ignora `LED_*`, `BEEP*`, `BUZZER_*` e `RESET`; somente A/B têm efeito no jogo |
| v2 | v1 | PC v2 detecta v1, limita a 2 equipes e preserva o caminho v1 (LEDs/buzzer) |
| v2 | v2 | 2 a 4 equipes; `CONFIG_TEAMS` + ACK `EQUIPES N`; sem comandos de LED/buzzer |

O caminho PC v2 + firmware v2 está **em validação** até a confirmação do Carlos.

## Como gravar

1. Abra [`duelo_v2/duelo_v2.ino`](duelo_v2/duelo_v2.ino) na Arduino IDE.
2. Selecione **Arduino Uno** e a porta correta.
3. Faça o upload e feche o Monitor Serial antes de abrir o jogo.
4. O aplicativo deve mostrar o status de Arduino conectado e reconhecer
   `VERSAO 2`.

## Validação

O roteiro completo, incluindo a matriz PC v1/v2 × firmware v1/v2, está em
[`ROTEIRO_VALIDACAO.md`](ROTEIRO_VALIDACAO.md). A bancada de 10 botões foi
validada separadamente; o firmware v2 de produção ainda precisa passar pelo
roteiro com o aplicativo antes da liberação.

Critérios de aceite:

- os 10 botões são lidos nos pinos D2–D11;
- `CONFIG_TEAMS 2`, `3` e `4` respondem `EQUIPES N`;
- `CONFIG_TEAMS 5`, `X`, `22` e vazio respondem `EQUIPES <atual>`;
- o debounce de 60 ms não repete evento com o botão mantido;
- o PC v2 envia `CONFIG_TEAMS N`, confirma o ACK e não envia LED/BEEP/RESET;
- reconexão/reset por DTR reenvia `CONFIG_TEAMS N`;
- a fronteira da contagem não aceita apertos anteriores ao `JÁ!`.
