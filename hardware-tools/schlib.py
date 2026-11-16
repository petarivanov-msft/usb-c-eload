"""Generator for USB-C-Eload-V1.kicad_sch (label-connected schematic, KiCad 10 format)."""
import sys, os, math, uuid, re, json, copy
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import kisym
from kisym import Sym, dump, flatten, pins_of, parse

S = Sym
PROJ_DIR = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
PROJECT = 'USB-C-Eload-V1'
ROOT_UUID = '87c1fb96-775c-478e-8feb-07854d7e8dcb'

CUSTOM_LIB = os.path.join(PROJ_DIR, 'eload.kicad_sym')


def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace(chr(10), '\\n')


def uid():
    return str(uuid.uuid4())


def n(v):
    v = round(v, 3)
    return int(v) if v == int(v) else v


class Schematic:
    def __init__(self):
        self.lib_symbols = {}   # 'Lib:Name' -> sexp
        self.items = []         # sexp elements
        self.refs = {}          # prefix -> counter
        self.pwr_n = 0
        self.bom = []           # dicts
        self.placed = []        # for footprint check: (ref, footprint, [pin numbers used])

    # ---- library handling
    def lib_sym(self, lib, name):
        key = f'{lib}:{name}'
        if key not in self.lib_symbols:
            if lib == 'eload':
                cl = parse(open(CUSTOM_LIB, encoding='utf-8').read())
                sym = None
                for c in cl:
                    if isinstance(c, list) and c and c[0] == 'symbol' and c[1] == name:
                        sym = copy.deepcopy(c)
                sym[1] = key
                self.lib_symbols[key] = sym
            else:
                self.lib_symbols[key] = kisym.embed(lib, name)
        return self.lib_symbols[key]

    # ---- primitives
    def wire(self, x1, y1, x2, y2):
        self.items.append([S('wire'), [S('pts'), [S('xy'), n(x1), n(y1)], [S('xy'), n(x2), n(y2)]],
                           [S('stroke'), [S('width'), 0], [S('type'), S('default')]], [S('uuid'), uid()]])

    def label(self, name, x, y, ang):
        just = 'left bottom' if ang in (0, 90) else 'right bottom'
        j = [S('justify')] + [S(w) for w in just.split()]
        self.items.append([S('label'), name, [S('at'), n(x), n(y), ang],
                           [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], j], [S('uuid'), uid()]])

    def global_label(self, name, x, y, ang):
        just = 'left' if ang in (0, 90) else 'right'
        self.items.append([S('global_label'), name, [S('shape'), S('input')], [S('at'), n(x), n(y), ang],
                           [S('fields_autoplaced'), S('yes')],
                           [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S(just)]], [S('uuid'), uid()],
                           [S('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [S('at'), n(x), n(y), 0], [S('hide'), S('yes')],
                            [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]]])

    def noconn(self, x, y):
        self.items.append([S('no_connect'), [S('at'), n(x), n(y)], [S('uuid'), uid()]])

    def text(self, s, x, y, size=1.8, bold=False):
        f = [S('font'), [S('size'), size, size]]
        if bold:
            f.append([S('bold'), S('yes')])
        self.items.append([S('text'), esc(s), [S('exclude_from_sim'), S('no')], [S('at'), n(x), n(y), 0],
                           [S('effects'), f, [S('justify'), S('left'), S('bottom')]], [S('uuid'), uid()]])

    def box(self, x1, y1, x2, y2, title=None):
        self.items.append([S('rectangle'), [S('start'), n(x1), n(y1)], [S('end'), n(x2), n(y2)],
                           [S('stroke'), [S('width'), 0.254], [S('type'), S('dash')]],
                           [S('fill'), [S('type'), S('none')]], [S('uuid'), uid()]])
        if title:
            self.text(title, x1 + 2, y1 + 5, 2.5, True)

    # ---- symbol placement
    def next_ref(self, prefix):
        self.refs[prefix] = self.refs.get(prefix, 0) + 1
        return f'{prefix}{self.refs[prefix]}'

    def place(self, lib, name, value, x, y, nets, fp=None, ref=None, prefix=None, unit=1,
              extra=None, power=False, show_value=True, ref_hide=False):
        if not power:
            x, y = round(x / 2.54) * 2.54, round(y / 2.54) * 2.54
        sym = self.lib_sym(lib, name)
        flat = flatten(lib, name) if lib != 'eload' else sym
        libprops = {c[1]: c for c in flat if isinstance(c, list) and c and c[0] == 'property'}
        if ref is None:
            ref = self.next_ref(prefix or re.sub(r'[^A-Za-z#]', '', libprops['Reference'][2]) or 'U')
        else:
            m = re.match(r'^([A-Za-z]+)(\d+)$', ref)
            if m:
                self.refs[m.group(1)] = max(self.refs.get(m.group(1), 0), int(m.group(2)))
        footprint = fp if fp is not None else libprops.get('Footprint', [0, 0, ''])[2]
        datasheet = libprops.get('Datasheet', [0, 0, ''])[2]
        desc = libprops.get('Description', [0, 0, ''])[2]

        def pr(pname, pval, hide=False, keep_pos=True):
            lp = libprops.get(pname)
            ax, ay, aa = x, y, 0
            if lp is not None:
                at = [c for c in lp if isinstance(c, list) and c[0] == 'at'][0]
                ax, ay, aa = x + float(at[1]), y - float(at[2]), float(at[3])
            justs = []
            if lp is not None:
                for c in lp:
                    if isinstance(c, list) and c[0] == 'effects':
                        for d in c:
                            if isinstance(d, list) and d[0] == 'justify':
                                justs = d
            eff = [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]
            if justs:
                eff.append(justs)
            p = [S('property'), pname, pval, [S('at'), n(ax), n(ay), n(aa)]]
            if hide:
                p.append([S('hide'), S('yes')])
            p.append(eff)
            return p

        inst = [S('symbol'), [S('lib_id'), f'{lib}:{name}'], [S('at'), n(x), n(y), 0], [S('unit'), unit],
                [S('exclude_from_sim'), S('no')], [S('in_bom'), S('no' if power else 'yes')],
                [S('on_board'), S('no' if power else 'yes')], [S('dnp'), S('no')], [S('uuid'), uid()]]
        inst.append(pr('Reference', ref, hide=(power or ref_hide)))
        inst.append(pr('Value', esc(value), hide=(not show_value)))
        inst.append(pr('Footprint', footprint, hide=True))
        inst.append(pr('Datasheet', datasheet, hide=True))
        inst.append(pr('Description', desc, hide=True))
        if extra:
            k = 0
            for key, val in extra.items():
                k += 1
                inst.append([S('property'), key, esc(val), [S('at'), n(x), n(y + 1.27 * k), 0], [S('hide'), S('yes')],
                             [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]])

        allpins = pins_of(flat)
        unitpins = [p for p in allpins if p['unit'] in (0, unit)]
        # stagger the stubs of adjacent sideways power flags so they do not overlap
        def horiz_out(p):
            a = math.radians(p['angle'])
            return abs(round(math.cos(a))) == 1
        hp = sorted([p for p in unitpins if nets.get(p['number']) in self.POWER_SYM and horiz_out(p)],
                    key=lambda p: (p['x'] > 0, -p['y']))
        stagger = {p['number']: (i % 2) for i, p in enumerate(hp)}
        for p in unitpins:
            inst.append([S('pin'), p['number'], [S('uuid'), uid()]])
        inst.append([S('instances'), [S('project'), PROJECT, [S('path'), f'/{ROOT_UUID}', [S('reference'), ref], [S('unit'), unit]]]])
        self.items.append(inst)

        used = []
        drawn = {}
        for p in unitpins:
            num = p['number']
            if num not in nets and p.get('name') in nets and p.get('name'):
                pass
            net = nets.get(num)
            if net is None:
                continue
            px, py = x + p['x'], y - p['y']
            a = math.radians(p['angle'])
            tx, ty = round(math.cos(a)), -round(math.sin(a))
            ox, oy = -tx, -ty
            key = (round(px, 3), round(py, 3))
            if key in drawn:
                assert drawn[key] == net, f'{ref} pin {num}: conflicting nets at same location {drawn[key]} vs {net}'
                used.append(num)
                continue
            drawn[key] = net
            used.append(num)
            L = 2.54 + 7.62 * stagger.get(num, 0)
            ex, ey = px + ox * L, py + oy * L
            if net == 'NC':
                self.noconn(px, py)
                continue
            self.wire(px, py, ex, ey)
            ang = 0 if ox == 1 else 180 if ox == -1 else 90 if oy == -1 else 270
            self.net_end(net, ex, ey, ang, ox, oy)
        self.placed.append((ref, footprint, sorted(set(used)), f'{lib}:{name}', unit))
        if not power:
            self.bom.append(dict(ref=ref, value=value, footprint=footprint, unit=unit, **(extra or {})))
        return ref

    POWER_SYM = {'GND': ('power', 'GND', 'down'), '+5V': ('power', '+5V', 'up'), '+3V3': ('power', '+3V3', 'up'),
                 'VBUS': ('power', 'VBUS', 'up')}

    def net_end(self, net, ex, ey, ang, ox, oy):
        ps = self.POWER_SYM.get(net)
        if ps and ((ps[2] == 'down' and oy == 1) or (ps[2] == 'up' and oy == -1)):
            self.pwr_n += 1
            self.place(ps[0], ps[1], net, ex, ey, {'1': None}, ref=f'#PWR{self.pwr_n:03d}', power=True, fp='')
        elif ps:
            self.global_label(net, ex, ey, ang)
        else:
            self.label(net, ex, ey, ang)

    def pwr_flag(self, net, x, y):
        """PWR_FLAG hanging off a net marker so ERC sees the net as driven."""
        x, y = round(x / 1.27) * 1.27, round(y / 1.27) * 1.27
        self.pwr_n += 1
        self.place('power', 'PWR_FLAG', 'PWR_FLAG', x, y, {'1': None}, ref=f'#FLG{self.pwr_n:03d}', power=True, fp='')
        # PWR_FLAG pin points up (angle 90): body above the pin; net marker below the pin
        self.wire(x, y, x, y + 2.54)
        self.net_end(net, x, y + 2.54, 270, 0, 1)

    # ---- passives helpers (vertical, pin1 top, pin2 bottom)
    def R(self, value, top, bot, x, y, lcsc='', mpn='', fp='Resistor_SMD:R_0603_1608Metric', **kw):
        return self.place('Device', 'R', value, x, y, {'1': top, '2': bot}, fp=fp,
                          extra={'LCSC': lcsc, 'MPN': mpn} if lcsc or mpn else None, **kw)

    def C(self, value, top, bot, x, y, lcsc='', mpn='', fp='Capacitor_SMD:C_0603_1608Metric', **kw):
        return self.place('Device', 'C', value, x, y, {'1': top, '2': bot}, fp=fp,
                          extra={'LCSC': lcsc, 'MPN': mpn} if lcsc or mpn else None, **kw)

    # ---- output
    def render(self):
        libs = [S('lib_symbols')] + [self.lib_symbols[k] for k in sorted(self.lib_symbols)]
        tb = [S('title_block'), [S('title'), 'USB-C PD Electronic Load V1'], [S('date'), '2026-11-13'],
              [S('rev'), '0.1'], [S('company'), 'Petar Ivanov'],
              [S('comment'), 1, 'CC load: 5/9/12/15/20V PD sink (CH224A), 0-1A, 20W target'],
              [S('comment'), 2, 'MCU: STM32G030F6P6  |  Load FET: FQP30N06L (TO-220, DC SOA verified)']]
        sch = [S('kicad_sch'), [S('version'), 20260306], [S('generator'), 'eeschema'], [S('generator_version'), '10.0'],
               [S('uuid'), ROOT_UUID], [S('paper'), 'A2'], tb, libs] + self.items + [
            [S('sheet_instances'), [S('path'), '/', [S('page'), '1']]], [S('embedded_fonts'), S('no')]]
        return dump(sch) + '\n'


