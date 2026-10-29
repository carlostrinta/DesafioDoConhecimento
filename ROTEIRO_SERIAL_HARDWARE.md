# Roteiro de validação serial com hardware real

Os testes automatizados usam portas falsas. **Só o hardware real valida:**

- o driver do Windows abrindo/fechando portas Bluetooth (COM3/COM4) sem travar;
- o tempo real entre abrir a porta e o `PRONTO` do firmware (reset por DTR);
- a reconexão física (tirar/voltar o cabo USB, trocar de porta);
- o comportamento do clone CH340 (VID `1A86:7523`) com o driver instalado;
- o `.exe` empacotado (PyInstaller) e o encerramento do processo.

## Antes de começar

1. Feche o app.
2. Gerenciador de Dispositivos → **Portas (COM e LPT)**. Anote as portas.
   Bluetooth aparece como *Serial Padrão por link Bluetooth* (sem VID/PID).
3. Para ver VID/PID de cada porta:

   ```powershell
   python -c "import serial.tools.list_ports as lp; [print(p.device, p.description, p.vid and format(p.vid,'04X'), p.pid and format(p.pid,'04X')) for p in lp.comports()]"
   ```

   Arduino Uno original: `2341:0043`. Mega: `2341:0042`. Clone CH340: `1A86:7523`.

## Roteiro

| # | Ação | Esperado |
| --- | --- | --- |
| 1 | **Sem placa**, abra o app | status "Arduino não conectado"; **nunca** "Arduino conectado (COM4)" |
| 2 | Sem placa, clique no **X** | janela fecha; processo some do Gerenciador de Tarefas em ~1 s |
| 3 | Conecte o **Uno original** | em até 3 s: "Arduino conectado (COMx)" |
| 4 | Aperte A/B, REVELAR, AVANÇAR | mesmas ações do teclado; LED e bipe corretos |
| 5 | **Tire o cabo** | em ~1 s volta para "não conectado"; não assume a COM4 |
| 6 | **Recoloque o cabo** (mesma porta) | reconecta em até 3 s |
| 7 | **Troque de porta USB** (ou use o clone) | reconecta na nova porta em até 3 s |
| 8 | Com o jogo numa rodada, aperte **RESET** na placa | "Arduino reiniciado." e o LED de quem apertou reacende |
| 9 | Feche o app com a placa conectada | LEDs apagam (`RESET`), porta fecha, processo termina |
| 10 | Repita 1–9 com o **clone CH340** | mesmo resultado (driver CH340 instalado) |
| 11 | Repita 1–10 no **`Desafio do Conhecimento.exe`** | mesmo resultado |
| 12 | Abra o app **sem placa** e deixe 1 min | console sem varredura infinita de portas; CPU baixa |

## Firmware v2 (somente depois da bancada)

Antes de liberar o v2, o sketch `firmware/bancada_botoes` precisa passar no
roteiro de [`firmware/bancada_botoes/README.md`](firmware/bancada_botoes/README.md).

Com o firmware v2 gravado:

1. Abra o app e confira o log: o Arduino deve enviar `PRONTO` e `VERSAO 2`.
2. Com 4 equipes, o app envia `CONFIG_TEAMS 4` e o Arduino responde
   `EQUIPES 4`.
3. Teste A/B/C/D, acertos A/B/C/D, `AVANÇAR` e `REVELAR`.
4. Em um teste separado, com o app fechado, use o Monitor Serial para enviar
   `CONFIG_TEAMS 2` e confirme que C/D deixam de gerar eventos; envie
   `CONFIG_TEAMS 5` e confira `ERRO EQUIPES`.
5. O v2 não tem LEDs nem buzzer: o feedback visual/sonoro deve continuar no PC.
6. Repita a reconexão (tirar/voltar o cabo) e o fechamento do app.

## Se algo falhar

- Porta certa, mas o app não conecta: confira se o firmware manda `PRONTO`
  no `setup()` (v1) e `PRONTO` + `VERSAO 2` (v2), e se o monitor serial está
  fechado.
- Porta fixa: em `config.py`, `PORTA_FORCADA = "COM6"` (tentada primeiro,
  mas ainda exige `PRONTO`).
- Driver: no Gerenciador de Dispositivos, desinstale a porta e reconecte.

## O que o teste automatizado já cobre

`tests/test_serial_comm.py` reproduz, com porta falsa: COM4 Bluetooth sem
`PRONTO` (nunca aceita), COM6 real, queda e volta em outra porta (COM7),
ausência total de portas, encerramento sem placa e com driver travado
(`parar()` em menos de 1,5 s), além de `RESET` ao fechar.
