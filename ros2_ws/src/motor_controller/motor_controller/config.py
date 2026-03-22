import logging

# -----------------------------------------------------------------------------
# Intento de importar la cámara oficial de Raspberry Pi.
# Si no está disponible, se desactiva el flujo de video.
# -----------------------------------------------------------------------------
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    Picamera2 = None
    PICAMERA2_AVAILABLE = False

# -----------------------------------------------------------------------------
# OpenCV se usa para comprimir frames a JPEG.
# Si no está disponible, se usa Pillow como alternativa.
# -----------------------------------------------------------------------------
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

# -----------------------------------------------------------------------------
# Loggers principales del sistema:
#  - log     : eventos de control / robot
#  - log_cam : eventos de cámara / MJPEG
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("robot")
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
WS_HOST = "0.0.0.0"
WS_PORT = 8765
MOVE_RATE_HZ = 20

# Límite máximo esperado del joystick.
# Ejemplo: si la app manda coordenadas de -10 a 10, aquí se normalizan a -1..1
JOYSTICK_LIMIT = 10.0

# -----------------------------------------------------------------------------
# Configuración de video
# -----------------------------------------------------------------------------
VIDEO_FPS = 15
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480
VIDEO_QUALITY = 70

MJPEG_HOST = "0.0.0.0"
MJPEG_PORT = 8080
MJPEG_ENDPOINT = "/stream"

# -----------------------------------------------------------------------------
# Rutas de archivos IA
# Actualmente estas rutas son utilizadas por SafetyUltrasonicNode para aplicar
# corrección de distancia cuando el modelo y el scaler están disponibles.
# -----------------------------------------------------------------------------
MODEL_PATH = "modelo_calibracion_patched.h5"
SCALER_PATH = "scaler.pkl"