// USB-C PD electronic load V1 - firmware (STM32G030F6P6, STM32duino / PlatformIO)
//
// Hardware does the real work: an analogue integrator loop regulates the current (Vset -> shunt), and a KILL bus
// (over-temperature, NTC open, hardware over-current, LOAD_DIS) clamps the gate independently of this firmware.
// The firmware sets the current target, picks the PD voltage, measures V/I/P/T and applies derating and protection.
//
// Safety rules implemented here:
//   * LOAD_DIS (PA5) is open-drain: released (hi-Z) = load off. It is only pulled low while the load is allowed.
//   * PWM setpoint is forced to 0 before every enable/disable and before every PD voltage change.
//   * Load never enables with a missing/shorted NTC, an active HW fault, or a VBUS that is not at the requested PD voltage.
//   * Independent watchdog (1 s). A hang releases LOAD_DIS via the reset.
//
// Flash is tight on the 32 KB part: integer maths only, no printf, U8x8 text mode for the OLED.

#include <Arduino.h>
#include <U8g2lib.h>
#include <IWatchdog.h>
#include "stm32yyxx_ll_tim.h"
#include "stm32yyxx_ll_gpio.h"
#include "stm32yyxx_ll_bus.h"

// ------------------------------------------------------------------ pins (see README pin map)
static const uint32_t PIN_VBUS_SENSE = PA0;
static const uint32_t PIN_I_SENSE    = PA1;
static const uint32_t PIN_NTC        = PA2;
static const uint32_t PIN_HW_FAULT   = PA3;
static const uint32_t PIN_SET_PWM    = PA4;   // TIM14_CH1
static const uint32_t PIN_LOAD_DIS   = PA5;   // low = load allowed, hi-Z = off
static const uint32_t PIN_ENC_A      = PA6;
static const uint32_t PIN_ENC_B      = PA7;
static const uint32_t PIN_LED_FAULT  = PA8;
static const uint32_t PIN_LED_LOAD   = PB3;
static const uint32_t PIN_BTN_LOAD   = PB8;
static const uint32_t PIN_BTN_PD     = PB9;
static const uint32_t PIN_ENC_SW     = PC15;

// ------------------------------------------------------------------ calibration constants
static const int32_t  VDDA_MV         = 3300;    // LDO output, adjust after measuring TP_3V3
static const int32_t  R_SHUNT_MOHM    = 330;     // 0.33 ohm
static const int32_t  VBUS_DIV_NUM    = 23;      // (100k + 15k) / 15k = 23/3
static const int32_t  VBUS_DIV_DEN    = 3;
static const int32_t  VSET_BIAS_UV    = 3300;    // 10M / 10k idle bias from the schematic (3.3 mV at 3.3 V)
static const int32_t  PWM_PER_VOLT_K  = 37683;   // 9.2 (divider) * 4096
static const int32_t  I_MAX_MA        = 1000;    // firmware limit (hardware cap about 1087 mA, OC comparator about 1380 mA)
static const int32_t  P_LIMIT_PASSIVE_MW = 10000;
static const int32_t  P_LIMIT_FAN_MW     = 20000;
static const int16_t  T_DERATE_START_C = 70;
static const int16_t  T_FAULT_C        = 90;
static const int32_t  IOFFSET_MAX_UV   = 15000;
static const int32_t  UV_PER_COUNT_X16 = (VDDA_MV * 16000L) / 4095;     // ADC step in uV, x16

// NTC 10k B3950 with 10k pull-up to 3V3, NTC to GND: {temperature C, 12-bit counts}
static const int16_t NTC_T[]   = {-20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130};
static const int16_t NTC_ADC[] = {3740, 3495, 3156, 2738, 2278, 1825, 1419, 1081, 815, 613, 462, 350, 267, 206, 160, 126};

static const uint8_t  PD_COUNT = 5;
static const uint16_t PD_MV[PD_COUNT] = {5000, 9000, 12000, 15000, 20000};   // CH224A reg 0x0A codes 0..4

enum State { ST_OFF, ST_ON, ST_FAULT };
enum Fault { F_NONE, F_HW, F_OVERTEMP, F_NTC, F_VBUS, F_OVERPOWER, F_OVERCURRENT };
static const char* const FAULT_TXT[] = {"", "HW TRIP", "OVER TEMP", "NTC FAULT", "VBUS DROP", "OVER POWER", "OVER CURR"};

// ------------------------------------------------------------------ globals
static U8X8_SSD1306_128X64_NONAME_SW_I2C oled(PA11 /*SCL*/, PA12 /*SDA*/, U8X8_PIN_NONE);

