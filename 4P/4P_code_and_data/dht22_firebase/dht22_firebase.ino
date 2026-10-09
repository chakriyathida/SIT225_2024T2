// SIT225 4P - the single DHT22 sensor (Arduino Nano 33 IoT on a USB phone charger, sends over WiFi)
// Reads the DHT22 every 30 seconds and POSTs it to Firebase Realtime Database at /readings/dht22.
// Firebase stamps each reading with its own server time (".sv": "timestamp"), so the board does not
// need a clock. Which room the sensor was in is worked out later from the time windows in config.py.
//
// Wiring (DHT22 module):  + -> 3.3V,  - -> GND,  OUT -> D2
// Libraries (Tools > Manage Libraries): "DHT sensor library" (Adafruit), "WiFiNINA", "ArduinoHttpClient"
// Board: Tools > Board > Arduino SAMD Boards > Arduino NANO 33 IoT

#include <WiFiNINA.h>
#include <ArduinoHttpClient.h>
#include "DHT.h"
#include "arduino_secrets.h"

#define DHTPIN 3
#define DHTTYPE DHT22
const unsigned long SAMPLE_MS = 30000;   // 30 s, same as the 3P protocol

DHT dht(DHTPIN, DHTTYPE);
WiFiSSLClient ssl;                               // HTTPS connection
HttpClient http(ssl, SECRET_FB_HOST, 443);

unsigned long lastSample = 0;
unsigned long sent = 0, failed = 0;              // simple counters, printed for the quality report

void connectWiFi() {
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Connecting to WiFi ");
    Serial.println(SECRET_SSID);
    WiFi.begin(SECRET_SSID, SECRET_PASS);
    delay(8000);
  }
  Serial.print("WiFi OK, IP: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(9600);
  delay(1500);                     // do NOT wait for Serial: the board must run on a charger with no laptop
  pinMode(LED_BUILTIN, OUTPUT);
  dht.begin();
  connectWiFi();

  // ---- start-up self-test: tells you which part is broken ----
  Serial.print("Firebase host: '"); Serial.print(SECRET_FB_HOST); Serial.println("'");
  if (ssl.connect(SECRET_FB_HOST, 443)) {
    Serial.println("SSL test: OK (board can reach Firebase)");
  } else {
    Serial.println("SSL test: FAILED -> check host spelling, then upload the host's SSL certificate "
                   "(Tools > Upload SSL Root Certificates / Firmware Updater)");
  }
  ssl.stop();
  float h0 = dht.readHumidity();
  Serial.print("DHT22 test on pin D"); Serial.print(DHTPIN); Serial.print(": ");
  Serial.println(isnan(h0) ? String("FAILED (check wiring / pin number)") : String(h0, 1) + " % RH OK");

  lastSample = millis() - SAMPLE_MS;
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();   // auto-reconnect if the router drops us

  if (millis() - lastSample >= SAMPLE_MS) {
    lastSample = millis();

    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (isnan(h) || isnan(t)) { delay(2100); h = dht.readHumidity(); t = dht.readTemperature(); }

    // A failed read is still sent (as -1 with ok:false) so the gap shows up as missing data later
    bool ok = !(isnan(h) || isnan(t));
    String body = "{\"temperature\":" + String(ok ? t : -1.0, 1) +
                  ",\"humidity\":"    + String(ok ? h : -1.0, 1) +
                  ",\"ok\":"          + String(ok ? "true" : "false") +
                  ",\"ts\":{\".sv\":\"timestamp\"}}";

    String path = "/readings/dht22.json?auth=" + String(SECRET_FB_AUTH);
    int err = http.post(path, "application/json", body);   // POST = push a new child with a unique key
    int status = (err == 0) ? http.responseStatusCode() : err;  // err -1 = could not connect to Firebase
    http.responseBody();                         // read and discard the reply so the connection is clean
    http.stop();

    if (status == 200) {
      sent++;
      digitalWrite(LED_BUILTIN, HIGH); delay(100); digitalWrite(LED_BUILTIN, LOW);  // blink = sent
    } else {
      failed++;
    }
    Serial.print(body); Serial.print("  -> HTTP "); Serial.print(status);
    Serial.print("  sent="); Serial.print(sent); Serial.print(" failed="); Serial.println(failed);
  }
}
