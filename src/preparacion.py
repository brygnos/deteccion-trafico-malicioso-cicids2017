"""Consolidación de los CSV crudos de CIC-IDS2017 en un único Parquet.

Lo que hace esta fase: une los 8 CSV, normaliza los nombres de columna y las
etiquetas, elimina la columna 'Fwd Header Length' repetida (después de
verificar que es una copia exacta), agrega la columna 'archivo_origen' y
reduce los dtypes (de float64 a float32, y los enteros al tipo más pequeño que
no pierda datos).

Lo que no hace es eliminar filas. Los duplicados, Inf, NaN y negativos se
conservan tal cual, porque esas decisiones de limpieza se toman después del
EDA, con evidencia.

Ejecutar desde la raíz del proyecto:
    python -m src.preparacion
"""

import numpy as np
import pandas as pd

from src.carga import (
    leer_csv_crudo,
    listar_archivos_crudos,
    normalizar_etiquetas,
    normalizar_nombres_columnas,
)
from src.config import ARCHIVO_CONSOLIDADO, COLUMNA_ETIQUETA

# Nombre que pandas le da a la segunda aparición de 'Fwd Header Length'
COLUMNA_REPETIDA = "Fwd Header Length.1"
COLUMNA_ORIGINAL = "Fwd Header Length"


def _preparar_archivo(ruta) -> tuple[pd.DataFrame, float]:
    """Lee un CSV crudo y lo deja listo para concatenar.

    Devuelve el DataFrame preparado y la memoria (MB) que ocupaba con los
    dtypes originales, para poder reportar el ahorro del downcast.
    """
    df = leer_csv_crudo(ruta)
    memoria_original_mb = df.memory_usage(deep=True).sum() / 1024**2

    df = normalizar_nombres_columnas(df)

    # La columna 'Fwd Header Length' viene dos veces en los CSV originales.
    # Solo se elimina la copia si es idéntica a la original (verificado).
    if COLUMNA_REPETIDA in df.columns:
        if not df[COLUMNA_REPETIDA].equals(df[COLUMNA_ORIGINAL]):
            raise ValueError(
                f"{ruta.name}: '{COLUMNA_REPETIDA}' NO es copia exacta de "
                f"'{COLUMNA_ORIGINAL}'; revisar antes de eliminar."
            )
        df = df.drop(columns=[COLUMNA_REPETIDA])

    df[COLUMNA_ETIQUETA] = normalizar_etiquetas(df[COLUMNA_ETIQUETA])

    # Downcast: los floats pasan a float32 y los enteros al tipo más pequeño sin pérdida.
    for col in df.columns:
        if df[col].dtype == np.float64:
            df[col] = df[col].astype(np.float32)
        elif np.issubdtype(df[col].dtype, np.integer):
            df[col] = pd.to_numeric(df[col], downcast="integer")

    df["archivo_origen"] = ruta.name
    return df, memoria_original_mb


def consolidar(verbose: bool = True) -> pd.DataFrame:
    """Une todos los CSV de data/raw/ y guarda el Parquet consolidado."""
    partes = []
    memoria_original_total = 0.0
    for ruta in listar_archivos_crudos():
        df, memoria_mb = _preparar_archivo(ruta)
        memoria_original_total += memoria_mb
        if verbose:
            print(f"  {ruta.name}: {len(df):,} filas ({memoria_mb:,.0f} MB crudos)")
        partes.append(df)

    consolidado = pd.concat(partes, ignore_index=True)
    del partes

    consolidado[COLUMNA_ETIQUETA] = consolidado[COLUMNA_ETIQUETA].astype("category")
    consolidado["archivo_origen"] = consolidado["archivo_origen"].astype("category")

    memoria_final_mb = consolidado.memory_usage(deep=True).sum() / 1024**2
    if verbose:
        print(f"\nFilas totales: {len(consolidado):,}")
        print(f"Columnas: {consolidado.shape[1]} (79 crudas - 1 repetida + archivo_origen)")
        print(f"Memoria con dtypes originales: {memoria_original_total:,.0f} MB")
        print(f"Memoria tras downcast:         {memoria_final_mb:,.0f} MB")

    ARCHIVO_CONSOLIDADO.parent.mkdir(parents=True, exist_ok=True)
    consolidado.to_parquet(ARCHIVO_CONSOLIDADO, index=False)
    if verbose:
        tamano_mb = ARCHIVO_CONSOLIDADO.stat().st_size / 1024**2
        print(f"Guardado en {ARCHIVO_CONSOLIDADO} ({tamano_mb:,.0f} MB en disco)")

    return consolidado


if __name__ == "__main__":
    consolidar()
