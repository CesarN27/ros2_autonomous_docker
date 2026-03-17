# =============================================================================
#  RAYOWS.PY
# =============================================================================
#  Sistema de control para robot móvil con:
#   1) ROS 2 para comunicación entre nodos
#   2) Control de motores por GPIO usando PWM por software
#   3) Sensor ultrasónico para frenado de emergencia
#   4) Servidor WebSocket para recibir comandos remotos
#   5) Servidor MJPEG para transmitir video de la cámara
#
#  Esquema de control:
#   - Eje Y del joystick -> velocidad / tracción
#   - Eje X del joystick -> dirección
#
#  Mapeo interno del mensaje Twist:
#   - msg.linear.x  -> velocidad
#   - msg.angular.z -> dirección
#
#  Topics ROS usados:
#   - /cmd_vel         : comando de movimiento
#   - /emergency_stop  : frenado de emergencia
#
#  Hilos principales:
#   - Hilo ROS2 executor
#   - Hilo de captura de cámara
#   - Hilo de servidor MJPEG
#   - Hilo de servidor WebSocket
#   - Hilo PWM del controlador de motor
#   - Hilo del sensor ultrasónico
# =============================================================================

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

import gpiod
import time
import threading
import asyncio
import websockets
import json
import base64
import io

from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver

import logging
import os
import collections
import statistics
import warnings
import numpy as np
import joblib
import tensorflow as tf

# -----------------------------------------------------------------------------
# Intento de importar la cámara oficial de Raspberry Pi.
# Si no está disponible, se desactiva el flujo de video.
# -----------------------------------------------------------------------------
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False

# -----------------------------------------------------------------------------
# OpenCV se usa para comprimir frames a JPEG.
# Si no está disponible, se usa Pillow como alternativa.
# -----------------------------------------------------------------------------
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# -----------------------------------------------------------------------------
# Loggers principales del sistema:
#  - log     : eventos de control / robot
#  - log_cam : eventos de cámara / MJPEG
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log     = logging.getLogger("robot")
log_cam = logging.getLogger("camera")

# -----------------------------------------------------------------------------
# Configuración de hardware
# -----------------------------------------------------------------------------
CHIP = "gpiochip0"

# Pines del sensor ultrasónico
TRIG = 16
ECHO = 20

# Pines del puente H / motores
# ENA controla PWM del motor de velocidad
# ENB controla PWM del motor de dirección
ENA, IN1, IN2 = 13, 5, 6
ENB, IN3, IN4 = 18, 23, 24
MOTOR_PINS = [ENA, IN1, IN2, ENB, IN3, IN4]

# Distancia mínima segura en cm para activar el freno
DISTANCIA_PELIGRO = 15.0

# -----------------------------------------------------------------------------
# Configuración WebSocket
# -----------------------------------------------------------------------------
WS_HOST      = "0.0.0.0"
WS_PORT      = 8765
MOVE_RATE_HZ = 20

# Límite máximo esperado del joystick.
# Ejemplo: si la app manda coordenadas de -10 a 10, aquí se normalizan a -1..1
JOYSTICK_LIMIT = 10.0

# -----------------------------------------------------------------------------
# Configuración de video
# -----------------------------------------------------------------------------
VIDEO_FPS     = 15
VIDEO_WIDTH   = 640
VIDEO_HEIGHT  = 480
VIDEO_QUALITY = 70

