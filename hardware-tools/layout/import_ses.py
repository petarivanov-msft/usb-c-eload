import pcbnew, sys
src, ses, dst = sys.argv[1], sys.argv[2], sys.argv[3]
b = pcbnew.LoadBoard(src)
ok = pcbnew.ImportSpecctraSES(b, ses)
print('ses import', ok)
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
tr = [t for t in b.GetTracks()]
print('tracks+vias:', len(tr), 'vias:', sum(1 for t in tr if t.GetClass() == 'PCB_VIA'))
