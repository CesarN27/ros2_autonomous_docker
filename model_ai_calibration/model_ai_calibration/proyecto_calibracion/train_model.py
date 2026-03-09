import os
import random
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

# Semilla para reproducibilidad
semilla = 122705
os.environ['PYTHONHASHSEED'] = str(semilla)
random.seed(semilla)
np.random.seed(semilla)
tf.random.set_seed(semilla)

print("Cargando dataset...")
df = pd.read_csv('data_set_calibracion.csv')
df = df.dropna()

X = df[['dist_sensor_cm', 'media', 'desviacion_estandar', 'mediana']]
y = df['dist_real_cm']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=semilla
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

joblib.dump(scaler, "scaler.pkl")
print("Scaler guardado como scaler.pkl")

# Modelo con las modificaciones (Dense 32 y Dropouts)
model = Sequential([
    Dense(32, activation='leaky_relu', input_shape=(X_train_scaled.shape[1],)),
    Dropout(0.2),
    Dense(16, activation='leaky_relu'),
    Dropout(0.2),
    Dense(8, activation='leaky_relu'),
    Dropout(0.2),
    Dense(1, activation='linear')
])

model.compile(
    optimizer='adam',
    loss='mse',
    metrics=['mae', 'mse']
)

model.summary()

early_stop = EarlyStopping(
    monitor='val_loss',
    patience=30,
    restore_best_weights=True
)

print("\nIniciando entrenamiento...")
history = model.fit(
    X_train_scaled,
    y_train,
    epochs=300,
    validation_split=0.2,
    batch_size=32,
    callbacks=[early_stop],
    verbose=1
)

loss, mae, mse = model.evaluate(X_test_scaled, y_test, verbose=0)
y_pred = model.predict(X_test_scaled).flatten()

print("\n--- RESULTADOS FINALES ---")
print(f"MAE en test: {mae:.4f} cm")
print(f"RMSE en test: {np.sqrt(mse):.4f} cm")
print(f"Desviacion estandar de errores: {np.std(y_test - y_pred):.4f} cm")

model.save("modelo_calibracion.keras")
print("Modelo guardado como modelo_calibracion.keras")

plt.figure()
plt.plot(history.history['loss'], label='train_loss')
plt.plot(history.history['val_loss'], label='val_loss')
plt.legend()
plt.title("Curva de entrenamiento")
plt.xlabel("Epoch")
plt.ylabel("Loss (MSE)")
plt.show()