import pcbnew, sys, json, subprocess
src, dst = sys.argv[1], sys.argv[2]
CLI = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
b = pcbnew.LoadBoard(src)
subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-all', '--all-track-errors', '--output', 'tmp_drc.json', src], capture_output=True)
d = json.load(open('tmp_drc.json', encoding='utf-8'))
removed = 0
for v in d['violations']:
    if v['type'] != 'track_dangling':
        continue
    it = v['items'][0]
    px, py = it['pos']['x'], it['pos']['y']
    for t in list(b.GetTracks()):
        if t.GetClass() == 'PCB_TRACK':
            s, e = t.GetStart(), t.GetEnd()
            if (abs(pcbnew.ToMM(s.x) - px) < 0.05 and abs(pcbnew.ToMM(s.y) - py) < 0.05) or (abs(pcbnew.ToMM(e.x) - px) < 0.05 and abs(pcbnew.ToMM(e.y) - py) < 0.05):
                if abs(pcbnew.ToMM(t.GetLength()) - 4.125) < 0.05 or True:
                    print('removing dangling track', t.GetNetname(), round(pcbnew.ToMM(t.GetLength()), 3))
                    b.Remove(t); removed += 1
                    break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print('removed', removed)
