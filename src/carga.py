"""Carga de los CSV crudos de CIC-IDS2017.

Los archivos crudos tienen trampas conocidas (nombres de columna con espacios,
codificación no UTF-8 en algunos días, valores Inf/NaN). Estas funciones
centralizan la lectura para que ningún notebook tenga que lidiar con eso.
"""

from pathlib import Path

import pandas as pd

from src.config import RUTA_RAW


def listar_archivos_crudos() -> list[Path]:
    """Devuelve la lista ordenada de CSV presentes en data/raw/.

    No asume nombres ni cantidad: lee lo que realmente exista en disco.
    """
    return sorted(RUTA_RAW.glob("*.csv"))


def leer_csv_crudo(ruta: Path, nrows: int | None = None) -> pd.DataFrame:
    """Lee un CSV crudo sin modificar los nombres de columna ni los valores.

    Intenta UTF-8 y, si el archivo trae caracteres de Windows (pasa en el
    archivo de ataques web, cuyas etiquetas usan un guion cp1252), vuelve a
    intentar con cp1252. `nrows` permite leer solo una muestra.
    """
    try:
        return pd.read_csv(ruta, nrows=nrows, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(ruta, nrows=nrows, low_memory=False, encoding="cp1252")


def normalizar_nombres_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Quita los espacios al inicio y al final de los nombres y colapsa los internos.

    Por ejemplo, ' Flow Duration' queda como 'Flow Duration'.
    """
    df = df.copy()
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    return df


def normalizar_etiquetas(serie: pd.Series) -> pd.Series:
    """Limpia la columna de etiqueta: espacios sobrantes y guiones raros.

    Las etiquetas de ataques web del jueves traen un carácter dañado en vez
    de guion (el CSV original contiene el carácter Unicode de reemplazo
    U+FFFD, p. ej. 'Web Attack � Brute Force'); se sustituye por un
    guion ASCII para que los nombres sean consistentes en tablas y gráficas.
    """
    return (
        serie.astype(str)
        .str.strip()
        .str.replace("�", "-", regex=False)  # carácter de reemplazo Unicode
        .str.replace("–", "-", regex=False)  # guion en (–), por si acaso
        .str.replace("\x96", "-", regex=False)  # mismo guion leído como latin-1
        .str.replace(r"\s+", " ", regex=True)
    )
