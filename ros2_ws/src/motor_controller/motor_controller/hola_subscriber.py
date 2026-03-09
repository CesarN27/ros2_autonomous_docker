import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class HolaSubscriber(Node):

    def __init__(self):
        super().__init__('hola_subscriber')

        self.subscription = self.create_subscription(
            String,
            '/hola_topic',
            self.listener_callback,
            10
        )

        self.get_logger().info("Subscriber iniciado")

    def listener_callback(self, msg):
        self.get_logger().info(f"Recibido: {msg.data}")


def main(args=None):
    rclpy.init(args=args)
    node = HolaSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
