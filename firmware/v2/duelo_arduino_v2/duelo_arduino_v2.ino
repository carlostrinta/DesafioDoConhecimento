/*
 * Desafio do Conhecimento — Firmware de produção v2
 *
 * Arduino Uno, protocolo v2, 10 botões em D2–D11 (INPUT_PULLUP).
 * Não usa LEDs nem buzzer: o feedback visual/sonoro fica no aplicativo.
 *
 * Handshake:
 *   PRONTO
 *   VERSAO 2
 *
 * Comandos PC -> Arduino:
 *   CONFIG_TEAMS 2|3|4  -> EQUIPES N
 *   CONFIG_TEAMS 5|X    -> ERRO EQUIPES
 *   CONFIG_TEAMS vazio  -> ERRO EQUIPES
 *   RESET               -> limpa o estado de debounce (sem saída física)
 *   LED_*/BEEP*/BUZZER* -> ignorados (compatibilidade; não há saída física)
 *
 * Eventos Arduino -> PC:
 *   BTN_A, BTN_B, BTN_AVANCAR, BTN_ACERTO_A, BTN_ACERTO_B,
 *   BTN_REVELAR, BTN_C, BTN_D, BTN_ACERTO_C, BTN_ACERTO_D
 *
 * Só envia BTN_C/BTN_D e BTN_ACERTO_C/BTN_ACERTO_D quando a equipe
 * correspondente está ativa em CONFIG_TEAMS. Avançar/revelar sempre valem.
 * Debounce de 60 ms, sem delay().
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

const uint8_t EQUIPES_PADRAO = 4;
const uint8_t MIN_EQUIPES = 2;
const uint8_t MAX_EQUIPES = 4;

// ---------- Controle de debounce ----------
struct Botao {
  uint8_t pino;
  const char* evento;
  char equipe;          // 'A'..'D' ou 0 para ações globais
  bool estadoAnterior;
  uint32_t ultimoTempo;
};

Botao botoes[] = {
  {BTN_A,        "BTN_A",        'A', HIGH, 0},
  {BTN_B,        "BTN_B",        'B', HIGH, 0},
  {BTN_AVANCAR,  "BTN_AVANCAR",  0,   HIGH, 0},
  {BTN_ACERTO_A, "BTN_ACERTO_A", 'A', HIGH, 0},
  {BTN_ACERTO_B, "BTN_ACERTO_B", 'B', HIGH, 0},
  {BTN_REVELAR,  "BTN_REVELAR",  0,   HIGH, 0},
  {BTN_C,        "BTN_C",        'C', HIGH, 0},
  {BTN_D,        "BTN_D",        'D', HIGH, 0},
  {BTN_ACERTO_C, "BTN_ACERTO_C", 'C', HIGH, 0},
  {BTN_ACERTO_D, "BTN_ACERTO_D", 'D', HIGH, 0}
};

const uint8_t NUM_BOTOES = sizeof(botoes) / sizeof(botoes[0]);
const uint16_t DEBOUNCE_MS = 60;

uint8_t equipesAtivas = EQUIPES_PADRAO;

// ---------- Buffer serial fixo ----------
const uint8_t TAM_BUFFER_SERIAL = 32;
char bufferSerial[TAM_BUFFER_SERIAL];
uint8_t tamBufferSerial = 0;
bool bufferEstourado = false;

// ---------- Utilidades ----------
bool equipeAtiva(char equipe) {
  if (equipe == 0) {
    return true;
  }
  return (uint8_t)(equipe - 'A') < equipesAtivas;
}

void resetarDebounce() {
  for (uint8_t i = 0; i < NUM_BOTOES; i++) {
    botoes[i].estadoAnterior = digitalRead(botoes[i].pino) == LOW;
    botoes[i].ultimoTempo = millis();
  }
}

void setup() {
  Serial.begin(9600);

  for (uint8_t i = 0; i < NUM_BOTOES; i++) {
    pinMode(botoes[i].pino, INPUT_PULLUP);
    botoes[i].estadoAnterior = digitalRead(botoes[i].pino) == LOW;
    botoes[i].ultimoTempo = 0;
  }

  equipesAtivas = EQUIPES_PADRAO;

  // O aplicativo espera PRONTO e, logo depois, VERSAO 2.
  Serial.println(F("PRONTO"));
  Serial.println(F("VERSAO 2"));
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
        && (agora - botoes[i].ultimoTempo) >= DEBOUNCE_MS
        && equipeAtiva(botoes[i].equipe)) {
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
  const uint8_t prefixo = 12;  // "CONFIG_TEAMS"

  if (strncmp(cmd, "CONFIG_TEAMS", prefixo) == 0) {
    const char* valor = cmd + prefixo;
    if (*valor == ' ') {
      ++valor;
    }

    if (valor[0] >= '2' && valor[0] <= '4' && valor[1] == '\0') {
      equipesAtivas = (uint8_t)(valor[0] - '0');
      Serial.print(F("EQUIPES "));
      Serial.println((int)equipesAtivas);
    } else {
      Serial.println(F("ERRO EQUIPES"));
    }
    return;
  }

  if (strcmp(cmd, "RESET") == 0) {
    resetarDebounce();
    return;
  }

  // LED_*, BEEP, BEEP_LONG, BUZZER_*: sem saída física no v2. Ignorar
  // mantém compatibilidade com o aplicativo e evita linhas de erro no log.
}
