param([string]$dir = 'pcb', [string]$mp = '30', [string]$strategy = 'greedy')
$root = 'C:\work\eload'
Set-Location $root
$py = 'C:\Program Files\KiCad\10.0\bin\python.exe'
$java = "$root\frtool\jdk25\jdk-25.0.5.0.2+1\bin\java.exe"
$env:PYTHONIOENCODING = 'utf-8'
Copy-Item "$dir\USB-C-Eload-V1.kicad_pro" "$dir\routed.kicad_pro" -Force -ErrorAction SilentlyContinue
(Get-Content export_dsn.py -Raw).Replace('pcb\USB-C-Eload-V1.kicad_pcb', "$dir\USB-C-Eload-V1.kicad_pcb").Replace('pcb\route_in.dsn', "$dir\route_in.dsn") | Set-Content "$dir\_export.py" -Encoding utf8
& $py "$dir\_export.py" 2>&1 | Select-Object -Last 1
Remove-Item "$dir\route_out.ses" -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $java -ArgumentList '-jar', 'frtool\freerouting.jar', '-de', "$dir\route_in.dsn", '-do', "$dir\route_out.ses", '-mp', $mp, '-us', $strategy -RedirectStandardOutput "$dir\fr_log.txt" -RedirectStandardError "$dir\fr_err.txt" -PassThru -WindowStyle Hidden
$p.WaitForExit(600000) | Out-Null
Get-Content "$dir\fr_log.txt" | Select-String 'Auto-routing stage completed|Optimization was completed|Saved' | ForEach-Object { $_.Line.Substring(24) }
& $py import_ses.py "$dir\USB-C-Eload-V1.kicad_pcb" "$dir\route_out.ses" "$dir\routed.kicad_pcb" 2>&1 | Select-Object -Last 2
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' pcb drc --format json --severity-all --all-track-errors --output "$dir\drc.json" "$dir\routed.kicad_pcb" 2>&1 | Select-Object -Last 3
python drcsum.py "$dir\drc.json" 4

