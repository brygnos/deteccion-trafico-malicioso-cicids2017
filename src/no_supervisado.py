"""Pregunta 3 (detección no supervisada), Fase 4. Cómputo con checkpoints.

La idea es entrenar un detector de anomalías usando únicamente el tráfico
benigno del lunes (el único día sin ataques) que cae en el conjunto de
entrenamiento, y probarlo con el resto de la semana: ¿marca como "anómalos"
los ataques que nunca vio, y cuántas falsas alarmas genera sobre el tráfico
normal?

Decisiones metodológicas:
- El escalado se ajusta solo con los benignos del lunes (el detector no puede
  ver estadísticas de los demás días).
- Isolation Forest como modelo principal y Local Outlier Factor como contraste
  (entrenado con una submuestra de 50.000 flujos, porque su costo de
  predicción crece con el tamaño del conjunto de entrenamiento).
- El umbral de anomalía se fija con cuantiles de los scores del propio lunes
  (0,5%, 1% y 2%). Esto equivale al parámetro de contaminación y tiene en
  cuenta la advertencia de la literatura de que el "benigno" del lunes puede
  contener ataques sin etiquetar (Engelen 2021; Lanvin 2023). El umbral de
  referencia es el 1%.
- La tasa de falsas alarmas sobre los benignos se reporta por día y archivo,
  porque el tráfico normal cambia entre días y eso aumenta las falsas alarmas.
- El conjunto de prueba sigue intacto: todo ocurre dentro del entrenamiento.

Resultados: checkpoint joblib en data/interim/fase4/ y CSVs resumidos en
reports/resultados_fase4/.

Ejecutar desde la raíz del proyecto:
    python -m src.no_supervisado
"""

import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from src.config import (
    ARCHIVO_TRAIN,
    COLUMNA_ETIQUETA,
    ETIQUETA_BENIGNA,
    RANDOM_STATE,
    RUTA_INTERIM,
    RUTA_REPORTES,
)
from src.features import features_finales

RUTA_CHECKPOINTS = RUTA_INTERIM / "fase4"
RUTA_EXPORT = RUTA_REPORTES / "resultados_fase4"

CUANTILES_UMBRAL = [0.005, 0.01, 0.02]  # 1% = referencia
N_SUBMUESTRA_LOF = 50_000
N_SCORES_MUESTRA = 40_000  # scores muestreados que se exportan para las figuras


def calcular() -> dict:
    train = pd.read_parquet(ARCHIVO_TRAIN)
    features = features_finales(train)

    es_lunes = train["archivo_origen"].astype(str).str.startswith("Monday").values
    assert (train.loc[es_lunes, COLUMNA_ETIQUETA] == ETIQUETA_BENIGNA).all()

    X_lunes = train.loc[es_lunes, features].astype(np.float32).values
    evaluacion = train.loc[~es_lunes, [COLUMNA_ETIQUETA, "archivo_origen"]].copy()
    X_eval = train.loc[~es_lunes, features].astype(np.float32).values
    print(f"Entrenamiento del detector: {len(X_lunes):,} benignos del lunes; "
          f"evaluación: {len(X_eval):,} flujos de martes-viernes", flush=True)

    # El escalado se ajusta solo con el lunes
    escalador = StandardScaler().fit(X_lunes)
    X_lunes = escalador.transform(X_lunes)
    X_eval = escalador.transform(X_eval)

    resultados = {"evaluacion": evaluacion}

    # --- Isolation Forest ---
    t0 = time.time()
    bosque = IsolationForest(
        n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1
    ).fit(X_lunes)
    scores_lunes = bosque.score_samples(X_lunes)
    scores_eval = bosque.score_samples(X_eval)
    resultados["iforest"] = {
        "umbrales": {q: float(np.quantile(scores_lunes, q)) for q in CUANTILES_UMBRAL},
        "scores_eval": scores_eval.astype(np.float32),
    }
    print(f"Isolation Forest: {time.time() - t0:.0f}s", flush=True)

    # --- Local Outlier Factor (contraste, submuestra de entrenamiento) ---
    t0 = time.time()
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X_lunes), size=min(N_SUBMUESTRA_LOF, len(X_lunes)), replace=False)
    lof = LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=-1).fit(X_lunes[idx])
    scores_lof_lunes = lof.decision_function(X_lunes[idx])
    scores_lof_eval = lof.decision_function(X_eval)
    resultados["lof"] = {
        "umbrales": {q: float(np.quantile(scores_lof_lunes, q)) for q in CUANTILES_UMBRAL},
        "scores_eval": scores_lof_eval.astype(np.float32),
    }
    print(f"Local Outlier Factor: {time.time() - t0:.0f}s", flush=True)

    return resultados


