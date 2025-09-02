// Minimal OOK Beacon (very low power) — non-critical use only
// TX pin toggles a shunt (shorted BJT/MOSFET) across LC tank.

const int TX_PIN = 5;

void setup() {
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);
}

void loop() {
  beaconBurst("JZ");       // send a short ID twice
  delay(3000 + analogRead(A0));  // pseudo-random backoff (noise-coupled)
}

void beaconBurst(const char* s) {
  for (const char* p = s; *p; ++p) {
    sendCharOOK(*p);
    delay(50);
  }
}

void sendCharOOK(char c) {
  for (int i = 0; i < 8; ++i) {
    bool bit1 = (c >> (7 - i)) & 1;
    if (bit1) keyOn(6); else keyOff(6);
    delay(2);
  }
  keyOff(20);
}

inline void keyOn(int ms)  { digitalWrite(TX_PIN, HIGH); delay(ms); }
inline void keyOff(int ms) { digitalWrite(TX_PIN, LOW);  delay(ms); }
