"""stitch.py <in> <out> [pitch_mm]: fill zones, add GND stitching vias in free spots, refill, save."""
import pcbnew, sys, math
src, dst = sys.argv[1], sys.argv[2]
pitch = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
MM, TM = pcbnew.FromMM, pcbnew.ToMM
OX = OY = 50.0
b = pcbnew.LoadBoard(src)
gnd = b.FindNet('GND')
if not any(z.GetNetCode() == gnd.GetNetCode() for z in b.Zones()):
    for L in (pcbnew.B_Cu, pcbnew.F_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(L); z.SetNet(gnd); z.SetLocalClearance(pcbnew.FromMM(0.3)); z.SetMinThickness(pcbnew.FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        ol = z.Outline(); ol.NewOutline()
        for (x, y) in [(0.3, 0.3), (99.7, 0.3), (99.7, 74.7), (0.3, 74.7)]:
            ol.Append(pcbnew.FromMM(50 + x), pcbnew.FromMM(50 + y))
        b.Add(z)
gcode = gnd.GetNetCode()
BW, BH = 100.0, 75.0
others = [t for t in b.GetTracks() if t.GetNetCode() != gcode]
opads = [p for p in b.GetPads() if p.GetNetCode() != gcode]
gvias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == gcode]
holes = [p for p in b.GetPads() if p.GetDrillSizeX() > 0]
CLR = MM(0.5 + 0.15)    # via radius + clearance + margin


def free(pt):
    for t in others:
        if t.HitTest(pt, CLR):
            return False
    for p in opads:
        if p.HitTest(pt, CLR):
            return False
    for p in holes:
        pp = p.GetPosition()
        if math.hypot(pp.x - pt.x, pp.y - pt.y) < max(p.GetDrillSizeX(), p.GetSizeX()) / 2 + MM(0.9):
            return False
    for v in gvias:
        pp = v.GetPosition()
        if math.hypot(pp.x - pt.x, pp.y - pt.y) < MM(2.0):
            return False
    return True


added = 0
y = 2.5
while y < BH - 2.0:
    x = 2.5 + (pitch / 2 if int(y / pitch) % 2 else 0)
    while x < BW - 2.0:
        pt = pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))
        if free(pt):
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pt); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
            b.Add(v); gvias.append(v); added += 1
        x += pitch
    y += pitch
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print('stitching vias added:', added)

