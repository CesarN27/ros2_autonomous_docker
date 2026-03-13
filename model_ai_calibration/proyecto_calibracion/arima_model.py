"""
=============================================================================
 HC-SR04 Sensor Calibration — Dual Model Training
 Neural Network (Keras .h5) + ARIMAX (.pkl)
=============================================================================
"""

import os, random, warnings, pickle
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from sklearn.preprocessing import RobustScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.regularizers import l2

from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import acf, pacf

warnings.filterwarnings("ignore")

# ── Reproducibilidad ──────────────────────────────────────────────────────────
SEED = 122705
os.environ["PYTHONHASHSEED"] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

OUTPUT_DIR = "/content/resultados"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 65)
print(" 1. CARGA Y LIMPIEZA DE DATOS")
print("=" * 65)

df = pd.read_csv("./HC-SR04 Data.csv")
df = df.sort_values("timestamp").reset_index(drop=True)

print(f"   Filas totales: {len(df):,}")
print(f"   Distancias reales únicas (cm): {sorted(df['dist_real_cm'].unique())}")
print(f"   Rango sensor: [{df['dist_sensor_cm'].min():.2f}, {df['dist_sensor_cm'].max():.2f}] cm")

# Eliminar lecturas físicamente imposibles del HC-SR04 (max ~400 cm, min ~2 cm)
# y outliers severos (>2.5 IQR por distancia real)
df = df[(df["dist_sensor_cm"] >= 1.0) & (df["dist_sensor_cm"] <= 60.0)].copy()

# Outlier removal por grupo de distancia real (usando transform para preservar columnas)
Q1  = df.groupby("dist_real_cm")["dist_sensor_cm"].transform("quantile", 0.25)
Q3  = df.groupby("dist_real_cm")["dist_sensor_cm"].transform("quantile", 0.75)
IQR = Q3 - Q1
df  = df[(df["dist_sensor_cm"] >= Q1 - 2.5 * IQR) &
         (df["dist_sensor_cm"] <= Q3 + 2.5 * IQR)].copy()
df = df.sort_values("timestamp").reset_index(drop=True)
print(f"   Filas tras limpieza: {len(df):,}")

# ── Feature Engineering ───────────────────────────────────────────────────────
print("\n" + "=" * 65)
print(" 2. FEATURE ENGINEERING")
print("=" * 65)

W = 7  # ventana rolling

df["roll_mean"]   = df["dist_sensor_cm"].rolling(W, min_periods=1).mean()
df["roll_median"] = df["dist_sensor_cm"].rolling(W, min_periods=1).median()
df["roll_std"]    = df["dist_sensor_cm"].rolling(W, min_periods=1).std().fillna(0)
df["roll_min"]    = df["dist_sensor_cm"].rolling(W, min_periods=1).min()
df["roll_max"]    = df["dist_sensor_cm"].rolling(W, min_periods=1).max()
df["roll_range"]  = df["roll_max"] - df["roll_min"]          # amplitud local
df["lag1"]        = df["dist_sensor_cm"].shift(1).fillna(df["dist_sensor_cm"])
df["lag2"]        = df["dist_sensor_cm"].shift(2).fillna(df["dist_sensor_cm"])
df["delta"]       = df["dist_sensor_cm"].diff().fillna(0)     # tasa de cambio

FEATURES = [
    "dist_sensor_cm",
    "roll_mean", "roll_median", "roll_std",
    "roll_min", "roll_max", "roll_range",
    "lag1", "lag2", "delta",
]
TARGET = "dist_real_cm"

print(f"   Features usadas ({len(FEATURES)}): {FEATURES}")

# ── Train / Test Split ────────────────────────────────────────────────────────
split = int(len(df) * 0.80)
train_df = df.iloc[:split]
test_df  = df.iloc[split:]

X_train = train_df[FEATURES].values
X_test  = test_df[FEATURES].values
y_train = train_df[TARGET].values
y_test  = test_df[TARGET].values

print(f"\n   Train: {len(X_train):,} muestras  |  Test: {len(X_test):,} muestras")

# RobustScaler: más resistente a outliers que StandardScaler
scaler = RobustScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)

joblib.dump(scaler, f"{OUTPUT_DIR}/scaler.pkl")
print("   ✔ scaler.pkl guardado")

# ═══════════════════════════════════════════════════════════════════════════════
#  MODELO 1: RED NEURONAL (Keras)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print(" 3. ENTRENAMIENTO — RED NEURONAL (Keras)")
print("=" * 65)

model = Sequential([
    Input(shape=(X_train_sc.shape[1],)),

    # Bloque 1
    Dense(128, activation="swish", kernel_regularizer=l2(1e-4)),
    BatchNormalization(),
    Dropout(0.2),

    # Bloque 2
    Dense(64, activation="swish", kernel_regularizer=l2(1e-4)),
    BatchNormalization(),
    Dropout(0.15),

    # Bloque 3
    Dense(32, activation="swish"),
    BatchNormalization(),

    # Bloque 4
    Dense(16, activation="swish"),

    # Salida lineal → regresión continua
    Dense(1, activation="linear"),
])

