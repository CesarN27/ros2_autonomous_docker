# =============================================================================
#  LÓGICA DIFUSA DE FRENADO
# =============================================================================
def fuzzy_brake_factor(dist):
    """
    Devuelve un factor de velocidad [0.0 – 1.0] según la distancia al obstáculo.

    Zonas difusas:
      >= 100 cm  -> 1.0  (muy lejos, velocidad plena)
       60–99 cm  -> 0.8  (lejos, leve reducción)
       35–59 cm  -> 0.6  (cerca, reducción moderada)
       20–34 cm  -> 0.3  (bastante cerca, freno significativo)
       10–19 cm  -> 0.1  (muy cerca, casi detenido)
        < 10 cm  -> 0.0  (STOP total)
    """
    if dist >= 100:
        return 1.0
    elif 60 <= dist < 100:
        return 0.8
    elif 35 <= dist < 60:
        return 0.6
    elif 20 <= dist < 35:
        return 0.3
    elif 10 <= dist < 20:
        return 0.1
    else:
        return 0.0