static State  state = ST_OFF;
static Fault  fault = F_NONE;
static int32_t iSet_mA = 100;
static int32_t iCmd_mA = 0;             // ramped command actually sent
static uint8_t pdIdx = 0;
static bool    pdPresent = false;
static uint8_t pdAddr = 0;
static uint8_t pdStatus = 0;
static bool    fanMode = false;
static bool    coarse = false;
static int32_t iOffset_uV = 0;

static int32_t vbus_mV = 0, i_mA = 0, p_mW = 0;
static int16_t temp_C = 25;
static bool    ntcOk = false;
static uint32_t pdSettleUntil = 0, enabledAt = 0, vbusLowSince = 0, ocSince = 0, hwSince = 0;

static volatile int8_t encAccum = 0;
static volatile uint8_t encState = 0;

// ------------------------------------------------------------------ helpers
static void encIsr() {
  static const int8_t tbl[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};
  encState = ((encState << 2) | (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B)) & 0x0F;
  encAccum += tbl[encState];
}

static uint16_t adcAvg(uint32_t pin, uint8_t n) {
  uint32_t s = 0;
  for (uint8_t k = 0; k < n; k++) s += analogRead(pin);
  return (uint16_t)(s / n);
}

static void pwmWrite(uint32_t counts) { LL_TIM_OC_SetCompareCH1(TIM14, counts); }

static void setPwmFromMa(int32_t ma) {
  if (ma < 0) ma = 0;
  int32_t vset_uV = ma * R_SHUNT_MOHM + (ma > 0 ? VSET_BIAS_UV : 0);          // <= 0.4 V
  int32_t counts = (vset_uV / 100) * PWM_PER_VOLT_K / (VDDA_MV * 10);          // 32-bit safe
  if (counts > 4095) counts = 4095;
  pwmWrite((uint32_t)counts);
}

static void loadRelease() {       // load off: PWM 0 first, then release LOAD_DIS
  setPwmFromMa(0);
  iCmd_mA = 0;
  digitalWrite(PIN_LOAD_DIS, HIGH);
  digitalWrite(PIN_LED_LOAD, LOW);
}

static void loadAllow() {
  setPwmFromMa(0);
  iCmd_mA = 0;
  digitalWrite(PIN_LOAD_DIS, LOW);
  digitalWrite(PIN_LED_LOAD, HIGH);
  enabledAt = millis();
}

static int16_t ntcToC(uint16_t adc, bool* ok) {
  *ok = (adc > 40 && adc < 3950);      // open (counts about 4095) or short (about 0) -> sensor fault
  if (!*ok) return 999;
  for (uint8_t k = 0; k + 1 < sizeof(NTC_T) / sizeof(NTC_T[0]); k++) {
    if (adc <= NTC_ADC[k] && adc >= NTC_ADC[k + 1]) {
      return NTC_T[k] + (int32_t)10 * (NTC_ADC[k] - adc) / (NTC_ADC[k] - NTC_ADC[k + 1]);
    }
  }
  return adc > NTC_ADC[0] ? NTC_T[0] : 130;
}

static void measure() {
  uint16_t av = adcAvg(PIN_VBUS_SENSE, 16);
  uint16_t ai = adcAvg(PIN_I_SENSE, 16);
  uint16_t an = adcAvg(PIN_NTC, 8);
  vbus_mV = ((int32_t)av * VDDA_MV / 4095) * VBUS_DIV_NUM / VBUS_DIV_DEN;
  int32_t vsh_uV = (int32_t)ai * UV_PER_COUNT_X16 / 16 - iOffset_uV;
  i_mA = vsh_uV / R_SHUNT_MOHM;                    // uV / mOhm = mA
  if (i_mA < 0) i_mA = 0;
  p_mW = vbus_mV * (i_mA / 4) / 250;               // keeps the product inside 32 bits
  temp_C = ntcToC(an, &ntcOk);
}

