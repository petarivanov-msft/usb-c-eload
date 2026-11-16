"""Builds the USB-C-Eload-V1 schematic. Usage: python gen_eload.py <outdir>"""
import sys, os, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import schlib
from schlib import Schematic

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
os.makedirs(OUT, exist_ok=True)
schlib.CUSTOM_LIB = os.path.join(OUT, 'eload.kicad_sym')

import mk_custom_lib
open(schlib.CUSTOM_LIB, 'w', encoding='utf-8', newline='\n').write(mk_custom_lib.build())

s = Schematic()
R, C = s.R, s.C

# ---- common part catalogue (LCSC code, MPN) ------------------------------------------------
RES = {'10k': ('C25804', '0603WAF1002T5E'), '1k': ('C21190', '0603WAF1001T5E'),
       '100k': ('C25803', '0603WAF1003T5E'), '6.8k': ('C23212', '0603WAF6801T5E'),
       '4.7k': ('C23162', '0603WAF4701T5E'), '15k': ('C22809', '0603WAF1502T5E'),
       '20k': ('C4184', '0603WAF2002T5E'), '680': ('C23228', '0603WAF6800T5E'),
       '7.5k': ('C23234', '0603WAF7501T5E'), '300k': ('C23024', '0603WAF3003T5E'),
       '10M': ('C7250', '0603WAF1005T5E'), '8.2k': ('C25981', '0603WAF8201T5E'),
       '47k': ('C25819', '0603WAF4702T5E')}
CAP = {'100nF': ('C1590', 'CL10B104KA8NNNC'), '1uF': ('C29936', 'CL10B105KA8NNNC'),
       '4.7uF': ('C1705', 'CL10A475KP8NNNC'), '10nF': ('C1589', 'CL10B103KB8NNNC'),
       '10uF/10V': ('C19702', 'CL10A106KP8NNNC'), '10uF/25V': ('C15850', 'CL21A106KAYNNNE'),
       '22uF/10V': ('C29277', 'CL21A226MPQNNNE'), '10uF/50V': ('C13585', 'CL31A106KBHNNNE'),
       '1uF/50V': ('C28323', 'CL21B105KBFNNNE'), '1nF': ('C1588', 'CL10B102KB8NNNC')}


def r(val, top, bot, x, y, **kw):
    code, mpn = RES[val]
    return R(val, top, bot, x, y, lcsc=code, mpn=mpn, **kw)


def c(key, top, bot, x, y, fp='Capacitor_SMD:C_0603_1608Metric', **kw):
    code, mpn = CAP[key]
    return C(key.replace('/', ' '), top, bot, x, y, lcsc=code, mpn=mpn, fp=fp, **kw)


def led(color, kref_net, anode_net, x, y):
    code = {'red': ('C2286', 'KT-0603R'), 'green': ('C12624', 'KT-0603G'), 'amber': ('C2287', 'KT-0603Y')}[color]
    return s.place('Device', 'LED', color.capitalize(), x, y, {'1': kref_net, '2': anode_net},
                   fp='LED_SMD:LED_0603_1608Metric', extra={'LCSC': code[0], 'MPN': code[1]})


def tp(net, x, y, name):
    return s.place('Connector', 'TestPoint', name, x, y, {'1': net}, fp='TestPoint:TestPoint_Pad_D1.5mm',
                   prefix='TP', show_value=False)


s.text('USB-C PD Electronic Load V1  -  constant-current sink, 5/9/12/15/20 V, 0-1 A, 20 W target', 10, 12, 4, True)

