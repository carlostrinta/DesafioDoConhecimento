/*
 * Duelo de Conhecimento — Firmware Arduino Uno
 * Versão 1.0
 *
 * Lê 6 botões (INPUT_PULLUP), controla 2 LEDs e 1 buzzer.
 * Comunica-se com o Windows via serial (9600 baud, linhas terminadas em \n).
 */

// ---------- Mapa de pinos ----------
const uint8_t BTN_A        = 2;
const uint8_t BTN_B        = 3;
const uint8_t BTN_AVANCAR  = 4;
const uint8_t BTN_ACERTO_A = 5;
const uint8_t BTN_ACERTO_B = 6;
const uint8_t BTN_REVELAR  = 7;
const uint8_t LED_A        = 8;
const uint8_t LED_B        = 9;
const uint8_t BUZZER       = 10;

// ---------- Controle de debounce ----------
struct Botao {
  uint8_t pino;
  const char* evento;
  bool estadoAnterior;
  unsigned long ultimoTempo;
};

Botao botoes[] = {
  {BTN_A,        "BTN_A",        HIGH, 0},
  {BTN_B,        "BTN_B",        HIGH, 0},
  {BTN_AVANCAR,  "BTN_AVANCAR",  HIGH, 0},
  {BTN_ACERTO_A, "BTN_ACERTO_A", HIGH, 0},
  {BTN_ACERTO_B, "BTN_ACERTO_B", HIGH, 0},
  {BTN_REVELAR,  "BTN_REVELAR",  HIGH, 0}
};
const uint8_t NUM_BOTOES = sizeof(botoes) / sizeof(botoes[0]);
const unsigned long DEBOUNCE_MS = 60;

// ---------- Buffer serial ----------
String bufferSerial = "";

void setup() {
  Serial.begin(9600);

  for (uint8_t i = 0; i < NUM_BOTOES; i++) {
    pinMode(botoes[i].pino, INPUT_PULLUP);
  }
  pinMode(LED_A, OUTPUT);
  pinMode(LED_B, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  digitalWrite(LED_A, LOW);
  digitalWrite(LED_B, LOW);
  digitalWrite(BUZZER, LOW);

  // Sinal de vida
  Serial.println("PRONTO");
}

void loop() {
  lerBotoes();
  lerSerial();
}

void lerBotoes() {
  unsigned long agora = millis();
  for (uint8_t i = 0; i < NUM_BOTOES; i++) {
    bool estado = digitalRead(botoes[i].pino);
    if (estado == LOW && botoes[i].estadoAnterior == HIGH
        && (agora - botoes[i].ultimoTempo) > DEBOUNCE_MS) {
      Serial.println(botoes[i].evento);
      botoes[i].ultimoTempo = agora;
    }
    botoes[i].estadoAnterior = estado;
  }
}

void lerSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      bufferSerial.trim();
      if (bufferSerial.length() > 0) {
        processarComando(bufferSerial);
      }
      bufferSerial = "";
    } else if (c != '\r') {
      bufferSerial += c;
      if (bufferSerial.length() > 32) bufferSerial = ""; // proteção
    }
  }
}

void processarComando(const String& cmd) {
  if (cmd == "LED_A_ON")       digitalWrite(LED_A, HIGH);
  else if (cmd == "LED_A_OFF") digitalWrite(LED_A, LOW);
  else if (cmd == "LED_B_ON")  digitalWrite(LED_B, HIGH);
  else if (cmd == "LED_B_OFF") digitalWrite(LED_B, LOW);
  else if (cmd == "BUZZER_ON") digitalWrite(BUZZER, HIGH);
  else if (cmd == "BUZZER_OFF")digitalWrite(BUZZER, LOW);
  else if (cmd == "BEEP") {
    digitalWrite(BUZZER, HIGH);
    delay(120);
    digitalWrite(BUZZER, LOW);
  }
  else if (cmd == "BEEP_LONG") {
    digitalWrite(BUZZER, HIGH);
    delay(600);
    digitalWrite(BUZZER, LOW);
  }
  else if (cmd == "RESET") {
    digitalWrite(LED_A, LOW);
    digitalWrite(LED_B, LOW);
    digitalWrite(BUZZER, LOW);
  }
}