# -----------------------------------------------------------------------------
# Rutas de archivos IA
# Nota: en esta versión actual no se usa la IA dentro del loop de seguridad,
# pero se conservan estas rutas por compatibilidad / evolución futura.
# -----------------------------------------------------------------------------
MODEL_PATH  = "modelo_calibracion_patched.h5"
SCALER_PATH = "scaler.pkl"


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
_video_lock        = threading.Lock()
_latest_frame_jpeg = None


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
    global _latest_frame_jpeg

    # Tiempo objetivo de cada ciclo para mantener el FPS configurado
    frame_delay = 1.0 / VIDEO_FPS

    if not PICAMERA2_AVAILABLE:
        log_cam.error("Picamera2 no disponible — sin video")
        return

    try:
        # Configuración del stream principal de video
        cam = Picamera2()
        config = cam.create_video_configuration(
            main={"size": (VIDEO_WIDTH, VIDEO_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": float(VIDEO_FPS)},
        )
        cam.configure(config)
        cam.start()

        # Pequeño tiempo de warm-up para estabilizar la cámara
        time.sleep(1)
        log_cam.info("Cámara iniciada (%dx%d @ %dfps)", VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS)
    except Exception as e:
        log_cam.error(f"Error al inicializar la cámara: {e}")
        return

    while True:
        try:
            t0 = time.monotonic()

            # Captura un frame RGB desde la cámara
            frame_rgb = cam.capture_array()

            # Si OpenCV está disponible, se usa para codificar a JPEG
            if CV2_AVAILABLE:
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                ok, buf   = cv2.imencode(
                    ".jpg",
                    frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, VIDEO_QUALITY]
                )
                if not ok:
                    continue
                jpeg_bytes = buf.tobytes()
            else:
                # Fallback a Pillow si no está OpenCV
                from PIL import Image as PILImage
                img    = PILImage.fromarray(frame_rgb)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=VIDEO_QUALITY)
                jpeg_bytes = buffer.getvalue()

            # Publicación del frame más reciente al buffer global
            with _video_lock:
                _latest_frame_jpeg = jpeg_bytes

            # Espera restante para mantener la frecuencia deseada
            elapsed = time.monotonic() - t0
            sleep_t = frame_delay - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        except Exception as e:
            log_cam.error(f"Error en el loop de captura: {e}")
            time.sleep(1)


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
        if self.path not in ("/stream", "/stream?"):
            if not self.path.startswith("/stream"):
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
                # Toma el último frame disponible
                with _video_lock:
                    frame = _latest_frame_jpeg

                # Si aún no hay frame, reintenta poco después
                if frame is None:
                    time.sleep(0.02)
                    continue

                # Cada parte multipart contiene un JPEG independiente
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

                # Ritmo de envío acorde al FPS objetivo
                time.sleep(1.0 / VIDEO_FPS)

        except (BrokenPipeError, ConnectionResetError):
            # Caso normal cuando el cliente cierra la conexión
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
    server = ThreadedHTTPServer(("0.0.0.0", 8080), MJPEGHandler)
    log_cam.info("MJPEG listo en http://0.0.0.0:8080/stream")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


