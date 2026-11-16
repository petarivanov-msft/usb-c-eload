import json, re, os, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import kisym
FP = kisym.FPDIR
placed = json.load(open(sys.argv[1]))
seen = {}
bad = 0
for ref, fp, used, libsym, unit in placed:
    if not fp or ref.startswith('#'):
        continue
    lib, name = fp.split(':')
    path = os.path.join(FP, lib + '.pretty', name + '.kicad_mod')
    if not os.path.exists(path):
        print('MISSING FOOTPRINT', ref, fp); bad += 1; continue
    if fp not in seen:
        t = open(path, encoding='utf-8').read()
        seen[fp] = set(re.findall(r'\(pad "([^"]*)"', t))
    pads = seen[fp]
    lb, sn = libsym.split(':')
    if lb == 'eload':
        symp = {p['number'] for p in kisym.pins_of(kisym.parse(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'eload.kicad_sym')).read())[4])}
    else:
        symp = {p['number'] for p in kisym.pins_of(kisym.flatten(lb, sn)) if p['unit'] in (0, unit)}
    missing = [p for p in symp if p not in pads]
    if missing and not (sn == 'TLV9062'):
        print('PAD MISMATCH', ref, fp, 'symbol pins without pad:', missing, 'pads:', sorted(pads)); bad += 1
    if sn == 'TLV9062':
        allp = {p['number'] for p in kisym.pins_of(kisym.flatten(lb, sn))}
        if not allp <= pads:
            print('PAD MISMATCH', ref, fp, allp - pads); bad += 1
print('checked', len(seen), 'footprints; problems:', bad)
for fp, pads in seen.items():
    print(f'  {fp}: pads {sorted(p for p in pads if p)}')
