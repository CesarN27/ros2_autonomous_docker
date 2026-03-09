import gpiod
import time
import collections
import statistics
import numpy as np
import joblib
import tensorflow as tf
from gpiod.line import Direction, Value

# ==========================================
# 1. CARGAR IA Y NORMALIZADOR
# ==========================================
print("Cargando red neuronal y scaler...")
model = tf.keras.models.load_model("modelo_calibracion.keras")
scaler = joblib.load("scaler.pkl")

# ==========================================
# 2. CONFIGURACIÓN DE PINES (MOTOR + SENSOR)
# ==========================================
CHIP = "/dev/gpiochip0"

TRIG = 16
ECHO = 20

ENA = 18
IN1 = 23
IN2 = 24

ENB = 13
IN3 = 5
IN4 = 6

chip = gpiod.Chip(CHIP)

lines = chip.request_lines(
    consumer="auto_inteligente_ia",
    config={
        TRIG: gpiod.LineSettings(direction=Direction.OUTPUT),
        ECHO: gpiod.LineSettings(direction=Direction.INPUT),
        ENA: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN1: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN2: gpiod.LineSettings(direction=Direction.OUTPUT),
        ENB: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN3: gpiod.LineSettings(direction=Direction.OUTPUT),
        IN4: gpiod.LineSettings(direction=Direction.OUTPUT),
    }
)

# ==========================================
# 3. FUNCIONES DE HARDWARE
# ==========================================
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

def mover_adelante():
    lines.set_value(IN1, Value.ACTIVE)
    lines.set_value(IN2, Value.INACTIVE)
    lines.set_value(ENA, Value.ACTIVE)
    lines.set_value(IN3, Value.ACTIVE)
    lines.set_value(IN4, Value.INACTIVE)
    lines.set_value(ENB, Value.ACTIVE)

def mover_atras():
    lines.set_value(IN1, Value.INACTIVE)
    lines.set_value(IN2, Value.ACTIVE)
    lines.set_value(ENA, Value.ACTIVE)
    lines.set_value(IN3, Value.INACTIVE)
    lines.set_value(IN4, Value.ACTIVE)
    lines.set_value(ENB, Value.ACTIVE)

# Para girar sobre su propio eje (tipo tanque)
def girar_derecha():
    # Motor A adelante, Motor B atrás
    lines.set_value(IN1, Value.ACTIVE)
    lines.set_value(IN2, Value.INACTIVE)
    lines.set_value(ENA, Value.ACTIVE)
    
    lines.set_value(IN3, Value.INACTIVE)
    lines.set_value(IN4, Value.ACTIVE)
    lines.set_value(ENB, Value.ACTIVE)

def detener():
    lines.set_value(ENA, Value.INACTIVE)
    lines.set_value(ENB, Value.INACTIVE)

# ==========================================
# 4. BUCLE PRINCIPAL (CONTROL + PREDICCIÓN)
# ==========================================
print("\n--- INICIANDO AUTO AUTÓNOMO ---")
print("Presiona Ctrl+C para detener.\n")

buffer_historico = collections.deque(maxlen=5)
intervalo = 0.025 

DISTANCIA_SEGURA = 30.0  
DISTANCIA_PELIGRO = 15.0 

estado_actual = "DETENIDO"
detener() 

print(f"{'Dato Crudo (cm)':<18} | {'IA Corregida (cm)':<18} | {'ACCIÓN':<15}")
print("-" * 55)

try:
    while True:
        t_inicio = time.perf_counter()
        
        dist_cruda = read_distance()
        
        if dist_cruda == 0.0:
            print(f"{'---':<18} | {'---':<18} | ERROR SENSOR")
            detener()
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
        dist_corregida = prediccion[0][0]

        # ----------------------------------------------------
        # LÓGICA DE MOVIMIENTO BASADA EN LA IA
        # ----------------------------------------------------
        accion_tomada = ""
        
        if dist_corregida > DISTANCIA_SEGURA:
            if estado_actual != "ADELANTE":
                mover_adelante()
                estado_actual = "ADELANTE"
            accion_tomada = "-> ADELANTE"
            
        elif dist_corregida < DISTANCIA_PELIGRO:
            print(f"\n¡OBSTÁCULO a {dist_corregida:.2f}cm! Iniciando evasión...")
            
            # 1. Detener el auto un instante
            detener()
            time.sleep(0.1)
            
            # 2. Retroceder (Si realmente quieres que AVANCE, cambia 'mover_atras()' por 'mover_adelante()')
            mover_atras()
            time.sleep(0.5) # Tiempo que el auto estará moviéndose linealmente
            
            # 3. Girar
            girar_derecha()
            time.sleep(0.4) # Tiempo que el auto estará rotando
            
            # 4. Detenerse antes de reanudar el bucle principal
            detener()
            estado_actual = "DETENIDO"
            accion_tomada = "** EVASIÓN **"
            
            # Limpiamos el buffer para que las mediciones viejas no afecten la siguiente lectura de la IA
            buffer_historico.clear()
            print("-" * 55)
            
        else:
            if estado_actual != "DETENIDO":
                detener()
                estado_actual = "DETENIDO"
            accion_tomada = "|| STOP"

        # Mostrar información en consola (solo si no estamos en evasión)
        if accion_tomada != "** EVASIÓN **":
            print(f"{dist_cruda:<18.2f} | {dist_corregida:<18.2f} | {accion_tomada}")

        # Control de 40Hz
        t_libre = intervalo - (time.perf_counter() - t_inicio)
        if t_libre > 0:
            time.sleep(t_libre)

except KeyboardInterrupt:
    print("\nDeteniendo el vehículo por orden del usuario...")

finally:
    detener()
    lines.release()
    print("Motores detenidos y GPIO liberado. Proceso finalizado.")