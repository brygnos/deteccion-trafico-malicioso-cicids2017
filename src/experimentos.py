"""Experimentos de desbalance (Fase 3, pregunta 2: tipo de ataque).

Matriz de 2 x 4 combinaciones:

- Eje A (capacidad del modelo): regresión logística (lineal, con escalado) y
  HistGradientBoostingClassifier (árboles con boosting, no necesita escalado).
- Eje B (técnica de desbalance): sin corrección, pesos de clase balanceados,
  SMOTE en las clases minoritarias, y submuestreo de BENIGN + SMOTE.

Reglas metodológicas:
- Solo se usa el conjunto de entrenamiento (el test sigue apartado).
- Validación cruzada estratificada de 5 particiones (con la misma semilla de
  las líneas base) y las mismas 48 features.
- Todo el remuestreo va dentro del imblearn.Pipeline, así que se aplica
  únicamente al tramo de entrenamiento de cada partición y nunca al de
  validación.

Elecciones de remuestreo:
- SMOTE eleva cada clase con menos de 20.000 casos hasta 20.000 (crea ejemplos
  sintéticos interpolando entre vecinos). No se iguala todo a BENIGN (1,3M)
  porque eso sería fabricar ~14M de filas sintéticas, algo intratable y sin
  sustento.
- El submuestreo reduce BENIGN a 200.000 casos antes de SMOTE, para que el
  modelo no quede dominado por el tráfico normal y el conjunto sea manejable.

Cada combinación se evalúa partición por partición (para reportar la media y
la desviación) y su resultado se guarda en data/interim/fase3/. Así el script
se puede reanudar, porque las combinaciones que ya se calcularon no se repiten.

Ejecutar desde la raíz del proyecto:
    python -m src.experimentos
"""

import time
from collections import Counter

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from imblearn.under_sampling import RandomUnderSampler
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from src.config import (
    ARCHIVO_TRAIN,
    COLUMNA_ETIQUETA,
    ETIQUETA_BENIGNA,
    RANDOM_STATE,
    RUTA_INTERIM,
)
from src.etiquetas import etiqueta_multiclase, mascara_multiclase
from src.features import features_finales

RUTA_RESULTADOS = RUTA_INTERIM / "fase3"

OBJETIVO_SMOTE = 20_000  # tamaño al que se elevan las clases minoritarias
OBJETIVO_BENIGN = 200_000  # tamaño al que se reduce BENIGN en el submuestreo

MODELOS = ["reglog", "arboles"]
TECNICAS = ["sin_correccion", "pesos", "smote", "submuestreo_smote"]


def estrategia_smote(y) -> dict:
    """Eleva a OBJETIVO_SMOTE las clases del fold con menos casos que eso."""
    conteo = Counter(y)
    return {clase: OBJETIVO_SMOTE for clase, n in conteo.items() if n < OBJETIVO_SMOTE}


def estrategia_submuestreo(y) -> dict:
    """Reduce BENIGN a OBJETIVO_BENIGN casos (las demás clases no se tocan)."""
    conteo = Counter(y)
    return {ETIQUETA_BENIGNA: min(OBJETIVO_BENIGN, conteo[ETIQUETA_BENIGNA])}


def construir_pipeline(modelo: str, tecnica: str) -> Pipeline:
    """Arma el imblearn.Pipeline de una combinación de la matriz."""
    peso = "balanced" if tecnica == "pesos" else None
    if modelo == "reglog":
        estimador = LogisticRegression(
            max_iter=1000, random_state=RANDOM_STATE, class_weight=peso
        )
        pasos = [("escalado", StandardScaler())]
    elif modelo == "arboles":
        estimador = HistGradientBoostingClassifier(
            max_iter=200, random_state=RANDOM_STATE, class_weight=peso
        )
        pasos = []
    else:
        raise ValueError(f"modelo desconocido: {modelo}")

    if tecnica in ("smote", "submuestreo_smote"):
        if tecnica == "submuestreo_smote":
            pasos.append(
                ("submuestreo", RandomUnderSampler(
                    sampling_strategy=estrategia_submuestreo, random_state=RANDOM_STATE
                ))
            )
        pasos.append(
            ("smote", SMOTE(sampling_strategy=estrategia_smote, random_state=RANDOM_STATE))
        )
    elif tecnica not in ("sin_correccion", "pesos"):
        raise ValueError(f"técnica desconocida: {tecnica}")

    pasos.append(("modelo", estimador))
    return Pipeline(pasos)


