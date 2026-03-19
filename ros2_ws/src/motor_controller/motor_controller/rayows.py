# =============================================================================
#  RAYOWS.PY
# =============================================================================
#  Sistema de control para robot móvil con:
#   1) ROS 2 para comunicación entre nodos
#   2) Control de motores por GPIO usando PWM por software
#   3) Sensor ultrasónico para frenado de emergencia
#   4) Servidor WebSocket para recibir comandos remotos
#   5) Servidor MJPEG para transmitir video de la cámara
#
#  Esquema de control:
#   - Eje Y del joystick -> velocidad / tracción
#   - Eje X del joystick -> dirección
#
#  Mapeo interno del mensaje Twist:
#   - msg.linear.x  -> velocidad
#   - msg.angular.z -> dirección
#
#  Topics ROS usados:
#   - /cmd_vel         : comando de movimiento
#   - /emergency_stop  : frenado de emergencia
#
#  Hilos principales:
#   - Hilo ROS2 executor
#   - Hilo de captura de cámara
#   - Hilo de servidor MJPEG
#   - Hilo de servidor WebSocket
#   - Hilo PWM del controlador de motor
#   - Hilo del sensor ultrasónico
# =============================================================================

import rclpy
from rclpy.executors import MultiThreadedExecutor

from .camera_stream import start_capture_thread
from .mjpeg_server import start_mjpeg_server_thread
from .motor_controller_node import MotorController
from .safety_ultrasonic_node import SafetyUltrasonicNode
from .websocket_bridge import WebSocketBridge


# =============================================================================
#  MAIN
# =============================================================================
def main():
    """
    Punto de entrada principal del sistema.

    Flujo general:
      1) Inicializa ROS2
      2) Crea nodos:
           - MotorController
           - SafetyUltrasonicNode
      3) Lanza hilos auxiliares:
           - captura de cámara
           - servidor MJPEG
           - servidor WebSocket
      4) Ejecuta el MultiThreadedExecutor de ROS2
      5) Al salir, libera recursos de forma segura
    """
    rclpy.init()

    motor = MotorController()
    safety = SafetyUltrasonicNode()

    start_capture_thread()
    start_mjpeg_server_thread()

    ws = WebSocketBridge(motor)
    ws.start()

    executor = MultiThreadedExecutor()
    executor.add_node(motor)
    executor.add_node(safety)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        motor.stop()
        motor.destroy_node()
        safety.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()