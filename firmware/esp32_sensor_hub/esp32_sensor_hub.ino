#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_VL53L0X.h>

Adafruit_MPU6050 mpu;
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// ESP32 Serial2 is usually pins 16(RX) and 17(TX)
#define MEGA_SERIAL Serial2 

void setup() {
  Serial.begin(115200);      // USB Debug
  MEGA_SERIAL.begin(115200); // Communication to Arduino

    Wire.begin();

  // Try to initialize sensors
    if (!mpu.begin()) {
        Serial.println("Error: MPU6050 not found. Check wiring!");
    }
    if (!lox.begin()) {
        Serial.println("Error: VL53L0X not found. Check wiring!");
    }

  // MPU Settings
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
}

void loop() {
  // 1. Read Distance
    VL53L0X_RangingMeasurementData_t measure;
    lox.rangingTest(&measure, false);
    int dist = 9999;
    if (measure.RangeStatus != 4) { 
    dist = measure.RangeMilliMeter;
    }

  // 2. Read Gyro
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

  // 3. Send formatted packet: "<D:150,AX:0.5>"
    String packet = "<D:" + String(dist) + ",AX:" + String(a.acceleration.x) + ">";

  MEGA_SERIAL.println(packet); // Send to Arduino
    Serial.println(packet);      // Debug to PC

    delay(50);
}