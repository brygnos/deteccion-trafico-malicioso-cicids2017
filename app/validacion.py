"""Ingesta y validación del archivo del usuario (R12) — todo en memoria (R18).

Recibe un archivo CSV con el esquema de CICFlowMeter (la herramienta estándar
que convierte tráfico de red en una tabla de flujos) y lo deja listo para
clasificar, reportando en lenguaje llano qué encontró ANTES de clasificar y
sin lanzar errores. Maneja sin romperse: archivo válido, con columnas
faltantes, vacío, y con valores inválidos.

Nada de lo que entra aquí se escribe a disco: el archivo llega como un buffer
en memoria y los resultados viven solo en la sesión.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.formato import formatear

# Columnas con el código -1 = "no aplica", del que se derivan indicadores
SENTINELAS = ["Init_Win_bytes_forward", "Init_Win_bytes_backward"]


@dataclass
class ResultadoValidacion:
    """Lo que la interfaz necesita mostrar antes de clasificar."""

    bloqueado: bool = False
    mensajes: list = field(default_factory=list)  # tuplas (nivel, texto llano)
    datos: pd.DataFrame | None = None  # listo para clasificar (o None)
    filas_leidas: int = 0
    filas_validas: int = 0
    filas_excluidas: int = 0


def _normalizar(nombre: str) -> str:
    return " ".join(str(nombre).split())


def validar_y_preparar(archivo, caracteristicas: list[str]) -> ResultadoValidacion:
    """Valida el CSV y lo prepara para el modelo. Nunca lanza una excepción.

    `archivo` es un objeto tipo archivo (el buffer en memoria que entrega el
    cargador) o una ruta. `caracteristicas` es la lista ordenada de las 48
    características que los modelos esperan (de models/metadatos.json).
    """
    r = ResultadoValidacion()

    # --- 1. Leer el archivo sin romperse ---
    try:
        df = pd.read_csv(archivo, low_memory=False, encoding_errors="replace")
    except pd.errors.EmptyDataError:
        r.bloqueado = True
        r.mensajes.append(("error", "El archivo está vacío: no trae ninguna fila ni encabezado."))
        return r
    except Exception:
        r.bloqueado = True
        r.mensajes.append(
            ("error",
             "No se pudo leer el archivo como CSV. Verifica que sea un archivo "
             "de texto separado por comas, como los que produce CICFlowMeter.")
        )
        return r

    r.filas_leidas = len(df)
    if len(df) == 0:
        r.bloqueado = True
        r.mensajes.append(("error", "El archivo trae encabezado pero ninguna fila de datos."))
        return r

    # --- 2. Normalizar nombres (espacios) y columnas repetidas ---
    df.columns = [_normalizar(c) for c in df.columns]
    # pandas renombra la segunda aparición como '<nombre>.1': es la columna
    # repetida que trae el esquema original; se conserva la primera
    repetidas = [c for c in df.columns if c.endswith(".1") and c[:-2] in df.columns]
    if repetidas:
        df = df.drop(columns=repetidas)
        r.mensajes.append(
            ("info",
             "El archivo trae una columna repetida (algo normal en el esquema de "
             "CICFlowMeter); se conservó la primera aparición.")
        )
    df = df.loc[:, ~df.columns.duplicated()]

    # --- 3. Si viene la columna de etiqueta, se ignora (y se avisa) ---
    if "Label" in df.columns:
        df = df.drop(columns=["Label"])
        r.mensajes.append(
            ("info",
             "El archivo trae una columna de etiqueta ('Label'). El tablero no "
             "la usa: clasifica cada flujo por su cuenta, sin mirar respuestas.")
        )

    # --- 4. ¿Están las características que el modelo necesita? ---
    # Los dos indicadores *_no_aplica no vienen en el archivo: se derivan aquí
    # del código -1, tal como se hizo al entrenar.
    requeridas = [c for c in caracteristicas if not c.endswith("_no_aplica")]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        r.bloqueado = True
        muestra = ", ".join(faltantes[:8]) + (" …" if len(faltantes) > 8 else "")
        r.mensajes.append(
            ("error",
             f"Faltan {formatear(len(faltantes))} de las {formatear(len(requeridas))} características "
             f"que el modelo necesita (por ejemplo: {muestra}). Esto suele pasar "
             "cuando el archivo no fue generado con CICFlowMeter o se recortaron "
             "columnas. No se puede clasificar sin ellas.")
        )
        return r

    extras = [c for c in df.columns if c not in requeridas]
    if extras:
        r.mensajes.append(
            ("info",
             f"El archivo trae {formatear(len(extras))} columnas adicionales que el modelo "
             "no usa; se ignoraron sin problema.")
        )

    # --- 5. Valores inválidos: convertir a número y contar lo no convertible ---
    df = df[requeridas].copy()
    no_numericos = 0
    for c in requeridas:
        if not pd.api.types.is_numeric_dtype(df[c]):
            antes = df[c].notna().sum()
            df[c] = pd.to_numeric(df[c], errors="coerce")
            no_numericos += int(antes - df[c].notna().sum())
    if no_numericos:
        r.mensajes.append(
            ("advertencia",
             f"Se encontraron {formatear(no_numericos)} valores que no son números (texto "
             "donde debía haber una cifra); se tratan como inválidos.")
        )

    # --- 6. Derivar los indicadores del código -1 (igual que en el análisis) ---
    for col in SENTINELAS:
        indicador = f"{col}_no_aplica"
        if indicador in caracteristicas:
            df[indicador] = (df[col] == -1).astype(np.int8)
            df[col] = df[col].where(df[col] != -1, 0)

    # --- 7. Excluir filas con valores faltantes o infinitos ---
    valores = df[caracteristicas]
    invalidas = valores.isna().any(axis=1) | np.isinf(valores).any(axis=1)
    r.filas_excluidas = int(invalidas.sum())
    if r.filas_excluidas:
        filas_afectadas = (df.index[invalidas] + 1).tolist()
        muestra_filas = ", ".join(map(str, filas_afectadas[:10]))
        if len(filas_afectadas) > 10:
            muestra_filas += " …"
        r.mensajes.append(
            ("advertencia",
             f"{formatear(r.filas_excluidas)} de {formatear(r.filas_leidas)} filas traen valores "
             "faltantes o infinitos en características que el modelo necesita; "
             "se excluyen de la clasificación (es más honesto que inventarles "
             f"un valor). Filas afectadas: {muestra_filas}.")
        )
    df = df.loc[~invalidas]

    if len(df) == 0:
        r.bloqueado = True
        r.mensajes.append(
            ("error",
             "Ninguna fila quedó utilizable: todas traen valores faltantes o "
             "inválidos en las características que el modelo necesita.")
        )
        return r

    r.filas_validas = len(df)
    r.datos = df
    r.mensajes.insert(
        0,
        ("ok",
         f"Archivo válido: {formatear(r.filas_validas)} de {formatear(r.filas_leidas)} filas "
         "listas para clasificar."),
    )
    return r