// ------------------------------------------------------------------ CH224A (bit-banged I2C on the OLED bus, open-drain emulation)
static const uint32_t I2C_SCL = PA11, I2C_SDA = PA12;
static inline void i2cDelay() { for (volatile uint8_t k = 0; k < 40; k++) { __NOP(); } }   // about 100 kHz at 64 MHz
static inline void sclLow()  { pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW); }
static inline void sclHigh() { pinMode(I2C_SCL, INPUT_PULLUP); }
static inline void sdaLow()  { pinMode(I2C_SDA, OUTPUT); digitalWrite(I2C_SDA, LOW); }
static inline void sdaHigh() { pinMode(I2C_SDA, INPUT_PULLUP); }
static void i2cStart() { sdaHigh(); sclHigh(); i2cDelay(); sdaLow(); i2cDelay(); sclLow(); }
static void i2cStop()  { sdaLow(); i2cDelay(); sclHigh(); i2cDelay(); sdaHigh(); i2cDelay(); }
static bool i2cWrite(uint8_t d) {
  for (uint8_t k = 0; k < 8; k++) { if (d & 0x80) sdaHigh(); else sdaLow(); d <<= 1; i2cDelay(); sclHigh(); i2cDelay(); sclLow(); }
  sdaHigh(); i2cDelay(); sclHigh(); i2cDelay();
  bool ack = (digitalRead(I2C_SDA) == LOW);
  sclLow();
  return ack;
}
static uint8_t i2cRead(bool ack) {
  uint8_t d = 0;
  sdaHigh();
  for (uint8_t k = 0; k < 8; k++) { i2cDelay(); sclHigh(); i2cDelay(); d = (d << 1) | (digitalRead(I2C_SDA) ? 1 : 0); sclLow(); }
  if (ack) sdaLow(); else sdaHigh();
  i2cDelay(); sclHigh(); i2cDelay(); sclLow(); sdaHigh();
  return d;
}

static void pdProbe() {
  const uint8_t addrs[2] = {0x22, 0x23};
  pdPresent = false;
  for (uint8_t a : addrs) {
    i2cStart();
    bool ok = i2cWrite(a << 1);
    i2cStop();
    if (ok) { pdAddr = a; pdPresent = true; break; }
  }
}

static bool pdApply(uint8_t idx) {
  loadRelease();
  if (state == ST_ON) state = ST_OFF;
  pdIdx = idx;
  pdSettleUntil = millis() + 1500;
  if (!pdPresent) pdProbe();
  if (!pdPresent) return false;
  i2cStart();
  bool ok = i2cWrite(pdAddr << 1) && i2cWrite(0x0A) && i2cWrite(idx);
  i2cStop();
  return ok;
}

static void pdReadStatus() {
  if (!pdPresent) return;
  i2cStart();
  if (i2cWrite(pdAddr << 1) && i2cWrite(0x09)) {
    i2cStart();
    if (i2cWrite((pdAddr << 1) | 1)) pdStatus = i2cRead(false);
  }
  i2cStop();
}

// ------------------------------------------------------------------ limits / faults
static int32_t currentLimitMa() {
  int32_t lim = I_MAX_MA;
  int32_t pLim = fanMode ? P_LIMIT_FAN_MW : P_LIMIT_PASSIVE_MW;
  if (vbus_mV > 1000) {
    int32_t byP = pLim * 1000 / vbus_mV;
    if (byP < lim) lim = byP;
  }
  if (temp_C >= T_FAULT_C) lim = 0;
  else if (temp_C > T_DERATE_START_C) lim = lim * (T_FAULT_C - temp_C) / (T_FAULT_C - T_DERATE_START_C);
  return lim;
}

static void tripFault(Fault f) {
  loadRelease();
  state = ST_FAULT;
  fault = f;
}

static bool canEnable() {
  if (!ntcOk || temp_C > T_DERATE_START_C) return false;
  if (millis() < pdSettleUntil) return false;
  int32_t target = PD_MV[pdIdx];
  if (vbus_mV < target * 90 / 100 || vbus_mV > target * 115 / 100) return false;
  return true;
}

static void checkFaults(uint32_t now) {
  if (state != ST_ON) return;
  if (!ntcOk) { tripFault(F_NTC); return; }
  if (temp_C >= T_FAULT_C) { tripFault(F_OVERTEMP); return; }
  if (now - enabledAt > 30) {
    if (digitalRead(PIN_HW_FAULT) == HIGH) {
      if (hwSince == 0) hwSince = now;
      if (now - hwSince > 30) { tripFault(F_HW); return; }
    } else hwSince = 0;
  }
  int32_t target = PD_MV[pdIdx];
  if (now > pdSettleUntil && vbus_mV < target * 80 / 100) {
    if (vbusLowSince == 0) vbusLowSince = now;
    if (now - vbusLowSince > 100) { tripFault(F_VBUS); return; }
  } else vbusLowSince = 0;
  int32_t pLim = fanMode ? P_LIMIT_FAN_MW : P_LIMIT_PASSIVE_MW;
  if (p_mW > pLim * 125 / 100 && now - enabledAt > 300) { tripFault(F_OVERPOWER); return; }
  if (i_mA > 1250) {
    if (ocSince == 0) ocSince = now;
    if (now - ocSince > 50) { tripFault(F_OVERCURRENT); return; }
  } else ocSince = 0;
}