# =========================================================================================
# 1. USB-C INPUT & PROTECTION
# =========================================================================================
s.box(10, 20, 170, 150, '1. USB-C INPUT AND PROTECTION')
s.place('Connector', 'USB_C_Receptacle_USB2.0_16P', 'USB-C (HRO TYPE-C-31-M-12)', 45, 80,
        {'A1': 'GND', 'B1': 'GND', 'A12': 'GND', 'B12': 'GND', 'SH': 'GND',
         'A4': 'VBUS_USB', 'B4': 'VBUS_USB', 'A9': 'VBUS_USB', 'B9': 'VBUS_USB',
         'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DM', 'B7': 'USB_DM',
         'A8': 'NC', 'B8': 'NC'},
        fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', ref='J1',
        extra={'LCSC': 'C165948', 'MPN': 'TYPE-C-31-M-12'})
s.place('Diode', 'SMAJ20A', 'SMAJ20A', 100, 60, {'1': 'VBUS', '2': 'GND'}, ref='D1',
        fp='Diode_SMD:D_SMA', extra={'LCSC': 'C148209', 'MPN': 'SMAJ20A'})
s.place('Device', 'Fuse', '2A 32V', 125, 45, {'1': 'VBUS_USB', '2': 'VBUS'}, ref='F1',
        fp='Fuse:Fuse_1206_3216Metric', extra={'LCSC': 'C206969', 'MPN': '0440002.WR'})
c('10uF/50V', 'VBUS', 'GND', 125, 95, fp='Capacitor_SMD:C_1206_3216Metric')
c('100nF', 'VBUS', 'GND', 140, 95)
s.pwr_flag('VBUS_USB', 90, 110)
s.pwr_flag('VBUS', 80, 120)
s.pwr_flag('GND', 100, 120)
s.text('F1 sits first: it protects D1, CH224A, the buck and the load path (2 A hold).\nD1 SMAJ20A: 20 V standoff TVS (clamp 32.4 V at rated surge).', 60, 140, 1.5)

# =========================================================================================
# 2. USB PD SINK (CH224A)
# =========================================================================================
s.box(180, 20, 300, 150, '2. USB PD SINK - CH224A (I2C)')
s.place('eload', 'CH224A', 'CH224A', 235, 75,
        {'1': 'VBUS', '8': 'VBUS', '7': 'CC1', '6': 'CC2', '4': 'USB_DP', '5': 'USB_DM',
         '9': 'CFG1', '2': 'I2C_SCL', '3': 'I2C_SDA', '10': 'PD_PG', '11': 'GND'}, ref='U2',
        extra={'LCSC': 'C42459160', 'MPN': 'CH224A'})
c('1uF/50V', 'VBUS', 'GND', 195, 110, fp='Capacitor_SMD:C_0805_2012Metric')
r('6.8k', 'CFG1', 'GND', 275, 100)
r('1k', '+3V3', 'PG_A', 290, 100)
led('green', 'PD_PG', 'PG_A', 272, 128)
s.text('Rset 6.8k => 9 V power-up default. MCU requests 5/9/12/15/20 V over I2C (reg 0x0A).\nI2C addr 0x22/0x23. CFG2/CFG3 have internal 10k pull-ups.', 185, 145, 1.5)

# =========================================================================================
# 3. POWER RAILS  VBUS -> 5 V buck -> 3.3 V LDO
# =========================================================================================
s.box(310, 20, 580, 150, '3. POWER RAILS - 5 V BUCK AND 3.3 V LDO')
s.place('Regulator_Switching', 'AP63205WU', 'AP63205WU-7', 350, 70,
        {'3': 'VBUS', '2': 'VBUS', '1': '+5V', '5': 'SW', '6': 'BST', '4': 'GND'}, ref='U4',
        extra={'LCSC': 'C2071056', 'MPN': 'AP63205WU-7'})
c('10uF/50V', 'VBUS', 'GND', 325, 105, fp='Capacitor_SMD:C_1206_3216Metric')
c('100nF', 'VBUS', 'GND', 340, 105)
c('100nF', 'BST', 'SW', 385, 105)
s.place('Device', 'L', '4.7uH', 405, 90, {'1': 'SW', '2': '+5V'}, ref='L1',
        fp='Inductor_SMD:L_Sunlord_SWPA4030S', extra={'LCSC': 'C57269', 'MPN': 'SWPA4030S4R7MT'})
