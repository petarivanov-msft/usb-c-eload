param([string]$dir)
$root = 'C:\work\eload'
Set-Location $root
$py = 'C:\Program Files\KiCad\10.0\bin\python.exe'
$cli = 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
$env:PYTHONIOENCODING = 'utf-8'
foreach ($n in 'stitched', 'fixed', 'bridged', 'silked') { Copy-Item "$dir\USB-C-Eload-V1.kicad_pro" "$dir\$n.kicad_pro" -Force }
& $py stitch.py "$dir\routed.kicad_pcb" "$dir\stitched.kicad_pcb" 6 | Out-Null
& $py island_fix.py "$dir\stitched.kicad_pcb" "$dir\fixed.kicad_pcb" 2>&1 | Out-Null
& $py bridge.py "$dir\fixed.kicad_pcb" "$dir\bridged.kicad_pcb" 2>&1 | Out-Null
& $py silk_tidy.py "$dir\bridged.kicad_pcb" "$dir\silked.kicad_pcb" 2>&1 | Out-Null
& $cli pcb drc --format json --severity-all --all-track-errors --output "$dir\drc_final.json" "$dir\silked.kicad_pcb" 2>&1 | Out-Null
python drcsum.py "$dir\drc_final.json" 3
