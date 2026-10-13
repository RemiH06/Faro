![Built with Love](https://forthebadge.com/images/badges/built-with-love.svg)
![Made with Python](https://forthebadge.com/images/badges/made-with-python.svg)
![PowerShell](https://img.shields.io/badge/-PowerShell-5391FE?style=for-the-badge&logo=powershell&logoColor=white)
![YOLO](https://img.shields.io/badge/-YOLO%20%2F%20Ultralytics-111F68?style=for-the-badge&logo=ultralytics&logoColor=white)

```ascii
███████╗ █████╗ ██████╗  ██████╗
██╔════╝██╔══██╗██╔══██╗██╔═══██╗
█████╗  ███████║██████╔╝██║   ██║
██╔══╝  ██╔══██║██╔══██╗██║   ██║
██║     ██║  ██║██║  ██║╚██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝
       by Hex (@RemiH06)          version 0.1.0
```

![AGPL-3.0](https://img.shields.io/badge/License-AGPLv3-blue.svg?style=for-the-badge)

## Resumen

### Descripción general

Faro ayuda a ubicar a una persona en videos y fotos de un evento público (una manifestación, por ejemplo) a partir de su ropa y señas visibles, para documentar dónde estaba y qué hacía. Nació para reunir evidencia en la defensa de una persona detenida, y sirve igual para colectivos de búsqueda.

Todo corre en local. Cada archivo se registra con su hash SHA-256, su URL, la cuenta que lo publicó y las fechas, para conservar una cadena de custodia básica. Un detector de personas (YOLO) con seguimiento (ByteTrack) recorre los videos, un filtro por color de ropa ordena a los candidatos, y el resultado es una hoja con los mejores recortes y su minuto exacto para que una persona los revise. También transcribe el audio con Whisper para buscar menciones de lugares y momentos.

Faro no identifica a nadie: prioriza qué momentos vale la pena que vea un humano. La confirmación siempre la da alguien que conoce a la persona y, ante un juez, un perito.

```diff
- Sin reconocimiento facial ni biométrico. No se usan face embeddings ni se afirma que dos caras son la misma persona.
- Sin rastreo automatizado de redes: nada de scraping de cuentas, hashtags ni feeds. Cada video entra uno por uno, a pedido.
- Los casos (videos, fichas, transcripciones, reportes) nunca van a un repositorio ni a un sitio público. La carpeta casos/ está en .gitignore; mejor aún, configúrala fuera del repo con FARO_CASOS.
- Publicar resultados puede poner en riesgo a la persona que se busca o defiende, y a terceros que aparecen en los videos.
- El filtro de color solo puntúa personas vistas casi de cuerpo completo y hay que calibrarlo por caso. En acercamientos de medio cuerpo manda la revisión humana.
```

## Installation

1. Clona el repo y crea un entorno virtual:
   ```bash
   git clone https://github.com/RemiH06/Faro.git
   cd Faro
   python -m venv .venv
   ```
2. Instala PyTorch según tu equipo ([selector oficial](https://pytorch.org/get-started/locally/)) y luego el resto:
   ```bash
   .venv/bin/python -m pip install torch torchvision          # Linux/macOS, CPU
   .venv/bin/python -m pip install -r requirements.txt
   ```
   En Windows con GPU NVIDIA basta con:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\preparar_windows_gpu.ps1
   ```
3. Copia `.env.example` como `.env` y, de preferencia, apunta `FARO_CASOS` a una carpeta fuera del repo (idealmente en un disco cifrado).
4. Crea el caso: `<FARO_CASOS>/<caso>/ficha.yaml` a partir de [`ejemplos/ficha.ejemplo.yaml`](ejemplos/ficha.ejemplo.yaml). El identificador del caso no debe llevar nombre ni iniciales.
   Para calibrar `atuendo_hsv`, toma una foto confirmada del mismo día en la que la persona se vea de cuerpo completo, mide los percentiles HSV de su torso y sus piernas (por ejemplo con `cv2.cvtColor(..., cv2.COLOR_BGR2HSV)`) y ajusta los rangos hasta que, entre todas las personas de esa foto, ella quede primera con margen amplio.
5. Ingresa videos y analiza:
   ```bash
   python -I scripts/ingerir.py <caso> <url-o-archivo> ... --nota "quién lo envió y por qué medio"
   python -I scripts/buscar.py <caso> --fps 5
   python -I scripts/transcribir.py <caso> --modelo small
   ```
   Los resultados quedan en `<FARO_CASOS>/<caso>/trabajo/<video>/`: `hoja.jpg`, `candidatos.csv`, `recortes/`, `contexto/` y `transcripcion.txt`.

## Launch arguments

`ingerir.py <caso> <entradas...>`

- `--nota` procedencia del material (quién lo envió, por qué medio).
- `@lista.txt` lee los argumentos de un archivo, uno por línea (útil para lotes de URLs).

`buscar.py <caso> [videos...]`

- `--fps` fotogramas analizados por segundo (3 por defecto; 5 o más si hay apariciones breves).
- `--top` candidatos por video en la hoja de revisión (20).
- `--yolo` pesos del detector: `yolo11n.pt` en CPU, `yolo11s.pt` por defecto, `yolo11m.pt` con GPU.
- `--solo-nuevos` salta videos que ya tienen resultados.
- `--clip` agrega similitud con CLIP contra `referencias/` y `descripcion_clip`. Lento en CPU y poco útil en multitudes vestidas de oscuro.

`transcribir.py <caso> [videos...]`

- `--modelo` modelo de Whisper (`small`, `medium`, `large-v3`).
- `--dispositivo` `auto`, `cpu` o `cuda`.

Equipo remoto con GPU (opcional, Windows con OpenSSH):

- `scripts/pasada_completa.ps1 <caso>` corre búsqueda y transcripción de todo lo pendiente, pensado para dejarlo desatendido.
- `scripts/descargar_y_enviar.sh <caso> <urls...>` descarga en local (reintentando bloqueos), manda los archivos al remoto definido en `FARO_REMOTO` y avisa a `pasada_completa.ps1` que hay material nuevo.

## Features

- Ingesta con cadena de custodia básica: original sin editar, SHA-256, URL, cuenta, fecha de publicación y de registro en `fuentes.jsonl`.
- Detección y seguimiento de personas con YOLO11 y ByteTrack, en CPU o GPU.
- Filtro de atuendo por color (HSV) configurable por caso en la ficha, por zonas de torso y piernas.
- Hoja de revisión por video con los mejores candidatos, recorte, fotograma completo marcado y minuto.
- Transcripción local con faster-whisper y marcas de tiempo, usando la GPU si existe.
- Escala de certeza con criterios fijos para registrar apariciones ([`ejemplos/escala_certeza.md`](ejemplos/escala_certeza.md)).
- Configuración por `.env`: carpeta de casos fuera del repo y equipo remoto con GPU.

## Future Features

- Re-identificación por apariencia (OSNet) entrenada con recortes confirmados, para acercamientos donde el filtro de color no aplica.
- Duración y resolución en el registro aunque el equipo no tenga `ffprobe`.
- Sincronización de videos por audio para reconstruir una línea de tiempo del evento.
- Reporte en PDF para entregar a la defensa, la fiscalía o la comisión de búsqueda.

## Autoría

por Hex ([@RemiH06](https://github.com/RemiH06))
