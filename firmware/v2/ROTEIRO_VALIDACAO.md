# Roteiro de validação do firmware v2

**Status: EM VALIDAÇÃO.** Este roteiro precisa ser executado no hardware real
antes da liberação do firmware v2 e da tag `v2.8.0-firmware-v2`.

Os testes automatizados usam porta falsa e cobrem handshake, ACK, retentativa,
fallback, reset por DTR e ausência de comandos v1 no modo v2. Eles **não**
substituem a validação física dos pinos, do clone CH340, do Mega e do `.exe`.

## 1. Placas e papéis

| Placa | Papel | Obrigatória |
| --- | --- | --- |
| Arduino Uno original (`2341:0043`) | placa principal; gravação e teste completo | sim |
| Clone Uno com CH340 (`1A86:7523`) | driver/porta e repetição do teste principal | sim |
| Arduino Mega 2560 (`2341:0042`) | placa complementar; mesma pinagem D2–D11 | recomendada |
| Arduino Uno com firmware v1 | regressão do caminho v1 | recomendada |

O firmware v2 usa somente D2–D11 como botões e não usa LEDs nem buzzer. O
`D0`/`D1` continua reservado para a serial/USB.

## 2. Antes de ligar

1. Desligue a placa e desconecte o USB.
2. **Remova toda a fiação antiga de LED/buzzer dos pinos D8, D9 e D10.** No
   firmware v1 esses pinos eram `LED_A`, `LED_B` e `BUZZER`; no v2 eles são
   botões. Mantê-los ligados a LEDs/buzzer pode causar leituras falsas.
3. Confirme que D11 não tem fiação antiga (no v1 ele era livre).
4. Religue somente os 10 botões entre o pino e o GND, com `INPUT_PULLUP`.
   Não use resistores externos de pull-up.
5. Com o multímetro, confira continuidade de cada botão entre o pino e o GND
   quando pressionado. Verifique também que não há curto entre pinos vizinhos
   nem entre um pino e 5 V.
6. Confira a pinagem:

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

## 3. Gravação

1. Abra [`duelo_v2/duelo_v2.ino`](duelo_v2/duelo_v2.ino) na Arduino IDE.
2. Selecione a placa (Uno ou Mega) e a porta correta.
3. Faça o upload.
4. Feche o Monitor Serial antes de abrir o aplicativo.
5. Abra o Monitor Serial a 9600 baud e pressione o reset da placa. A saída deve
   ser exatamente:

   ```text
   PRONTO
   VERSAO 2
   ```

## 4. Matriz de compatibilidade PC × firmware

| PC | Firmware | Resultado esperado | Como validar |
| --- | --- | --- | --- |
| v1 | v1 | 2 equipes; A/B, acertos, avançar/revelar; LEDs/buzzer ativos; `RESET` ao fechar | regressão com build anterior e sketch v1 |
| v1 | v2 | PC v1 ignora `VERSAO 2`/`EQUIPES N`; o firmware ignora `LED_*`, `BEEP*`, `BUZZER_*` e `RESET`; somente A/B têm efeito no jogo | build anterior + v2; conferir que C/D não entram e que não há LED/buzzer |
| v2 | v1 | PC v2 detecta v1, limita a 2 equipes e preserva LEDs/buzzer e `RESET` | gravar v1 e abrir o app desta branch |
| v2 | v2 | 2 a 4 equipes; `CONFIG_TEAMS N` + ACK `EQUIPES N`; sem comandos de LED/buzzer/RESET; C/D ativos quando N ≥ 3/4 | teste principal abaixo |

Observação: o firmware v2 **não** tem LEDs nem buzzer. No cruzamento
PC v1 + firmware v2, o feedback visual/sonoro continua apenas no PC.

## 5. Teste do firmware sem o aplicativo

Use o Monitor Serial a 9600 baud, com o aplicativo fechado.

