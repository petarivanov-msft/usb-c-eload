import numpy as np, math

print('=== 1. SETPOINT / SENSING SCALE ===')
Rs = 0.33
div = 1.0 / (8.2 + 1.0)          # 1k / (8.2k+1k)
vset_fs = 3.3 * div
print(f'Setpoint divider ratio {div:.4f}; Vset full scale {vset_fs*1000:.1f} mV -> I full scale {vset_fs/Rs:.3f} A')
print(f'PWM step (12 bit, 64 MHz/4096 = {64e6/4096/1000:.2f} kHz): {vset_fs/Rs/4096*1000:.3f} mA/step')
print(f'Shunt drop @1 A {Rs*1000:.0f} mV, dissipation @1.25 A {1.25**2*Rs:.2f} W (2512 1 W part)')
print(f'ADC current LSB {3.3/4096/Rs*1000:.2f} mA (x16 oversample ~ {3.3/4096/Rs*1000/4:.2f} mA)')
vbias = 3.3 * 10e3 / (10e6 + 10e3)
print(f'Idle bias {vbias*1000:.2f} mV (Vos max 1.6 mV) -> dead zone {vbias/Rs*1000:.1f} mA; worst-case offset error +/-{1.6e-3/Rs*1000:.1f} mA')
rdiv = 15 / (100 + 15)
print(f'VBUS divider {rdiv:.4f}: 21 V -> {21*rdiv:.2f} V, 25 V -> {25*rdiv:.2f} V; LSB {3.3/4096/rdiv*1000:.2f} mV')

print('\n=== 2. NTC / HARDWARE OTP ===')
B = 3950.0
def rntc(tc):
    return 10e3 * math.exp(B * (1 / (tc + 273.15) - 1 / 298.15))
def vntc(tc, rpu=10e3):
    r = rntc(tc)
    return 3.3 * r / (r + rpu)
rup, rdn, rfb = 100e3, 7.5e3, 300e3
vlow = 3.3 / (1 + rup * (1 / rdn + 1 / rfb))
vhigh = (3.3 / rup + 4.9 / rfb) / (1 / rup + 1 / rdn + 1 / rfb)
def temp_at(v):
    lo, hi = -40, 200
    for _ in range(60):
        mid = (lo + hi) / 2
        if vntc(mid) > v:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
print(f'Comparator thresholds: trip V+={vlow*1000:.0f} mV (T={temp_at(vlow):.0f} C), release V+={vhigh*1000:.0f} mV (T={temp_at(vhigh):.0f} C)')
for tc in (25, 60, 80, 90, 100, 120):
    print(f'  NTC {tc:3d} C: R={rntc(tc):8.0f} ohm  V={vntc(tc)*1000:6.0f} mV  ADC={vntc(tc)/3.3*4095:5.0f}')

print('\n=== 3. MOSFET (FQP30N06L) ===')
# Transfer curve read from datasheet fig.2: Vgs for Id=1 A about 2.2 V @25C, ~2.5 V @-55C; allow +0.4 V part spread
vgs_need = 2.2 + 0.4 + 0.3
vg_avail_min = 4.3
print(f'Vgs needed @1.25 A (worst) ~{vgs_need:.1f} V; gate drive available >= {vg_avail_min - 1.25*Rs:.2f} V above source (5V rail >= 4.3 V) -> margin {vg_avail_min - 1.25*Rs - vgs_need:.2f} V')
RthJC, Pd25, derate = 1.9, 79.0, 0.53
for name, rcs, rsa in [('no sink (TO-220 free air, RthJA 62.5)', None, None), ('clip heatsink 6 C/W + insulator 1.5', 1.5, 6.0),
                      ('heatsink 3 C/W + insulator 1.5', 1.5, 3.0), ('heatsink 3 C/W + fan (~1.5 C/W) + insul', 1.5, 1.5)]:
    print(' ', name)
    for P in (5, 10, 15, 20):
        if rcs is None:
            tj = 25 + P * 62.5
            print(f'     P={P:2d} W: Tj={tj:6.0f} C', '(exceeds 175 C)' if tj > 175 else '')
        else:
            tc = 25 + P * (rcs + rsa)
            tj = tc + P * RthJC
            soa = (Pd25 - derate * (tc - 25))
            print(f'     P={P:2d} W: Tc={tc:5.0f} C Tj={tj:5.0f} C  DC-SOA power limit at that Tc={soa:5.1f} W  margin x{soa/P:.1f}', '  <-- too hot' if tj > 150 else '')
