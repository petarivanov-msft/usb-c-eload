"""bridge.py <in> <out>: connect isolated GND island pads to the main GND copper with a short F.Cu track."""
import sys, math
sys.argv = ['x', sys.argv[1], sys.argv[2]]
src_, dst_ = sys.argv[1], sys.argv[2]
code = open(r'C:\work\eload\island_fix.py').read().split("for rnd in range(6):")[0]
exec(code)
oth = others()
ot, op, holes = oth

def path_ok(a, c, clr=MM(0.27)):
    n = max(2, int(math.hypot(c.x - a.x, c.y - a.y) / MM(0.1)))
    for k in range(n + 1):
        pt = pcbnew.VECTOR2I(int(a.x + (c.x - a.x) * k / n), int(a.y + (c.y - a.y) * k / n))
        for t in ot:
            if t.HitTest(pt, clr): return False
        for p in op:
            if p.HitTest(pt, clr): return False
        for p in holes:
            pp = p.GetPosition()
            if math.hypot(pp.x - pt.x, pp.y - pt.y) < max(p.GetDrillSizeX(), p.GetSizeX()) / 2 + MM(0.35): return False
    return True

for rnd in range(4):
    polys, nodes, find, which, main = analyse()
    comps = {}
    for n in nodes: comps.setdefault(find(n), []).append(n)
    bad = [m for k, m in comps.items() if k != main]
    print('round', rnd, 'isolated components', len(bad))
    if not bad: break
    # components that carry no pad and no track are only floating copper held by stitching vias: drop those vias
    removed = 0
    for members in bad:
        has_pad = False
        for (L, i) in members:
            for p in b.GetPads():
                if p.GetNetCode() == gcode and polys[L].Contains(p.GetPosition(), i):
                    has_pad = True
        if has_pad:
            continue
        for t in list(b.GetTracks()):
            if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == gcode:
                if any(polys[L].Contains(t.GetPosition(), i) for (L, i) in members):
                    b.Remove(t); removed += 1
    if removed:
        print('  removed floating stitching vias:', removed)
        continue
    verts = []
    for (L, i) in nodes:
        if find((L, i)) == main and L == pcbnew.F_Cu:
            ch = polys[L].Outline(i)
            for k in range(ch.PointCount()):
                verts.append(ch.GetPoint(k))
    fixed = 0
    for members in bad:
        for (L, i) in members:
            if L != pcbnew.F_Cu: continue
            for p in b.GetPads():
                if p.GetNetCode() == gcode and p.GetDrillSizeX() == 0 and polys[L].Contains(p.GetPosition(), i):
                    a = p.GetPosition()
                    cands = sorted(verts, key=lambda v: math.hypot(v.x - a.x, v.y - a.y))
                    for v in cands[:400]:
                        d = math.hypot(v.x - a.x, v.y - a.y)
                        if d < MM(0.8) or d > MM(9): continue
                        if path_ok(a, v):
                            t = pcbnew.PCB_TRACK(b)
                            t.SetStart(a); t.SetEnd(v); t.SetWidth(MM(0.25)); t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd)
                            b.Add(t); fixed += 1
                            print('  bridged pad at', round(TM(a.x) - 50, 2), round(TM(a.y) - 50, 2), '->', round(TM(v.x) - 50, 2), round(TM(v.y) - 50, 2))
                            break
    if not fixed: break
# thin tracks -> 0.15 mm
n = 0
for t in b.GetTracks():
    if t.GetClass() == 'PCB_TRACK' and t.GetWidth() < MM(0.15):
        t.SetWidth(MM(0.15)); n += 1
print('widened thin tracks:', n)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst_, b)
