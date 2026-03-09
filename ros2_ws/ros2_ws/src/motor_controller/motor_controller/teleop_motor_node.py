import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import gpiod
import sys
import termios
import tty
import threading

CHIP = "gpiochip0"

# -------- Motor A (Izquierdo) --------
ENA = 18
IN1 = 23
IN2 = 24

# -------- Motor B (Derecho) ----------
ENB = 13
IN3 = 5
IN4 = 6

PINS = [ENA, IN1, IN2, ENB, IN3, IN4]

# =====================================
# MOTOR CONTROLLER (SUBSCRIBER)
# =====================================
class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.get_logger().info("Motor Controller iniciado (WASD + mezcla correcta)")

        self.chip = gpiod.Chip(CHIP)
        self.lines = self.chip.get_lines(PINS)
        self.lines.request(
            consumer="motor_controller",
            type=gpiod.LINE_REQ_DIR_OUT
        )

        self.stop()

        self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_callback,
            10
        )

    # --------- Helpers por motor ----------
    def motor_a(self, forward: bool):
        self.lines.set_values([
            1,                    # ENA
            1 if forward else 0,  # IN1
            0 if forward else 1,  # IN2
            self.lines.get_values()[3],
            self.lines.get_values()[4],
            self.lines.get_values()[5],
        ])

    def motor_b(self, forward: bool):
        self.lines.set_values([
            self.lines.get_values()[0],
            self.lines.get_values()[1],
            self.lines.get_values()[2],
            1,                    # ENB
            1 if forward else 0,  # IN3
            0 if forward else 1,  # IN4
        ])

    def stop(self):
        self.lines.set_values([0, 0, 0, 0, 0, 0])

    # --------- Lógica correcta ----------
    def cmd_callback(self, msg):
        lin = msg.linear.x     # adelante / atrás
        ang = msg.angular.z   # giro

        if lin == 0 and ang == 0:
            self.stop()
            return

        # Mezcla tipo diferencial
        left = lin - ang
        right = lin + ang

        # Motor A (izquierdo)
        if left > 0:
            self.motor_a(True)
        elif left < 0:
            self.motor_a(False)
        else:
            self.lines.set_values([0, 0, 0,
                                   self.lines.get_values()[3],
                                   self.lines.get_values()[4],
                                   self.lines.get_values()[5]])

        # Motor B (derecho)
        if right > 0:
            self.motor_b(True)
        elif right < 0:
            self.motor_b(False)
        else:
            self.lines.set_values([
                self.lines.get_values()[0],
                self.lines.get_values()[1],
                self.lines.get_values()[2],
                0, 0, 0
            ])

# =====================================
# TELEOP (PUBLISHER)
# =====================================
class TeleopPublisher(Node):
    def __init__(self):
        super().__init__('teleop_publisher')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info(
            "\nW/S → Adelante / Atrás\n"
            "A/D → Girar\n"
            "Combinable: WA WD SA SD\n"
            "Q → Salir\n"
        )

        self.linear = 0.0
        self.angular = 0.0

        thread = threading.Thread(target=self.keyboard_loop, daemon=True)
        thread.start()

    def get_key(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def keyboard_loop(self):
        while rclpy.ok():
            key = self.get_key().lower()

            if key == 'w':
                self.linear = 1.0
            elif key == 's':
                self.linear = -1.0
            elif key == 'a':
                self.angular = 1.0
            elif key == 'd':
                self.angular = -1.0
            elif key == 'q':
                rclpy.shutdown()
                break
            else:
                self.linear = 0.0
                self.angular = 0.0

            msg = Twist()
            msg.linear.x = self.linear
            msg.angular.z = self.angular
            self.pub.publish(msg)

# =====================================
# MAIN
# =====================================
def main(args=None):
    rclpy.init(args=args)

    motor = MotorController()
    teleop = TeleopPublisher()

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(motor)
    executor.add_node(teleop)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        motor.stop()
        motor.destroy_node()
        teleop.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
