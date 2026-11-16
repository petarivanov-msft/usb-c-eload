"""silk_tidy.py <in> <out>: relocate silk reference texts and add labels without overlaps."""
import pcbnew, sys, math
src, dst = sys.argv[1], sys.argv[2]
MM, TM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(src)
BW, BH = 100.0, 75.0
OX = OY = 50.0

def rect(bb, m=0.0):
    return [bb.GetX() - MM(m), bb.GetY() - MM(m), bb.GetRight() + MM(m), bb.GetBottom() + MM(m)]

def hit(a, c):
    return a[0] < c[2] and a[2] > c[0] and a[1] < c[3] and a[3] > c[1]

fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
obst = []
for fp in fps.values():
    for p in fp.Pads():
        obst.append(rect(p.GetBoundingBox(), 0.2))
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        obst.append(rect(cy.BBox(), 0.0))
edge = MM(0.5)
bounds = [MM(OX) + edge, MM(OY) + edge, MM(OX + BW) - edge, MM(OY + BH) - edge]
placed = []

def inside(r):
    return r[0] >= bounds[0] and r[1] >= bounds[1] and r[2] <= bounds[2] and r[3] <= bounds[3]

def own_court(fp):
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    return rect(cy.BBox()) if cy.OutlineCount() else rect(fp.GetBoundingBox(False))

def try_place(txt, anchor_rect, own, prefer=('top', 'bottom', 'right', 'left'), allow_own=False, maxd=6.0):
    cx, cy = (anchor_rect[0] + anchor_rect[2]) / 2, (anchor_rect[1] + anchor_rect[3]) / 2
    for dist in [0.3 + 0.5 * k for k in range(int(maxd / 0.5))]:
        for side in prefer:
            txt.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); txt.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            txt.SetPosition(pcbnew.VECTOR2I(int(cx), int(cy)))
            w, h = txt.GetBoundingBox().GetWidth(), txt.GetBoundingBox().GetHeight()
            if side == 'top':
                p = (cx, anchor_rect[1] - MM(dist) - h / 2)
            elif side == 'bottom':
                p = (cx, anchor_rect[3] + MM(dist) + h / 2)
            elif side == 'left':
                p = (anchor_rect[0] - MM(dist) - w / 2, cy)
            else:
                p = (anchor_rect[2] + MM(dist) + w / 2, cy)
            txt.SetPosition(pcbnew.VECTOR2I(int(p[0]), int(p[1])))
            r = rect(txt.GetBoundingBox(), 0.1)
            if not inside(r):
                continue
            bad = False
            for o in obst:
                if hit(r, o):
                    if allow_own and own is not None and abs(o[0] - own[0]) < 5 and abs(o[1] - own[1]) < 5 and abs(o[2] - own[2]) < 5:
                        continue
                    bad = True; break
            if bad or any(hit(r, q) for q in placed):
                continue
            placed.append(r)
            return True
    return False

# 1. references that live on the silkscreen
missed = []
for ref, fp in sorted(fps.items()):
    t = fp.Reference()
    if t.GetLayer() != pcbnew.F_SilkS or not t.IsVisible():
        continue
    t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); t.SetTextThickness(MM(0.12))
    t.SetTextAngleDegrees(0)
    ar = own_court(fp)
    own = ar
    obst_wo = [o for o in obst if o != own]
    saved = obst[:]
    obst[:] = obst_wo
    ok = try_place(t, ar, None)
    obst[:] = saved
    if not ok:
        missed.append(ref)

# 2. extra labels
def pad_xy(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == str(num):
            return p.GetPosition()

def label(text, x, y, size=0.8, th=0.12, ang=0):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(th))
    t.SetTextAngleDegrees(ang)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    b.Add(t)
    return t

def pin_labels(ref, names, side='right', size=0.8):
    for i, nm in enumerate(names, start=1):
        pp = pad_xy(ref, i)
        t = label(nm, pp.x, pp.y, size, 0.11)
        w = t.GetBoundingBox().GetWidth()
        for dx in [MM(2.0) + MM(0.3) * k for k in range(12)]:
            sgn = 1 if side == 'right' else -1
            t.SetPosition(pcbnew.VECTOR2I(int(pp.x + sgn * (dx + w / 2)), int(pp.y)))
            r = rect(t.GetBoundingBox(), 0.05)
            if inside(r) and not any(hit(r, o) for o in obst if not (o[0] <= pp.x <= o[2] and o[1] <= pp.y <= o[3])) and not any(hit(r, q) for q in placed):
                placed.append(r); break

pin_labels('J2', ['GND', '3V3', 'SCL', 'SDA'], 'left')
pin_labels('J3', ['GND', 'CLK', 'DIO', 'RST'], 'right')
pin_labels('J4', ['NTC', 'GND'], 'right')
pin_labels('J6', ['+5V', 'GND'], 'right')
pin_labels('J5', ['VBUS', 'GND'], 'right', 0.8)
def near_label(ref, text, prefer, size=0.9, maxd=6):
    fp = fps[ref]
    t = label(text, fp.GetPosition().x, fp.GetPosition().y, size, 0.14)
    ok = try_place(t, own_court(fp), None, prefer, maxd=maxd)
    if not ok:
        b.Remove(t); missed.append('label ' + text)
near_label('SW2', 'LOAD', ('bottom', 'top', 'left', 'right'))
near_label('SW3', 'PD V', ('bottom', 'top', 'left', 'right'))
near_label('D7', 'LOAD', ('top', 'bottom', 'right', 'left'), 0.8)
near_label('D8', 'FLT', ('top', 'bottom', 'right', 'left'), 0.8)
near_label('D2', 'PD', ('top', 'bottom', 'right', 'left'), 0.8)
near_label('SW1', 'ENCODER', ('bottom', 'top', 'left', 'right'))
near_label('J1', 'USB-C PD IN', ('bottom', 'top', 'right'))
near_label('R27', '0R33 SHUNT', ('top', 'bottom', 'left', 'right'), 0.8)
near_label('Q1', 'Q1 TAB=VBUS: INSULATE', ('bottom', 'right'), 0.8, maxd=12)
t = label('USB-C ELOAD V1', MM(OX + 30), MM(OY + BH - 6), 1.2, 0.18)
placed.append(rect(t.GetBoundingBox(), 0.2))
print('could not place:', missed)
pcbnew.SaveBoard(dst, b)

