# Firmware

Os sketches ficam todos nesta pasta, cada um na própria pasta de sketch do
Arduino IDE. Não há mais cópia do v1 na raiz do projeto.

| Versão | Arquivo | Uso |
| --- | --- | --- |
| v1 | [`v1/duelo_arduino_v1/duelo_arduino_v1.ino`](v1/duelo_arduino_v1/duelo_arduino_v1.ino) | firmware congelado, 2 equipes, LEDs/buzzer |
| bancada | [`bancada_botoes/bancada_botoes.ino`](bancada_botoes/bancada_botoes.ino) | validação dos 10 botões e do parser |
| v2 | [`v2/duelo_arduino_v2/duelo_arduino_v2.ino`](v2/duelo_arduino_v2/duelo_arduino_v2.ino) | produção v2, 4 equipes, sem LEDs/buzzer |

## Validação

O v2 foi validado no Arduino Uno em 29/10/2026. A ordem executada foi:

1. Gravar e validar a [bancada](bancada_botoes/README.md) no Arduino Uno.
2. Gravar o [v2](v2/README.md) e testar o aplicativo com 4 equipes.
3. Integrar a branch `etapa5-firmware` na `main` e criar a tag de release.

A branch foi integrada e a tag de release criada depois dessa validação.

O [v1](v1/README.md) é um ponto de retorno congelado: não edite o conteúdo
dele para implementar mudanças novas.
