/*
 * Duelo de Conhecimento — Sketch de bancada dos botões
 *
 * Valida somente o hardware dos 10 botões no Arduino Uno:
 *   D2  BTN_A        D7  BTN_REVELAR
 *   D3  BTN_B        D8  BTN_C
 *   D4  BTN_AVANCAR  D9  BTN_D
 *   D5  BTN_ACERTO_A D10 BTN_ACERTO_C
 *   D6  BTN_ACERTO_B D11 BTN_ACERTO_D
 *
 * Não aciona LED nem buzzer e não envia PRONTO/VERSAO 2: a validação é feita
 * pelo Monitor Serial (9600 baud). Use o aplicativo fechado para não disputar
 * a porta.
 *
 * Comandos aceitos:
 *   CONFIG_TEAMS 2|3|4  -> responde "EQUIPES N" (ACK)
 *
 * Cada aperto (borda de descida) envia o nome do botão. O estado inicial é
 * lido no setup() e cada botão tem lockout de 60 ms. Não há delay().
 */

#include <string.h>

// ---------- Mapa de pinos ----------
const uint8_t BTN_A        = 2;
const uint8_t BTN_B        = 3;
const uint8_t BTN_AVANCAR  = 4;
const uint8_t BTN_ACERTO_A = 5;
const uint8_t BTN_ACERTO_B = 6;
const uint8_t BTN_REVELAR  = 7;
const uint8_t BTN_C        = 8;
const uint8_t BTN_D        = 9;
const uint8_t BTN_ACERTO_C = 10;
const uint8_t BTN_ACERTO_D = 11;

// ---------- Controle de debounce ----------
struct Botao {
  uint8_t pino;
  const char* evento;
  bool estadoAnterior;
  uint32_t ultimoTempo;
};

Botao botoes[] = {
  {BTN_A,        "BTN_A",        HIGH, 0},
  {BTN_B,        "BTN_B",        HIGH, 0},
  {BTN_AVANCAR,  "BTN_AVANCAR",  HIGH, 0},
  {BTN_ACERTO_A, "BTN_ACERTO_A", HIGH, 0},
  {BTN_ACERTO_B, "BTN_ACERTO_B", HIGH, 0},
  {BTN_REVELAR,  "BTN_REVELAR",  HIGH, 0},
  {BTN_C,        "BTN_C",        HIGH, 0},
  {BTN_D,        "BTN_D",        HIGH, 0},
  {BTN_ACERTO_C, "BTN_ACERTO_C", HIGH, 0},
  {BTN_ACERTO_D, "BTN_ACERTO_D", HIGH, 0}
};

const uint8_t NUM_BOTOES = sizeof(botoes) / sizeof(botoes[0]);
const uint16_t DEBOUNCE_MS = 60;

// ---------- Buffer serial fixo ----------
const uint8_t TAM_BUFFER_SERIAL = 32;
char bufferSerial[TAM_BUFFER_SERIAL];
uint8_t tamBufferSerial = 0;
bool bufferEstourado = false;

void setup() {
  Serial.begin(9600);

  for (uint8_t i = 0; i < NUM_BOTOES; i++) {
    pinMode(botoes[i].pino, INPUT_PULLUP);
    botoes[i].estadoAnterior = digitalRead(botoes[i].pino) == LOW;
    botoes[i].ultimoTempo = 0;
  }

  Serial.println(F("BANCADA_BOTOES"));
}

void loop() {
  lerBotoes();
  lerSerial();
}

void lerBotoes() {
  uint32_t agora = millis();

  for (uint8_t i = 0; i < NUM_BOTOES; i++) {
    bool estado = digitalRead(botoes[i].pino) == LOW;

    if (estado && !botoes[i].estadoAnterior
        && (agora - botoes[i].ultimoTempo) >= DEBOUNCE_MS) {
      Serial.println(botoes[i].evento);
      botoes[i].ultimoTempo = agora;
    }

    botoes[i].estadoAnterior = estado;
  }
}

void lerSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n') {
      bufferSerial[tamBufferSerial] = '\0';
      if (!bufferEstourado && tamBufferSerial > 0) {
        processarComando(bufferSerial);
      }
      tamBufferSerial = 0;
      bufferEstourado = false;
    } else if (c != '\r') {
      if (tamBufferSerial < TAM_BUFFER_SERIAL - 1) {
        bufferSerial[tamBufferSerial++] = c;
      } else {
        bufferEstourado = true;
      }
    }
  }
}

void processarComando(const char* cmd) {
  const uint8_t prefixo = 13;  // "CONFIG_TEAMS "

  if (strncmp(cmd, "CONFIG_TEAMS ", prefixo) == 0) {
    const char* valor = cmd + prefixo;
    if (valor[0] >= '2' && valor[0] <= '4' && valor[1] == '\0') {
      uint8_t equipes = (uint8_t)(valor[0] - '0');
      Serial.print(F("EQUIPES "));
      Serial.println((int)equipes);
    }
  }
}
