# Derechos de imagen, de autor y privacidad

Resumen práctico para usar el estudio de vídeo en España/UE. **No es asesoramiento jurídico**;
ante un uso comercial o dudoso, consulta a un profesional.

## 1. ¿Qué es público y qué es privado?

| Qué | Dónde queda | ¿Público? |
|---|---|---|
| Código, documentación y `ejemplos/` | Repositorio GitHub | **Sí: el repositorio es público** |
| Tus fotos y vídeos de la cámara, vídeos creados o editados | Carpeta `salidas/` (o la que indiques) en tu ordenador | No. `.gitignore` excluye `salidas/` y cualquier `.mp4`, `.mov`, `.png`, `.jpg`, `.wav`, `.mp3`… de `estudio_video/` salvo `ejemplos/` |
| Imagen de la cámara y audio del micrófono | Se procesan en memoria en tu ordenador | No se envían a ningún servidor (MediaPipe y Vosk funcionan sin conexión) |
| Textos que mandas con `--ia` | API de Anthropic (Claude) | Sólo el texto de la orden o descripción; nunca imagen ni audio |

Para no publicar algo por error: no hagas `git add -f` sobre tus vídeos y no los muevas a
`ejemplos/`. Los ejemplos del repositorio están generados íntegramente por código (sin
personas ni material de terceros).

## 2. Derecho a la propia imagen (LO 1/1982)

* Grabarte y transformarte a **ti mismo** no plantea problema.
* Para grabar, transformar o publicar a **otras personas** necesitas su consentimiento
  (expreso para publicarlo). Con **menores**, el de sus padres o tutores, y aun así con cautela.
* Las «caretas» (`--cara imagen.png`) sólo con imágenes tuyas o con derechos: no pongas la
  cara de una persona real identificable sobre otra.
* La herramienta **no hace intercambio realista de caras** (deepfake) a propósito: hacerse pasar
  por otra persona puede vulnerar su derecho a la imagen y al honor, y en casos graves ser delito.

## 3. Datos personales (RGPD)

* La imagen y la voz de una persona identificable son datos personales. Para uso doméstico
  propio no aplica el RGPD; si grabas a otros para difundirlo, sí.
* La detección de caras/cuerpo que usa la herramienta **no identifica** a nadie (sólo localiza
  dónde está la cara para aplicar el efecto) y no guarda plantillas biométricas.

## 4. Transparencia de contenido hecho con IA (Reglamento UE 2024/1689, art. 50)

Desde el 2 de agosto de 2026, quien difunde imágenes o vídeos generados o manipulados con IA
que puedan parecer reales debe indicarlo. Por eso, por defecto:

* todo MP4 generado lleva en sus metadatos «Contenido generado o modificado con IA (estudio_video)»;
* los vídeos y fotos de la cámara o de `procesar` con un efecto activo llevan además la marca
  visible **«Modificado con IA»** en la esquina (`--sin-marca` la quita; hazlo sólo si vas a
  avisar de otra forma, p. ej. con la etiqueta de IA de la red social).

## 5. Derechos de autor del material que añades

* **Música** (`--musica`, `editar musica`): usa música propia, con licencia libre (Creative
  Commons compatible con tu uso, dominio público) o comprada con licencia de sincronización.
  Las canciones comerciales pueden provocar bloqueos o reclamaciones en YouTube/TikTok/Instagram.
* **Fondos propios** (`--fondo foto.jpg`): sólo imágenes/vídeos tuyos o con licencia.
* Lo que crees con la herramienta es tuyo en la medida en que haya aportación creativa tuya
  (textos, guion, montaje, grabación). Los entornos y efectos generados por código no
  reproducen obras de terceros.

## 6. Licencias del software usado

| Componente | Licencia |
|---|---|
| numpy, Pillow (HPND), OpenCV (Apache 2.0 desde 4.5) | Permisivas |
| MediaPipe y sus modelos *selfie segmenter* / *BlazeFace* | Apache 2.0 |
| Vosk y su modelo pequeño de español | Apache 2.0 |
| ffmpeg (sistema o el binario de `imageio-ffmpeg`) | LGPL/GPL: libre para uso personal; si redistribuyes un programa que incluya el binario, revisa sus condiciones |
| anthropic (SDK) | MIT |

El repositorio **no tiene archivo `LICENSE`**: por defecto el código es «todos los derechos
reservados» aunque sea visible (GitHub permite verlo y bifurcarlo, no reutilizarlo). Si quieres
que otros puedan usarlo, añade una licencia (p. ej. MIT).
