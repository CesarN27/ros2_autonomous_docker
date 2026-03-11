import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import gpiod

CHIP = "gpiochip0"

# Motor A
ENA = 18
IN1 = 23
IN2 = 24

# Motor B
ENB = 25
IN3 = 5
IN4 = 6

PINS = [ENA, IN1, IN2, ENB, IN3, IN4]


class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.get_logger().info("Motor Controller iniciado (GPIO REAL – legacy API)")

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
            self.cmd_vel_callback,
            10
        )

    # ---------------- MOVIMIENTOS ----------------
    def stop(self):
        self.lines.set_values([0, 0, 0, 0, 0, 0])

    def forward(self):
        self.lines.set_values([1, 1, 0, 1, 1, 0])

    def backward(self):
        self.lines.set_values([1, 0, 1, 1, 0, 1])

    def left(self):
        self.lines.set_values([1, 0, 1, 1, 1, 0])

    def right(self):
        self.lines.set_values([1, 1, 0, 1, 0, 1])

    # ---------------- CALLBACK ----------------
    def cmd_vel_callback(self, msg):
        lin = msg.linear.x
        ang = msg.angular.z

        self.get_logger().info(
            f"cmd_vel → linear={lin:.2f}, angular={ang:.2f}"
        )

        if lin > 0.05:
            self.forward()
        elif lin < -0.05:
            self.backward()
        elif ang > 0.05:
            self.left()
        elif ang < -0.05:
            self.right()
        else:
            self.stop()


def main(args=None):
    rclpy.init(args=args)
    node = MotorController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

