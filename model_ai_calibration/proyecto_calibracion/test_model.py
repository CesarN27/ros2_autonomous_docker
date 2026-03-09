import numpy as np
import joblib
import tensorflow as tf

# Cargar modelo y scaler
model = tf.keras.models.load_model("modelo_calibracion.h5")
scaler = joblib.load("scaler.pkl")

# Ejemplo de datos nuevos
# (sensor, media, desviacion, mediana)
nuevo_dato = np.array([[10.2, 10.1, 0.15, 10.1]])

# Escalar
nuevo_dato_scaled = scaler.transform(nuevo_dato)

# Predecir
prediccion = model.predict(nuevo_dato_scaled)

print("Distancia corregida:", prediccion[0][0], "cm")