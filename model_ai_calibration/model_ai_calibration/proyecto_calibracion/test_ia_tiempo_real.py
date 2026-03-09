import gpiod
import time
import collections
import statistics
import numpy as np
import joblib
import tensorflow as tf
import csv
import os
import warnings
from gpiod.line import Direction, Value

# Ocultar advertencias
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
warnings.filterwarnings("ignore", category=UserWarning)

# ==========================================
# 1. CARGAR IA Y NORMALIZADOR
# ==========================================
print("Cargando red neuronal y scaler...")
model = tf.keras.models.load_model("modelo_calibracion.keras")
scaler = joblib.load("scaler.pkl")

# ==========================================
# 2. CONFIGURACIÓN DEL SENSOR Y HARDWARE
# ==========================================
CHIP = "/dev/gpiochip0"
TRIG = 16
ECHO = 20

chip = gpiod.Chip(CHIP)
lines = chip.request_lines(
    consumer="ultrasonic_ia",
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

# ==========================================
# 3. BUCLE PRINCIPAL (TIEMPO REAL + MUESTRAS)
# ==========================================
archivo_csv = "datos_prueba_ia.csv"
datos_para_csv = []
id_dato = 0

# Solicitar número de muestras
total_muestras = int(input("\n¿Cuántas muestras deseas tomar?: "))

print(f"\n--- INICIANDO LECTURA DE {total_muestras} MUESTRAS ---")
print("Presiona Ctrl+C para detener y guardar el CSV.\n")

buffer_historico = collections.deque(maxlen=5)
intervalo = 0.025 # 25ms = 40Hz

# Encabezado de consola ajustado con Diferencia
print(f"{'ID':<6} | {'Timestamp':<12} | {'Real (cm)':<12} | {'Corregida (cm)':<15} | {'Diferencia (cm)'}")
print("-" * 70)

try:
    while id_dato < total_muestras:
        t_inicio = time.perf_counter()
        
        dist_cruda = read_distance()
        timestamp = round(time.time(), 3) # Timestamp con 3 decimales
        
        if dist_cruda == 0.0:
            print(f"{'---':<6} | {'---':<12} | {'---':<12} | {'---':<15} | {'---'}")
            continue

        buffer_historico.append(dist_cruda)

        if len(buffer_historico) >= 2:
            media = statistics.mean(buffer_historico)
            mediana = statistics.median(buffer_historico)
            desviacion = statistics.stdev(buffer_historico)
        else:
            media = dist_cruda
            mediana = dist_cruda
            desviacion = 0.0

        datos_entrada = np.array([[dist_cruda, media, desviacion, mediana]])
        datos_escalados = scaler.transform(datos_entrada)

        prediccion = model.predict(datos_escalados, verbose=0)
        dist_corregida = round(float(prediccion[0][0]), 2)
        
        id_dato += 1
        
        # Calcular la diferencia absoluta
        diferencia = round(abs(dist_cruda - dist_corregida), 2)
        
        # Guardar datos solicitados en el CSV
        datos_para_csv.append([id_dato, timestamp, dist_cruda, dist_corregida, diferencia])

        # Mostrar en consola
        print(f"{id_dato:<6} | {timestamp:<12} | {dist_cruda:<12.2f} | {dist_corregida:<15.2f} | {diferencia:<12.2f}")

        t_libre = intervalo - (time.perf_counter() - t_inicio)
        if t_libre > 0:
            time.sleep(t_libre)

except KeyboardInterrupt:
    print("\nLectura detenida por el usuario.")

finally:
    # ==========================================
    # 4. GUARDADO EN CSV AL FINALIZAR
    # ==========================================
    if datos_para_csv:
        print(f"\nGuardando {len(datos_para_csv)} registros en {archivo_csv}...")
        archivo_vacio = not os.path.exists(archivo_csv) or os.path.getsize(archivo_csv) == 0
        with open(archivo_csv, mode='a', newline='') as file:
            writer = csv.writer(file)
            if archivo_vacio:
                writer.writerow(["id_dato", "timestamp", "distancia_real", "distancia_corregida", "diferencia"])
            writer.writerows(datos_para_csv)
        print("CSV guardado correctamente.")

    lines.release()
    chip.close()
    print("GPIO liberado. Proceso finalizado.")