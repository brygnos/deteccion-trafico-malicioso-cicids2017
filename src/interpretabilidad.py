"""Pregunta 1 (interpretabilidad), Fase 4. Cómputo pesado con checkpoints.

Tiene tres partes, todas solo con el conjunto de entrenamiento, y las dos
primeras sobre el problema binario (Normal vs Ataque):

1. Lectura sencilla: los coeficientes de la regresión logística estandarizada,
   ajustada en cada una de las 5 particiones (media ± desviación para ver qué
   tan estables son). Como las features están estandarizadas, la magnitud del
   coeficiente se puede comparar entre features y el signo dice hacia dónde
   empuja.
2. El modelo real: la importancia por permutación del HistGB con pesos de
   clase (el mejor modelo de la Fase 3), medida sobre una porción de
   validación que el modelo no vio. Si al barajar una feature el desempeño cae
   mucho, quiere decir que el modelo dependía de ella.
3. Verificación de validez con el puerto de destino: 'Destination Port'
   identifica el servicio y no describe el comportamiento del tráfico (en este
   dataset el ataque web siempre usa el puerto 80, pero en el mundo real puede
   usar cualquier otro). Se reentrena el mejor modelo multiclase sin esa
   feature y se compara con el resultado de la Fase 3 (que sí la incluía). Si
   el desempeño se mantiene, el modelo aprende comportamiento; si cae mucho,
   se estaba apoyando en un artefacto del dataset.

Resultados: checkpoints joblib en data/interim/fase4/ y CSVs resumidos en
reports/resultados_fase4/ (los notebooks solo leen los CSVs).

Ejecutar desde la raíz del proyecto:
    python -m src.interpretabilidad
"""

import joblib
import numpy as np
import pandas as pd
from imblearn.pipeline import Pipeline
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from src.config import (
    ARCHIVO_TRAIN,
    COLUMNA_ETIQUETA,
    RANDOM_STATE,
    RUTA_INTERIM,
    RUTA_REPORTES,
)
from src.etiquetas import etiqueta_binaria, etiqueta_multiclase, mascara_multiclase
from src.experimentos import RUTA_RESULTADOS as RUTA_FASE3
from src.experimentos import evaluar_combinacion
from src.features import features_finales

RUTA_CHECKPOINTS = RUTA_INTERIM / "fase4"
RUTA_EXPORT = RUTA_REPORTES / "resultados_fase4"

# Features que identifican el servicio en lugar de describir el comportamiento (verificación 4-5)
FEATURES_IDENTIFICADORAS = ["Destination Port"]

# Tamaño de la muestra de validación para la importancia por permutación
N_VALIDACION_PERMUTACION = 300_000


def _checkpoint(nombre: str, calcular):
    """Ejecuta `calcular()` solo si el checkpoint no existe aún."""
    archivo = RUTA_CHECKPOINTS / f"{nombre}.joblib"
    if archivo.exists():
        print(f"[ya existe] {nombre}", flush=True)
        return joblib.load(archivo)
    print(f"[ejecutando] {nombre}", flush=True)
    resultado = calcular()
    joblib.dump(resultado, archivo)
    return resultado


def coeficientes_logistica(X, y_bin, features) -> pd.DataFrame:
    """Coeficientes (espacio estandarizado) por partición: folds x features."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    filas = []
    for k, (idx_tr, _) in enumerate(cv.split(X, y_bin), 1):
        pipe = Pipeline([
            ("escalado", StandardScaler()),
            ("modelo", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
        ])
        pipe.fit(X[idx_tr], y_bin[idx_tr])
        filas.append(pipe.named_steps["modelo"].coef_[0])
        print(f"    fold {k}/5 listo", flush=True)
    return pd.DataFrame(filas, columns=features)


def importancia_permutacion(X, y_bin, features) -> pd.DataFrame:
    """Importancia por permutación del HistGB binario con pesos de clase.

    Se ajusta con el 80% de la primera partición y se mide sobre una muestra
    de la validación (que el modelo nunca vio), con macro-F1 como métrica.
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    idx_tr, idx_va = next(cv.split(X, y_bin))
    modelo = HistGradientBoostingClassifier(
        max_iter=200, random_state=RANDOM_STATE, class_weight="balanced"
    )
    modelo.fit(X[idx_tr], y_bin[idx_tr])

    rng = np.random.default_rng(RANDOM_STATE)
    muestra = rng.choice(idx_va, size=min(N_VALIDACION_PERMUTACION, len(idx_va)), replace=False)
    resultado = permutation_importance(
        modelo, X[muestra], y_bin[muestra],
        scoring="f1_macro", n_repeats=5, random_state=RANDOM_STATE, n_jobs=-1,
    )
    return pd.DataFrame(
        {
            "feature": features,
            "importancia_media": resultado.importances_mean,
            "importancia_desv": resultado.importances_std,
        }
    ).sort_values("importancia_media", ascending=False)


