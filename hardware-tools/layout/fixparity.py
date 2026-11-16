import pcbnew, sys, xml.etree.ElementTree as ET
src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
root = ET.parse(r'C:\work\eload\build\net.xml').getroot()
comps = {c.get('ref'): c for c in root.find('components')}
n_fp = n_f = 0
for fp in b.GetFootprints():
    c = comps.get(fp.GetReference())
    if c is None: print('no comp for', fp.GetReference()); continue
    fid = c.findtext('footprint')
    if fid and fp.GetFPIDAsString() != fid:
        fp.SetFPIDAsString(fid); n_fp += 1
    fields = {f.get('name'): (f.text or '') for f in c.find('fields')}
    for name in ('LCSC', 'MPN'):
        if name in fields and not fp.HasField(name):
            fp.SetField(name, fields[name])
            fp.GetField(name).SetVisible(False); n_f += 1
    for name in ('Description', 'Datasheet'):
        v = fields.get(name, '')
        if fp.GetFieldText(name) != v:
            fp.SetField(name, v)
    if fp.GetReference()[:1] in ('H', 'T') and fp.GetReference()[:2] in ('H1','H2','H3','H4','TP'):
        fp.SetExcludedFromBOM(False)
print('fpid set', n_fp, 'fields added', n_f)
for pname, ref, pad in (('unconnected-(J1-SBU1-PadA8)', 'J1', 'A8'), ('unconnected-(J1-SBU2-PadB8)', 'J1', 'B8'), ('unconnected-(U5-NC-Pad4)', 'U5', '4')):
    net = b.FindNet(pname)
    if net is None:
        net = pcbnew.NETINFO_ITEM(b, pname); b.Add(net)
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == pad:
            p.SetNet(net)
pcbnew.SaveBoard(dst, b)
print('saved')