c('22uF/10V', '+5V', 'GND', 425, 105, fp='Capacitor_SMD:C_0805_2012Metric')
c('22uF/10V', '+5V', 'GND', 440, 105, fp='Capacitor_SMD:C_0805_2012Metric')
c('100nF', '+5V', 'GND', 455, 105)
s.pwr_flag('+5V', 470, 100)
s.place('Regulator_Linear', 'AP2112K-3.3', 'AP2112K-3.3', 510, 70,
        {'1': '+5V', '3': '+5V', '2': 'GND', '5': '+3V3', '4': 'NC'}, ref='U5',
        extra={'LCSC': 'C51118', 'MPN': 'AP2112K-3.3TRG1'})
c('1uF', '+5V', 'GND', 485, 105)
c('1uF', '+3V3', 'GND', 535, 105)
c('100nF', '+3V3', 'GND', 550, 105)
s.text('AP63205: 3.8-32 V in, fixed 5 V, 2 A, 1.1 MHz. EN tied to VIN (auto-start).\n5 V rail feeds op-amp (gate drive headroom) and fan header; LDO gives quiet 3.3 V for MCU/ADC/OLED.', 315, 143, 1.5)

# =========================================================================================
# 4. MCU
# =========================================================================================
s.box(10, 160, 170, 345, '4. MCU - STM32G030F6P6')
s.place('MCU_ST_STM32G0', 'STM32G030F6Px', 'STM32G030F6P6', 95, 255,
        {'4': '+3V3', '5': 'GND', '6': 'NRST',
         '7': 'VBUS_SENSE', '8': 'I_SENSE', '9': 'NTC_SENSE', '10': 'HW_FAULT', '11': 'SET_PWM', '12': 'LOAD_DIS',
         '13': 'ENC_A', '14': 'ENC_B', '15': 'LED_FAULT', '16': 'I2C_SCL', '17': 'I2C_SDA', '18': 'SWDIO',
         '19': 'SWCLK', '1': 'BTN_LOAD', '2': 'BTN_PD', '3': 'ENC_SW', '20': 'LED_LOAD'}, ref='U1',
        extra={'LCSC': 'C529330', 'MPN': 'STM32G030F6P6TR'})
c('100nF', '+3V3', 'GND', 30, 200)
c('4.7uF', '+3V3', 'GND', 47, 200)
c('100nF', 'NRST', 'GND', 64, 200)
s.place('Connector_Generic', 'Conn_01x04', 'SWD', 35, 315, {'1': 'GND', '2': 'SWCLK', '3': 'SWDIO', '4': 'NRST'},
        ref='J3', fp='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
        extra={'LCSC': 'C2691448', 'MPN': 'PZ254V-11-04P'})
s.text('Pin map: PA4=TIM14_CH1 (setpoint PWM), PA6/PA7=TIM3 encoder, PA9/PA10=I2C1,\nPA0-PA2=ADC (VBUS, I, NTC). BOOT0 shares PA14/SWCLK: leave it unpulled.\nSWD header: GND, SWCLK, SWDIO, NRST (do not feed 3V3 from the programmer).', 15, 340, 1.4)

# =========================================================================================
# 5. CONSTANT-CURRENT LOOP, HARDWARE PROTECTION, SENSING
# =========================================================================================
s.box(180, 160, 448, 405, '5. CONSTANT-CURRENT LOOP, HARDWARE PROTECTION AND SENSING')
s.text('Setpoint: PWM -> /9.2 divider -> 2nd-order RC (~16 Hz). Hardware full scale 1.09 A at 0.33 ohm.', 190, 188, 1.5)
x0, p = 192, 17
r('100k', 'SET_PWM', 'GND', x0 + 0 * p, 205)
r('8.2k', 'SET_PWM', 'SET_RC1', x0 + 1 * p, 205)
r('1k', 'SET_RC1', 'GND', x0 + 2 * p, 205)
c('10uF/10V', 'SET_RC1', 'GND', x0 + 3 * p, 205)
r('10k', 'SET_RC1', 'VSET', x0 + 4 * p, 205)
c('1uF', 'VSET', 'GND', x0 + 5 * p, 205)

