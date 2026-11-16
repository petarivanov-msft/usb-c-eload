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

