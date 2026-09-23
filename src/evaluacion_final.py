"""Evaluación final sobre el conjunto de prueba (fase final). Se ejecuta una sola vez.

Este es el único módulo del proyecto que calcula métricas con test.parquet
(src/preparar_demo.py también lo lee, pero solo para sacar las muestras de la
demostración del tablero). Reglas:

- El umbral de Bot (UMBRAL_BOT) se fijó antes, solo con las probabilidades
  out-of-fold del entrenamiento (ver la sección 7 de reports/reporte_tecnico_final.pdf, ajuste 4).
  La alarma de Bot solo se emite si P(Bot) >= 0,999, y si no, el flujo se
  reasigna a la segunda clase más probable. Con las probabilidades out-of-fold
  del train ese punto da precisión 0,93 / recall 0,68 (con puerto) y
  0,87 / 0,61 (sin puerto), frente a 0,61 / 0,98 y 0,46 / 0,61 del argmax.
- Se evalúan dos variantes del mejor modelo (árboles + pesos de clase,
  reentrenado con todo el train): con puerto y sin identificadores
  ('Destination Port' es el único identificador entre las 48 features, ya
  verificado).
- También se evalúan el detector binario (para las clases extremadamente raras
  del test, con n mínima, así que sus cifras son ilustrativas) y el Isolation
  Forest del lunes sobre el test.
- Una vez calculado, no se reajusta nada con base en estos resultados.

El checkpoint queda en data/interim/fase5/ y los CSVs resumidos en
reports/resultados_final/.

Ejecutar desde la raíz del proyecto:
    python -m src.evaluacion_final
"""

import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler

from src.config import (
    ARCHIVO_TEST,
    ARCHIVO_TRAIN,
    COLUMNA_ETIQUETA,
    ETIQUETA_BENIGNA,
    RANDOM_STATE,
    RUTA_INTERIM,
    RUTA_REPORTES,
)
from src.etiquetas import (
    CLASES_EXCLUIDAS_MULTICLASE,
    etiqueta_binaria,
    etiqueta_multiclase,
    mascara_multiclase,
)
from src.features import features_finales
from src.interpretabilidad import FEATURES_IDENTIFICADORAS

RUTA_CHECKPOINT = RUTA_INTERIM / "fase5" / "evaluacion_test.joblib"
RUTA_EXPORT = RUTA_REPORTES / "resultados_final"

# Se fijó con las probabilidades out-of-fold del train; el test nunca se usó para elegirlo.
UMBRAL_BOT = 0.999

CUANTILES_UMBRAL_IF = [0.005, 0.01, 0.02]


def _aplicar_umbral_bot(proba: np.ndarray, clases: np.ndarray) -> np.ndarray:
    """Regla de operación: Bot solo si P(Bot) >= UMBRAL_BOT; si no, la
    segunda clase más probable."""
    pred = clases[np.argmax(proba, axis=1)]
    idx_bot = list(clases).index("Bot")
    dudosos = (pred == "Bot") & (proba[:, idx_bot] < UMBRAL_BOT)
    if dudosos.any():
        proba_sin_bot = proba[dudosos].copy()
        proba_sin_bot[:, idx_bot] = -np.inf
        pred = pred.copy()
        pred[dudosos] = clases[np.argmax(proba_sin_bot, axis=1)]
    return pred


def _metricas_multiclase(y_true, pred, proba, clases) -> dict:
    ataques = [c for c in clases if c != ETIQUETA_BENIGNA]
    return {
        "macro_f1": f1_score(y_true, pred, average="macro"),
        "macro_f1_solo_ataques": f1_score(
            y_true, pred, labels=ataques, average="macro", zero_division=0
        ),
        "recall": recall_score(y_true, pred, labels=clases, average=None),
        "precision": precision_score(y_true, pred, labels=clases, average=None, zero_division=0),
        "ap": [
            average_precision_score((y_true == c).astype(int), proba[:, i])
            for i, c in enumerate(clases)
        ],
        "soporte": [int((y_true == c).sum()) for c in clases],
        "confusion": confusion_matrix(y_true, pred, labels=clases),
    }


