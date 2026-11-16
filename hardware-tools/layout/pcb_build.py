"""Builds the USB-C-Eload-V1 PCB from the netlist: place footprints, outline, planes.
Run with KiCad's python:  python pcb_build.py <netlist.xml> <outdir>
"""
import pcbnew, sys, os, re, json, math, copy
import xml.etree.ElementTree as ET

NET, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
FPDIR = r'C:\Program Files\KiCad\10.0\share\kicad\footprints'
MM = pcbnew.FromMM
BW, BH = 100.0, 75.0           # board size (mm)
OX, OY = 50.0, 50.0            # board origin inside the KiCad sheet

def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))

# ------------------------------------------------------------------ netlist
root = ET.parse(NET).getroot()
comps = {}
for c in root.find('components'):
    ref = c.get('ref')
    fields = {f.get('name'): f.text for f in (list(c.find('fields')) if c.find('fields') is not None else [])}
    comps[ref] = dict(value=c.findtext('value'), fp=c.findtext('footprint'), fields=fields,
                      uuid=(c.findtext('tstamps') or '').split()[0] if c.findtext('tstamps') else None)
nets = {}
for nn in root.find('nets'):
    name = nn.get('name')
    nets[name] = [(x.get('ref'), x.get('pin')) for x in nn]

# ------------------------------------------------------------------ placement table (centre x, y, rotation)
P = {
    # USB input / protection
    'J1': (4.0, 37.5, 270), 'F1': (15.0, 33.0, 0), 'D1': (16.5, 47.5, 0), 'C1': (24.0, 33.0, 0),
    'C2': (24.0, 37.5, 0), 'TP5': (21.0, 41.0, 0), 'TP6': (21.0, 45.5, 0),
    # CH224A
    'U2': (34.0, 54.0, 0), 'C3': (28.0, 49.0, 0), 'R1': (41.0, 49.0, 90), 'R2': (44.0, 49.0, 90),
    'D2': (47.0, 53.0, 90),
    # buck + LDO
    'U4': (16.0, 66.0, 0), 'C4': (9.0, 71.0, 0), 'C5': (9.0, 65.0, 0), 'C6': (21.0, 62.5, 0),
    'L1': (27.0, 69.0, 0), 'C7': (35.0, 66.0, 0), 'C8': (35.0, 71.0, 0), 'C9': (40.5, 66.0, 0),
    'TP7': (42.0, 72.5, 0), 'U5': (49.0, 67.0, 0), 'C10': (44.5, 62.0, 0), 'C11': (54.0, 63.0, 0),
    'C12': (54.0, 67.0, 0),
    # load stage
    'Q1': (24.0, 8.5, 0), 'R27': (31.5, 17.0, 90), 'TP2': (37.0, 12.0, 0), 'TP3': (20.0, 14.0, 0),
    'J4': (38.0, 5.0, 0), 'J6': (44.0, 5.0, 0),
    # loop / analog
    'U3': (47.0, 22.0, 0), 'U6': (63.0, 22.0, 0),
    'R7': (40.5, 28.0, 90), 'R8': (43.5, 28.0, 90), 'C18': (46.5, 28.0, 90), 'R9': (49.5, 28.0, 90),
    'R10': (52.5, 28.0, 90), 'R11': (55.5, 28.0, 90), 'C19': (58.5, 28.0, 90),
    'R3': (40.5, 36.0, 90), 'R4': (43.5, 36.0, 90), 'R5': (46.5, 36.0, 90), 'C16': (49.5, 36.0, 90),
    'R6': (52.5, 36.0, 90), 'C17': (55.5, 36.0, 90),
    'TP1': (59.5, 36.0, 0), 'TP4': (59.5, 31.0, 0),
    'R12': (40.5, 44.0, 90), 'R13': (43.5, 44.0, 90), 'R14': (46.5, 44.0, 90), 'R15': (49.5, 44.0, 90),
    'R16': (52.5, 44.0, 90), 'R17': (55.5, 44.0, 90), 'R18': (58.5, 44.0, 90),
    'Q2': (62.0, 38.0, 0), 'Q3': (66.0, 38.0, 0), 'D5': (62.0, 44.0, 0), 'D6': (67.0, 44.0, 0),
    'R19': (70.5, 26.0, 90), 'C20': (73.5, 26.0, 90), 'R22': (70.5, 18.0, 90), 'R23': (73.5, 18.0, 90),
    'R24': (70.5, 12.0, 90), 'R25': (73.5, 12.0, 90), 'R26': (76.5, 12.0, 90), 'C24': (79.5, 12.0, 90),
    'C25': (76.5, 18.0, 90), 'C22': (82.5, 18.0, 90), 'C23': (79.5, 18.0, 90), 'C9X': (0, 0, 0),
    'R20': (70.5, 34.0, 90), 'R21': (73.5, 34.0, 90), 'C21': (76.5, 34.0, 90),
    # MCU
    'U1': (82.0, 48.0, 0), 'C13': (74.0, 41.5, 0), 'C14': (88.0, 41.5, 0), 'C15': (74.0, 56.0, 0),
    'J3': (76.0, 62.0, 90), 'TP8': (80.0, 58.0, 0),
    # UI / connectors
    'SW1': (74.0, 8.0, 0), 'R30': (84.0, 24.5, 90), 'R31': (87.0, 24.5, 90), 'C26': (90.0, 24.5, 90),
    'C27': (93.0, 24.5, 90), 'SW2': (86.0, 30.0, 0), 'SW3': (86.0, 42.0, 0),
    'R32': (100.0, 60.0, 90), 'D7': (100.0, 65.0, 90), 'R33': (104.0, 60.0, 90), 'D8': (104.0, 65.0, 90),
    'R28': (96.0, 62.0, 90), 'R29': (93.0, 62.0, 90), 'J2': (94.0, 11.0, 0), 'J5': (56.0, 66.0, 0),
    # mounting holes
    'H1': (4.0, 4.0, 0), 'H2': (BW - 4.0, 4.0, 0), 'H3': (4.0, BH - 4.0, 0), 'H4': (BW - 4.0, BH - 4.0, 0),
}
P.pop('C9X', None)

