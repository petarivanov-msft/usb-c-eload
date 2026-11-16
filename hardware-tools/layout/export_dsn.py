import pcbnew, sys
b = pcbnew.LoadBoard(r'C:\work\eload\pcb\USB-C-Eload-V1.kicad_pcb')
ok = pcbnew.ExportSpecctraDSN(b, r'C:\work\eload\pcb\route_in.dsn')
print('dsn export', ok)
