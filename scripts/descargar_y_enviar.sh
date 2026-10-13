#!/usr/bin/env bash
# Descarga e ingiere URLs en el equipo local (reintentando las que fallen, p. ej. 403 de
# YouTube) y manda lo que baje al equipo remoto con GPU: archivos a originales/, sus filas a
# fuentes.jsonl y la bandera lote_extra.listo para que pasada_completa.ps1 haga otra pasada.
#
# Requiere en .env o en el entorno:
#   FARO_REMOTO        alias SSH del equipo remoto (Windows con OpenSSH), p. ej. gpu-casa
#   FARO_REMOTO_CASOS  carpeta de casos en el remoto, relativa a su home, p. ej. faro/casos
#
#   bash scripts/descargar_y_enviar.sh <caso> <url> [url ...]
set -u
raiz=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$raiz/.env" ] && { set -a; . "$raiz/.env"; set +a; }
: "${FARO_REMOTO:?define FARO_REMOTO en .env}" "${FARO_REMOTO_CASOS:?define FARO_REMOTO_CASOS en .env}"

caso=$1; shift
py="$raiz/.venv/Scripts/python"; [ -x "$py" ] || py="$raiz/.venv/bin/python"
local_caso=$("$py" -I -c "import sys; sys.path.insert(0, '$raiz/scripts'); import config; print(config.carpeta_casos())" | tr -d '\r')/$caso
remoto="$FARO_REMOTO_CASOS/$caso"
pendientes=("$@")

antes=$(wc -l < "$local_caso/fuentes.jsonl" 2>/dev/null || echo 0)
for intento in 1 2 3 4; do
    [ ${#pendientes[@]} -eq 0 ] && break
    echo "== intento $intento: ${#pendientes[@]} pendientes $(date +%H:%M)"
    quedan=()
    for url in "${pendientes[@]}"; do
        salida=$("$py" -I "$raiz/scripts/ingerir.py" "$caso" "$url" --nota "descargar_y_enviar.sh, $(date +%F)" 2>&1)
        echo "$salida" | grep -E "^\[(ok|error|repetido)\]"
        echo "$salida" | grep -q "^\[ok\]\|^\[repetido\]" || quedan+=("$url")
    done
    pendientes=("${quedan[@]+"${quedan[@]}"}")
    [ ${#pendientes[@]} -gt 0 ] && [ $intento -lt 4 ] && sleep 1200
done

nuevas=$(tail -n +$((antes + 1)) "$local_caso/fuentes.jsonl")
if [ -z "$nuevas" ]; then
    echo "== nada nuevo que mandar"; exit 0
fi
echo "$nuevas" > "$local_caso/.filas_nuevas.jsonl"
# python en Windows termina cada línea con CR; se quita para que el nombre quede limpio
for archivo in $(echo "$nuevas" | "$py" -I -c "import sys,json; [print(json.loads(l)['archivo']) for l in sys.stdin if l.strip()]" | tr -d '\r'); do
    scp -q "$local_caso/originales/$archivo" "$FARO_REMOTO:$remoto/originales/" && echo "enviado $archivo"
done
scp -q "$local_caso/.filas_nuevas.jsonl" "$FARO_REMOTO:$remoto/.filas_nuevas.jsonl"
ssh "$FARO_REMOTO" "cd $remoto; Get-Content .filas_nuevas.jsonl -Encoding UTF8 | Add-Content fuentes.jsonl -Encoding UTF8; Remove-Item .filas_nuevas.jsonl; New-Item lote_extra.listo -ItemType File | Out-Null"
rm "$local_caso/.filas_nuevas.jsonl"
echo "== listo: $(echo "$nuevas" | wc -l) videos mandados a $FARO_REMOTO $(date +%H:%M)"