# ------------------------------------------------------------------ build board
board = pcbnew.BOARD()
board.SetCopperLayerCount(4 if os.environ.get('LAYERS') == '4' else 2)
netitems = {}
for name in nets:
    if name.startswith('unconnected-'):
        continue
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netitems[name] = ni

fps = {}
for ref, c in comps.items():
    lib, name = c['fp'].split(':')
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
    if fp is None:
        raise SystemExit('cannot load ' + c['fp'])
    fp.SetReference(ref)
    fp.SetValue(c['value'])
    if c['uuid']:
        fp.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
    fp.Reference().SetTextThickness(MM(0.12))
    fp.Value().SetVisible(False)
    board.Add(fp)
    fps[ref] = fp

for name, nodes in nets.items():
    if name not in netitems:
        continue
    for ref, pin in nodes:
        for pad in fps[ref].Pads():
            if pad.GetNumber() == pin:
                pad.SetNet(netitems[name])

# ------------------------------------------------------------------ placement with overlap resolution
def court(fp):
    try:
        fp.BuildCourtyardCaches()
    except Exception:
        pass
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    return bb

def rect_of(fp):
    bb = court(fp)
    return [pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())]

keepouts = [  # x1,y1,x2,y2 in board coords (heatsink zone above Q1, board edge)
]
placed = []
GAP = 0.3

def overlaps(r, others):
    for o in others:
        if r[0] < o[2] + GAP and r[2] + GAP > o[0] and r[1] < o[3] + GAP and r[3] + GAP > o[1]:
            return True
    return False

order = ['H1', 'H2', 'H3', 'H4', 'J1', 'Q1', 'SW1', 'SW2', 'SW3', 'J5', 'J2', 'U2', 'U1', 'U3', 'U6', 'U4', 'U5', 'L1',
         'R27', 'F1', 'D1', 'J3', 'J4', 'J6']
