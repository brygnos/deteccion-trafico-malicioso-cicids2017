"""Agregación y exportación de los resultados de la Fase 3.

Los experimentos (src/experimentos.py) guardan por cada combinación un archivo
joblib grande (incluye las probabilidades out-of-fold) en data/interim/fase3/.
Ese formato es local y no se comparte, así que este módulo lo resume en CSVs de
pocos kilobytes dentro de reports/resultados_fase3/, que sí viajan con el
repositorio:

- fase3_macro_f1.csv               media ± desviación por combinación
- fase3_<métrica>_por_clase.csv    recall / precision / ap por clase (formato largo)
- fase3_confusion__<combo>.csv     matriz de confusión out-of-fold por combinación
- fase3_pr__<combo>.csv            puntos de la curva PR de las clases minoritarias

Así los notebooks y el informe se pueden regenerar en segundos en cualquier
máquina, sin volver a entrenar nada.

Ejecutar desde la raíz del proyecto (después de src.experimentos):
    python -m src.resultados
"""

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_curve

from src.config import RUTA_REPORTES
from src.experimentos import MODELOS, RUTA_RESULTADOS, TECNICAS, cargar_datos

RUTA_EXPORT = RUTA_REPORTES / "resultados_fase3"

# Clases minoritarias cuyo detalle (AP, curvas PR) se reporta siempre
CLASES_MINORITARIAS = [
    "Bot",
    "Web Attack",
    "SSH-Patator",
    "DoS Slowhttptest",
    "DoS slowloris",
]

NOMBRES_TECNICA = {
    "sin_correccion": "Sin corrección",
    "pesos": "Pesos de clase",
    "smote": "SMOTE",
    "submuestreo_smote": "Submuestreo + SMOTE",
}
NOMBRES_MODELO = {"reglog": "Regresión logística", "arboles": "Árboles (HistGB)"}


def cargar_resultados() -> dict[tuple[str, str], dict]:
    """Carga los joblib de todas las combinaciones ya calculadas."""
    resultados = {}
    for modelo in MODELOS:
        for tecnica in TECNICAS:
            archivo = RUTA_RESULTADOS / f"{modelo}__{tecnica}.joblib"
            if archivo.exists():
                resultados[(modelo, tecnica)] = joblib.load(archivo)
    return resultados


def etiqueta_combo(modelo: str, tecnica: str) -> str:
    return f"{NOMBRES_MODELO[modelo]} + {NOMBRES_TECNICA[tecnica]}"


def tabla_macro_f1(resultados: dict) -> pd.DataFrame:
    """Macro-F1 por combinación: media y desviación entre folds."""
    filas = []
    for (modelo, tecnica), res in resultados.items():
        f1 = res["f1_macro_folds"]
        filas.append(
            {
                "modelo": NOMBRES_MODELO[modelo],
                "tecnica": NOMBRES_TECNICA[tecnica],
                "macro_f1_media": f1.mean(),
                "macro_f1_desv": f1.std(),
            }
        )
    return (
        pd.DataFrame(filas)
        .sort_values("macro_f1_media", ascending=False)
        .reset_index(drop=True)
    )


def tabla_por_clase(resultados: dict, metrica: str) -> pd.DataFrame:
    """Métrica por clase en formato largo: combinación, clase, media, desv.

    `metrica` es una de: 'recall', 'precision', 'ap'.
    """
    clave = f"{metrica}_folds"
    filas = []
    for (modelo, tecnica), res in resultados.items():
        df = res[clave]
        for clase in df.columns:
            filas.append(
                {
                    "modelo": NOMBRES_MODELO[modelo],
                    "tecnica": NOMBRES_TECNICA[tecnica],
                    "clase": clase,
                    "media": df[clase].mean(),
                    "desv": df[clase].std(),
                }
            )
    return pd.DataFrame(filas)


def _curva_pr_reducida(y_bin: np.ndarray, scores: np.ndarray, max_puntos: int = 400):
    """Curva PR con a lo sumo `max_puntos` puntos (para CSVs livianos)."""
    prec, rec, _ = precision_recall_curve(y_bin, scores)
    if len(prec) > max_puntos:
        idx = np.linspace(0, len(prec) - 1, max_puntos).astype(int)
        prec, rec = prec[idx], rec[idx]
    return prec, rec


def exportar(verbose: bool = True) -> None:
    """Condensa los joblib en los CSVs compartibles de reports/resultados_fase3/."""
    RUTA_EXPORT.mkdir(parents=True, exist_ok=True)
    resultados = cargar_resultados()
    if not resultados:
        raise FileNotFoundError(f"No hay resultados en {RUTA_RESULTADOS}")

    _, y = cargar_datos()

    tabla_macro_f1(resultados).to_csv(RUTA_EXPORT / "fase3_macro_f1.csv", index=False)
    for metrica in ["recall", "precision", "ap"]:
        tabla_por_clase(resultados, metrica).to_csv(
            RUTA_EXPORT / f"fase3_{metrica}_por_clase.csv", index=False
        )

    for (modelo, tecnica), res in resultados.items():
        clases = np.array(res["clases"])
        pred = clases[res["oof_pred"]]

        matriz = confusion_matrix(y, pred, labels=clases)
        pd.DataFrame(matriz, index=clases, columns=clases).to_csv(
            RUTA_EXPORT / f"fase3_confusion__{modelo}__{tecnica}.csv"
        )

        curvas = []
        for clase in CLASES_MINORITARIAS:
            col = list(clases).index(clase)
            prec, rec = _curva_pr_reducida(
                (y == clase).astype(int), res["oof_proba"][:, col].astype(np.float32)
            )
            curvas.append(pd.DataFrame({"clase": clase, "precision": prec, "recall": rec}))
        pd.concat(curvas, ignore_index=True).to_csv(
            RUTA_EXPORT / f"fase3_pr__{modelo}__{tecnica}.csv", index=False
        )

    if verbose:
        archivos = sorted(RUTA_EXPORT.glob("*.csv"))
        total_kb = sum(a.stat().st_size for a in archivos) / 1024
        print(f"{len(archivos)} CSVs exportados a {RUTA_EXPORT} ({total_kb:,.0f} KB en total)")
        print(f"Combinaciones incluidas: {len(resultados)}")


if __name__ == "__main__":
    exportar()
