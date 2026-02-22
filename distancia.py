import os
import gpiod
import time
import csv
from datetime import datetime
from gpiod.line import Direction, Value

CHIP = "/dev/gpiochip0"
TRIG = 16
ECHO = 20
archivo_csv = "calibracion_ultrasonico_40hz.csv"

chip = gpiod.Chip(CHIP)
lines = chip.request_lines(
    consumer="ultrasonic_40hz",
    config={
        TRIG: gpiod.LineSettings(direction=Direction.OUTPUT),
        ECHO: gpiod.LineSettings(direction=Direction.INPUT),
    }
)

def read_distance():
    lines.set_value(TRIG, Value.ACTIVE)
    time.sleep(0.00001)
    lines.set_value(TRIG, Value.INACTIVE)

    timeout = time.perf_counter() + 0.020 

    while lines.get_value(ECHO) == Value.INACTIVE:
        if time.perf_counter() > timeout: return 0.0
    
    pulse_start = time.perf_counter()

    while lines.get_value(ECHO) == Value.ACTIVE:
        if time.perf_counter() > timeout: return 0.0
    
    pulse_end = time.perf_counter()
    
    duration = pulse_end - pulse_start
    return round(duration * 17150, 2)

dist_real = float(input("Distancia REAL (cm): "))
muestras_objetivo = int(input("¿Cuántas muestras a 40Hz?: "))
datos = []

print(f"\n{'N°':<6} | {'Real (cm)':<10} | {'Sensor (cm)':<12} | {'Estado'}")
print("-" * 45)

contador = 0
intervalo = 0.025 # 25ms = 40Hz

try:
    while contador < muestras_objetivo:
        t_inicio = time.perf_counter()
        
        dist = read_distance()
        ts = time.time()
        
        datos.append((ts, dist_real, dist))
        
        status = "OK" if dist else "TIMEOUT"
        val = dist if dist else "---"
        print(f"{contador+1:<6} | {dist_real:<10} | {val:<12} | {status}")
        
        contador += 1

        t_libre = intervalo - (time.perf_counter() - t_inicio)
        if t_libre > 0:
            time.sleep(t_libre)

except KeyboardInterrupt:
    print("\nCaptura terminada por el usuario.")

if datos:
    print(f"\nGuardando en {archivo_csv}...")
    archivo_vacio = not os.path.exists(archivo_csv) or os.path.getsize(archivo_csv) == 0
    with open(archivo_csv, mode='a', newline='') as file:
        writer = csv.writer(file)
        if archivo_vacio:
            writer.writerow(["timestamp", "dist_real_cm", "dist_sensor_cm"])
            
        writer.writerows(datos)

lines.release()
print("Proceso finalizado y datos añadidos.")
