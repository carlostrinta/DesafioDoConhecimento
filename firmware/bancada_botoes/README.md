# Bancada dos 10 botões

Sketch de validação **somente de hardware** para o Arduino Uno. Ele não
implementa o protocolo v2 de produção, não envia `PRONTO`/`VERSAO 2` e não
aciona LEDs ou buzzer. O objetivo é provar os 10 botões, o parser de
`CONFIG_TEAMS` e o debounce antes de liberar o firmware v2.

## Ligação

Use `INPUT_PULLUP`: cada botão fica entre o pino e o **GND**.

| Pino | Evento | Pino | Evento |
| --- | --- | --- | --- |
| `D2` | `BTN_A` | `D7` | `BTN_REVELAR` |
| `D3` | `BTN_B` | `D8` | `BTN_C` |
| `D4` | `BTN_AVANCAR` | `D9` | `BTN_D` |
| `D5` | `BTN_ACERTO_A` | `D10` | `BTN_ACERTO_C` |
| `D6` | `BTN_ACERTO_B` | `D11` | `BTN_ACERTO_D` |

## Procedimento

1. Abra `bancada_botoes.ino` na Arduino IDE, selecione **Arduino Uno** e a
   porta correta e faça o upload.
2. Abra o **Monitor Serial** em **9600 baud** e feche o aplicativo do jogo.
3. Confirme a linha inicial `BANCADA_BOTOES`.
4. Envie os comandos e confira as respostas:

   | Comando | Resposta esperada |
   | --- | --- |
   | `CONFIG_TEAMS 2` | `EQUIPES 2` |
   | `CONFIG_TEAMS 3` | `EQUIPES 3` |
   | `CONFIG_TEAMS 4` | `EQUIPES 4` |
   | `CONFIG_TEAMS 5` | `ERRO EQUIPES` |
   | `CONFIG_TEAMS X` | `ERRO EQUIPES` |
   | `CONFIG_TEAMS 22` | `ERRO EQUIPES` |
   | `CONFIG_TEAMS` | `ERRO EQUIPES` |

5. Aperte cada botão, um de cada vez, e confira o evento correspondente na
   tabela de pinos. Solte o botão entre os testes.
6. Debounce de **60 ms**:
   - mantenha o botão pressionado: deve sair **uma única linha**;
   - aperte e solte rapidamente duas vezes: dois eventos se o intervalo for
     maior que 60 ms; um único evento se for menor;
   - repita em pelo menos dois botões diferentes.
7. Anote placa, porta, driver e qualquer divergência. Se algum pino não
   responder, confira a ligação para GND antes de alterar o firmware.

## Critério para liberar o v2

O firmware v2 de produção só deve ser mesclado na `main` depois que:

- os 10 botões forem lidos nos pinos D2–D11;
- `CONFIG_TEAMS 2`, `3` e `4` responderem `EQUIPES N`;
- `CONFIG_TEAMS 5`, `X`, `22` e vazio responderem `ERRO EQUIPES`;
- o debounce de 60 ms não produzir eventos repetidos com o botão mantido.

O resultado deve ser registrado no pull request da branch `etapa5-firmware`.