// ------------------------------------------------------------------ UI
struct Btn { uint32_t pin; bool last; uint32_t t; };
static Btn bLoad = {PIN_BTN_LOAD, true, 0}, bEnc = {PIN_ENC_SW, true, 0};
static uint32_t bPdDown = 0;

static bool pressed(Btn& b, uint32_t now) {      // falling edge with 30 ms debounce
  bool v = digitalRead(b.pin);
  bool ev = (!v && b.last && now - b.t > 30);
  if (v != b.last) b.t = now;
  b.last = v;
  return ev;
}

static void handleInputs(uint32_t now) {
  int8_t acc;
  noInterrupts(); acc = encAccum; if (acc >= 4 || acc <= -4) encAccum = 0; interrupts();
  if (acc >= 4 || acc <= -4) {
    int32_t step = coarse ? 50 : 10;
    iSet_mA += (acc > 0 ? step : -step);
    if (iSet_mA < 0) iSet_mA = 0;
    if (iSet_mA > I_MAX_MA) iSet_mA = I_MAX_MA;
  }
  if (pressed(bEnc, now)) coarse = !coarse;
  if (pressed(bLoad, now)) {
    if (state == ST_ON) { loadRelease(); state = ST_OFF; }
    else if (state == ST_FAULT) { if (ntcOk && temp_C < T_DERATE_START_C) { state = ST_OFF; fault = F_NONE; } }
    else if (canEnable()) { state = ST_ON; loadAllow(); hwSince = ocSince = vbusLowSince = 0; }
  }
  bool pdDown = !digitalRead(PIN_BTN_PD);
  if (pdDown && bPdDown == 0) bPdDown = now ? now : 1;
  if (!pdDown && bPdDown != 0) {
    uint32_t held = now - bPdDown; bPdDown = 0;
    if (held > 1500) fanMode = !fanMode;                         // long press: toggle 10 W / 20 W (fan fitted)
    else if (held > 30) pdApply((pdIdx + 1) % PD_COUNT);       // short press: next PD voltage
  }
}

// tiny formatters (no printf): append text / integers into a 17-char line buffer
static char* put(char* p, const char* s) { while (*s) *p++ = *s++; return p; }
static char* putFixed(char* p, int32_t v, uint8_t intDigits, uint8_t decimals, uint8_t dpDivPow) {
  // v is scaled by 10^dpDivPow; prints intDigits.decimals (leading spaces for the integer part)
  int32_t div = 1;
  for (uint8_t k = 0; k < dpDivPow; k++) div *= 10;
  int32_t ip = v / div, fp = v % div;
  for (uint8_t k = dpDivPow; k > decimals; k--) fp /= 10;
  char tmp[6]; uint8_t n = 0;
  do { tmp[n++] = '0' + (ip % 10); ip /= 10; } while (ip && n < 5);
  for (uint8_t k = n; k < intDigits; k++) *p++ = ' ';
  while (n) *p++ = tmp[--n];
  if (decimals) {
    *p++ = '.';
    int32_t m = 1;
    for (uint8_t k = 1; k < decimals; k++) m *= 10;
    for (; m; m /= 10) { *p++ = '0' + (fp / m) % 10; }
  }
  return p;
}
static void line(uint8_t row, char* start, char* end) {
  while (end - start < 16) *end++ = ' ';
  *end = 0;
  oled.drawString(0, row, start);
}

static void drawUi() {
  char b[20]; char* p;
  p = put(b, "PD "); p = putFixed(p, PD_MV[pdIdx] / 1000, 2, 0, 0); p = put(p, "V ");
  p = put(p, pdPresent ? ((pdStatus & 0x08) ? "PDok " : "wait ") : "noI2C");
  p = put(p, fanMode ? " FAN20W" : " 10W");
  line(0, b, p);
  p = b; p = putFixed(p, vbus_mV / 10, 2, 2, 2); p = put(p, "V");
  *p = 0; oled.draw2x2String(0, 1, b);
  p = b; p = putFixed(p, i_mA, 1, 3, 3); p = put(p, "A ");
  *p = 0; oled.draw2x2String(0, 3, b);
  p = put(b, "P "); p = putFixed(p, p_mW / 100, 2, 1, 1); p = put(p, "W ");
  if (ntcOk) { p = put(p, "T "); p = putFixed(p, temp_C, 3, 0, 0); p = put(p, "C"); } else p = put(p, "T --");
  line(5, b, p);
  p = put(b, "SET "); p = putFixed(p, iSet_mA, 1, 3, 3); p = put(p, "A x"); p = put(p, coarse ? "50" : "10");
  line(6, b, p);
  if (state == ST_FAULT) { p = put(b, "FAULT "); p = put(p, FAULT_TXT[fault]); }
  else { p = put(b, state == ST_ON ? "LOAD ON " : "load off "); p = put(p, "lim "); p = putFixed(p, currentLimitMa(), 4, 0, 0); }
  line(7, b, p);
}

