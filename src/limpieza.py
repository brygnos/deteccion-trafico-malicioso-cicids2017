"""Limpieza del dataset consolidado (Fase 2).

Aplica las decisiones de limpieza aprobadas (explicadas en la sección 4 de
reports/reporte_tecnico_final.pdf, Cuadro 3). La poda por correlación y la división train/test
también hacen parte de esas decisiones, pero están en src/features.py y
src/split.py porque dependen solo del conjunto de entrenamiento.

1. Eliminar las filas duplicadas (ignorando `archivo_origen`). El motivo es que
   una misma fila repetida puede caer a la vez en entrenamiento y en prueba, y
   el modelo "acertaría" porque la memorizó (fuga de información).
2. Eliminar las filas con Inf o NaN en `Flow Bytes/s` / `Flow Packets/s`
   (divisiones entre duración 0; 0,10% de las filas).
3. Eliminar las filas con `Flow Duration` < 0 (error de captura).
4. `Init_Win_bytes_forward/backward`: el −1 es un código de "no aplica", así
   que se crea un indicador binario `*_no_aplica` y el −1 pasa a 0.
5. Eliminar las features constantes (mismo valor en todas las filas).

Guarda el resultado en data/interim/ y reporta el efecto de cada paso.

Ejecutar desde la raíz del proyecto:
    python -m src.limpieza
"""

import numpy as np
import pandas as pd

from src.config import ARCHIVO_CONSOLIDADO, ARCHIVO_LIMPIO, COLUMNA_ETIQUETA

# Columnas con el código -1 = "no aplica" (ventana TCP inicial inexistente)
COLUMNAS_SENTINELA = ["Init_Win_bytes_forward", "Init_Win_bytes_backward"]

# Columnas de tasa donde viven todos los Inf/NaN del dataset
COLUMNAS_TASA = ["Flow Bytes/s", "Flow Packets/s"]


def limpiar(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Aplica las decisiones de limpieza aprobadas y reporta cada paso."""
    n0 = len(df)

    # 1. Duplicados exactos (sin considerar el archivo de origen)
    columnas_dato = [c for c in df.columns if c != "archivo_origen"]
    df = df.loc[~df.duplicated(subset=columnas_dato)]
    n1 = len(df)

    # 2. Inf/NaN en las columnas de tasa
    tasas = df[COLUMNAS_TASA]
    mascara_valida = ~(tasas.isna().any(axis=1) | np.isinf(tasas).any(axis=1))
    df = df.loc[mascara_valida]
    n2 = len(df)

    # 3. Duraciones negativas (físicamente imposibles)
    df = df.loc[df["Flow Duration"] >= 0]
    n3 = len(df)

    # 4. Código -1 = "no aplica": se crea un indicador binario y el -1 pasa a 0
    df = df.copy()
    for col in COLUMNAS_SENTINELA:
        df[f"{col}_no_aplica"] = (df[col] == -1).astype(np.int8)
        df[col] = df[col].where(df[col] != -1, 0)

    # 5. Features constantes (calculadas sobre los datos, no hardcodeadas)
    numericas = df.select_dtypes(include=[np.number])
    constantes = numericas.columns[numericas.nunique() <= 1].tolist()
    df = df.drop(columns=constantes)

    # Verificación final: no debe quedar ningún Inf ni NaN en el dataset
    numericas = df.select_dtypes(include=[np.number])
    restantes = int(np.isinf(numericas).sum().sum() + df.isna().sum().sum())
    if restantes > 0:
        raise ValueError(f"Quedaron {restantes} Inf/NaN tras la limpieza; revisar.")

    if verbose:
        print(f"Filas iniciales:                     {n0:,}")
        print(f"  - duplicados eliminados:           {n0 - n1:,} ({100 * (n0 - n1) / n0:.2f}%)")
        print(f"  - filas con Inf/NaN eliminadas:    {n1 - n2:,}")
        print(f"  - duraciones negativas eliminadas: {n2 - n3:,}")
        print(f"Filas finales:                       {len(df):,} ({100 * len(df) / n0:.2f}% del original)")
        print(f"Features constantes eliminadas ({len(constantes)}): {constantes}")
        print(f"Indicadores creados: {[f'{c}_no_aplica' for c in COLUMNAS_SENTINELA]}")
        print(f"Columnas finales: {df.shape[1]}")
        print("\nDistribución de clases tras la limpieza:")
        conteo = df[COLUMNA_ETIQUETA].value_counts()
        for clase, n in conteo.items():
            print(f"  {clase}: {n:,} ({100 * n / len(df):.4f}%)")

    return df


def main() -> None:
    df = pd.read_parquet(ARCHIVO_CONSOLIDADO)
    df = limpiar(df)
    ARCHIVO_LIMPIO.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(ARCHIVO_LIMPIO, index=False)
    print(f"\nGuardado en {ARCHIVO_LIMPIO} ({ARCHIVO_LIMPIO.stat().st_size / 1024**2:,.0f} MB)")


if __name__ == "__main__":
    main()