s.text('Integrator loop: Rin 10k + Cf 10 nF. 10 Meg to 3V3 adds ~3 mV bias so the integrator rails LOW when idle.\nRg 1k isolates the gate capacitance; Cf is tapped before Rg.', 190, 233, 1.5)
r('10k', 'SH_TOP', 'AMP_FB', x0 + 0 * p, 250)
r('10M', '+3V3', 'AMP_FB', x0 + 1 * p, 250)
c('10nF', 'AMP_OUT', 'AMP_FB', x0 + 2 * p, 250)
r('1k', 'AMP_OUT', 'GATE', x0 + 3 * p, 250)
r('10k', 'GATE', 'GND', x0 + 4 * p, 250)
r('1k', 'SH_TOP', 'I_SENSE', x0 + 5 * p, 250)
c('100nF', 'I_SENSE', 'GND', x0 + 6 * p, 250)

s.text('KILL bus (active high, OR of 4 sources) clamps GATE (Q3) and VSET (Q2). LOAD_DIS is pulled up: MCU hi-Z = load off.\nHW_FAULT to MCU = KILL via 10k/20k.  OTP comparator: trips ~98 C, releases ~84 C.', 190, 278, 1.5)
r('100k', '+3V3', 'OTP_REF', x0 + 0 * p, 295)
r('7.5k', 'OTP_REF', 'GND', x0 + 1 * p, 295)
r('300k', 'OTP_OUT', 'OTP_REF', x0 + 2 * p, 295)
r('10k', 'KILL', 'HW_FAULT', x0 + 3 * p, 295)
r('20k', 'HW_FAULT', 'GND', x0 + 4 * p, 295)
r('100k', 'KILL', 'GND', x0 + 5 * p, 295)
r('10k', '+3V3', 'LOAD_DIS', x0 + 6 * p, 295)

s.text('NTC 10k B3950 on header J4 (bond to Q1 tab). VBUS divider 100k/15k (0.1304).', 190, 323, 1.5)
r('10k', '+3V3', 'NTC_SENSE', x0 + 0 * p, 340)
c('100nF', 'NTC_SENSE', 'GND', x0 + 1 * p, 340)
r('100k', 'VBUS', 'VBUS_SENSE', x0 + 2 * p, 340)
r('15k', 'VBUS_SENSE', 'GND', x0 + 3 * p, 340)
c('100nF', 'VBUS_SENSE', 'GND', x0 + 4 * p, 340)
c('100nF', '+5V', 'GND', x0 + 5 * p, 340)
c('10uF/10V', '+5V', 'GND', x0 + 6 * p, 340)

s.text('U6A: NTC open/very-cold detect (>3.0 V). U6B: hardware overcurrent comparator, trips ~1.38 A (0.454 V on shunt).', 190, 368, 1.5)
r('10k', '+3V3', 'NTC_REF', x0 + 0 * p, 385)
r('100k', 'NTC_REF', 'GND', x0 + 1 * p, 385)
r('47k', '+3V3', 'OC_REF', x0 + 2 * p, 385)
r('7.5k', 'OC_REF', 'GND', x0 + 3 * p, 385)
r('1k', 'SH_TOP', 'I_FILT', x0 + 4 * p, 385)
c('1nF', 'I_FILT', 'GND', x0 + 5 * p, 385)
c('100nF', '+5V', 'GND', x0 + 6 * p, 385)