def exportar(res: dict) -> None:
    RUTA_EXPORT.mkdir(parents=True, exist_ok=True)
    evaluacion = res["evaluacion"]
    etiquetas = evaluacion[COLUMNA_ETIQUETA].astype(str).values
    dias = evaluacion["archivo_origen"].astype(str).values
    es_benigno = etiquetas == ETIQUETA_BENIGNA

    filas_ataque, filas_dia = [], []
    for nombre in ["iforest", "lof"]:
        scores = res[nombre]["scores_eval"]
        for q, umbral in res[nombre]["umbrales"].items():
            anomalo = scores < umbral

            for clase in np.unique(etiquetas[~es_benigno]):
                m = etiquetas == clase
                filas_ataque.append(
                    {"modelo": nombre, "umbral_pct": 100 * q, "clase": clase,
                     "n": int(m.sum()), "recall": float(anomalo[m].mean())}
                )
            filas_ataque.append(
                {"modelo": nombre, "umbral_pct": 100 * q, "clase": "TODOS LOS ATAQUES",
                 "n": int((~es_benigno).sum()), "recall": float(anomalo[~es_benigno].mean())}
            )

            for dia in np.unique(dias):
                m = (dias == dia) & es_benigno
                filas_dia.append(
                    {"modelo": nombre, "umbral_pct": 100 * q, "dia": dia,
                     "n_benignos": int(m.sum()), "tasa_falsas_alarmas": float(anomalo[m].mean())}
                )

    pd.DataFrame(filas_ataque).to_csv(RUTA_EXPORT / "q3_recall_por_ataque.csv", index=False)
    pd.DataFrame(filas_dia).to_csv(RUTA_EXPORT / "q3_falsas_alarmas_por_dia.csv", index=False)

    # Muestra de scores para las figuras (benignos submuestreados, ataques todos
    # los que quepan en el resto de la muestra)
    rng = np.random.default_rng(RANDOM_STATE)
    idx_benigno = rng.choice(np.where(es_benigno)[0], size=N_SCORES_MUESTRA // 2, replace=False)
    idx_ataque = np.where(~es_benigno)[0]
    if len(idx_ataque) > N_SCORES_MUESTRA // 2:
        idx_ataque = rng.choice(idx_ataque, size=N_SCORES_MUESTRA // 2, replace=False)
    idx_muestra = np.concatenate([idx_benigno, idx_ataque])
    pd.DataFrame(
        {
            "score_iforest": res["iforest"]["scores_eval"][idx_muestra],
            "clase": etiquetas[idx_muestra],
        }
    ).to_csv(RUTA_EXPORT / "q3_scores_muestra.csv", index=False)

    print(f"CSVs de la pregunta 3 exportados a {RUTA_EXPORT}", flush=True)


def main() -> None:
    RUTA_CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    archivo = RUTA_CHECKPOINTS / "q3_no_supervisado.joblib"
    if archivo.exists():
        print("[ya existe] q3_no_supervisado", flush=True)
        res = joblib.load(archivo)
    else:
        print("[ejecutando] q3_no_supervisado", flush=True)
        res = calcular()
        joblib.dump(res, archivo)
    exportar(res)


if __name__ == "__main__":
    main()
