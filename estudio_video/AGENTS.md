# AGENTS.md — estudio de vídeo

Guía para agentes de IA (y personas) que modifiquen `estudio_video/`. Proyecto **independiente**
del resto del repo: dependencias propias (`requirements.txt`, `requirements-camara.txt`), tests
propios. Documentación en español; identificadores en inglés.

## Mapa

| Archivo | Responsabilidad |
|---|---|
| `videostudio/plan.py` | Texto → `Storyboard` (escenas, duración, formato, entorno) por reglas |
| `videostudio/render.py` | `Storyboard` → MP4 (fondo + rótulo + transiciones) vía tubería a ffmpeg |
| `videostudio/backgrounds.py` | Entornos procedurales `f(t, w, h) -> uint8 RGB`, `BACKGROUND_WORDS` |
| `videostudio/effects.py` | Efectos `f(img, t) -> img` para cuerpo/cara, `EFFECT_WORDS`, caretas desde imagen |
| `videostudio/looks.py` | `Look` y `parse_look`: órdenes en español → entorno/cuerpo/cara |
| `videostudio/segment.py` | Máscara de persona y cajas de cara: MediaPipe Tasks o alternativa OpenCV |
| `videostudio/camera.py` | `compose`, `Transformer`, `process_video`, bucle `live` de cámara |
| `videostudio/edit.py` | Operaciones ffmpeg; cada una con `*_cmd` puro (probable sin ejecutar) |
| `videostudio/llm.py` | Modo IA opcional (Claude, structured outputs); devuelve `None` ante cualquier fallo |
| `videostudio/voice.py` | Voz sin conexión (Vosk): `VoiceListener`, `dictate`, `voice_action` (graba/para/foto/salir) |
| `videostudio/cli.py` | `python -m videostudio crear|guion|camara|procesar|editar|opciones` |
| `ejemplos/` | `generar.py` regenera `entornos.png` y `viaje.mp4` |

## Comandos (desde `estudio_video/`)

```bash
pip install -r requirements.txt
pytest tests              # ~2 s, sin red, sin cámara; deben pasar siempre (job CI «Tests del estudio de vídeo»)
python ejemplos/generar.py
```

## Invariantes (vigiladas por tests)

1. Imágenes RGB `uint8` (h, w, 3) en todo el código; BGR sólo en la frontera con OpenCV.
2. Entornos deterministas en `t` y animados; efectos conservan forma y tipo.
3. `compose` con `Look()` vacío = identidad; máscara 0 ⇒ entorno puro; máscara 1 ⇒ persona.
4. Nada de red en tests: usar `OpenCVSegmenter` con referencia sintética; la IA nunca es obligatoria.
5. Transparencia: todo MP4 lleva `render.AI_NOTICE` en metadatos; las salidas con look activo,
   la marca visible `camera.label_frame` salvo `--sin-marca`. No añadir intercambio realista
   de caras con terceros. Nunca comprometer vídeos/fotos personales (repo **público**; ver `DERECHOS.md`).
6. Vectorizar con numpy por píxel; los bucles sólo sobre objetos pequeños (árboles, caras).

## Recetas

- **Nuevo entorno**: función en `backgrounds.py`, entrada en `BACKGROUNDS` y `BACKGROUND_WORDS`
  (palabras normalizadas, sin tildes), regenerar `ejemplos/`. El test parametrizado lo cubre.
- **Nuevo efecto**: función en `effects.py`, entrada en `EFFECTS` y `EFFECT_WORDS`.
- **Nueva orden de edición**: `xxx_cmd` + `xxx` en `edit.py`, subcomando en `cli.py`, test.

## Ideas / siguiente paso

- Vídeo generativo realista: adaptador opcional a un servicio externo (requiere clave y coste).
- No implementar intercambio realista de cara con terceros (suplantación); las caretas con
  imagen propia y los efectos estilizados cubren el caso de uso.