def calcular() -> dict:
    train = pd.read_parquet(ARCHIVO_TRAIN)
    test = pd.read_parquet(ARCHIVO_TEST)
    features = features_finales(train)

    # Verificación: el único identificador entre las features es el puerto
    assert FEATURES_IDENTIFICADORAS == ["Destination Port"]
    assert set(FEATURES_IDENTIFICADORAS) <= set(features)

    resultados = {"umbral_bot": UMBRAL_BOT}

    # ---------- Multiclase: el mejor modelo con todo el train, en dos variantes ----------
    m_tr = mascara_multiclase(train[COLUMNA_ETIQUETA]).values
    m_te = mascara_multiclase(test[COLUMNA_ETIQUETA]).values
    y_tr = etiqueta_multiclase(train.loc[m_tr, COLUMNA_ETIQUETA]).astype(str).values
    y_te = etiqueta_multiclase(test.loc[m_te, COLUMNA_ETIQUETA]).astype(str).values

    variantes = {
        "con_puerto": features,
        "sin_identificadores": [f for f in features if f not in FEATURES_IDENTIFICADORAS],
    }
    for nombre, feats in variantes.items():
        t0 = time.time()
        modelo = HistGradientBoostingClassifier(
            max_iter=200, random_state=RANDOM_STATE, class_weight="balanced"
        ).fit(train.loc[m_tr, feats].astype(np.float32).values, y_tr)
        proba = modelo.predict_proba(test.loc[m_te, feats].astype(np.float32).values)
        clases = modelo.classes_

        resultados[nombre] = {
            "clases": clases.tolist(),
            "argmax": _metricas_multiclase(y_te, clases[np.argmax(proba, axis=1)], proba, clases),
            "umbral_bot": _metricas_multiclase(
                y_te, _aplicar_umbral_bot(proba, clases), proba, clases
            ),
        }
        print(f"[multiclase {nombre}] listo en {time.time() - t0:.0f}s "
              f"(macro-F1 argmax = {resultados[nombre]['argmax']['macro_f1']:.3f})", flush=True)

    # ---------- Binario: para las clases extremadamente raras (n mínima) ----------
    t0 = time.time()
    y_bin_tr = etiqueta_binaria(train[COLUMNA_ETIQUETA]).values
    y_bin_te = etiqueta_binaria(test[COLUMNA_ETIQUETA]).values
    modelo_bin = HistGradientBoostingClassifier(
        max_iter=200, random_state=RANDOM_STATE, class_weight="balanced"
    ).fit(train[features].astype(np.float32).values, y_bin_tr)
    pred_bin = modelo_bin.predict(test[features].astype(np.float32).values)

    raras = {}
    for clase in CLASES_EXCLUIDAS_MULTICLASE:
        filas = (test[COLUMNA_ETIQUETA] == clase).values
        raras[clase] = {"n": int(filas.sum()), "detectadas": int(pred_bin[filas].sum())}
    resultados["binario"] = {
        "recall_ataque": float(recall_score(y_bin_te, pred_bin)),
        "precision_ataque": float(precision_score(y_bin_te, pred_bin)),
        "macro_f1": float(f1_score(y_bin_te, pred_bin, average="macro")),
        "raras": raras,
    }
    print(f"[binario] listo en {time.time() - t0:.0f}s", flush=True)

    # ---------- No supervisado: IF del lunes (train) sobre el test ----------
    t0 = time.time()
    es_lunes_tr = train["archivo_origen"].astype(str).str.startswith("Monday").values
    X_lunes = train.loc[es_lunes_tr, features].astype(np.float32).values
    escalador = StandardScaler().fit(X_lunes)
    bosque = IsolationForest(
        n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1
    ).fit(escalador.transform(X_lunes))
    scores_lunes = bosque.score_samples(escalador.transform(X_lunes))
    umbrales = {q: float(np.quantile(scores_lunes, q)) for q in CUANTILES_UMBRAL_IF}

    scores_test = bosque.score_samples(
        escalador.transform(test[features].astype(np.float32).values)
    )
    resultados["iforest"] = {
        "umbrales": umbrales,
        "scores_test": scores_test.astype(np.float32),
        "etiquetas": test[COLUMNA_ETIQUETA].astype(str).values,
        "dias": test["archivo_origen"].astype(str).values,
    }
    print(f"[iforest] listo en {time.time() - t0:.0f}s", flush=True)

    return resultados


