#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_VL53L0X.h>

Adafruit_MPU6050 mpu;
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// ESP32 Serial2 is usually pins 16(RX) and 17(TX)
#define MEGA_SERIAL Serial2 

bool mpu_ok = false;
bool lox_ok = false;
unsigned long lastSendTime = 0;
const unsigned long interval = 50; // Non-blocking 50ms interval

void setup() {
  Serial.begin(115200);      // USB Debug
  MEGA_SERIAL.begin(115200); // Communication to Arduino

  // Initialize I2C Bus first
  Wire.begin();

  // Try to initialize sensors safely
  if (mpu.begin()) {
    mpu_ok = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("MPU6050 initialized successfully.");
  } else {
    Serial.println("Error: MPU6050 not found. Check wiring!");
  }

  // Initialize VL53L0X safely
  if (lox.begin()) {
    lox_ok = true;
    Serial.println("VL53L0X initialized successfully.");
  } else {
    Serial.println("Error: VL53L0X not found. Check wiring!");
  }
}

void loop() {
  unsigned long currentTime = millis();
  
  if (currentTime - lastSendTime >= interval) {
    lastSendTime = currentTime;

    int dist = 9999;
    float ax = 0.0;

    // 1. Read Distance safely
    if (lox_ok) {
      VL53L0X_RangingMeasurementData_t measure;
      lox.rangingTest(&measure, false);
      if (measure.RangeStatus != 4) { 
        dist = measure.RangeMilliMeter;
      }
    }

    // 2. Read Gyro safely
    if (mpu_ok) {
      sensors_event_t a, g, temp;
      mpu.getEvent(&a, &g, &temp);
      ax = a.acceleration.x;
    }

    // 3. Send formatted packet: "<D:150,AX:0.5>"
    String packet = "<D:" + String(dist) + ",AX:" + String(ax, 2) + ">";

    MEGA_SERIAL.println(packet); // Send to Arduino
    Serial.println(packet);      // Debug to PC
  }
}