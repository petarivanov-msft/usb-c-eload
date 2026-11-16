"""island_fix.py <in> <out>: link isolated GND zone islands to the main GND copper with extra vias."""
import pcbnew, sys, math
src, dst = sys.argv[1], sys.argv[2]
MM, TM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(src)
gnd = b.FindNet('GND'); gcode = gnd.GetNetCode()
LAY = (pcbnew.F_Cu, pcbnew.B_Cu)
CLR = MM(0.5 + 0.15)

def others():
    return ([t for t in b.GetTracks() if t.GetNetCode() != gcode], [p for p in b.GetPads() if p.GetNetCode() != gcode],
            [p for p in b.GetPads() if p.GetDrillSizeX() > 0])

def free(pt, oth):
    ot, op, holes = oth
    for t in ot:
        if t.HitTest(pt, CLR): return False
    for p in op:
        if p.HitTest(pt, CLR): return False
    for p in holes:
        pp = p.GetPosition()
        if math.hypot(pp.x - pt.x, pp.y - pt.y) < max(p.GetDrillSizeX(), p.GetSizeX()) / 2 + MM(0.9): return False
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == gcode:
            pp = t.GetPosition()
            if math.hypot(pp.x - pt.x, pp.y - pt.y) < MM(1.0): return False
    return True

def analyse():
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    polys = {}
    for L in LAY:
        z = [z for z in b.Zones() if z.GetLayer() == L and z.GetNetCode() == gcode][0]
        polys[L] = z.GetFilledPolysList(L)
    nodes = [(L, i) for L in LAY for i in range(polys[L].OutlineCount())]
    parent = {n: n for n in nodes}
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, c):
        if a and c: parent[find(a)] = find(c)
    def which(L, pt):
        ps = polys[L]
        for i in range(ps.OutlineCount()):
            if ps.Contains(pt, i): return (L, i)
        return None
    for t in b.GetTracks():
        if t.GetNetCode() != gcode: continue
        if t.GetClass() == 'PCB_VIA':
            union(which(pcbnew.F_Cu, t.GetPosition()), which(pcbnew.B_Cu, t.GetPosition()))
        elif t.GetLayer() in LAY:
            union(which(t.GetLayer(), t.GetStart()), which(t.GetLayer(), t.GetEnd()))
    for p in b.GetPads():
        if p.GetNetCode() == gcode and p.GetDrillSizeX() > 0:
            union(which(pcbnew.F_Cu, p.GetPosition()), which(pcbnew.B_Cu, p.GetPosition()))
    area = {}
    for n in nodes:
        area[find(n)] = area.get(find(n), 0) + polys[n[0]].Outline(n[1]).Area()
    main = max(area, key=area.get)
    return polys, nodes, find, which, main

for rnd in range(6):
    polys, nodes, find, which, main = analyse()
    comps = {}
    for n in nodes:
        comps.setdefault(find(n), []).append(n)
    bad = {k: v for k, v in comps.items() if k != main}
    print('round', rnd, 'islands', len(nodes), 'components', len(comps), 'isolated', len(bad))
    if not bad:
        break
    oth = others()
    added = 0
    for k, members in bad.items():
        done = False
        for (L, i) in sorted(members, key=lambda n: -polys[n[0]].Outline(n[1]).Area()):
            ps = polys[L]
            bb = ps.Outline(i).BBox()
            other_L = pcbnew.B_Cu if L == pcbnew.F_Cu else pcbnew.F_Cu
            x0, y0, x1, y1 = bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()
            step = MM(0.4)
            cands = []
            x = x0
            while x <= x1:
                y = y0
                while y <= y1:
                    pt = pcbnew.VECTOR2I(int(x), int(y))
                    if ps.Contains(pt, i):
                        ok = all(ps.Contains(pcbnew.VECTOR2I(int(x + MM(0.45) * math.cos(a)), int(y + MM(0.45) * math.sin(a))), i)
                                 for a in [k2 * math.pi / 4 for k2 in range(8)])
                        if ok:
                            tgt = which(other_L, pt)
                            if tgt and find(tgt) == main:
                                cands.append(pt)
                    y += step
                x += step
            for pt in cands:
                if free(pt, oth):
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pt); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
                    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
                    b.Add(v); added += 1; done = True
                    print('   linking via at', round(TM(pt.x) - 50, 2), round(TM(pt.y) - 50, 2), 'layer', b.GetLayerName(L))
                    break
            if done: break
        if not done:
            print('   could not link component with', len(members), 'islands; areas', [round(polys[n[0]].Outline(n[1]).Area() / 1e12, 2) for n in members])
    if not added:
        break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