order += [r for r in P if r not in order]
report = []
final = {}
for ref in order:
    if ref not in fps:
        continue
    x, y, rot = P[ref]
    fp = fps[ref]
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(V(0, 0))
    r0 = rect_of(fp)                       # rect at origin of the sheet frame (OX,OY offset included)
    base = [r0[0] - OX, r0[1] - OY, r0[2] - OX, r0[3] - OY]
    best = None
    fixed = ref in ('J1', 'H1', 'H2', 'H3', 'H4', 'Q1')
    cand = [(0.0, 0.0)]
    if not fixed:
        for rad in [i * 0.5 for i in range(1, 41)]:
            n = max(8, int(rad * 8))
            for k in range(n):
                a = 2 * math.pi * k / n
                cand.append((rad * math.cos(a), rad * math.sin(a)))
    for dx, dy in cand:
        cx, cy = round((x + dx) * 2) / 2, round((y + dy) * 2) / 2
        rect = [base[0] + cx, base[1] + cy, base[2] + cx, base[3] + cy]
        if rect[0] < 1.0 or rect[1] < 1.0 or rect[2] > BW - 1.0 or rect[3] > BH - 1.0:
            if not fixed:
                continue
        if overlaps(rect, placed) or overlaps(rect, keepouts):
            continue
        best = (cx, cy, rect)
        break
    if best is None:
        best = (x, y, [base[0] + x, base[1] + y, base[2] + x, base[3] + y])
        report.append(f'NO SPACE for {ref}')
    fp.SetPosition(V(best[0], best[1]))
    placed.append(best[2])
    final[ref] = [best[0], best[1], rot]
    if abs(best[0] - x) > 0.01 or abs(best[1] - y) > 0.01:
        report.append(f'{ref}: moved ({x},{y}) -> ({best[0]:.1f},{best[1]:.1f})')
for line in report:
    print(line)

# ------------------------------------------------------------------ connectivity-driven refinement
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import placer
geom = {}
for ref, fp in fps.items():
    fp.SetOrientationDegrees(0)
    fp.SetPosition(V(0, 0))
    r0 = rect_of(fp)
    pads = []
    for pad in fp.Pads():
        pads.append((pad.GetNetname(), pcbnew.ToMM(pad.GetX()) - OX, pcbnew.ToMM(pad.GetY()) - OY))
    geom[ref] = dict(pads=pads, rect=(r0[0] - OX, r0[1] - OY, r0[2] - OX, r0[3] - OY))
# convention check: rotate U1 by 90 and compare with pcbnew
t = fps['U1']
t.SetOrientationDegrees(90); t.SetPosition(V(0, 0))
for pad in t.Pads():
    if pad.GetNumber() == '1':
        ex = (pcbnew.ToMM(pad.GetX()) - OX, pcbnew.ToMM(pad.GetY()) - OY)
        n0 = [p for p in geom['U1']['pads']]
        break
px = [p for p in fps['U1'].Pads() if p.GetNumber() == '1'][0]
p1 = [(a, b) for (n, a, b), pp in zip(geom['U1']['pads'], [q for q in fps['U1'].Pads()]) if pp.GetNumber() == '1'][0]
mine = placer.rot_vec(p1[0], p1[1], 90)
assert abs(mine[0] - ex[0]) < 0.01 and abs(mine[1] - ex[1]) < 0.01, ('rotation convention mismatch', mine, ex)
pl = placer.Placer(geom, final, (BW, BH))
c0 = pl.total()
c1, acc = pl.run(iters=int(os.environ.get('SA_ITERS', '40000')), seed=int(os.environ.get('SA_SEED', '1')))
print(f'placement cost {c0:.0f} -> {c1:.0f}  (accepted {acc})')
for ref, (x, y, rot) in pl.pos.items():
    fps[ref].SetOrientationDegrees(rot)
    fps[ref].SetPosition(V(x, y))

# ------------------------------------------------------------------ hand fan-out of the USB-C connector (0.5 mm pitch)
def add_track(x1, y1, x2, y2, w, layer, netname):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(x1, y1)); t.SetEnd(pcbnew.VECTOR2I(x2, y2))
    t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(netitems[netname])
    board.Add(t)