# =============================================================================
#  MOTOR CONTROLLER (Y = VELOCIDAD, X = DIRECCION, AMBOS CON PWM)
# =============================================================================
class MotorController(Node):
    """
    Nodo ROS2 encargado del control físico del robot.

    Responsabilidades principales:
      - Recibir /cmd_vel
      - Recibir /emergency_stop
      - Traducir velocidad y dirección a:
          * direcciones IN1/IN2/IN3/IN4
          * PWM proporcional en ENA y ENB
      - Ejecutar PWM por software en un hilo independiente

    Convención de control:
      - linear.x  -> velocidad / tracción
      - angular.z -> dirección
    """

    def __init__(self):
        super().__init__("motor_controller")

        # Inicializa el chip GPIO y solicita control de los pines de motor
        self.chip  = gpiod.Chip(CHIP)
        self.lines = self.chip.get_lines(MOTOR_PINS)
        self.lines.request(consumer="motor", type=gpiod.LINE_REQ_DIR_OUT)

        # Estado global del freno de emergencia
        self.emergency_stop = False

        # Duty cycle PWM de cada canal
        # ENA -> motor de tracción
        # ENB -> motor de dirección
        self.pwm_ena = 0.0
        self.pwm_enb = 0.0

        # Estado lógico de dirección:
        # [IN1, IN2, IN3, IN4]
        self.dir_state = [0, 0, 0, 0]

        # Hilo que genera PWM por software continuamente
        self._running_pwm = True
        self.pwm_thread = threading.Thread(target=self._pwm_loop, daemon=True)
        self.pwm_thread.start()

        # Publicadores ROS
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.emg_pub = self.create_publisher(Bool,  "/emergency_stop", 10)

        # Suscriptores ROS
        self.create_subscription(Twist, "/cmd_vel", self.cmd_callback, 10)
        self.create_subscription(Bool,  "/emergency_stop", self.emergency_callback, 10)

        # Asegura arranque en estado detenido
        self.stop()

    def emergency_callback(self, msg):
        """
        Callback del topic /emergency_stop.

        Si el freno está activo, se fuerzan PWM y direcciones a cero.
        """
        self.emergency_stop = msg.data
        if self.emergency_stop:
            self.stop()

    def stop(self):
        """
        Lleva ambos motores a estado neutro:
          - PWM = 0
          - sin dirección activa
        """
        self.pwm_ena = 0.0
        self.pwm_enb = 0.0
        self.dir_state = [0, 0, 0, 0]

    def cmd_callback(self, msg):
        """
        Callback principal de movimiento.

        Traduce el Twist recibido a:
          - PWM proporcional para velocidad
          - PWM proporcional para dirección
          - dirección lógica de los pines del puente H

        Esquema:
          - Y = velocidad  -> msg.linear.x
          - X = dirección  -> msg.angular.z
        """
        if self.emergency_stop:
            self.stop()
            return

        # Entrada del joystick / comando remoto
        y = msg.linear.x
        x = msg.angular.z

        # Si no hay movimiento ni dirección, detener el robot
        if y == 0.0 and x == 0.0:
            self.stop()
            return

        # ---------------------------------------------------------------------
        # Normalización estricta a [-1.0, 1.0]
        # Esto permite trabajar con cualquier fuente de coordenadas mientras
        # JOYSTICK_LIMIT represente el valor máximo esperado.
        # ---------------------------------------------------------------------
        norm_y = round(y / JOYSTICK_LIMIT, 10)
        norm_x = round(x / JOYSTICK_LIMIT, 10)

        norm_y = max(-1.0, min(1.0, norm_y))
        norm_x = max(-1.0, min(1.0, norm_x))

        # ---------------------------------------------------------------------
        # MOTOR A (ENA, IN1, IN2) = VELOCIDAD / TRACCION
        #   Y > 0 -> adelante
        #   Y < 0 -> atrás
        # ---------------------------------------------------------------------
        self.pwm_ena = round(abs(norm_y), 10)

        if norm_y > 0.0:
            in1, in2 = 1, 0
        elif norm_y < 0.0:
            in1, in2 = 0, 1
        else:
            in1, in2 = 0, 0

        # ---------------------------------------------------------------------
        # MOTOR B (ENB, IN3, IN4) = DIRECCION
        #   X < 0 -> izquierda
        #   X > 0 -> derecha
        # También se aplica PWM proporcional para modular intensidad de giro.
        # ---------------------------------------------------------------------
        self.pwm_enb = round(abs(norm_x), 10)

        if norm_x < 0.0:
            in3, in4 = 1, 0   # izquierda
        elif norm_x > 0.0:
            in3, in4 = 0, 1   # derecha
        else:
            in3, in4 = 0, 0

        # Guarda el estado final a usar por el hilo PWM
        self.dir_state = [in1, in2, in3, in4]

    def _pwm_loop(self):
        """
        Genera PWM por software sobre ENA y ENB.

        Este loop:
          - lee el duty cycle actual de cada canal
          - activa/desactiva ENA y ENB durante una ventana fija
          - mantiene IN1..IN4 constantes durante el periodo correspondiente

        period = 0.02  -> 50 Hz aprox.
        """
        period = 0.02

        while self._running_pwm:
            # Copias locales para evitar inconsistencias si otro hilo actualiza
            p_a = self.pwm_ena
            p_b = self.pwm_enb
            d_st = self.dir_state

            # Si hay freno o ambos motores están en cero, se apagan todas las salidas
            if self.emergency_stop or (p_a == 0.0 and p_b == 0.0):
                self.lines.set_values([0, 0, 0, 0, 0, 0])
                time.sleep(0.02)
                continue

            # Caso especial: ambos duty cycles al 100%
            if p_a == 1.0 and p_b == 1.0:
                self.lines.set_values([1, d_st[0], d_st[1], 1, d_st[2], d_st[3]])
                time.sleep(period)
                continue

            # Tiempo activo de cada canal dentro del periodo
            t_a = p_a * period
            t_b = p_b * period

            # Etapa 1: ambos canales que deban iniciar activos se encienden
            val_a = 1 if t_a > 0 else 0
            val_b = 1 if t_b > 0 else 0
            self.lines.set_values([val_a, d_st[0], d_st[1], val_b, d_st[2], d_st[3]])

            # Primer apagado: el canal con menor tiempo activo
            first_off = min(t_a, t_b)
            if first_off > 0:
                time.sleep(first_off)

            # Etapa 2: se apaga el canal que ya cumplió su duty
            val_a = 1 if t_a > first_off else 0
            val_b = 1 if t_b > first_off else 0
            self.lines.set_values([val_a, d_st[0], d_st[1], val_b, d_st[2], d_st[3]])

            # Segundo apagado: el canal con mayor tiempo activo
            second_off = max(t_a, t_b)
            if second_off > first_off:
                time.sleep(second_off - first_off)

            # Etapa 3: fin del periodo, ambos EN quedan apagados
            self.lines.set_values([0, d_st[0], d_st[1], 0, d_st[2], d_st[3]])

            # Espera el resto del periodo
            remainder = period - second_off
            if remainder > 0:
                time.sleep(remainder)

    def destroy_node(self):
        """
        Libera recursos al cerrar el nodo:
          - detiene el hilo PWM
          - apaga salidas
          - libera líneas GPIO y chip
        """
        self._running_pwm = False
        try:
            self.stop()
        finally:
            try:
                self.lines.release()
            except Exception:
                pass
            try:
                self.chip.close()
            except Exception:
                pass
            super().destroy_node()


