import asyncio
import json
import threading
import time

import websockets
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

from .config import MOVE_RATE_HZ, WS_HOST, WS_PORT


# =============================================================================
#  WEBSOCKET BRIDGE
# =============================================================================
class WebSocketBridge:
    """
    Puente entre clientes remotos y ROS2 mediante WebSocket.

    Responsabilidades:
      - Aceptar conexiones remotas
      - Interpretar mensajes JSON
      - Convertirlos a publicaciones ROS sobre /cmd_vel o /emergency_stop
      - Limitar frecuencia de envío para no saturar el controlador
    """

    def __init__(self, motor):
        self.motor = motor
        self._last_move = 0
        self._min_dt = 1.0 / MOVE_RATE_HZ

    def publish_move(self, x, y):
        """
        Convierte coordenadas del joystick remoto a un Twist ROS.

        Convención:
          - y -> velocidad   -> linear.x
          - x -> dirección   -> angular.z
        """
        now = time.monotonic()
        if now - self._last_move < self._min_dt:
            return

        msg = Twist()
        msg.linear.x = float(y)
        msg.angular.z = float(x)

        self.motor.cmd_pub.publish(msg)
        self._last_move = now

    async def handler(self, ws):
        """
        Handler por conexión WebSocket.

        Mensajes esperados:
          - {"command": "MOVE", "x": ..., "y": ...}
          - {"command": "EMERGENCY_STOP"}
          - {"command": "RESUME"}
          - {"command": "STOP"}
        """
        try:
            async for raw in ws:
                data = json.loads(raw)
                cmd = data.get("command", "")

                if cmd == "MOVE":
                    self.publish_move(
                        float(data.get("x", 0)),
                        float(data.get("y", 0)),
                    )

                elif cmd == "EMERGENCY_STOP":
                    msg = Bool()
                    msg.data = True
                    self.motor.emg_pub.publish(msg)

                elif cmd == "RESUME":
                    msg = Bool()
                    msg.data = False
                    self.motor.emg_pub.publish(msg)

                elif cmd == "STOP":
                    self.motor.cmd_pub.publish(Twist())

        except Exception:
            pass
        finally:
            self.motor.cmd_pub.publish(Twist())

    async def run(self):
        """
        Inicia el servidor WebSocket y queda a la espera indefinidamente.
        """
        async with websockets.serve(self.handler, WS_HOST, WS_PORT):
            await asyncio.Future()

    def start(self):
        """
        Lanza el servidor WebSocket en un hilo daemon separado.
        """
        threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True).start()