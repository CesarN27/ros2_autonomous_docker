#include <Arduino.h>

#define TRIG_PIN 25
#define ECHO_PIN 26

#define RXD2 16
#define TXD2 17

long duration;
float distance;

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Serial.begin(115200);        // Debug USB
  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);  // UART hacia Raspberry
}

float readUltrasonic() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  duration = pulseIn(ECHO_PIN, HIGH);
  distance = duration * 0.034 / 2;

  return distance;
}

void loop() {
  float d = readUltrasonic();

  // Enviar por USB (debug)
  Serial.print("Distancia: ");
  Serial.print(d);
  Serial.println(" cm");

  // Enviar a Raspberry por UART
  Serial2.println(d);

  delay(200);
}