# =============================================================================
#  SAFETY ULTRASONIC NODE
# =============================================================================
class SafetyUltrasonicNode(Node):
    """
    Nodo ROS2 de seguridad basado en sensor ultrasónico.

    Función:
      - Monitorea distancia frontal continuamente
      - Solo activa el freno si el robot está avanzando
      - Publica el estado en /emergency_stop

    La idea es evitar colisiones frontales cuando el vehículo se mueve hacia
    adelante.
    """

    def __init__(self):
        super().__init__("ultrasonic")

        # Publicador del freno de emergencia
        self.pub = self.create_publisher(Bool, "/emergency_stop", 10)

        # Bandera que indica si el robot está intentando avanzar
        self.forward_active = False

        # Escucha /cmd_vel para saber si va hacia adelante
        self.create_subscription(Twist, "/cmd_vel", self.cmd_vel_callback, 10)

        # Configuración de GPIO del sensor ultrasónico
        self.chip = gpiod.Chip(CHIP)

        self.trig = self.chip.get_lines([TRIG])
        self.trig.request(consumer="trig", type=gpiod.LINE_REQ_DIR_OUT)

        self.echo = self.chip.get_lines([ECHO])
        self.echo.request(consumer="echo", type=gpiod.LINE_REQ_DIR_IN)

        # Hilo de monitoreo continuo de distancia
        threading.Thread(target=self.sensor_loop, daemon=True).start()

    def cmd_vel_callback(self, msg):
        """
        Se considera "avance activo" solo si la velocidad lineal es positiva.
        Esto evita frenar por obstáculo frontal cuando el robot va en reversa.
        """
        self.forward_active = (msg.linear.x > 0)

    def read_distance(self):
        """
        Realiza una medición de distancia con HC-SR04.

        Flujo:
          1) Pulso corto en TRIG
          2) Espera subida de ECHO
          3) Mide duración del pulso alto
          4) Convierte el tiempo a distancia en cm

        Retorna:
          - distancia en cm
          - 999 si hubo timeout
        """
        self.trig.set_values([1])
        time.sleep(0.00001)
        self.trig.set_values([0])

        timeout = time.time() + 0.02

        while self.echo.get_values()[0] == 0:
            if time.time() > timeout:
                return 999

        start = time.time()

        while self.echo.get_values()[0] == 1:
            if time.time() > timeout:
                return 999

        return (time.time() - start) * 17150

    def sensor_loop(self):
        """
        Loop continuo de seguridad.

        Publica True en /emergency_stop si:
          - el robot va hacia adelante
          - la distancia medida es menor a DISTANCIA_PELIGRO
        """
        while rclpy.ok():
            dist = self.read_distance()

            msg = Bool()
            msg.data = self.forward_active and dist < DISTANCIA_PELIGRO
            self.pub.publish(msg)

            time.sleep(0.05)

    def destroy_node(self):
        """
        Libera recursos GPIO del sensor al cerrar el nodo.
        """
        try:
            self.trig.set_values([0])
        except Exception:
            pass
        finally:
            for l in (self.trig, self.echo):
                try:
                    l.release()
                except Exception:
                    pass
            try:
                self.chip.close()
            except Exception:
                pass
            super().destroy_node()


