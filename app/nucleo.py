"""Núcleo del tablero: modelos serializados y clasificación por lotes.

No importa Streamlit (el cacheo lo aplica streamlit_app.py al envolver
`cargar_recursos`), así que se puede probar sin interfaz.

Los modelos y sus metadatos vienen de models/ (generados por
src/modelo_final.py usando todo el conjunto de entrenamiento). Las métricas
fijas de la evaluación vienen de los CSVs versionados en
reports/resultados_final/. No se recalculan cifras del proyecto aquí.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

RAIZ = Path(__file__).resolve().parent.parent
RUTA_MODELOS = RAIZ / "models"
RUTA_DEMO = RAIZ / "data" / "demo"
RUTA_RESULTADOS = RAIZ / "reports" / "resultados_final"
RUTA_RESULTADOS_FASE4 = RAIZ / "reports" / "resultados_fase4"

ETIQUETA_NORMAL = "BENIGN"
NOMBRE_NORMAL = "Normal"

# Versión de la ESTRUCTURA que devuelve cargar_recursos(). El dash la pasa
# como argumento a la función cacheada. Si cambia, Streamlit descarta el caché
# viejo y vuelve a cargar. Sin esto, un servidor que lleva rato corriendo
# sigue sirviendo un diccionario de recursos anterior aunque el código ya
# haya cambiado, y las pantallas fallan con un KeyError críptico.
# SUBIR ESTE NÚMERO al agregar, quitar o renombrar una clave del diccionario.
VERSION_RECURSOS = "3"

# Claves que las pantallas dan por sentadas (se verifican al arrancar)
CLAVES_REQUERIDAS = frozenset({
    "multiclase", "binario", "detector", "meta", "metricas_clase",
    "confusion", "importancia", "falsas_alarmas_dia", "version_sklearn_activa",
    "version_sklearn_modelos",
})

# Etiquetas del deslizador de anomalías -> cuantil guardado con el detector.
# Cada opción es un presupuesto explícito de falsas alarmas (ver la sección 5.1 del reporte técnico).
CUANTILES = {"0,5%": "0.005", "1%": "0.01", "2%": "0.02"}

# Cifras oficiales del proyecto, las mismas del reporte técnico (secciones 5.3 y 7.1). No se recalculan.
CIFRAS_OFICIALES = {
    "macro_f1_final": "0,975",
    "macro_f1_solo_ataques": "0,972",
    "falsas_alarmas_pct": "0,12%",
    "piso_trivial": "0,082",
    "flujos_prueba": "499.616",
}


def cargar_recursos(version: str = VERSION_RECURSOS) -> dict:
    """Carga los tres modelos, sus metadatos y las métricas fijas del test.

    `version` no se usa dentro: existe para que el caché del tablero se
    invalide cuando cambie la estructura del diccionario (ver
    VERSION_RECURSOS).
    """
    meta = json.loads((RUTA_MODELOS / "metadatos.json").read_text(encoding="utf-8"))

    metricas_clase = pd.read_csv(RUTA_RESULTADOS / "final_multiclase_por_clase.csv")
    metricas_clase = metricas_clase.query(
        "variante == 'con_puerto' and regla == 'umbral_bot'"
    ).drop(columns=["variante", "regla"])

    confusion = pd.read_csv(
        RUTA_RESULTADOS / "final_confusion__con_puerto__umbral_bot.csv", index_col=0
    )

    importancia = pd.read_csv(RUTA_RESULTADOS_FASE4 / "q1_importancia_permutacion.csv")

    # R11: tasa de falsas alarmas del detector desagregada por día/tramo, en la
    # evaluación final sobre el test. Es la evidencia de la deriva temporal.
    falsas_alarmas_dia = pd.read_csv(RUTA_RESULTADOS / "final_iforest_fp_dia.csv")

    return {
        "importancia": importancia,
        "falsas_alarmas_dia": falsas_alarmas_dia,
        "multiclase": joblib.load(RUTA_MODELOS / "modelo_multiclase.joblib"),
        "binario": joblib.load(RUTA_MODELOS / "modelo_binario.joblib"),
        "detector": joblib.load(RUTA_MODELOS / "detector_anomalias.joblib"),
        "meta": meta,
        "metricas_clase": metricas_clase,
        "confusion": confusion,
        "version_sklearn_activa": sklearn.__version__,
        "version_sklearn_modelos": meta["version_sklearn"],
    }


def nombre_visible(clase: str) -> str:
    """BENIGN se muestra como 'Normal'; los ataques conservan su nombre."""
    return NOMBRE_NORMAL if clase == ETIQUETA_NORMAL else clase


def clasificar(datos: pd.DataFrame, recursos: dict) -> pd.DataFrame:
    """Clasifica un lote ya validado y devuelve una tabla por flujo.

    Aplica el modelo final oficial: clase multiclase con la regla de Bot
    (alarma de Bot solo si su probabilidad supera el umbral; si no, la
    segunda clase más probable), el clasificador binario, y el score del
    detector de anomalías con su marca al umbral elegido.
    """
    meta = recursos["meta"]
    X = datos[meta["caracteristicas"]].astype(np.float32).values

    # Multiclase + regla de operación de Bot (el modelo final oficial)
    proba = recursos["multiclase"].predict_proba(X)
    clases = recursos["multiclase"].classes_
    pred = clases[np.argmax(proba, axis=1)]
    idx_bot = list(clases).index("Bot")
    dudosos = (pred == "Bot") & (proba[:, idx_bot] < meta["umbral_bot"])
    if dudosos.any():
        sin_bot = proba[dudosos].copy()
        sin_bot[:, idx_bot] = -np.inf
        pred = pred.copy()
        pred[dudosos] = clases[np.argmax(sin_bot, axis=1)]
    confianza = proba[np.arange(len(pred)), [list(clases).index(c) for c in pred]]

    # Binario (ataque sí/no) con su probabilidad
    prob_ataque = recursos["binario"].predict_proba(X)[:, 1]

    # Detector de anomalías: se guarda el score; la marca de anomalía se
    # calcula en cada pantalla con el umbral elegido (ver marcar_anomalias)
    detector = recursos["detector"]
    score = detector["bosque"].score_samples(detector["escalador"].transform(X))

    return pd.DataFrame(
        {
            "fila": datos.index + 1,  # 1 = primera fila de datos del archivo
            "clase": [nombre_visible(c) for c in pred],
            "confianza": confianza,
            "clase_binaria": np.where(prob_ataque >= 0.5, "Ataque", NOMBRE_NORMAL),
            "prob_ataque": prob_ataque,
            "score_anomalia": score,
        }
    )


MARCAS_ANOMALIA = ("Todas", "Solo anómalas", "Solo no anómalas")


def filtrar_alertas(resultado: pd.DataFrame, anomalo: pd.Series, tipos, confianza_minima: float,
                    marca: str = "Todas") -> pd.DataFrame:
    """Las alertas del resultado (flujos con un tipo de ataque asignado) que
    cumplen el filtro de la pantalla Alertas, con la columna `anomalo`.

    Es la única definición del filtro: la usan la pantalla Alertas y la
    descarga de Reportes, así que las dos muestran siempre lo mismo para el
    archivo activo.
    """
    alertas = resultado.assign(anomalo=anomalo)
    alertas = alertas[alertas["clase"] != NOMBRE_NORMAL]
    alertas = alertas[alertas["clase"].isin(list(tipos)) & (alertas["confianza"] >= confianza_minima)]
    if marca == "Solo anómalas":
        alertas = alertas[alertas["anomalo"]]
    elif marca == "Solo no anómalas":
        alertas = alertas[~alertas["anomalo"]]
    return alertas


def marcar_anomalias(resultado: pd.DataFrame, recursos: dict, etiqueta_cuantil: str):
    """Marca de anomalía al umbral elegido en el deslizador (R15).

    Devuelve (serie booleana, umbral numérico usado). El umbral es el cuantil
    correspondiente de los scores del tráfico benigno del lunes, guardado
    junto al detector: un presupuesto explícito de falsas alarmas.
    """
    umbral = recursos["detector"]["umbrales"][CUANTILES[etiqueta_cuantil]]
    return resultado["score_anomalia"] < umbral, umbral