# op-amps (TLV9062): U3 = loop + over-temperature, U6 = open-sensor + overcurrent
OP = dict(fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
opx = {'LCSC': 'C398355', 'MPN': 'TLV9062IDR'}
s.place('Amplifier_Operational', 'TLV9062', 'TLV9062IDR', 345, 215, {'3': 'VSET', '2': 'AMP_FB', '1': 'AMP_OUT'},
        ref='U3', unit=1, extra=opx, **OP)
s.place('Amplifier_Operational', 'TLV9062', 'TLV9062IDR', 345, 265, {'5': 'OTP_REF', '6': 'NTC_SENSE', '7': 'OTP_OUT'},
        ref='U3', unit=2, extra=opx, **OP)
s.place('Amplifier_Operational', 'TLV9062', 'TLV9062IDR', 345, 315, {'8': '+5V', '4': 'GND'},
        ref='U3', unit=3, extra=opx, **OP)
s.place('Amplifier_Operational', 'TLV9062', 'TLV9062IDR', 395, 215, {'3': 'NTC_SENSE', '2': 'NTC_REF', '1': 'NTC_OPEN'},
        ref='U6', unit=1, extra=opx, **OP)
s.place('Amplifier_Operational', 'TLV9062', 'TLV9062IDR', 395, 265, {'5': 'I_FILT', '6': 'OC_REF', '7': 'OC_TRIP'},
        ref='U6', unit=2, extra=opx, **OP)
s.place('Amplifier_Operational', 'TLV9062', 'TLV9062IDR', 395, 315, {'8': '+5V', '4': 'GND'},
        ref='U6', unit=3, extra=opx, **OP)

# power stage
s.place('Transistor_FET', 'IRLZ44N', 'FQP30N06L', 425, 350, {'1': 'GATE', '2': 'VBUS', '3': 'SH_TOP'}, ref='Q1',
        fp='Package_TO_SOT_THT:TO-220-3_Vertical', extra={'LCSC': 'C243087', 'MPN': 'FQP30N06L'})
s.place('Device', 'R', '0.33R 1% 1W', 425, 385, {'1': 'SH_TOP', '2': 'GND'},
        fp='Resistor_SMD:R_2512_6332Metric', extra={'LCSC': 'C314696', 'MPN': 'RL2512FK-070R33L'})
bss = {'LCSC': 'C52895', 'MPN': 'BSS138'}
s.place('Transistor_FET', 'BSS138', 'BSS138', 345, 355, {'1': 'KILL', '2': 'GND', '3': 'VSET'}, ref='Q2',
        fp='Package_TO_SOT_SMD:SOT-23', extra=bss)
s.place('Transistor_FET', 'BSS138', 'BSS138', 385, 355, {'1': 'KILL', '2': 'GND', '3': 'GATE'}, ref='Q3',
        fp='Package_TO_SOT_SMD:SOT-23', extra=bss)
s.place('Diode', 'BAT54C', 'BAT54C', 345, 388, {'1': 'LOAD_DIS', '2': 'OTP_OUT', '3': 'KILL'}, ref='D5',
        fp='Package_TO_SOT_SMD:SOT-23', extra={'LCSC': 'C37704', 'MPN': 'BAT54C,215'})
s.place('Diode', 'BAT54C', 'BAT54C', 390, 388, {'1': 'NTC_OPEN', '2': 'OC_TRIP', '3': 'KILL'}, ref='D6',
        fp='Package_TO_SOT_SMD:SOT-23', extra={'LCSC': 'C37704', 'MPN': 'BAT54C,215'})
tp('VSET', 435, 200, 'TP_VSET')
tp('SH_TOP', 435, 225, 'TP_ISH')
tp('GATE', 435, 250, 'TP_GATE')
tp('AMP_OUT', 435, 275, 'TP_AMPOUT')
s.text('Q1 tab = drain = VBUS: insulate the heatsink (silicone pad + shoulder washer).', 300, 402, 1.5)

# =========================================================================================
# 6. USER INTERFACE AND CONNECTORS
# =========================================================================================
s.box(450, 160, 585, 375, '6. UI AND CONNECTORS')
s.place('Connector_Generic', 'Conn_01x04', 'OLED SSD1306 0.96" I2C (GND VCC SCL SDA)', 480, 195,
        {'1': 'GND', '2': '+3V3', '3': 'I2C_SCL', '4': 'I2C_SDA'}, ref='J2',
        fp='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical', extra={'LCSC': 'C2691448', 'MPN': 'PZ254V-11-04P'})
r('4.7k', '+3V3', 'I2C_SCL', 525, 200)
r('4.7k', '+3V3', 'I2C_SDA', 542, 200)
s.place('Device', 'RotaryEncoder_Switch_MP', 'EC11 encoder + switch', 490, 250,
        {'A': 'ENC_A', 'B': 'ENC_B', 'C': 'GND', 'S1': 'ENC_SW', 'S2': 'GND', 'MP': 'GND'}, ref='SW1',
        fp='Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm', extra={'LCSC': 'C361165', 'MPN': 'EC11E1834403'})
r('10k', '+3V3', 'ENC_A', 525, 250)
r('10k', '+3V3', 'ENC_B', 542, 250)
c('10nF', 'ENC_A', 'GND', 559, 250)
c('10nF', 'ENC_B', 'GND', 574, 250)
s.place('Switch', 'SW_Push', 'LOAD ON/OFF', 495, 295, {'1': 'BTN_LOAD', '2': 'GND'}, ref='SW2',
        fp='Button_Switch_THT:SW_PUSH_6mm_H5mm')
s.place('Switch', 'SW_Push', 'PD VOLTAGE', 495, 312, {'1': 'BTN_PD', '2': 'GND'}, ref='SW3',
        fp='Button_Switch_THT:SW_PUSH_6mm_H5mm')
r('680', 'LED_LOAD', 'LED_LOAD_A', 535, 295)
led('red', 'GND', 'LED_LOAD_A', 560, 305)
r('680', 'LED_FAULT', 'LED_FAULT_A', 535, 335)
led('amber', 'GND', 'LED_FAULT_A', 560, 345)
s.place('Connector', 'Screw_Terminal_01x02', 'VBUS OUT', 480, 335, {'1': 'VBUS', '2': 'GND'}, ref='J5',
        fp='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
        extra={'LCSC': 'C474952', 'MPN': 'KF128-5.08-2P'})
s.place('Connector_Generic', 'Conn_01x02', 'NTC 10k B3950', 480, 355, {'1': 'NTC_SENSE', '2': 'GND'}, ref='J4',
        fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', extra={'LCSC': 'C492401', 'MPN': 'PZ254V-11-02P'})
s.place('Connector_Generic', 'Conn_01x02', 'FAN 5V', 535, 360, {'1': '+5V', '2': 'GND'}, ref='J6',
        fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', extra={'LCSC': 'C492401', 'MPN': 'PZ254V-11-02P'})
tp('VBUS', 150, 100, 'TP_VBUS')
tp('GND', 162, 100, 'TP_GND')
tp('+5V', 485, 105, 'TP_5V')
tp('+3V3', 570, 105, 'TP_3V3')
for k in range(4):
    s.place('Mechanical', 'MountingHole', 'M3', 555 + (k % 2) * 15, 35 + (k // 2) * 12, {}, prefix='H',
            fp='MountingHole:MountingHole_3.2mm_M3', show_value=False)

with open(os.path.join(OUT, 'USB-C-Eload-V1.kicad_sch'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(s.render())
json.dump(s.bom, open(os.path.join(OUT, 'bom_raw.json'), 'w'), indent=1)
json.dump(s.placed, open(os.path.join(OUT, 'placed.json'), 'w'), indent=1)
open(os.path.join(OUT, 'sym-lib-table'), 'w').write(
    '(sym_lib_table\n  (version 7)\n  (lib (name "eload")(type "KiCad")(uri "${KIPRJMOD}/eload.kicad_sym")(options "")(descr "USB-C Eload custom symbols"))\n)\n')
print('parts placed:', len(s.bom), ' lib symbols:', len(s.lib_symbols))

