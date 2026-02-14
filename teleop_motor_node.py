import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import gpiod
import sys, termios, tty, threading

CHIP = "gpiochip0"
ENA = 18
IN1 = 23
IN2 = 24
ENB = 13
IN3 = 5
IN4 = 6
PINS = [ENA, IN1, IN2, ENB, IN3, IN4]

class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.chip = gpiod.Chip(CHIP)
        self.lines = self.chip.get_lines(PINS)
        self.lines.request(
            consumer="motor_controller",
            type=gpiod.LINE_REQ_DIR_OUT
        )
        self.stop()
        self.create_subscription(Twist, '/cmd_vel', self.cb, 10)

    def stop(self):
        self.lines.set_values([0,0,0,0,0,0])

    def drive(self, left_fwd, right_fwd):
        self.lines.set_values([
            1,
            left_fwd, not left_fwd,
            1,
            right_fwd, not right_fwd
        ])

    def cb(self, msg):
        lin = msg.linear.x
        ang = msg.angular.z

        if lin > 0:
            self.drive(True, True)
        elif lin < 0:
            self.drive(False, False)
        elif ang > 0:
            self.drive(False, True)
        elif ang < 0:
            self.drive(True, False)
        else:
            self.stop()

class Teleop(Node):
    def __init__(self):
        super().__init__('teleop')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        threading.Thread(target=self.loop, daemon=True).start()

    def get_key(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def loop(self):
        while rclpy.ok():
            key = self.get_key().lower()
            msg = Twist()
            if key == 'w': msg.linear.x = 1.0
            elif key == 's': msg.linear.x = -1.0
            elif key == 'a': msg.angular.z = 1.0
            elif key == 'd': msg.angular.z = -1.0
            elif key == 'q': rclpy.shutdown()
            self.pub.publish(msg)

def main():
    rclpy.init()
    mc = MotorController()
    tp = Teleop()
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(mc)
    executor.add_node(tp)
    executor.spin()

if __name__ == '__main__':
    main()