def experimento_puerto(train, features) -> dict:
    """Reentrena el mejor modelo multiclase (árboles + pesos) sin el puerto.

    La variante con puerto no se recalcula, porque es exactamente el
    resultado guardado de la Fase 3 (mismas particiones, misma semilla).
    """
    mascara = mascara_multiclase(train[COLUMNA_ETIQUETA]).values
    y_multi = etiqueta_multiclase(train.loc[mascara, COLUMNA_ETIQUETA]).astype(str).values

    sin_ident = [f for f in features if f not in FEATURES_IDENTIFICADORAS]
    X_sin = train[sin_ident].astype(np.float32).values[mascara]
    resultado_sin = evaluar_combinacion("arboles", "pesos", X_sin, y_multi)

    resultado_con = joblib.load(RUTA_FASE3 / "arboles__pesos.joblib")
    return {"con_puerto": resultado_con, "sin_puerto": resultado_sin,
            "features_retiradas": FEATURES_IDENTIFICADORAS}


def exportar(coefs: pd.DataFrame, perm: pd.DataFrame, puerto: dict) -> None:
    RUTA_EXPORT.mkdir(parents=True, exist_ok=True)

    resumen_coef = pd.DataFrame(
        {
            "feature": coefs.columns,
            "coef_media": coefs.mean().values,
            "coef_desv": coefs.std().values,
        }
    )
    resumen_coef["magnitud"] = resumen_coef["coef_media"].abs()
    resumen_coef.sort_values("magnitud", ascending=False).drop(columns="magnitud").to_csv(
        RUTA_EXPORT / "q1_coeficientes_logistica.csv", index=False
    )

    perm.to_csv(RUTA_EXPORT / "q1_importancia_permutacion.csv", index=False)

    filas_f1, filas_recall, filas_precision = [], [], []
    for variante, res in [("con_puerto", puerto["con_puerto"]), ("sin_puerto", puerto["sin_puerto"])]:
        for k, f1 in enumerate(res["f1_macro_folds"], 1):
            filas_f1.append({"variante": variante, "fold": k, "macro_f1": f1})
        for destino, clave in [(filas_recall, "recall_folds"), (filas_precision, "precision_folds")]:
            df = res[clave]
            for clase in df.columns:
                destino.append(
                    {
                        "variante": variante,
                        "clase": clase,
                        "media": df[clase].mean(),
                        "desv": df[clase].std(),
                    }
                )
    pd.DataFrame(filas_f1).to_csv(RUTA_EXPORT / "q1_puerto_macro_f1.csv", index=False)
    pd.DataFrame(filas_recall).to_csv(RUTA_EXPORT / "q1_puerto_recall_por_clase.csv", index=False)
    pd.DataFrame(filas_precision).to_csv(RUTA_EXPORT / "q1_puerto_precision_por_clase.csv", index=False)

    print(f"CSVs de la pregunta 1 exportados a {RUTA_EXPORT}", flush=True)


def main() -> None:
    RUTA_CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    train = pd.read_parquet(ARCHIVO_TRAIN)
    features = features_finales(train)
    X = train[features].astype(np.float32).values
    y_bin = etiqueta_binaria(train[COLUMNA_ETIQUETA]).values
    print(f"Train: {X.shape[0]:,} filas, {X.shape[1]} features", flush=True)

    coefs = _checkpoint("q1_coef_logistica", lambda: coeficientes_logistica(X, y_bin, features))
    perm = _checkpoint("q1_perm_importancia", lambda: importancia_permutacion(X, y_bin, features))
    puerto = _checkpoint("q1_experimento_puerto", lambda: experimento_puerto(train, features))

    exportar(coefs, perm, puerto)


if __name__ == "__main__":
    main()
