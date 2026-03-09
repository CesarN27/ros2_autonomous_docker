import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

import gpiod
import time
import threading
import sys
import select
import termios
import tty

# ====== IA calibración ======
import os
import collections
import statistics
import numpy as np
import joblib
import tensorflow as tf

# Parche loaders
import zipfile
import json
import tempfile
import shutil
import h5py

# ✅ Para quitar spam de warnings
import warnings

CHIP = "gpiochip0"

# -------- Pines Sensor --------
TRIG = 16
ECHO = 20

# -------- Pines Motores --------
ENA, IN1, IN2 = 13, 5, 6     # Motor Tracción
ENB, IN3, IN4 = 18, 23, 24   # Motor Dirección
MOTOR_PINS = [ENA, IN1, IN2, ENB, IN3, IN4]

DISTANCIA_PELIGRO = 15.0

# ✅ Modelo .h5
MODEL_PATH = "modelo_calibracion_patched.h5"
SCALER_PATH = "scaler.pkl"


# ============================================================
#  MOTOR CONTROLLER (NO TOCAR)
# ============================================================
class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.get_logger().info("Motor Controller iniciado. (Manual/Auto via /cmd_vel)")

        self.chip = gpiod.Chip(CHIP)
        self.lines = self.chip.get_lines(MOTOR_PINS)
        self.lines.request(consumer="motor_controller", type=gpiod.LINE_REQ_DIR_OUT)

        self.state = [0, 0, 0, 0, 0, 0]
        self.emergency_stop = False
        self._last_emergency = False

        self.stop()

        self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.create_subscription(Bool, '/emergency_stop', self.emergency_callback, 10)

    def emergency_callback(self, msg: Bool):
        self.emergency_stop = bool(msg.data)
        if self.emergency_stop and not self._last_emergency:
            self.get_logger().warn("🚨 EMERGENCY STOP ACTIVADO -> Frenando motores")
            self.stop()
        if (not self.emergency_stop) and self._last_emergency:
            self.get_logger().info("✅ EMERGENCY STOP DESACTIVADO -> Motores habilitados")
        self._last_emergency = self.emergency_stop

    def update_pins(self):
        self.lines.set_values(self.state)

    def stop(self):
        self.state = [0, 0, 0, 0, 0, 0]
        self.update_pins()

    def cmd_callback(self, msg: Twist):
        if self.emergency_stop:
            self.stop()
            return

        lin = msg.linear.x
        ang = msg.angular.z

        if lin == 0 and ang == 0:
            self.stop()
            return

        if lin > 0:
            self.state[0:3] = [1, 1, 0]  # Adelante
        elif lin < 0:
            self.state[0:3] = [1, 0, 1]  # Atras
        else:
            self.state[0:3] = [0, 0, 0]  # Freno traccion

        if ang > 0:
            self.state[3:6] = [1, 0, 1]  # Izquierda (A)
        elif ang < 0:
            self.state[3:6] = [1, 1, 0]  # Derecha (D)
        else:
            self.state[3:6] = [0, 0, 0]  # Centro

        self.update_pins()

    def destroy_node(self):
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


# ============================================================
#  TELEOP (NO TOCAR)
# ============================================================
class TeleopPublisher(Node):
    def __init__(self):
        super().__init__('teleop_publisher')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Bool, '/emergency_stop', self.emergency_callback, 10)

        self.emergency_stop = False

        self.get_logger().info(
            "Controles de Toque:\n"
            "W/S: Adelante/Atras\n"
            "A/D: Izquierda/Centro/Derecha\n"
            "ESPACIO: Freno Total\n"
            "Q: Salir"
        )

        thread = threading.Thread(target=self.keyboard_loop, daemon=True)
        thread.start()

    def emergency_callback(self, msg: Bool):
        self.emergency_stop = bool(msg.data)

    def get_key(self, timeout=0.1):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                key = sys.stdin.read(1)
            else:
                key = ''
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return key

    def keyboard_loop(self):
        msg = Twist()

        while rclpy.ok():
            key = self.get_key(timeout=0.1).lower()

            if key == 'q':
                rclpy.shutdown()
                break

            if self.emergency_stop:
                msg.linear.x = 0.0
                msg.angular.z = 0.0
                self.pub.publish(msg)
                continue

            if key == 'w':
                msg.linear.x = 1.0
            elif key == 's':
                msg.linear.x = -1.0

            elif key == 'a':
                if msg.angular.z == -1.0:
                    msg.angular.z = 0.0
                else:
                    msg.angular.z = 1.0

            elif key == 'd':
                if msg.angular.z == 1.0:
                    msg.angular.z = 0.0
                else:
                    msg.angular.z = -1.0

            elif key == 'c':
                msg.angular.z = 0.0

            elif key == ' ':
                msg.linear.x = 0.0
                msg.angular.z = 0.0

            self.pub.publish(msg)


