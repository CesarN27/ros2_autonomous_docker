import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class HolaPublisher(Node):

    def __init__(self):
        super().__init__('hola_publisher')

        self.publisher_ = self.create_publisher(String, 'hola_topic', 10)
        self.timer = self.create_timer(1.0, self.timer_callback)

        self.count = 1
        self.get_logger().info("Publisher iniciado")

    def timer_callback(self):
        msg = String()
        msg.data = f"Hola mundo: {self.count}"

        self.publisher_.publish(msg)
        self.get_logger().info(f"Enviado: {msg.data}")

        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = HolaPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