def evaluar_combinacion(modelo: str, tecnica: str, X, y) -> dict:
    """Evalúa una combinación con validación cruzada estratificada de 5 particiones.

    Devuelve las métricas de cada partición (para la media ± desviación) y
    las predicciones y probabilidades out-of-fold (para las matrices de
    confusión y las curvas PR agregadas).
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    clases = np.unique(y)

    f1_folds, tiempos = [], []
    recall_folds, precision_folds, ap_folds = [], [], []
    oof_pred = np.empty(len(y), dtype=np.int8)
    oof_proba = np.empty((len(y), len(clases)), dtype=np.float16)

    for k, (idx_tr, idx_va) in enumerate(cv.split(X, y), 1):
        t0 = time.time()
        pipe = construir_pipeline(modelo, tecnica)
        pipe.fit(X[idx_tr], y[idx_tr])
        assert np.array_equal(pipe.classes_, clases)

        proba = pipe.predict_proba(X[idx_va])
        pred = clases[np.argmax(proba, axis=1)]
        y_va = y[idx_va]

        f1_folds.append(f1_score(y_va, pred, average="macro"))
        recall_folds.append(recall_score(y_va, pred, labels=clases, average=None))
        precision_folds.append(
            precision_score(y_va, pred, labels=clases, average=None, zero_division=0)
        )
        ap_folds.append(
            [average_precision_score((y_va == c).astype(int), proba[:, i])
             for i, c in enumerate(clases)]
        )
        oof_pred[idx_va] = np.searchsorted(clases, pred).astype(np.int8)
        oof_proba[idx_va] = proba.astype(np.float16)

        tiempos.append(time.time() - t0)
        print(f"    fold {k}/5: macro-F1={f1_folds[-1]:.3f} ({tiempos[-1]:.0f}s)", flush=True)

    return {
        "modelo": modelo,
        "tecnica": tecnica,
        "clases": clases.tolist(),
        "f1_macro_folds": np.array(f1_folds),
        "recall_folds": pd.DataFrame(recall_folds, columns=clases),
        "precision_folds": pd.DataFrame(precision_folds, columns=clases),
        "ap_folds": pd.DataFrame(ap_folds, columns=clases),
        "oof_pred": oof_pred,
        "oof_proba": oof_proba,
        "tiempos": tiempos,
    }


def cargar_datos() -> tuple[np.ndarray, np.ndarray]:
    """X (48 features float32) e y multiclase del conjunto de entrenamiento."""
    train = pd.read_parquet(ARCHIVO_TRAIN)
    mascara = mascara_multiclase(train[COLUMNA_ETIQUETA]).values
    X = train[features_finales(train)].astype(np.float32).values[mascara]
    y = etiqueta_multiclase(train.loc[mascara, COLUMNA_ETIQUETA]).astype(str).values
    return X, y


def main() -> None:
    RUTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    X, y = cargar_datos()
    print(f"Datos multiclase: {X.shape[0]:,} filas, {X.shape[1]} features, "
          f"{len(np.unique(y))} clases", flush=True)

    for modelo in MODELOS:
        for tecnica in TECNICAS:
            archivo = RUTA_RESULTADOS / f"{modelo}__{tecnica}.joblib"
            if archivo.exists():
                print(f"[ya existe] {modelo} + {tecnica}", flush=True)
                continue
            print(f"[ejecutando] {modelo} + {tecnica}", flush=True)
            resultado = evaluar_combinacion(modelo, tecnica, X, y)
            joblib.dump(resultado, archivo)
            media = resultado["f1_macro_folds"].mean()
            desv = resultado["f1_macro_folds"].std()
            print(f"  -> macro-F1 = {media:.3f} ± {desv:.3f}", flush=True)

    print("\nListo. Resultados en", RUTA_RESULTADOS, flush=True)


if __name__ == "__main__":
    main()
