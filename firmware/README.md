# Firmware

Os sketches ficam todos nesta pasta, cada um na própria pasta de sketch do
Arduino IDE. Não há mais cópia do v1 na raiz do projeto.

| Versão | Arquivo | Uso |
| --- | --- | --- |
| v1 | [`v1/duelo_arduino_v1/duelo_arduino_v1.ino`](v1/duelo_arduino_v1/duelo_arduino_v1.ino) | firmware congelado, 2 equipes, LEDs/buzzer |
| bancada | [`bancada_botoes/bancada_botoes.ino`](bancada_botoes/bancada_botoes.ino) | validação dos 10 botões e do parser |
| v2 | [`v2/duelo_v2/duelo_v2.ino`](v2/duelo_v2/duelo_v2.ino) | produção v2 em validação, 4 equipes, sem LEDs/buzzer |

## Validação

O firmware v2 de produção está **EM VALIDAÇÃO**. A bancada de 10 botões já foi
validada; falta executar o roteiro do v2 com o aplicativo:

1. Gravar e validar a [bancada](bancada_botoes/README.md) no Arduino Uno.
2. Gravar o [v2](v2/README.md) e testar o aplicativo com 4 equipes.
3. Só depois da confirmação do Carlos, integrar na `main` e criar a tag de
   release.

O roteiro completo está em
[`v2/ROTEIRO_VALIDACAO.md`](v2/ROTEIRO_VALIDACAO.md).

O [v1](v1/README.md) é um ponto de retorno congelado: não edite o conteúdo
dele para implementar mudanças novas.
