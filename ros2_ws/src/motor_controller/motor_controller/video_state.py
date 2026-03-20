import threading

# =============================================================================
#  BUFFER DE VIDEO GLOBAL
# =============================================================================
# _latest_frame_jpeg guarda el último frame JPEG producido por la cámara.
# Este frame es compartido entre:
#   - el hilo de captura
#   - el servidor MJPEG
#
# El lock evita condiciones de carrera al leer/escribir el frame.
# =============================================================================
_video_lock = threading.Lock()
_latest_frame_jpeg = None


def set_latest_frame(jpeg_bytes):
    global _latest_frame_jpeg
    with _video_lock:
        _latest_frame_jpeg = jpeg_bytes


def get_latest_frame():
    with _video_lock:
        return _latest_frame_jpeg