"""Generates eload.kicad_sym (custom parts) for USB-C-Eload-V1."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from kisym import Sym, dump

S = Sym


def eff(size=1.27, hide=False, justify=None, italic=False):
    e = [S('effects'), [S('font'), [S('size'), size, size]] + ([[S('italic'), S('yes')]] if italic else [])]
    if justify:
        e.append([S('justify'), S(justify)])
    if hide:
        e.append([S('hide'), S('yes')])
    return e


def prop(name, value, x, y, a=0, hide=False, justify=None):
    p = [S('property'), name, value, [S('at'), x, y, a]]
    if hide:
        p.append([S('hide'), S('yes')])
    p.append(eff(justify=justify))
    return p


def pin(ptype, x, y, ang, name, number, length=2.54):
    return [S('pin'), S(ptype), S('line'), [S('at'), x, y, ang], [S('length'), length],
            [S('name'), name, eff()], [S('number'), number, eff()]]


def ch224a():
    left = [  # (type, name, number, y)
        ('power_in', 'VHV', '1', 7.62),
        ('input', 'VBUS', '8', 5.08),
        ('bidirectional', 'CC1', '7', 2.54),
        ('bidirectional', 'CC2', '6', 0.0),
        ('bidirectional', 'DP', '4', -2.54),
        ('bidirectional', 'DM', '5', -5.08),
    ]
    right = [
        ('input', 'CFG1', '9', 7.62),
        ('bidirectional', 'CFG2/SCL', '2', 5.08),
        ('bidirectional', 'CFG3/SDA', '3', 2.54),
        ('open_collector', 'PG', '10', 0.0),
    ]
    pins = [pin(t, -12.7, y, 0, n, num) for t, n, num, y in left]
    pins += [pin(t, 12.7, y, 180, n, num) for t, n, num, y in right]
    pins.append(pin('power_in', 0, -10.16, 90, 'GND', '11'))
    sym = [S('symbol'), 'CH224A',
           [S('pin_names'), [S('offset'), 1.016]],
           [S('exclude_from_sim'), S('no')], [S('in_bom'), S('yes')], [S('on_board'), S('yes')],
           [S('in_pos_files'), S('yes')], [S('duplicate_pin_numbers_are_jumpers'), S('no')],
           prop('Reference', 'U', -10.16, 10.795, 0, justify='left'),
           prop('Value', 'CH224A', 10.16, 10.795, 0, justify='right'),
           prop('Footprint', 'Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm', 0, 0, 0, hide=True),
           prop('Datasheet', 'https://www.wch-ic.com/downloads/CH224DS1_PDF.html', 0, 0, 0, hide=True),
           prop('Description', 'WCH USB PD3.2 sink controller, I2C/single-resistor/IO config, 4-30V, ESSOP-10-EP', 0, 0, 0, hide=True),
           [S('symbol'), 'CH224A_0_1',
            [S('rectangle'), [S('start'), -10.16, 10.16], [S('end'), 10.16, -10.16],
             [S('stroke'), [S('width'), 0.254], [S('type'), S('default')]], [S('fill'), [S('type'), S('background')]]]],
           [S('symbol'), 'CH224A_1_1'] + pins,
           [S('embedded_fonts'), S('no')]]
    return sym


def build():
    lib = [S('kicad_symbol_lib'), [S('version'), 20251024], [S('generator'), 'kicad_symbol_editor'],
           [S('generator_version'), '10.0'], ch224a()]
    return dump(lib) + '\n'


if __name__ == '__main__':
    out = sys.argv[1]
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(build())
    print('wrote', out)