model.compile(
    optimizer=tf.keras.optimizers.AdamW(learning_rate=1e-3, weight_decay=1e-5),
    loss="huber",          # más robusto que MSE ante outliers residuales
    metrics=["mae"],
)

model.summary()

callbacks = [
    EarlyStopping(monitor="val_loss", patience=40,
                  restore_best_weights=True, verbose=1),
    ReduceLROnPlateau(monitor="val_loss", factor=0.4,
                      patience=15, min_lr=1e-7, verbose=1),
]

history = model.fit(
    X_train_sc, y_train,
    epochs=600,
    batch_size=64,
    validation_split=0.15,
    callbacks=callbacks,
    verbose=1,
)

model.save(f"{OUTPUT_DIR}/modelo_calibracion.h5")
print("   ✔ modelo_calibracion.h5 guardado")

y_pred_nn = model.predict(X_test_sc, verbose=0).flatten()

mae_nn  = mean_absolute_error(y_test, y_pred_nn)
rmse_nn = np.sqrt(mean_squared_error(y_test, y_pred_nn))
r2_nn   = r2_score(y_test, y_pred_nn)
print(f"\n   [NN]  MAE={mae_nn:.4f} cm  RMSE={rmse_nn:.4f} cm  R²={r2_nn:.5f}")

# ═══════════════════════════════════════════════════════════════════════════════
#  MODELO 2: ARIMAX  (ARIMA con variable exógena = dist_sensor_cm)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print(" 4. ENTRENAMIENTO — ARIMAX(1,0,1)")
print("=" * 65)

# Usamos solo dist_sensor_cm como exógena (parsimonia → ARIMAX es rápido)
exog_train = train_df[["dist_sensor_cm"]].values
exog_test  = test_df[["dist_sensor_cm"]].values

print("   Ajustando ARIMAX(1,0,1) …")
arima_model = ARIMA(
    endog=y_train,
    exog=exog_train,
    order=(1, 0, 1),       # p=1, d=0 (serie estacionaria), q=1
)
arima_result = arima_model.fit(method_kwargs={"warn_convergence": False})
print(arima_result.summary())

with open(f"{OUTPUT_DIR}/modelo_calibracion_arima.pkl", "wb") as f:
    pickle.dump(arima_result, f)
print("   ✔ modelo_calibracion_arima.pkl guardado")

y_pred_arima = arima_result.forecast(steps=len(y_test), exog=exog_test)

mae_ar  = mean_absolute_error(y_test, y_pred_arima)
rmse_ar = np.sqrt(mean_squared_error(y_test, y_pred_arima))
r2_ar   = r2_score(y_test, y_pred_arima)
print(f"\n   [ARIMAX]  MAE={mae_ar:.4f} cm  RMSE={rmse_ar:.4f} cm  R²={r2_ar:.5f}")

# ═══════════════════════════════════════════════════════════════════════════════
#  GRÁFICAS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print(" 5. GENERANDO GRÁFICAS")
print("=" * 65)

STYLE = {
    "real":   {"color": "#2ecc71", "lw": 2.0,  "label": "Distancia Real"},
    "nn":     {"color": "#3498db", "lw": 1.8,  "label": "Red Neuronal (Keras)"},
    "arima":  {"color": "#e74c3c", "lw": 1.8,  "label": "ARIMAX(1,0,1)"},
    "raw":    {"color": "#95a5a6", "lw": 1.2,  "alpha": 0.6, "label": "Sensor Crudo"},
}

fig = plt.figure(figsize=(18, 22))
fig.patch.set_facecolor("#0f1117")
gs = gridspec.GridSpec(4, 2, figure=fig, hspace=0.45, wspace=0.35)

ax_color = "#1c1f26"

def style_ax(ax, title):
    ax.set_facecolor(ax_color)
    ax.set_title(title, color="white", fontsize=12, fontweight="bold", pad=8)
    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.legend(facecolor="#2a2d35", edgecolor="#555", labelcolor="white", fontsize=9)
    ax.grid(True, alpha=0.15, color="white")

# ── Gráfica 1: Curva de entrenamiento ────────────────────────────────────────
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(history.history["loss"],     color="#3498db", lw=1.5, label="Train Loss (Huber)")
ax1.plot(history.history["val_loss"], color="#e67e22", lw=1.5, label="Val Loss (Huber)", ls="--")
ax1.set_yscale("log")
ax1.set_xlabel("Épocas")
ax1.set_ylabel("Huber Loss (log)")
stopped = len(history.history["loss"])
ax1.axvline(stopped - 1, color="#9b59b6", ls=":", lw=1.2, label=f"Early stop @ época {stopped}")
style_ax(ax1, "📉  Curva de Entrenamiento — Red Neuronal")