# ============================================================
#  SENSOR ANTICOLISIÓN + IA
#  - Frena SOLO si va hacia adelante (W/WA/WD)
#  - Parchea quantization_config dentro de .h5
#  - Silencia warnings de sklearn
# ============================================================
class SafetyUltrasonicNode(Node):
    def __init__(self):
        super().__init__('safety_ultrasonic')
        self.get_logger().info("🛡️ Sensor anticolisión iniciado (con calibración IA)")
        self.get_logger().info(f"TensorFlow version: {tf.__version__}")

        # ✅ Silenciar warnings molestos de sklearn (sin afectar ejecución)
        # InconsistentVersionWarning vive en sklearn.exceptions, pero filtrarlo por mensaje es suficiente
        warnings.filterwarnings("ignore", message="Trying to unpickle estimator.*")
        warnings.filterwarnings("ignore", message="X does not have valid feature names.*")

        self.pub = self.create_publisher(Bool, '/emergency_stop', 10)

        # ✅ Solo frenar si vamos hacia adelante
        self.forward_active = False
        self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)

        # --- Cargar modelo y scaler (una vez) ---
        self.model = None
        self.scaler = None

        model_path = self._resolve_file(MODEL_PATH)
        scaler_path = self._resolve_file(SCALER_PATH)

        try:
            if model_path is None or scaler_path is None:
                raise FileNotFoundError(
                    f"No encontré archivos. model_path={model_path} scaler_path={scaler_path}"
                )

            self.get_logger().info(f"Usando modelo en: {model_path}")
            self.model = self._load_model_compat(model_path)

            self.get_logger().info(f"Usando scaler en: {scaler_path}")
            self.scaler = joblib.load(scaler_path)

            # ✅ Evita warning de feature names en tiempo real
            if hasattr(self.scaler, "feature_names_in_"):
                try:
                    delattr(self.scaler, "feature_names_in_")
                except Exception:
                    pass

            self.get_logger().info("✅ IA de calibración cargada correctamente")

        except Exception as e:
            self.get_logger().error(
                f"❌ No se pudo cargar IA/scaler. Se usará distancia cruda. Error: {e}"
            )

        self.buffer_historico = collections.deque(maxlen=5)

        # --- GPIO (MISMA API que tu código que funciona) ---
        self.chip = gpiod.Chip(CHIP)

        self.trig_lines = self.chip.get_lines([TRIG])
        self.trig_lines.request(consumer="ultrasonic_trig", type=gpiod.LINE_REQ_DIR_OUT)
        self.trig_lines.set_values([0])

        self.echo_lines = self.chip.get_lines([ECHO])
        self.echo_lines.request(consumer="ultrasonic_echo", type=gpiod.LINE_REQ_DIR_IN)

        self.emergency_stop = False

        threading.Thread(target=self.sensor_loop, daemon=True).start()

    def cmd_vel_callback(self, msg: Twist):
        self.forward_active = (msg.linear.x > 0.0)

    def _resolve_file(self, filename: str):
        candidates = [
            os.path.join(os.getcwd(), filename),
            os.path.join("/ros2_ws/src/sensor_ai", filename),
            os.path.join(os.path.dirname(__file__), filename),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    def _strip_quantization_config(self, obj):
        if isinstance(obj, dict):
            obj.pop("quantization_config", None)
            for k, v in list(obj.items()):
                obj[k] = self._strip_quantization_config(v)
            return obj
        if isinstance(obj, list):
            return [self._strip_quantization_config(v) for v in obj]
        return obj

    def _patch_h5_file(self, src_path: str) -> str:
        tmpdir = tempfile.mkdtemp(prefix="patched_h5_")
        dst_path = os.path.join(tmpdir, "model_patched.h5")
        shutil.copy2(src_path, dst_path)

        with h5py.File(dst_path, "r+") as f:
            if "model_config" not in f.attrs:
                return dst_path

            raw = f.attrs["model_config"]
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")

            cfg = json.loads(raw)
            cfg = self._strip_quantization_config(cfg)
            f.attrs.modify("model_config", json.dumps(cfg))

        return dst_path

    def _load_model_tfkeras(self, path: str):
        custom_objects = {"leaky_relu": tf.nn.leaky_relu}
        try:
            return tf.keras.models.load_model(
                path,
                compile=False,
                custom_objects=custom_objects,
                safe_mode=False,
            )
        except TypeError:
            return tf.keras.models.load_model(
                path,
                compile=False,
                custom_objects=custom_objects,
            )

    def _load_model_compat(self, model_path: str):
        try:
            return self._load_model_tfkeras(model_path)
        except Exception as e:
            msg = str(e)
            if "quantization_config" in msg or "Unrecognized keyword arguments" in msg:
                self.get_logger().warn("⚠ Detecté incompatibilidad por quantization_config. Parcheando modelo...")
                patched_path = self._patch_h5_file(model_path)
                self.get_logger().info(f"Intentando cargar modelo parcheado en: {patched_path}")
                return self._load_model_tfkeras(patched_path)
            raise

    # ---- MISMA lógica de tu read_distance (sin tocar motores) ----
    def read_distance(self):
        self.trig_lines.set_values([1])
        time.sleep(0.00001)
        self.trig_lines.set_values([0])

        timeout = time.time() + 0.02

        while self.echo_lines.get_values()[0] == 0:
            if time.time() > timeout:
                return 999

        start = time.time()

        while self.echo_lines.get_values()[0] == 1:
            if time.time() > timeout:
                return 999

        end = time.time()

        duration = end - start
        return duration * 17150

    def calibrate_distance_with_ai(self, dist_cruda: float) -> float:
        if self.model is None or self.scaler is None:
            return dist_cruda

        self.buffer_historico.append(dist_cruda)

        if len(self.buffer_historico) >= 2:
            media = statistics.mean(self.buffer_historico)
            mediana = statistics.median(self.buffer_historico)
            desviacion = statistics.stdev(self.buffer_historico)
        else:
            media = dist_cruda
            mediana = dist_cruda
            desviacion = 0.0

        datos_entrada = np.array([[dist_cruda, media, desviacion, mediana]], dtype=np.float32)
        datos_escalados = self.scaler.transform(datos_entrada)
        pred = self.model.predict(datos_escalados, verbose=0)
        return float(pred[0][0])

    def sensor_loop(self):
        while rclpy.ok():
            dist_cruda = self.read_distance()
            dist_usa = dist_cruda

            if dist_cruda != 999:
                dist_usa = self.calibrate_distance_with_ai(dist_cruda)

            should_brake = self.forward_active and (dist_usa < DISTANCIA_PELIGRO)

            if should_brake:
                if not self.emergency_stop:
                    print(f"\n⚠ OBSTÁCULO (IA) {dist_usa:.2f}cm | cruda {dist_cruda:.2f}cm - FRENO")
                self.emergency_stop = True
            else:
                self.emergency_stop = False

            msg = Bool()
            msg.data = self.emergency_stop
            self.pub.publish(msg)

            time.sleep(0.05)

    def destroy_node(self):
        try:
            try:
                self.trig_lines.set_values([0])
            except Exception:
                pass
        finally:
            try:
                self.trig_lines.release()
            except Exception:
                pass
            try:
                self.echo_lines.release()
            except Exception:
                pass
            try:
                self.chip.close()
            except Exception:
                pass
            super().destroy_node()


# ================= MAIN =================
def main(args=None):
    rclpy.init(args=args)

    motor = MotorController()
    teleop = TeleopPublisher()
    safety = SafetyUltrasonicNode()

    executor = MultiThreadedExecutor()
    executor.add_node(motor)
    executor.add_node(teleop)
    executor.add_node(safety)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            motor.stop()
        except Exception:
            pass

        for n in (motor, teleop, safety):
            try:
                n.destroy_node()
            except Exception:
                pass

        # ✅ Evita crash por doble shutdown (Q ya llama shutdown)
        try:
            rclpy.shutdown()
        except RuntimeError:
            pass


if __name__ == '__main__':
    main()