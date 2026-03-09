import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import gpiod
import sys
import select
import termios
import tty
import threading

CHIP = "gpiochip0"

# -------- Pines --------
ENA, IN1, IN2 = 13, 5, 6   # Motor Traccion
ENB, IN3, IN4 = 18, 23, 24 # Motor Direccion
PINS = [ENA, IN1, IN2, ENB, IN3, IN4]

class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.get_logger().info("Motor Controller iniciado. Modo Piloto Automatico.")

        self.chip = gpiod.Chip(CHIP)
        self.lines = self.chip.get_lines(PINS)
        self.lines.request(consumer="motor_controller", type=gpiod.LINE_REQ_DIR_OUT)
        
        self.state = [0, 0, 0, 0, 0, 0]
        self.stop()

        self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)

    def update_pins(self):
        self.lines.set_values(self.state)

    def stop(self):
        self.state = [0, 0, 0, 0, 0, 0]
        self.update_pins()

    def cmd_callback(self, msg):
        lin = msg.linear.x    
        ang = msg.angular.z   

        if lin == 0 and ang == 0:
            self.stop()
            return

        # Logica Motor de Traccion (ENA, IN1, IN2)
        if lin > 0:
            self.state[0:3] = [1, 1, 0] # Adelante
        elif lin < 0:
            self.state[0:3] = [1, 0, 1] # Atras
        else:
            self.state[0:3] = [0, 0, 0] # Freno de traccion

        # Logica Motor de Direccion (ENB, IN3, IN4)
        if ang > 0:
            self.state[3:6] = [1, 0, 1] # Gira a la Izquierda (A)
        elif ang < 0:
            self.state[3:6] = [1, 1, 0] # Gira a la Derecha (D)
        else:
            self.state[3:6] = [0, 0, 0] # Freno/Centro de direccion

        self.update_pins()

class TeleopPublisher(Node):
    def __init__(self):
        super().__init__('teleop_publisher')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.get_logger().info("Controles de Toque:\nW/S: Adelante/Atras\nA/D: Izquierda/Centro/Derecha\nESPACIO: Freno Total\nQ: Salir")
        
        thread = threading.Thread(target=self.keyboard_loop, daemon=True)
        thread.start()

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
        # Mantenemos el estado de la velocidad aqui
        msg = Twist()
        
        while rclpy.ok():
            key = self.get_key(timeout=0.1).lower()

            if key == 'w':
                msg.linear.x = 1.0
            elif key == 's':
                msg.linear.x = -1.0
                
            elif key == 'a':
                # Si esta girando a la derecha (-1.0), primero centra la direccion
                if msg.angular.z == -1.0:
                    msg.angular.z = 0.0
                else:
                    msg.angular.z = 1.0
                    
            elif key == 'd':
                # Si esta girando a la izquierda (1.0), primero centra la direccion
                if msg.angular.z == 1.0:
                    msg.angular.z = 0.0
                else:
                    msg.angular.z = -1.0
                    
            elif key == 'c':
                # Mantenemos la C por si acaso, pero ya no es estrictamente necesaria
                msg.angular.z = 0.0
            elif key == ' ':
                # Barra espaciadora = Freno total de emergencia
                msg.linear.x = 0.0
                msg.angular.z = 0.0
            elif key == 'q':
                rclpy.shutdown()
                break
            
            # Publicamos el estado actual constantemente
            self.pub.publish(msg)

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
