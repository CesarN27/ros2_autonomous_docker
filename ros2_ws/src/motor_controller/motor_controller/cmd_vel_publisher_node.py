import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class CmdVelPublisher(Node):
    def __init__(self):
        super().__init__('cmd_vel_publisher')

        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.timer = self.create_timer(2.0, self.timer_callback)

        self.state = 0
        self.get_logger().info("CmdVel Publisher iniciado")

    def timer_callback(self):
        msg = Twist()

        if self.state == 0:
            msg.linear.x = 0.3
            self.get_logger().info("Adelante")
        elif self.state == 1:
            msg.angular.z = 0.6
            self.get_logger().info("Giro izquierda")
        elif self.state == 2:
            msg.linear.x = -0.3
            self.get_logger().info("Atras")
        else:
            self.get_logger().info("Stop")

        self.pub.publish(msg)
        self.state = (self.state + 1) % 4


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
