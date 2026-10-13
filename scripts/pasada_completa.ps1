# Pasada completa sobre un caso en un equipo Windows con GPU: búsqueda por atuendo y
# transcripción de todo lo que falte. Después espera hasta 2 h la bandera
# <casos>\<caso>\lote_extra.listo (la crea descargar_y_enviar.sh al mandar videos nuevos)
# y, si llega, hace otra pasada. Pensado para correr desatendido (tarea programada o similar):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pasada_completa.ps1 <caso>
param([Parameter(Mandatory)][string]$caso)
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = (Resolve-Path .venv\Scripts\python.exe).Path
$casos = (& $py -I -c "import sys; sys.path.insert(0, 'scripts'); import config; print(config.carpeta_casos())").Trim()
New-Item -ItemType Directory -Force modelos | Out-Null   # pesos de YOLO (ignorados por git)

function Pasada {
    Push-Location modelos
    & $py -I ..\scripts\buscar.py $caso --solo-nuevos --fps 5 --top 20 --yolo yolo11m.pt
    Pop-Location
    & $py -I scripts\transcribir.py $caso --modelo large-v3
}

"== pasada 1 $(Get-Date -Format s)"
Pasada
$bandera = Join-Path $casos "$caso\lote_extra.listo"
for ($i = 0; $i -lt 240 -and -not (Test-Path $bandera); $i++) { Start-Sleep -Seconds 30 }
if (Test-Path $bandera) {
    "== pasada 2 (lote extra) $(Get-Date -Format s)"
    Remove-Item $bandera
    Pasada
}
"== pasada completa terminada $(Get-Date -Format s)"