# ── Gráfica 2: Comparativa de modelos (ventana 300 pts) ──────────────────────
V = 300
ax2 = fig.add_subplot(gs[1, :])
ax2.plot(y_test[:V],            **STYLE["real"])
ax2.plot(y_pred_nn[:V],         **STYLE["nn"],    ls="-.")
ax2.plot(y_pred_arima[:V],      **STYLE["arima"],  ls="--")
ax2.plot(test_df["dist_sensor_cm"].values[:V], **STYLE["raw"])
ax2.set_xlabel("Muestras")
ax2.set_ylabel("Distancia (cm)")
style_ax(ax2, f"🔍  Comparativa de Modelos — Primeros {V} puntos del Test")

# ── Gráfica 3: Distribución del error (NN) ───────────────────────────────────
ax3 = fig.add_subplot(gs[2, 0])
err_nn = y_pred_nn - y_test
ax3.hist(err_nn, bins=80, color="#3498db", alpha=0.8, edgecolor="none")
ax3.axvline(err_nn.mean(), color="#f1c40f", lw=1.5, ls="--",
            label=f"μ={err_nn.mean():.3f} cm")
ax3.axvline(0, color="white", lw=0.8, alpha=0.5)
ax3.set_xlabel("Error (predicho − real) [cm]")
ax3.set_ylabel("Frecuencia")
style_ax(ax3, "📊  Distribución Error — Red Neuronal")

# ── Gráfica 4: Distribución del error (ARIMAX) ───────────────────────────────
ax4 = fig.add_subplot(gs[2, 1])
err_ar = y_pred_arima - y_test
ax4.hist(err_ar, bins=80, color="#e74c3c", alpha=0.8, edgecolor="none")
ax4.axvline(err_ar.mean(), color="#f1c40f", lw=1.5, ls="--",
            label=f"μ={err_ar.mean():.3f} cm")
ax4.axvline(0, color="white", lw=0.8, alpha=0.5)
ax4.set_xlabel("Error (predicho − real) [cm]")
ax4.set_ylabel("Frecuencia")
style_ax(ax4, "📊  Distribución Error — ARIMAX")

# ── Gráfica 5: Scatter Real vs Predicho (NN) ─────────────────────────────────
ax5 = fig.add_subplot(gs[3, 0])
ax5.scatter(y_test, y_pred_nn, s=2, alpha=0.3, color="#3498db")
lims = [y_test.min() - 1, y_test.max() + 1]
ax5.plot(lims, lims, "w--", lw=1, label="Predicción perfecta")
ax5.set_xlabel("Real (cm)")
ax5.set_ylabel("Predicho (cm)")
ax5.text(0.05, 0.92, f"R²={r2_nn:.4f}  MAE={mae_nn:.3f}",
         transform=ax5.transAxes, color="#2ecc71", fontsize=10)
style_ax(ax5, "🎯  Scatter: Real vs Predicho — Red Neuronal")

# ── Gráfica 6: Scatter Real vs Predicho (ARIMAX) ─────────────────────────────
ax6 = fig.add_subplot(gs[3, 1])
ax6.scatter(y_test, y_pred_arima, s=2, alpha=0.3, color="#e74c3c")
ax6.plot(lims, lims, "w--", lw=1, label="Predicción perfecta")
ax6.set_xlabel("Real (cm)")
ax6.set_ylabel("Predicho (cm)")
ax6.text(0.05, 0.92, f"R²={r2_ar:.4f}  MAE={mae_ar:.3f}",
         transform=ax6.transAxes, color="#2ecc71", fontsize=10)
style_ax(ax6, "🎯  Scatter: Real vs Predicho — ARIMAX")

plt.suptitle("HC-SR04 Sensor Calibration — Resultados de Entrenamiento",
             color="white", fontsize=15, fontweight="bold", y=1.01)

plt.savefig(f"{OUTPUT_DIR}/resultados_entrenamiento.png",
            dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print("   ✔ resultados_entrenamiento.png guardado")

# ─── Resumen final ────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print(" RESUMEN FINAL")
print("=" * 65)
print(f"{'Modelo':<15} {'MAE (cm)':<12} {'RMSE (cm)':<12} {'R²':<10}")
print("-" * 50)
print(f"{'Red Neuronal':<15} {mae_nn:<12.4f} {rmse_nn:<12.4f} {r2_nn:<10.5f}")
print(f"{'ARIMAX(1,0,1)':<15} {mae_ar:<12.4f} {rmse_ar:<12.4f} {r2_ar:<10.5f}")
print("=" * 65)
print("\nArchivos generados:")
print(f"  → {OUTPUT_DIR}/modelo_calibracion.h5")
print(f"  → {OUTPUT_DIR}/modelo_calibracion_arima.pkl")
print(f"  → {OUTPUT_DIR}/scaler.pkl")
print(f"  → {OUTPUT_DIR}/resultados_entrenamiento.png")