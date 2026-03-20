import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.callbacks import EarlyStopping

print("Cargando dataset...")
df = pd.read_csv('data_set_calibracion.csv')
df = df.dropna()

X = df[['dist_sensor_cm', 'media', 'desviacion_estandar', 'mediana']]
y = df['dist_real_cm']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

joblib.dump(scaler, "scaler.pkl")
print("Scaler guardado como scaler.pkl")

model = Sequential([
    Dense(16, activation='relu', input_shape=(X_train_scaled.shape[1],)),
    Dense(8, activation='relu'),
    Dense(1, activation='linear')
])

model.compile(
    optimizer='adam',
    loss='mse',
    metrics=['mae']
)

model.summary()

early_stop = EarlyStopping(
    monitor='val_loss',
    patience=10,
    restore_best_weights=True
)

print("\nIniciando entrenamiento...")
history = model.fit(
    X_train_scaled,
    y_train,
    epochs=200,
    validation_split=0.2,
    batch_size=32,
    callbacks=[early_stop],
    verbose=1
)

loss, mae = model.evaluate(X_test_scaled, y_test, verbose=0)

print("\n--- RESULTADOS FINALES ---")
print(f"MAE en test: {mae:.4f} cm")

model.save("modelo_calibracion.h5")
print("Modelo guardado como modelo_calibracion.h5")

plt.figure()
plt.plot(history.history['loss'], label='train_loss')
plt.plot(history.history['val_loss'], label='val_loss')
plt.legend()
plt.title("Curva de entrenamiento")
plt.xlabel("Epoch")
plt.ylabel("Loss (MSE)")
plt.show()
