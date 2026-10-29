# Firmware v2 — produção

**Status: em validação na branch `etapa5-firmware`.** Não mesclar na `main`
antes de validar o sketch de bancada no Arduino Uno.

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

`D0`/`D1` continuam reservados para a serial/USB.

## Protocolo

Arduino → PC, no `setup()`:

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
| `CONFIG_TEAMS 5` | `ERRO EQUIPES` | não altera |
| `CONFIG_TEAMS X` | `ERRO EQUIPES` | não altera |
| `CONFIG_TEAMS 22` | `ERRO EQUIPES` | não altera |
| `CONFIG_TEAMS` (sem valor) | `ERRO EQUIPES` | não altera |
| `RESET` | — | reinicia o debounce |
| `LED_*`, `BEEP*`, `BUZZER_*` | — | ignorados (sem saída física) |

Eventos enviados: `BTN_A`, `BTN_B`, `BTN_AVANCAR`, `BTN_ACERTO_A`,
`BTN_ACERTO_B`, `BTN_REVELAR`, `BTN_C`, `BTN_D`, `BTN_ACERTO_C`,
`BTN_ACERTO_D`.

Os eventos de C/D só são enviados quando `CONFIG_TEAMS` ativou essas equipes.
O debounce é de **60 ms** e não há `delay()` no loop.

## Como gravar

1. Abra `duelo_arduino_v2/duelo_arduino_v2.ino` na Arduino IDE.
2. Selecione **Arduino Uno** e a porta correta.
3. Faça o upload e feche o Monitor Serial antes de abrir o jogo.
4. O aplicativo deve mostrar o status de Arduino conectado e reconhecer
   `VERSAO 2`.

## Critério de liberação

Antes de mesclar na `main`, execute o roteiro
[`firmware/bancada_botoes/README.md`](../bancada_botoes/README.md) e registre
no pull request:

- os 10 botões e seus eventos;
- `CONFIG_TEAMS 2`, `3`, `4` com ACK;
- `CONFIG_TEAMS 5`, `X` e `22` com `ERRO EQUIPES`;
- o debounce de 60 ms sem repetição com o botão mantido.

Depois disso, valide o aplicativo completo com o firmware v2 e só então faça
o merge, o push e a tag de release.