# =============================================================================
#  WEBSOCKET BRIDGE
# =============================================================================
class WebSocketBridge:
    """
    Puente entre clientes remotos y ROS2 mediante WebSocket.

    Responsabilidades:
      - Aceptar conexiones remotas
      - Interpretar mensajes JSON
      - Convertirlos a publicaciones ROS sobre /cmd_vel o /emergency_stop
      - Limitar frecuencia de envío para no saturar el controlador
    """

    def __init__(self, motor):
        self.motor = motor
        self._last_move = 0
        self._min_dt = 1.0 / MOVE_RATE_HZ

    def publish_move(self, x, y):
        """
        Convierte coordenadas del joystick remoto a un Twist ROS.

        Convención:
          - y -> velocidad   -> linear.x
          - x -> dirección   -> angular.z
        """
        now = time.monotonic()
        if now - self._last_move < self._min_dt:
            return

        msg = Twist()
        msg.linear.x = float(y)    # velocidad
        msg.angular.z = float(x)   # dirección

        self.motor.cmd_pub.publish(msg)
        self._last_move = now

    async def handler(self, ws):
        """
        Handler por conexión WebSocket.

        Mensajes esperados:
          - {"command": "MOVE", "x": ..., "y": ...}
          - {"command": "EMERGENCY_STOP"}
          - {"command": "RESUME"}
          - {"command": "STOP"}
        """
        try:
            async for raw in ws:
                data = json.loads(raw)
                cmd = data.get("command", "")

                if cmd == "MOVE":
                    self.publish_move(
                        float(data.get("x", 0)),
                        float(data.get("y", 0))
                    )

                elif cmd == "EMERGENCY_STOP":
                    msg = Bool()
                    msg.data = True
                    self.motor.emg_pub.publish(msg)

                elif cmd == "RESUME":
                    msg = Bool()
                    msg.data = False
                    self.motor.emg_pub.publish(msg)

                elif cmd == "STOP":
                    self.motor.cmd_pub.publish(Twist())

        except Exception:
            # Se ignoran errores de cliente para no detener el servidor
            pass
        finally:
            # Al desconectarse el cliente, se manda STOP por seguridad
            self.motor.cmd_pub.publish(Twist())

    async def run(self):
        """
        Inicia el servidor WebSocket y queda a la espera indefinidamente.
        """
        async with websockets.serve(self.handler, WS_HOST, WS_PORT):
            await asyncio.Future()

    def start(self):
        """
        Lanza el servidor WebSocket en un hilo daemon separado.
        """
        threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True).start()


# =============================================================================
#  MAIN
# =============================================================================
def main():
    """
    Punto de entrada principal del sistema.

    Flujo general:
      1) Inicializa ROS2
      2) Crea nodos:
           - MotorController
           - SafetyUltrasonicNode
      3) Lanza hilos auxiliares:
           - captura de cámara
           - servidor MJPEG
           - servidor WebSocket
      4) Ejecuta el MultiThreadedExecutor de ROS2
      5) Al salir, libera recursos de forma segura
    """
    rclpy.init()

    motor = MotorController()
    safety = SafetyUltrasonicNode()

    # Hilo de captura de video
    threading.Thread(target=_capture_loop, daemon=True).start()

    # Hilo servidor de stream MJPEG
    threading.Thread(target=start_mjpeg_server, daemon=True).start()

    # Hilo servidor WebSocket
    ws = WebSocketBridge(motor)
    ws.start()

    # Executor ROS2 multihilo para procesar callbacks de ambos nodos
    executor = MultiThreadedExecutor()
    executor.add_node(motor)
    executor.add_node(safety)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        motor.stop()
        motor.destroy_node()
        safety.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()