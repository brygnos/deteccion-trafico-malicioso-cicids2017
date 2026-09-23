"""Diagnóstico de calidad de datos para los flujos de CIC-IDS2017.

Cuantifica las trampas conocidas del dataset: valores infinitos, faltantes,
negativos en columnas que no deberían tenerlos y filas duplicadas.
"""

import numpy as np
import pandas as pd


def resumen_calidad(df: pd.DataFrame) -> dict:
    """Resumen global de calidad: Inf, NaN, negativos y duplicados.

    Devuelve un dict con conteos totales y por columna (solo columnas
    afectadas), pensado para imprimirse o tabularse en el EDA.
    """
    numericas = df.select_dtypes(include=[np.number])

    inf_por_col = numericas.apply(lambda c: np.isinf(c).sum())
    inf_por_col = inf_por_col[inf_por_col > 0].sort_values(ascending=False)

    nan_por_col = df.isna().sum()
    nan_por_col = nan_por_col[nan_por_col > 0].sort_values(ascending=False)

    neg_por_col = numericas.apply(lambda c: (c < 0).sum())
    neg_por_col = neg_por_col[neg_por_col > 0].sort_values(ascending=False)

    n_duplicadas = int(df.duplicated().sum())

    return {
        "filas": len(df),
        "columnas": df.shape[1],
        "inf_total": int(inf_por_col.sum()),
        "inf_por_columna": inf_por_col,
        "nan_total": int(nan_por_col.sum()),
        "nan_por_columna": nan_por_col,
        "negativos_total": int(neg_por_col.sum()),
        "negativos_por_columna": neg_por_col,
        "filas_duplicadas": n_duplicadas,
        "memoria_mb": float(df.memory_usage(deep=True).sum() / 1024**2),
    }


def imprimir_resumen(nombre: str, resumen: dict, max_columnas: int = 5) -> None:
    """Imprime un resumen de calidad en formato compacto y legible."""
    print(f"--- {nombre} ---")
    print(
        f"  filas={resumen['filas']:,}  columnas={resumen['columnas']}  "
        f"memoria={resumen['memoria_mb']:.1f} MB"
    )
    print(
        f"  Inf={resumen['inf_total']:,}  NaN={resumen['nan_total']:,}  "
        f"negativos={resumen['negativos_total']:,}  "
        f"duplicadas={resumen['filas_duplicadas']:,}"
    )
    for etiqueta, clave in [
        ("Inf", "inf_por_columna"),
        ("NaN", "nan_por_columna"),
        ("negativos", "negativos_por_columna"),
    ]:
        serie = resumen[clave]
        if len(serie) > 0:
            top = ", ".join(
                f"{col}={n:,}" for col, n in serie.head(max_columnas).items()
            )
            extra = f" (+{len(serie) - max_columnas} cols más)" if len(serie) > max_columnas else ""
            print(f"  {etiqueta} por columna: {top}{extra}")
