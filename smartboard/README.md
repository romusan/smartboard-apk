# SmartBoard APK + Ollama Local

Prototipo funcional de pizarra inteligente para tableta Android/Samsung. El producto mínimo viable sincroniza trazos vectoriales por WebSocket en JSON; no transmite video. Un visor web en el computador reconstruye la pizarra con baja latencia y puede enviar respuestas de IA local de vuelta a la APK.

## Estructura

```text
smartboard/
  android/              # APK Kotlin + Jetpack Compose
  backend/              # FastAPI + WebSocket + Ollama + visor web
.github/workflows/      # Compilación de APK y pruebas en GitHub Actions
```

## Compilar la APK en GitHub

1. Sube este proyecto a GitHub.
2. Abre `Actions` > `SmartBoard CI` > `Run workflow`.
3. Descarga el artefacto `smartboard-debug-apk`.
4. Instala `app-debug.apk` en la tableta Samsung.

El workflow usa Java 17, Android SDK y Gradle remoto; no requiere instalar Android Studio en este computador.

## Ejecutar backend en el computador

```powershell
cd smartboard/backend
py -m pip install -r requirements.txt
$env:OLLAMA_URL="http://localhost:11434"
$env:OLLAMA_MODEL="llama3.1:8b"
py -m uvicorn smartboard_backend.main:app --host 0.0.0.0 --port 8000
```

Abre el visor en:

```text
http://IP_DEL_COMPUTADOR:8000
```

En la APK escribe la misma URL, por ejemplo:

```text
http://192.168.1.10:8000
```

## Endpoints

- `GET /`: visor web de la pizarra.
- `POST /sessions`: crea una sesión.
- `GET /sessions/{session_id}`: devuelve historial JSONL almacenado.
- `WS /ws/{session_id}`: sincronización bidireccional de trazos y comandos.
- `POST /ai/query`: consulta `Tutor_materias`/Ollama y emite `ai_response` a todos los clientes conectados.

## Mensaje JSON de trazo

```json
{
  "type": "stroke_end",
  "session_id": "demo",
  "client_id": "tablet-uuid",
  "page_id": "page-1",
  "stroke_id": "stroke-123",
  "timestamp": 1760000000000,
  "version": 1,
  "payload": {
    "stroke": {
      "id": "stroke-123",
      "page_id": "page-1",
      "color": "#111111",
      "width": 4.0,
      "points": [
        { "x": 0.15, "y": 0.30, "pressure": 0.8, "t": 1760000000000 },
        { "x": 0.18, "y": 0.32, "pressure": 0.9, "t": 1760000000016 }
      ]
    }
  }
}
```

Las coordenadas `x/y` están normalizadas entre `0` y `1`, por eso el visor reconstruye el dibujo en cualquier resolución.

## Consulta IA

En Android, el botón `Consultar IA` usa ML Kit Digital Ink para convertir los trazos manuscritos
en `recognized_text` antes de enviar la consulta. La primera vez la tableta puede requerir internet
para descargar el modelo de escritura en español.

Ejemplo `POST /ai/query`:

```json
{
  "action": "solve",
  "session_id": "demo",
  "page_id": "page-1",
  "selection_id": "lasso-1",
  "strokes": [],
  "png_base64": "...",
  "recognized_text": "Resolver integral de x^2",
  "page_context": "Clase de materiales / ejercicios"
}
```

Acciones disponibles desde la APK:

- Explicar: `explain`
- Completar idea: `complete`
- Corregir: `correct`
- Resolver: `solve`
- Crear esquema: `outline`
- Generar ejercicio: `exercise`
- Dibujar en 3D: `draw3d`

La respuesta puede ser `text`, `latex`, `svg`, `image`, `threejs` u `openscad`. El backend ya reenvía `ai_response` por WebSocket para insertar el resultado en la tableta.

## Funciones MVP incluidas

- Escritura con lápiz táctil usando `Canvas` y eventos pointer.
- Borrado básico, deshacer y creación de página.
- Selección por lazo como modo preparado para filtrar trazos.
- WebSocket estable con reconexión automática y cola en memoria.
- JSON vectorial con coordenadas normalizadas, grosor, color, presión, tiempo, id y acción.

## Pizarra por materias y síntesis de mecanismos

La barra superior de la APK separa las herramientas de **Materiales**, **Mecanismos** y
**Dinámica**. En Mecanismos, al cerrar con el lápiz una trayectoria de al menos 12 puntos,
la APK solicita automáticamente una síntesis al backend Python.

El backend:

- remuestrea y normaliza la curva cerrada;
- genera un identificador reproducible y una respuesta única por geometría;
- ajusta un mecanismo de cuatro barras con una versión didáctica rápida de PSO-TASS;
- ofrece alternativas topológicas de seis barras Watt I y Stephenson III basadas en las
  familias por grafos del proyecto de investigación FEF-Graph;
- entrega únicamente resultados, parámetros y una simulación animada HTML; no expone el
  procedimiento interno de optimización en la interfaz de clase.

La tarjeta de respuesta permite alternar entre cuatro barras, Watt I y Stephenson III.
- Visor web que reconstruye la pizarra desde trazos.
- Backend FastAPI con sesiones persistidas en JSONL.
- Reconocimiento manuscrito en la APK con ML Kit Digital Ink.
- Consulta a `Tutor_materias` sobre los materiales del curso vía Ollama local.
- Entidades Room preparadas para cola/proyectos persistentes.
- Exportación PNG desde el visor web.
- GitHub Actions para pruebas y APK debug.

## Pendientes intencionales para siguiente iteración

- Persistir la cola local realmente en Room mediante DAO y migraciones.
- Exportar PDF/JSON desde la APK, además del visor.
- Inserción visual editable de respuestas IA en el lienzo Android.
- Código QR real para descubrimiento del servidor.
- Conflictos avanzados tipo CRDT; por ahora se ordena por `timestamp` y se conserva historial.
- Modalidad opcional `MediaProjection + WebRTC` para pantalla completa; queda fuera del MVP porque el flujo principal es vectorial.

## Pruebas

Backend:

```powershell
cd smartboard/backend
py -m pip install -r requirements.txt
pytest -q
```

Android en GitHub:

```bash
gradle testDebugUnitTest assembleDebug
```
