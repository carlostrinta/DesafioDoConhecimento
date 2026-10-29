# Firmware

Os sketches ficam todos nesta pasta, cada um na própria pasta de sketch do
Arduino IDE. Não há mais cópia do v1 na raiz do projeto.

| Versão | Arquivo | Uso |
| --- | --- | --- |
| v1 | [`v1/duelo_arduino_v1/duelo_arduino_v1.ino`](v1/duelo_arduino_v1/duelo_arduino_v1.ino) | firmware congelado, 2 equipes, LEDs/buzzer |
| bancada | [`bancada_botoes/bancada_botoes.ino`](bancada_botoes/bancada_botoes.ino) | validação dos 10 botões e do parser |
| v2 | [`v2/duelo_v2/duelo_v2.ino`](v2/duelo_v2/duelo_v2.ino) | produção v2, 4 equipes, sem LEDs/buzzer |

## Validação

O firmware v2 de produção foi **validado no Arduino Uno e no Mega 2560**. A
bancada de 10 botões também foi validada. O **clone CH340** com firmware v2
continua como pendência explícita: se o `PRONTO` demorar mais de 3 s após o
reset por DTR, aumente `serial.timeout_pronto` no `config.json`.

O roteiro completo, incluindo a matriz PC v1/v2 × firmware v1/v2, está em
[`v2/ROTEIRO_VALIDACAO.md`](v2/ROTEIRO_VALIDACAO.md).

O [v1](v1/README.md) é um ponto de retorno congelado: não edite o conteúdo
dele para implementar mudanças novas.