| # | Ação | Esperado |
| --- | --- | --- |
| 1 | Pressione o reset | `PRONTO` e `VERSAO 2`, uma vez |
| 2 | Envie `CONFIG_TEAMS 2` | `EQUIPES 2` |
| 3 | Envie `CONFIG_TEAMS 3` | `EQUIPES 3` |
| 4 | Envie `CONFIG_TEAMS 4` | `EQUIPES 4` |
| 5 | Envie `CONFIG_TEAMS 5` | `EQUIPES 4` (mantém o atual) |
| 6 | Envie `CONFIG_TEAMS X` | `EQUIPES 4` |
| 7 | Envie `CONFIG_TEAMS 22` | `EQUIPES 4` |
| 8 | Envie `CONFIG_TEAMS` (vazio) | `EQUIPES 4` |
| 9 | Envie `LED_A_ON`, `BEEP`, `BEEP_LONG`, `BUZZER_ON`, `RESET` | nenhuma saída e nenhum evento de botão |
| 10 | Envie um comando desconhecido | nenhuma resposta |
| 11 | Com `EQUIPES 2`, aperte C, D, ACERTO_C e ACERTO_D | nenhum evento |
| 12 | Com `EQUIPES 3`, aperte C/ACERTO_C e D/ACERTO_D | eventos de C; nenhum de D |
| 13 | Com `EQUIPES 4`, aperte os 10 botões | todos os eventos corretos |
| 14 | Mantenha A pressionado por 2 s | somente um `BTN_A` |
| 15 | Solte A e aperte de novo depois de 60 ms | novo `BTN_A`; soltar não gera evento |
| 16 | Envie uma linha com mais de 31 caracteres e depois `\n` | linha descartada; o próximo comando válido funciona |
| 17 | Use `\r\n` no Monitor Serial | aceito como uma linha |

Para o item 16, não é necessário decorar o buffer: envie
`CONFIG_TEAMS 222222222222222222222222222222` e depois `CONFIG_TEAMS 2`; a
segunda linha deve responder normalmente.

## 6. Teste principal com o aplicativo (PC v2 + firmware v2)

Prepare um `config.json` local com `"num_equipes": 4`. O envio de
`CONFIG_TEAMS` é automático quando o app detecta o v2. **Não altere
`config.exemplo.json`.**

1. Inicie o app com a placa conectada. Em até `serial.timeout_pronto`
   (padrão 3 s), o status deve ficar conectado.
2. No log, confira `PRONTO`, `VERSAO 2` e o envio de `CONFIG_TEAMS 4`.
3. O Arduino deve responder `EQUIPES 4`. O ACK normal é registrado em DEBUG.
4. Escolha um tema e inicie uma partida com 4 equipes.
5. Confirme que A, B, C e D acendem/entram no placar corretamente.
6. Confirme acertos A/B/C/D, `AVANÇAR` e `REVELAR`.
7. Confirme que o app v2 **não** envia `LED_*`, `BEEP*`, `BUZZER_*` nem
   `RESET` em nenhum momento, inclusive ao fechar.
8. A cada pergunta nova, confira no log um novo `CONFIG_TEAMS 4` e o ACK
   `EQUIPES 4`.
9. Pressione o reset físico da placa **no meio de uma rodada**. O app deve
   receber `PRONTO` + `VERSAO 2` e enviar `CONFIG_TEAMS 4` imediatamente,
   sem esperar a próxima pergunta.
10. Tire e recoloque o cabo USB. A reconexão deve repetir o handshake, o envio
    de `CONFIG_TEAMS 4` e o ACK.

### ACK perdido ou divergente

O fluxo de retentativa e aviso é coberto por `pytest` com porta falsa. Para
repetir no hardware sem alterar o firmware de produção, use uma cópia de teste
do sketch que ignore `CONFIG_TEAMS` ou responda um valor diferente:

