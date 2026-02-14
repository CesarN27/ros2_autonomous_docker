import gpiod
import time
from gpiod.line import Direction, Value

CHIP = "/dev/gpiochip0"

# -------- Motor A --------
ENA = 18
IN1 = 23
IN2 = 24

# -------- Motor B --------
ENB = 13
IN3 = 5
IN4 = 6

chip = gpiod.Chip(CHIP)

lines = chip.request_lines(
    consumer="motor_test_dual",
    config={
        ENA: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN1: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN2: gpiod.LineSettings(direction=Direction.OUTPUT),
        ENB: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN3: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN4: gpiod.LineSettings(direction=Direction.OUTPUT),
    }
)

try:
    print("ADELANTE")
    lines.set_value(IN1, Value.ACTIVE)
    lines.set_value(IN2, Value.INACTIVE)
    lines.set_value(IN3, Value.ACTIVE)
    lines.set_value(IN4, Value.INACTIVE)
    lines.set_value(ENA, Value.ACTIVE)
    lines.set_value(ENB, Value.ACTIVE)
    time.sleep(3)

    print("ATRÁS")
    lines.set_value(IN1, Value.INACTIVE)
    lines.set_value(IN2, Value.ACTIVE)
    lines.set_value(IN3, Value.INACTIVE)
    lines.set_value(IN4, Value.ACTIVE)
    time.sleep(3)

    print("STOP")
    lines.set_value(ENA, Value.INACTIVE)
    lines.set_value(ENB, Value.INACTIVE)

finally:
    lines.release()