print('  DC SOA read from FQP30N06L fig. 9: ~3.9 A @ 20 V (79 W / 20 V) at Tc=25 C; our worst case is 1.0 A @ 20 V.')
for v in (5, 9, 12, 15, 20):
    print(f'  Vin={v:2d} V, 1.0 A -> {v*1.0:4.1f} W (+shunt/fuse drop {1.0*(Rs+0.06):.2f} V)')

print('\n=== 4. LOOP (integrator Rin*Cf) ===')
Rin, Cf, Rg = 10e3, 10e-9, 1e3
for gm in (0.1, 0.3, 1.0, 3.0):
    G = gm * Rs / (1 + gm * Rs)
    print(f'  gm={gm:3.1f} S: outer-loop (integrator) crossover ~{G/(2*math.pi*Rin*Cf):6.0f} Hz, current time-constant ~{1e3*Rin*Cf/G:5.2f} ms')
print('  Above ~1.6 kHz Cf couples AMP_OUT back to the inverting input: the op-amp is a unity-gain follower,')
print('  phase margin = datasheet 55 deg (G=+1), Rg=1k isolates the 1.2 nF gate load. Verify with a load-step test at bring-up.')
print('  Gate pole Rg*Ciss ~ %.1f us (>> loop crossover, no interaction).' % (Rg * (Cgs := 1.05e-9) * 1e6))

print('\n=== 4b. HARDWARE PROTECTION THRESHOLDS ===')
ioc = 3.3 * 7.5 / (47 + 7.5) / Rs
print(f'  Overcurrent comparator: Vref={3.3*7.5/(47+7.5)*1000:.0f} mV -> trip {ioc:.2f} A nominal (tol: 3V3 +/-2%, R 1%x2, Vos 1.6 mV -> {ioc*0.93:.2f}-{ioc*1.07:.2f} A)')
print(f'  Passive setpoint cap: {vset_fs/Rs:.3f} A nominal, worst ~{vset_fs/Rs*1.04+0.005:.2f} A (3V3 +2%, R 1%, shunt 1%, Vos) -> margin to OC trip OK')
print(f'  NTC-open detect threshold {3.3*100/110:.2f} V (NTC at {temp_at(3.0):.0f} C or open): trips if sensor missing')
print(f'  KILL levels: comparator -> ~4.7 V; LOAD_DIS-high -> ~3.0 V (BSS138 Vth max 1.5 V). HW_FAULT = KILL x 2/3: {4.7*2/3:.2f} V / {3.0*2/3:.2f} V')
Q1_ID = 1.38
print(f'  OC-trip worst case at 20 V: {20*Q1_ID:.1f} W for a few microseconds (comparator ~1-2 us + gate discharge ~2 us) -> pulsed SOA OK')
print('\n=== 5. RAIL BUDGET ===')
i5 = 0.55e-3 * 2 + 0.05 + 0.02 + 0.15   # opamp both ch, LDO load, fan header allowance
i33 = 0.012 + 0.025 + 0.004
print(f'3V3 load ~{i33*1000:.0f} mA (MCU 12 + OLED 25 + misc) -> LDO dissipation (5->3.3 V) {(5-3.3)*i33*1000:.0f} mW')
for vin in (5, 9, 12, 20):
    p_out = 5 * (i33 + 0.002 + 0.006)
    print(f'  Vin={vin:2d} V: 5 V rail load ~{(i33+0.01)*1000:.0f} mA (fan header off) -> buck input ~{p_out/0.8/vin*1000:.0f} mA @80% eff')
print('  Fan header: ~150 mA 5 V fan adds ~0.75 W; buck rated 2 A.')
print('  AP63205 dropout at VBUS=5 V: rail ~4.7-4.9 V light load (3.8 V min Vin, ~0.3 V drop) -> gate drive & op-amp OK; LDO needs >= 3.6 V.')

