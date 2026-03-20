import collections
import threading
import time
import warnings

import gpiod
import joblib
import numpy as np
import tensorflow as tf
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool

from .config import CHIP, ECHO, MODEL_PATH, SCALER_PATH, TRIG
from .fuzzy import fuzzy_brake_factor


# =============================================================================
#  SAFETY ULTRASONIC NODE
# =============================================================================
class SafetyUltrasonicNode(Node):
    """
    Nodo ROS2 de seguridad basado en sensor ultrasónico.

    Función:
      - Monitorea distancia frontal continuamente
      - Calibra la distancia con un modelo de IA (si está disponible)
      - Aplica lógica difusa para modular la velocidad de forma progresiva
      - Solo activa el freno total si el factor difuso llega a 0.0 y el robot avanza
      - Publica el factor difuso en /fuzzy_cmd
      - Publica el estado de frenado en /emergency_stop

    La idea es evitar colisiones frontales con frenado suave e inteligente.
    """

    def __init__(self):
        super().__init__("ultrasonic")

        self.pub = self.create_publisher(Bool, "/emergency_stop", 10)
        self.fuzzy_pub = self.create_publisher(Twist, "/fuzzy_cmd", 10)

        self.forward_active = False

        self.create_subscription(Twist, "/cmd_vel", self.cmd_vel_callback, 10)

        warnings.filterwarnings("ignore")

        self.model = None
        self.scaler = None
        self.buffer = collections.deque(maxlen=5)

        try:
            self.model = tf.keras.models.load_model(MODEL_PATH, compile=False)
            self.scaler = joblib.load(SCALER_PATH)
            self.get_logger().info("✅ Modelo IA cargado correctamente")
        except Exception as e:
            self.get_logger().warning(f"⚠ IA no disponible, usando distancia cruda: {e}")

        self.chip = gpiod.Chip(CHIP)

        self.trig = self.chip.get_lines([TRIG])
        self.trig.request(consumer="trig", type=gpiod.LINE_REQ_DIR_OUT)

        self.echo = self.chip.get_lines([ECHO])
        self.echo.request(consumer="echo", type=gpiod.LINE_REQ_DIR_IN)

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

    def calibrate(self, d):
        """
        Calibra la distancia cruda usando el modelo de IA.

        Si el modelo no está disponible, retorna la distancia sin modificar.

        Entradas al modelo:
          - distancia actual
          - media del buffer reciente
          - desviación estándar del buffer
          - mediana del buffer
        """
        if self.model is None or self.scaler is None:
            return d

        self.buffer.append(d)

        if len(self.buffer) < 2:
            return d

        arr = np.array(
            [[
                d,
                np.mean(self.buffer),
                np.std(self.buffer),
                np.median(self.buffer),
            ]],
            dtype=np.float32,
        )

        arr = self.scaler.transform(arr)
        return float(self.model.predict(arr, verbose=0)[0][0])

    def sensor_loop(self):
        """
        Loop continuo de seguridad con IA + lógica difusa.

        Por cada ciclo:
          1) Lee distancia cruda del sensor
          2) Calibra con IA (si está disponible)
          3) Calcula el factor difuso según la distancia
          4) Publica el factor en /fuzzy_cmd para modular la velocidad
          5) Activa /emergency_stop solo si el factor es 0.0 y hay avance activo
        """
        while True:
            dist = self.read_distance()

            if dist != 999:
                dist = self.calibrate(dist)

            factor = fuzzy_brake_factor(dist)

            fuzzy_msg = Twist()
            fuzzy_msg.linear.x = factor
            self.fuzzy_pub.publish(fuzzy_msg)

            stop_msg = Bool()
            stop_msg.data = self.forward_active and (factor == 0.0)
            self.pub.publish(stop_msg)

            self.get_logger().debug(f"[FUZZY] {dist:.2f} cm → factor {factor:.2f}")

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