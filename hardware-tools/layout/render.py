"""render.py <pcb file> <out png> [layers] [dpi] -> crops board area at high dpi"""
import sys, subprocess, pymupdf, functools
pcb, out = sys.argv[1], sys.argv[2]
layers = sys.argv[3] if len(sys.argv) > 3 else 'F.Cu,F.Silkscreen,Edge.Cuts'
dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 240
cli = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
pdf = out.replace('.png', '.pdf')
subprocess.run([cli, 'pcb', 'export', 'pdf', '--layers', layers, '--output', pdf, pcb], capture_output=True)
p = pymupdf.open(pdf)[0]
box = pymupdf.Rect(141.7 - 6, 141.7 - 6, 141.7 + 283.5 + 6, 141.7 + 212.6 + 6)
if len(sys.argv) > 8:
    x0, y0, x1, y1 = [float(v) for v in sys.argv[5:9]]
    w, h = box.width, box.height
    box = pymupdf.Rect(box.x0 + w * x0, box.y0 + h * y0, box.x0 + w * x1, box.y0 + h * y1)
p.get_pixmap(dpi=dpi, clip=box).save(out)
print('saved', out, box)