def exportar(res: dict) -> None:
    RUTA_EXPORT.mkdir(parents=True, exist_ok=True)

    filas_macro, filas_clase = [], []
    for variante in ["con_puerto", "sin_identificadores"]:
        clases = res[variante]["clases"]
        for regla in ["argmax", "umbral_bot"]:
            met = res[variante][regla]
            filas_macro.append(
                {
                    "variante": variante,
                    "regla": regla,
                    "macro_f1": met["macro_f1"],
                    "macro_f1_solo_ataques": met["macro_f1_solo_ataques"],
                }
            )
            for i, clase in enumerate(clases):
                filas_clase.append(
                    {
                        "variante": variante,
                        "regla": regla,
                        "clase": clase,
                        "recall": met["recall"][i],
                        "precision": met["precision"][i],
                        "ap": met["ap"][i],
                        "soporte": met["soporte"][i],
                    }
                )
            pd.DataFrame(met["confusion"], index=clases, columns=clases).to_csv(
                RUTA_EXPORT / f"final_confusion__{variante}__{regla}.csv"
            )
    pd.DataFrame(filas_macro).to_csv(RUTA_EXPORT / "final_multiclase_macro.csv", index=False)
    pd.DataFrame(filas_clase).to_csv(RUTA_EXPORT / "final_multiclase_por_clase.csv", index=False)

    binario = res["binario"]
    pd.DataFrame(
        [
            {"metrica": "recall_ataque", "valor": binario["recall_ataque"]},
            {"metrica": "precision_ataque", "valor": binario["precision_ataque"]},
            {"metrica": "macro_f1", "valor": binario["macro_f1"]},
        ]
    ).to_csv(RUTA_EXPORT / "final_binario_metricas.csv", index=False)
    pd.DataFrame(
        [{"clase": c, **v} for c, v in binario["raras"].items()]
    ).to_csv(RUTA_EXPORT / "final_binario_raras.csv", index=False)

    etiquetas = res["iforest"]["etiquetas"]
    dias = res["iforest"]["dias"]
    scores = res["iforest"]["scores_test"]
    es_benigno = etiquetas == ETIQUETA_BENIGNA
    filas_rec, filas_dia = [], []
    for q, umbral in res["iforest"]["umbrales"].items():
        anomalo = scores < umbral
        for clase in np.unique(etiquetas[~es_benigno]):
            m = etiquetas == clase
            filas_rec.append(
                {"umbral_pct": 100 * q, "clase": clase, "n": int(m.sum()),
                 "recall": float(anomalo[m].mean())}
            )
        filas_rec.append(
            {"umbral_pct": 100 * q, "clase": "TODOS LOS ATAQUES",
             "n": int((~es_benigno).sum()), "recall": float(anomalo[~es_benigno].mean())}
        )
        for dia in np.unique(dias):
            m = (dias == dia) & es_benigno
            filas_dia.append(
                {"umbral_pct": 100 * q, "dia": dia, "n_benignos": int(m.sum()),
                 "tasa_falsas_alarmas": float(anomalo[m].mean())}
            )
    pd.DataFrame(filas_rec).to_csv(RUTA_EXPORT / "final_iforest_recall.csv", index=False)
    pd.DataFrame(filas_dia).to_csv(RUTA_EXPORT / "final_iforest_fp_dia.csv", index=False)

    print(f"CSVs finales exportados a {RUTA_EXPORT}", flush=True)


def main() -> None:
    RUTA_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    if RUTA_CHECKPOINT.exists():
        print("[ya existe] evaluación final (no se recalcula: una sola pasada)", flush=True)
        res = joblib.load(RUTA_CHECKPOINT)
    else:
        print("[ejecutando] evaluación final sobre el test (única pasada)", flush=True)
        res = calcular()
        joblib.dump(res, RUTA_CHECKPOINT)
    exportar(res)


if __name__ == "__main__":
    main()