- primeira falha: WARNING e **uma** retentativa;
- segunda falha: WARNING + aviso visível `Arduino não confirmou 4 equipes`;
- a partida continua em 2 equipes, e o protocolo detectado permanece v2;
- o aviso não pode desaparecer silenciosamente antes do `JÁ!`.

Se não for possível usar uma cópia de teste, registre que esse item foi
validado apenas pelos testes automatizados.

## 7. Fronteira da contagem

Com `contagem_largada` em 3 (padrão):

1. Inicie a pergunta e aguarde o overlay `3`, `2`, `1`.
2. Aperte A/B/C/D durante a contagem. Nenhuma equipe deve ganhar a vez.
3. Aperte uma equipe imediatamente depois do `JÁ!`. A equipe deve ganhar.
4. Segure um botão durante a contagem e solte depois do `JÁ!`. O aperto antigo
   não pode valer; é preciso soltar e apertar de novo.
5. Repita com `contagem_largada: 0` e confirme que a pergunta já começa em
   `AGUARDANDO`.

## 8. Clone CH340 e Mega

1. Repita as seções 3, 5, 6 e 7 no clone CH340. O driver deve abrir a porta sem
   travar e o app deve reconhecer a placa.
2. Repita no Mega 2560. A pinagem D2–D11 é a mesma; confira apenas a porta e a
   placa selecionada na IDE.
3. Anote porta, VID/PID, driver e qualquer diferença de tempo de conexão.

## 9. Regressão do caminho v1

1. Grave o firmware v1 em um Uno (ou use outra placa).
2. Abra o app desta branch. Ele deve detectar v1, limitar a partida a 2 equipes
   e continuar enviando `LED_*`, `BEEP` e `RESET` como antes.
3. Confirme que LEDs e buzzer do v1 continuam funcionando.
4. Confirme que o fechamento do app no v1 ainda envia `RESET`.

## 10. Critérios de aceite

A validação só está concluída quando todos os itens abaixo forem verdadeiros:

- [ ] Os 10 botões respondem nos pinos D2–D11, sem fiação antiga de LED/buzzer
      em D8–D10.
- [ ] `PRONTO` + `VERSAO 2` aparecem uma vez por boot.
- [ ] `CONFIG_TEAMS 2`, `3` e `4` respondem `EQUIPES N`.
- [ ] `CONFIG_TEAMS 5`, `X`, `22` e vazio respondem `EQUIPES <atual>`.
- [ ] C/ACERTO_C só funcionam com N ≥ 3; D/ACERTO_D só com N = 4.
- [ ] O lockout de 60 ms não repete evento com o botão mantido.
- [ ] `LED_*`, `BEEP*`, `BUZZER_*`, `RESET` e comandos desconhecidos são
      ignorados pelo firmware v2.
- [ ] O PC v2 confirma o ACK `EQUIPES N` sem bloquear a contagem.
- [ ] ACK perdido/divergente gera WARNING, uma retentativa e, na segunda falha,
      o aviso visível `Arduino não confirmou N equipes`.
- [ ] O PC v2 não envia `LED_*`, `BEEP*`, `BUZZER_*` nem `RESET`, inclusive no
      fechamento.
- [ ] Reset por DTR no meio da rodada reenvia `CONFIG_TEAMS N` imediatamente.
- [ ] A fronteira da contagem continua rejeitando apertos antes do `JÁ!`.
- [ ] O caminho v1 continua funcionando com LEDs/buzzer e `RESET` ao fechar.
- [ ] `pytest` verde em Python 3.12.15 e na versão atual do ambiente.
- [ ] Smoke Tk percorre tema, contagem e `AGUARDANDO`.
- [ ] O teste foi repetido no Uno original, no clone CH340 e no Mega (quando
      disponível).

## 11. Resultado

Preencher após a execução:

- Data:
- Placas testadas:
- Portas/drivers:
- Python usado:
- Observações:
- Aprovado por:
