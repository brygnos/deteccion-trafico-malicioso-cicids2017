"""Configuración central del proyecto.

Todas las rutas y constantes compartidas viven aquí para que los notebooks
y scripts no las repitan ni las hardcodeen.
"""

from pathlib import Path

# Raíz del proyecto (carpeta que contiene src/, data/, notebooks/, ...)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

RUTA_DATOS = RAIZ_PROYECTO / "data"
RUTA_RAW = RUTA_DATOS / "raw"
RUTA_INTERIM = RUTA_DATOS / "interim"
RUTA_PROCESSED = RUTA_DATOS / "processed"
RUTA_REPORTES = RAIZ_PROYECTO / "reports"
RUTA_FIGURAS = RUTA_REPORTES / "figures"

# Semilla única para todo el proyecto (reproducibilidad total)
RANDOM_STATE = 42

# Nombre de la columna objetivo después de normalizar los nombres de columna
COLUMNA_ETIQUETA = "Label"
ETIQUETA_BENIGNA = "BENIGN"

# Archivo consolidado que produce la fase de preparación
ARCHIVO_CONSOLIDADO = RUTA_PROCESSED / "cicids2017_consolidado.parquet"

# Fase 2: dataset limpio (las decisiones de limpieza están en la sección 4 de reports/reporte_tecnico_final.pdf, Cuadro 3)
ARCHIVO_LIMPIO = RUTA_INTERIM / "cicids2017_limpio.parquet"

# Fase 2: split único train/test (test apartado hasta el final del proyecto)
ARCHIVO_TRAIN = RUTA_PROCESSED / "train.parquet"
ARCHIVO_TEST = RUTA_PROCESSED / "test.parquet"
PROPORCION_TEST = 0.2