def add_via(x, y, netname, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(netitems[netname]); board.Add(v)

def fanout_usbc():
    pads = {}
    for p in fps['J1'].Pads():
        if p.GetNumber() != 'SH':
            pads[p.GetNumber()] = (p.GetX(), p.GetY())
    tail = max(x for x, y in pads.values()) + MM(0.725)     # pad ends (board is to +x)
    X = lambda mmx: tail + MM(mmx)
    Y = lambda n: pads[n][1]
    pxc = lambda n: pads[n][0]
    # VBUS_USB: via at each group, joined on B.Cu
    for grp in ('A4', 'A9'):
        add_track(pxc(grp), Y(grp), X(0.5), Y(grp), 0.5, pcbnew.F_Cu, '/VBUS_USB')
        add_via(X(0.5), Y(grp), '/VBUS_USB')
    add_track(X(0.5), Y('A4'), X(0.5), Y('A9'), 0.6, pcbnew.B_Cu, '/VBUS_USB')
    # GND groups: via to the plane
    for grp in ('A1', 'A12'):
        add_track(pxc(grp), Y(grp), X(0.5), Y(grp), 0.5, pcbnew.F_Cu, 'GND')
        add_via(X(0.5), Y(grp), 'GND')
    # CC lines leave straight
    add_track(pxc('A5'), Y('A5'), X(3.4), Y('A5'), 0.2, pcbnew.F_Cu, '/CC1')
    add_track(pxc('B5'), Y('B5'), X(3.4), Y('B5'), 0.2, pcbnew.F_Cu, '/CC2')
    # D-: vias then B.Cu link
    for n in ('B7', 'A7'):
        add_track(pxc(n), Y(n), X(1.8), Y(n), 0.2, pcbnew.F_Cu, '/USB_DM')
        add_via(X(1.8), Y(n), '/USB_DM', d=0.5)
    add_track(X(1.8), Y('B7'), X(1.8), Y('A7'), 0.2, pcbnew.B_Cu, '/USB_DM')
    # D+: loop on F.Cu beyond the D- vias
    add_track(pxc('A6'), Y('A6'), X(2.8), Y('A6'), 0.2, pcbnew.F_Cu, '/USB_DP')
    add_track(X(2.8), Y('A6'), X(2.8), Y('B6'), 0.2, pcbnew.F_Cu, '/USB_DP')
    add_track(pxc('B6'), Y('B6'), X(2.8), Y('B6'), 0.2, pcbnew.F_Cu, '/USB_DP')

fanout_usbc()

def gnd_fanout():
    gnd = netitems['GND']
    gcode = gnd.GetNetCode()
    count = 0
    clr = MM(0.15)
    def conflict(pt, radius):
        for t in board.GetTracks():
            if t.GetNetCode() != gcode and t.HitTest(pt, radius + clr):
                return True
        for p in board.GetPads():
            if p.GetNetCode() != gcode and p.HitTest(pt, radius + clr):
                return True
        for v in [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']:
            pp = v.GetPosition()
            if math.hypot(pp.x - pt.x, pp.y - pt.y) < radius + v.GetWidth(pcbnew.F_Cu) / 2 + clr:
                return True
        for p in board.GetPads():
            if p.GetDrillSizeX() > 0:
                pp = p.GetPosition()
                if math.hypot(pp.x - pt.x, pp.y - pt.y) < max(p.GetDrillSizeX(), p.GetSizeX()) / 2 + radius + clr:
                    return True
        return False
    r = MM(0.25)
    for ref, fp in fps.items():
        if ref in ('J1', 'C19') or ref.startswith('TP'):
            continue
        fc = fp.GetPosition()
        for pad in fp.Pads():
            if pad.GetNetname() != 'GND' or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            bb = pad.GetBoundingBox()
            cx, cy = pad.GetPosition().x, pad.GetPosition().y
            hw, hh = bb.GetWidth() / 2, bb.GetHeight() / 2
            if hw > MM(1.2) and hh > MM(1.2):                       # exposed pad: via grid inside
                for dx in (-0.5, 0.5):
                    for dy in (-1.0, 0.0, 1.0):
                        pt = pcbnew.VECTOR2I(int(cx + MM(dx)), int(cy + MM(dy)))
                        if not conflict(pt, r):
                            add_via(pt.x, pt.y, 'GND', d=0.5, drill=0.3); count += 1
                continue
            vx, vy = cx - fc.x, cy - fc.y
            dirs = sorted([(1, 0), (-1, 0), (0, 1), (0, -1)], key=lambda d: -(d[0] * vx + d[1] * vy))
            done = False
            for d in dirs:
                for extra in (0.95, 1.2, 1.5):
                    ext = (hw if d[0] else hh)
                    off = ext + MM(extra)
                    pt = pcbnew.VECTOR2I(int(cx + d[0] * off), int(cy + d[1] * off))
                    if conflict(pt, r):
                        continue
                    mid = pcbnew.VECTOR2I(int((cx + pt.x) / 2), int((cy + pt.y) / 2))
                    if conflict(mid, MM(0.125)):
                        continue
                    add_track(cx, cy, pt.x, pt.y, 0.25, pcbnew.F_Cu, 'GND')
                    add_via(pt.x, pt.y, 'GND', d=0.5, drill=0.3)
                    count += 1; done = True
                    break
                if done:
                    break
    print('gnd fan-out vias:', count)

gnd_fanout()

def gnd_backbone():
    """Pre-route a B.Cu GND spanning tree through all GND vias / THT pads so ground can never be split by signals."""
    gnd = netitems['GND']; gcode = gnd.GetNetCode()
    pts = []
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == gcode:
            pts.append((t.GetPosition().x, t.GetPosition().y))
    for fp in fps.values():
        for p in fp.Pads():
            if p.GetNetCode() == gcode and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                pts.append((p.GetPosition().x, p.GetPosition().y))
    other_tracks = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetCode() != gcode and t.GetLayer() == pcbnew.B_Cu]
    other_vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetCode() != gcode]
    other_pads = [p for fp in fps.values() for p in fp.Pads() if p.GetNetCode() != gcode and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    holes = [p for fp in fps.values() for p in fp.Pads() if p.GetDrillSizeX() > 0]
    clr = MM(0.3)
    def seg_ok(a, c):
        n = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / MM(0.25)))
        for k in range(n + 1):
            pt = pcbnew.VECTOR2I(int(a[0] + (c[0] - a[0]) * k / n), int(a[1] + (c[1] - a[1]) * k / n))
            if pt.x < MM(OX + 1.0) or pt.x > MM(OX + BW - 1.0) or pt.y < MM(OY + 1.0) or pt.y > MM(OY + BH - 1.0):
                return False
            for t in other_tracks:
                if t.HitTest(pt, clr): return False
            for v in other_vias:
                pp = v.GetPosition()
                if math.hypot(pp.x - pt.x, pp.y - pt.y) < v.GetWidth(pcbnew.B_Cu) / 2 + MM(0.45): return False
            for p in other_pads:
                if p.HitTest(pt, clr): return False
            for p in holes:
                pp = p.GetPosition()
                if math.hypot(pp.x - pt.x, pp.y - pt.y) < max(p.GetDrillSizeX(), p.GetSizeX()) / 2 + MM(0.5): return False
        return True
    edges = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            edges.append((math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]), i, j))
    edges.sort()
    parent = list(range(len(pts)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    made = 0
    for d, i, j in edges:
        if find(i) == find(j) or d > MM(30):
            continue
        a, c = pts[i], pts[j]
        for corner in ((c[0], a[1]), (a[0], c[1])):
            if seg_ok(a, corner) and seg_ok(corner, c):
                for s, e in ((a, corner), (corner, c)):
                    if s != e:
                        add_track(s[0], s[1], e[0], e[1], 0.3, pcbnew.B_Cu, 'GND')
                parent[find(i)] = find(j); made += 1
                break
    comps = len({find(i) for i in range(len(pts))})
    print('gnd backbone edges:', made, 'components left:', comps, 'points:', len(pts))

if os.environ.get('GND_BACKBONE') == '1':
    gnd_backbone()

# silkscreen tidy: passives' references on the fab layer, hole references hidden
for ref, fp in fps.items():
    if re.match(r'^(R|C|TP)\d+$', ref):
        fp.Reference().SetLayer(pcbnew.F_Fab)
    if ref.startswith('H'):
        fp.Reference().SetVisible(False)

# ------------------------------------------------------------------ outline
def line(x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
    s.SetLayer(layer); s.SetWidth(MM(w))
    board.Add(s)

line(0, 0, BW, 0); line(BW, 0, BW, BH); line(BW, BH, 0, BH); line(0, BH, 0, 0)

# ------------------------------------------------------------------ GND planes (filled later after routing)
def zone(layer, netname, x1, y1, x2, y2, prio=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(netitems[netname])
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(0.3))
    z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    ol = z.Outline()
    ol.NewOutline()
    for (x, y) in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
        ol.Append(MM(OX + x), MM(OY + y))
    board.Add(z)
    return z

if os.environ.get('LAYERS') == '4':
    zone(pcbnew.In1_Cu, 'GND', 0.3, 0.3, BW - 0.3, BH - 0.3)
elif os.environ.get('NO_ZONES') != '1':
    zone(pcbnew.B_Cu, 'GND', 0.3, 0.3, BW - 0.3, BH - 0.3)
    zone(pcbnew.F_Cu, 'GND', 0.3, 0.3, BW - 0.3, BH - 0.3)
out_pcb = os.path.join(OUT, 'USB-C-Eload-V1.kicad_pcb')
pcbnew.SaveBoard(out_pcb, board)
json.dump({r: [fp.GetPosition().x / 1e6 - OX, fp.GetPosition().y / 1e6 - OY, fp.GetOrientationDegrees()] for r, fp in fps.items()},
          open(os.path.join(OUT, 'positions.json'), 'w'))
print('saved', out_pcb, 'footprints', len(fps), 'nets', len(netitems))










