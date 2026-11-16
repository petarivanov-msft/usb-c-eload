import pcbnew
f = r'C:\work\USB-C-Eload-V1\USB-C-Eload-V1.kicad_pcb'
b = pcbnew.LoadBoard(f)
mm, fm = pcbnew.ToMM, pcbnew.FromMM
j3 = b.FindFootprintByReference('J3')
print('J3 pads', [(p.GetNumber(), round(mm(p.GetPosition().x)-50,2), round(mm(p.GetPosition().y)-50,2)) for p in j3.Pads()], 'rot', j3.GetOrientationDegrees())
names = {'GND', 'CLK', 'DIO', 'RST'}
old = [d for d in b.GetDrawings() if d.GetClass() == 'PCB_TEXT' and d.GetText() in names and d.GetLayerName() == 'F.Silkscreen' and mm(d.GetY()) - 50 > 60 and mm(d.GetX()) - 50 > 80]
print('removing', [d.GetText() for d in old])
for d in old: b.Remove(d)
lab = {'1': 'GND', '2': 'CLK', '3': 'DIO', '4': 'RST'}
for i, p in enumerate(sorted(j3.Pads(), key=lambda q: int(q.GetNumber()))):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(lab[p.GetNumber()]); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(fm(0.8), fm(0.8))); t.SetTextThickness(fm(0.15))
    t.SetPosition(pcbnew.VECTOR2I(p.GetPosition().x, p.GetPosition().y + fm(3.0 + 1.3 * (i % 2))))
    b.Add(t)
for d in b.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and d.GetText() == 'USB-C ELOAD V1':
        d.SetPosition(pcbnew.VECTOR2I(fm(50 + 23), fm(50 + 58)))
pcbnew.SaveBoard(f, b)
print('saved')

