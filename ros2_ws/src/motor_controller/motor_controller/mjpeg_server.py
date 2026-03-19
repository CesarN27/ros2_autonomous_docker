import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from .config import MJPEG_ENDPOINT, MJPEG_HOST, MJPEG_PORT, VIDEO_FPS, log_cam
from .video_state import get_latest_frame


# =============================================================================
#  MJPEG SERVER  (PUERTO 8080)
# =============================================================================
class MJPEGHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP que sirve el stream MJPEG.

    Endpoint esperado:
      - /stream

    El contenido se transmite como multipart/x-mixed-replace, de modo que
    clientes compatibles puedan ver video continuo.
    """

    def log_message(self, format, *args):
        """Silencia el log HTTP por request para no saturar la consola."""
        pass

    def do_GET(self):
        """
        Atiende peticiones GET al endpoint /stream.

        Flujo:
          1) Valida la ruta
          2) Responde con headers MJPEG
          3) Entra a un loop enviando frames JPEG sucesivos
          4) Sale cuando el cliente se desconecta
        """
        if self.path not in (MJPEG_ENDPOINT, f"{MJPEG_ENDPOINT}?"):
            if not self.path.startswith(MJPEG_ENDPOINT):
                self.send_error(404)
                return

        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        log_cam.info(f"Cliente MJPEG conectado: {self.client_address[0]}")

        try:
            while True:
                frame = get_latest_frame()

                if frame is None:
                    time.sleep(0.02)
                    continue

                part_header = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                    b"\r\n"
                )

                self.wfile.write(part_header)
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

                time.sleep(1.0 / VIDEO_FPS)

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            log_cam.warning(f"Stream cortado: {e}")

        log_cam.info(f"Cliente MJPEG desconectado: {self.client_address[0]}")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """
    Servidor HTTP multihilo.

    Permite múltiples clientes simultáneos para el stream de video.
    """
    daemon_threads = True
    allow_reuse_address = True


def start_mjpeg_server():
    """
    Inicia el servidor HTTP MJPEG en el puerto 8080.

    Este servidor consume el buffer global de video y lo expone en /stream.
    """
    server = ThreadedHTTPServer((MJPEG_HOST, MJPEG_PORT), MJPEGHandler)
    log_cam.info(f"MJPEG listo en http://{MJPEG_HOST}:{MJPEG_PORT}{MJPEG_ENDPOINT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def start_mjpeg_server_thread():
    threading.Thread(target=start_mjpeg_server, daemon=True).start()