"""División única train/test (Fase 2).

Regla metodológica del proyecto: el conjunto de prueba se aparta una sola vez
(20%, estratificado por clase, RANDOM_STATE=42) y no se toca hasta la
evaluación final. Toda decisión que dependa de los datos (selección de
features, ajuste de parámetros, remuestreo) se toma únicamente con el conjunto
de entrenamiento.

Los dos conjuntos se guardan en data/processed/ para que todo el proyecto
(notebooks y scripts) use exactamente las mismas filas. Para evitar
regenerarlos por accidente (lo que invalidaría cualquier resultado anterior),
el script se niega a sobrescribirlos si ya existen.

Ejecutar desde la raíz del proyecto:
    python -m src.split
"""

import sys

import pandas as pd
from sklearn.model_selection import train_test_split

from src.config import (
    ARCHIVO_LIMPIO,
    ARCHIVO_TEST,
    ARCHIVO_TRAIN,
    COLUMNA_ETIQUETA,
    PROPORCION_TEST,
    RANDOM_STATE,
)


def main() -> None:
    if ARCHIVO_TRAIN.exists() or ARCHIVO_TEST.exists():
        sys.exit(
            "ERROR: el split ya existe y NO debe regenerarse (los resultados del "
            "proyecto dependen de que sea único). Si de verdad hay que rehacerlo, "
            f"borrar manualmente:\n  {ARCHIVO_TRAIN}\n  {ARCHIVO_TEST}"
        )

    df = pd.read_parquet(ARCHIVO_LIMPIO)
    train, test = train_test_split(
        df,
        test_size=PROPORCION_TEST,
        stratify=df[COLUMNA_ETIQUETA],
        random_state=RANDOM_STATE,
    )

    ARCHIVO_TRAIN.parent.mkdir(parents=True, exist_ok=True)
    train.to_parquet(ARCHIVO_TRAIN, index=False)
    test.to_parquet(ARCHIVO_TEST, index=False)

    resumen = pd.DataFrame(
        {
            "train": train[COLUMNA_ETIQUETA].value_counts(),
            "test": test[COLUMNA_ETIQUETA].value_counts(),
        }
    )
    resumen["test_pct"] = (100 * resumen["test"] / (resumen["train"] + resumen["test"])).round(1)
    print(f"Train: {len(train):,} filas -> {ARCHIVO_TRAIN}")
    print(f"Test:  {len(test):,} filas -> {ARCHIVO_TEST}")
    print("\nDistribución por clase (el test debe rondar 20% en todas):")
    print(resumen.to_string())


if __name__ == "__main__":
    main()
