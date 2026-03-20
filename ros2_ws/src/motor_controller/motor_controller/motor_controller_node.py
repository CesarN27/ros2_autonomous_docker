import threading
import time

import gpiod
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool

from .config import CHIP, JOYSTICK_LIMIT, MOTOR_PINS


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

        self.chip = gpiod.Chip(CHIP)
        self.lines = self.chip.get_lines(MOTOR_PINS)
        self.lines.request(consumer="motor", type=gpiod.LINE_REQ_DIR_OUT)

        self.emergency_stop = False

        self.pwm_ena = 0.0
        self.pwm_enb = 0.0

        self.dir_state = [0, 0, 0, 0]

        self._running_pwm = True
        self.pwm_thread = threading.Thread(target=self._pwm_loop, daemon=True)
        self.pwm_thread.start()

        self.fuzzy_factor = 1.0

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.emg_pub = self.create_publisher(Bool, "/emergency_stop", 10)

        self.create_subscription(Twist, "/cmd_vel", self.cmd_callback, 10)
        self.create_subscription(Bool, "/emergency_stop", self.emergency_callback, 10)
        self.create_subscription(Twist, "/fuzzy_cmd", self.fuzzy_callback, 10)

        self.stop()

    def emergency_callback(self, msg):
        """
        Callback del topic /emergency_stop.

        Si el freno está activo, se fuerzan PWM y direcciones a cero.
        """
        self.emergency_stop = msg.data
        if self.emergency_stop:
            self.stop()

    def fuzzy_callback(self, msg):
        """
        Actualiza el factor difuso de velocidad.

        Publicado por SafetyUltrasonicNode en /fuzzy_cmd (linear.x = factor).
        El factor va de 0.0 (STOP) a 1.0 (velocidad plena).
        """
        self.fuzzy_factor = msg.linear.x

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

        y = msg.linear.x
        x = msg.angular.z

        if y == 0.0 and x == 0.0:
            self.stop()
            return

        norm_y = round(y / JOYSTICK_LIMIT, 10)
        norm_x = round(x / JOYSTICK_LIMIT, 10)

        norm_y = max(-1.0, min(1.0, norm_y))
        norm_x = max(-1.0, min(1.0, norm_x))

        base_speed = abs(norm_y)
        self.pwm_ena = round(base_speed * self.fuzzy_factor, 10)

        if norm_y > 0.0:
            in1, in2 = 1, 0
        elif norm_y < 0.0:
            in1, in2 = 0, 1
        else:
            in1, in2 = 0, 0

        self.pwm_enb = round(abs(norm_x), 10)

        if norm_x < 0.0:
            in3, in4 = 1, 0
        elif norm_x > 0.0:
            in3, in4 = 0, 1
        else:
            in3, in4 = 0, 0

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
            p_a = self.pwm_ena
            p_b = self.pwm_enb
            d_st = self.dir_state

            if self.emergency_stop or (p_a == 0.0 and p_b == 0.0):
                self.lines.set_values([0, 0, 0, 0, 0, 0])
                time.sleep(0.02)
                continue

            if p_a == 1.0 and p_b == 1.0:
                self.lines.set_values([1, d_st[0], d_st[1], 1, d_st[2], d_st[3]])
                time.sleep(period)
                continue

            t_a = p_a * period
            t_b = p_b * period

            val_a = 1 if t_a > 0 else 0
            val_b = 1 if t_b > 0 else 0
            self.lines.set_values([val_a, d_st[0], d_st[1], val_b, d_st[2], d_st[3]])

            first_off = min(t_a, t_b)
            if first_off > 0:
                time.sleep(first_off)

            val_a = 1 if t_a > first_off else 0
            val_b = 1 if t_b > first_off else 0
            self.lines.set_values([val_a, d_st[0], d_st[1], val_b, d_st[2], d_st[3]])

            second_off = max(t_a, t_b)
            if second_off > first_off:
                time.sleep(second_off - first_off)

            self.lines.set_values([0, d_st[0], d_st[1], 0, d_st[2], d_st[3]])

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