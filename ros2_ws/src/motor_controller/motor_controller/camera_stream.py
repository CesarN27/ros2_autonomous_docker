import io
import threading
import time

from .config import (
    CV2_AVAILABLE,
    PICAMERA2_AVAILABLE,
    Picamera2,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_QUALITY,
    VIDEO_WIDTH,
    cv2,
    log_cam,
)
from .video_state import set_latest_frame


# =============================================================================
#  CAPTURA DE CÁMARA
# =============================================================================
def _capture_loop():
    """
    Hilo de captura continua de la cámara.

    Flujo:
      1) Inicializa la cámara con Picamera2
      2) Captura frames RGB
      3) Los comprime a JPEG
      4) Guarda el último JPEG en el buffer global
      5) Respeta VIDEO_FPS para mantener un frame rate estable

    Si falla la cámara o la compresión, se registra el error y el hilo
    intenta continuar.
    """
    frame_delay = 1.0 / VIDEO_FPS

    if not PICAMERA2_AVAILABLE:
        log_cam.error("Picamera2 no disponible — sin video")
        return

    try:
        cam = Picamera2()
        config = cam.create_video_configuration(
            main={"size": (VIDEO_WIDTH, VIDEO_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": float(VIDEO_FPS)},
        )
        cam.configure(config)
        cam.start()

        time.sleep(1)
        log_cam.info(
            "Cámara iniciada (%dx%d @ %dfps)",
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
            VIDEO_FPS,
        )
    except Exception as e:
        log_cam.error(f"Error al inicializar la cámara: {e}")
        return

    while True:
        try:
            t0 = time.monotonic()

            frame_rgb = cam.capture_array()

            if CV2_AVAILABLE:
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                ok, buf = cv2.imencode(
                    ".jpg",
                    frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, VIDEO_QUALITY],
                )
                if not ok:
                    continue
                jpeg_bytes = buf.tobytes()
            else:
                from PIL import Image as PILImage

                img = PILImage.fromarray(frame_rgb)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=VIDEO_QUALITY)
                jpeg_bytes = buffer.getvalue()

            set_latest_frame(jpeg_bytes)

            elapsed = time.monotonic() - t0
            sleep_t = frame_delay - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        except Exception as e:
            log_cam.error(f"Error en el loop de captura: {e}")
            time.sleep(1)


def start_capture_thread():
    threading.Thread(target=_capture_loop, daemon=True).start()