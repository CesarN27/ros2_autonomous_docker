import gpiod
import time
import numpy as np
import joblib
import tensorflow as tf
from gpiod.line import Direction, Value

CHIP = "/dev/gpiochip0"
TRIG = 16   # GPIO16
ECHO = 20   # GPIO20

VENTANA = 10        # cantidad de muestras para estadísticos
INTERVALO = 0.025   # 40 Hz

# CARGAR MODELO Y SCALER
print("Cargando modelo y scaler...")
model = tf.keras.models.load_model("modelo_calibracion.keras")
scaler = joblib.load("scaler.pkl")
print("Modelo cargado correctamente.\n")

# CONFIGURAR GPIO
chip = gpiod.Chip(CHIP)
lines = chip.request_lines(
    consumer="ultrasonic_calibrated",
    config={
        TRIG: gpiod.LineSettings(direction=Direction.OUTPUT),
        ECHO: gpiod.LineSettings(direction=Direction.INPUT),
    }
)

# FUNCIÓN DE MEDICIÓN
def read_distance():
    # Pulso de disparo
    lines.set_value(TRIG, Value.ACTIVE)
    time.sleep(0.00001)
    lines.set_value(TRIG, Value.INACTIVE)

    timeout = time.perf_counter() + 0.020

    while lines.get_value(ECHO) == Value.INACTIVE:
        if time.perf_counter() > timeout:
            return None

    pulse_start = time.perf_counter()

    while lines.get_value(ECHO) == Value.ACTIVE:
        if time.perf_counter() > timeout:
            return None

    pulse_end = time.perf_counter()

    duration = pulse_end - pulse_start
    return round(duration * 17150, 2)

# LOOP PRINCIPAL
ventana_datos = []

print("Sistema de calibración en tiempo real iniciado...\n")

try:
    while True:

        t_inicio = time.perf_counter()
        dist = read_distance()

        if dist is not None:
            ventana_datos.append(dist)

        # Cuando se llena la ventana
        if len(ventana_datos) == VENTANA:

            media = np.mean(ventana_datos)
            desviacion = np.std(ventana_datos)
            mediana = np.median(ventana_datos)
            dist_sensor = ventana_datos[-1]

            # Preparar datos para el modelo
            X = np.array([[dist_sensor, media, desviacion, mediana]])
            X_scaled = scaler.transform(X)

            # Predicción
            dist_calibrada = model.predict(X_scaled, verbose=0)[0][0]

            print(
                f"Cruda: {dist_sensor:6.2f} cm | "
                f"Media: {media:6.2f} | "
                f"Calibrada: {dist_calibrada:6.2f} cm"
            )

            ventana_datos.clear()

        # Mantener 40 Hz
        t_libre = INTERVALO - (time.perf_counter() - t_inicio)
        if t_libre > 0:
            time.sleep(t_libre)

except KeyboardInterrupt:
    print("\nSistema detenido por el usuario.")

finally:
    lines.release()
    print("GPIO liberado.")