// ------------------------------------------------------------------ setup / loop
void setup() {
  pinMode(PIN_LOAD_DIS, OUTPUT_OPEN_DRAIN);
  digitalWrite(PIN_LOAD_DIS, HIGH);              // released: load off
  pinMode(PIN_LED_LOAD, OUTPUT); pinMode(PIN_LED_FAULT, OUTPUT);
  pinMode(PIN_HW_FAULT, INPUT);
  pinMode(PIN_BTN_LOAD, INPUT_PULLUP); pinMode(PIN_BTN_PD, INPUT_PULLUP); pinMode(PIN_ENC_SW, INPUT_PULLUP);
  pinMode(PIN_ENC_A, INPUT); pinMode(PIN_ENC_B, INPUT);

  // TIM14 CH1 on PA4 (AF4): 64 MHz / 4096 = 15.6 kHz, 12-bit PWM, driven straight from the LL driver
  LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_TIM14);
  LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_4, LL_GPIO_MODE_ALTERNATE);
  LL_GPIO_SetAFPin_0_7(GPIOA, LL_GPIO_PIN_4, LL_GPIO_AF_4);
  LL_TIM_SetPrescaler(TIM14, 0);
  LL_TIM_SetAutoReload(TIM14, 4095);
  LL_TIM_OC_SetMode(TIM14, LL_TIM_CHANNEL_CH1, LL_TIM_OCMODE_PWM1);
  LL_TIM_OC_EnablePreload(TIM14, LL_TIM_CHANNEL_CH1);
  LL_TIM_OC_SetCompareCH1(TIM14, 0);
  LL_TIM_CC_EnableChannel(TIM14, LL_TIM_CHANNEL_CH1);
  LL_TIM_EnableARRPreload(TIM14);
  LL_TIM_EnableCounter(TIM14);
  LL_TIM_GenerateEvent_UPDATE(TIM14);

  analogReadResolution(12);
  IWatchdog.begin(1000000);

  oled.begin();
  oled.setFont(u8x8_font_chroma48medium8_r);
  oled.drawString(0, 3, "USB-C PD E-LOAD");
  oled.drawString(0, 4, "V1  calibrating");

  delay(300);
  uint32_t acc = 0;                               // zero-current offset of the sense path
  for (uint8_t k = 0; k < 32; k++) { acc += analogRead(PIN_I_SENSE); IWatchdog.reload(); }
  iOffset_uV = (int32_t)(acc / 32) * UV_PER_COUNT_X16 / 16;
  if (iOffset_uV > IOFFSET_MAX_UV) iOffset_uV = IOFFSET_MAX_UV;

  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encIsr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encIsr, CHANGE);
  pdProbe();
  pdApply(0);                                     // start at 5 V (CH224A powers up at 9 V from Rset)
  oled.clear();
}

void loop() {
  static uint32_t tCtl = 0, tUi = 0, tPd = 0;
  uint32_t now = millis();
  IWatchdog.reload();
  handleInputs(now);

  if (now - tCtl >= 10) {
    tCtl = now;
    measure();
    checkFaults(now);
    if (state == ST_ON) {
      int32_t target = min(iSet_mA, currentLimitMa());
      if (iCmd_mA < target) iCmd_mA = min(iCmd_mA + 20, target);
      else if (iCmd_mA > target) iCmd_mA = max(iCmd_mA - 50, target);
      setPwmFromMa(iCmd_mA);
    }
    digitalWrite(PIN_LED_FAULT, state == ST_FAULT ? ((now / 250) & 1) : (ntcOk ? LOW : HIGH));
  }
  if (now - tPd >= 500) { tPd = now; pdReadStatus(); }
  if (now - tUi >= 250) { tUi = now; drawUi(); }
}
