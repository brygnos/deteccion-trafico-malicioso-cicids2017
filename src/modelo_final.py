"""Serialización de los modelos finales que usa el tablero (Fase A del prototipo).

Entrena con todo el conjunto de entrenamiento y guarda en models/:

- modelo_multiclase.joblib: el mejor modelo (HistGradientBoosting + pesos de
  clase, 11 clases). Es el mismo modelo, con los mismos datos, semilla y
  versiones con los que se hizo la evaluación final, así que re-entrenarlo aquí
  reproduce el artefacto de forma determinista sin tocar el conjunto de prueba.
- modelo_binario.joblib: ataque sí/no (mismo algoritmo y pesos).
- detector_anomalias.joblib: un dict con el Isolation Forest entrenado solo con
  el tráfico benigno del lunes, su StandardScaler (ajustado solo con ese
  tráfico) y los umbrales por cuantiles 0,5% / 1% / 2% de sus propios scores.
- metadatos.json: lo que necesita el tablero, es decir, la lista ordenada de
  las 48 características, los nombres de las clases, la versión de
  scikit-learn y la regla de operación de Bot (alarma solo si
  P(Bot) >= 0,999; si no, la segunda clase más probable), que hace parte del
  modelo final oficial.

El script usa checkpoints: si un artefacto ya existe, no lo vuelve a entrenar.
No lee el conjunto de prueba ni recalcula ninguna cifra del proyecto.

Ejecutar desde la raíz del proyecto:
    python -m src.modelo_final
"""

import json
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler

from src.config import (
    ARCHIVO_TRAIN,
    COLUMNA_ETIQUETA,
    ETIQUETA_BENIGNA,
    RAIZ_PROYECTO,
    RANDOM_STATE,
)
from src.etiquetas import etiqueta_binaria, etiqueta_multiclase, mascara_multiclase
from src.evaluacion_final import CUANTILES_UMBRAL_IF, UMBRAL_BOT
from src.features import features_finales

RUTA_MODELOS = RAIZ_PROYECTO / "models"

ARCHIVO_MULTICLASE = RUTA_MODELOS / "modelo_multiclase.joblib"
ARCHIVO_BINARIO = RUTA_MODELOS / "modelo_binario.joblib"
ARCHIVO_DETECTOR = RUTA_MODELOS / "detector_anomalias.joblib"
ARCHIVO_METADATOS = RUTA_MODELOS / "metadatos.json"


def _nuevo_hgb() -> HistGradientBoostingClassifier:
    """La configuración exacta del mejor modelo de la evaluación final."""
    return HistGradientBoostingClassifier(
        max_iter=200, random_state=RANDOM_STATE, class_weight="balanced"
    )


def main() -> None:
    RUTA_MODELOS.mkdir(parents=True, exist_ok=True)
    train = pd.read_parquet(ARCHIVO_TRAIN)
    features = features_finales(train)
    X = train[features].astype(np.float32).values

    # --- Clasificador multiclase (el mejor modelo) ---
    if ARCHIVO_MULTICLASE.exists():
        print("[ya existe] modelo multiclase", flush=True)
        clases_multiclase = joblib.load(ARCHIVO_MULTICLASE).classes_.tolist()
    else:
        t0 = time.time()
        mascara = mascara_multiclase(train[COLUMNA_ETIQUETA]).values
        y_multi = etiqueta_multiclase(train.loc[mascara, COLUMNA_ETIQUETA]).astype(str).values
        modelo = _nuevo_hgb().fit(X[mascara], y_multi)
        joblib.dump(modelo, ARCHIVO_MULTICLASE, compress=3)
        clases_multiclase = modelo.classes_.tolist()
        print(f"[entrenado] multiclase en {time.time() - t0:.0f}s", flush=True)

    # --- Clasificador binario ---
    if ARCHIVO_BINARIO.exists():
        print("[ya existe] modelo binario", flush=True)
    else:
        t0 = time.time()
        y_bin = etiqueta_binaria(train[COLUMNA_ETIQUETA]).values
        joblib.dump(_nuevo_hgb().fit(X, y_bin), ARCHIVO_BINARIO, compress=3)
        print(f"[entrenado] binario en {time.time() - t0:.0f}s", flush=True)

    # --- Detector de anomalías (lunes benigno) ---
    if ARCHIVO_DETECTOR.exists():
        print("[ya existe] detector de anomalías", flush=True)
    else:
        t0 = time.time()
        es_lunes = train["archivo_origen"].astype(str).str.startswith("Monday").values
        assert (train.loc[es_lunes, COLUMNA_ETIQUETA] == ETIQUETA_BENIGNA).all()
        X_lunes = train.loc[es_lunes, features].astype(np.float32).values
        escalador = StandardScaler().fit(X_lunes)
        bosque = IsolationForest(
            n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1
        ).fit(escalador.transform(X_lunes))
        scores_lunes = bosque.score_samples(escalador.transform(X_lunes))
        umbrales = {str(q): float(np.quantile(scores_lunes, q)) for q in CUANTILES_UMBRAL_IF}
        joblib.dump(
            {"escalador": escalador, "bosque": bosque, "umbrales": umbrales},
            ARCHIVO_DETECTOR,
            compress=3,
        )
        print(f"[entrenado] detector en {time.time() - t0:.0f}s | umbrales: {umbrales}", flush=True)

    # --- Metadatos para el tablero ---
    metadatos = {
        "caracteristicas": features,  # lista ordenada: el tablero debe respetar este orden
        "clases_multiclase": clases_multiclase,
        "clases_binario": {"0": "Normal", "1": "Ataque"},
        "umbral_bot": UMBRAL_BOT,
        "regla_bot": (
            "Alarma de Bot solo si P(Bot) >= umbral_bot; si no, se asigna la "
            "segunda clase más probable. Es la regla del modelo final oficial."
        ),
        "cuantiles_detector": [str(q) for q in CUANTILES_UMBRAL_IF],
        "version_sklearn": sklearn.__version__,
        "version_python": "3.13",
        "semilla": RANDOM_STATE,
    }
    ARCHIVO_METADATOS.write_text(
        json.dumps(metadatos, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("[escrito] metadatos.json", flush=True)

    for archivo in [ARCHIVO_MULTICLASE, ARCHIVO_BINARIO, ARCHIVO_DETECTOR, ARCHIVO_METADATOS]:
        mb = archivo.stat().st_size / 1024**2
        aviso = "  <-- SUPERA 50 MB" if mb > 50 else ""
        print(f"  {archivo.name}: {mb:,.1f} MB{aviso}", flush=True)


if __name__ == "__main__":
    main()
