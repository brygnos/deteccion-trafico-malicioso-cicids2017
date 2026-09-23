"""Fixtures compartidos por las pruebas de requerimientos.

Todo lo que se carga aquí sale del repositorio (models/, data/demo/,
reports/resultados_*/): las pruebas corren en cualquier equipo que tenga el
entorno de la app instalado. Las que necesitan los datos grandes (que no
viajan con el repo) se marcan `datos_locales` y se omiten si faltan.
"""

import io
from pathlib import Path

import pandas as pd
import pytest

from app import nucleo, validacion

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DEMO = RAIZ / "data" / "demo"
RUTA_FINAL = RAIZ / "reports" / "resultados_final"
RUTA_FASE3 = RAIZ / "reports" / "resultados_fase3"
RUTA_FASE4 = RAIZ / "reports" / "resultados_fase4"
RUTA_TRAIN = RAIZ / "data" / "processed" / "train.parquet"
RUTA_LIMPIO = RAIZ / "data" / "interim" / "cicids2017_limpio.parquet"


@pytest.fixture(scope="session")
def recursos():
    """Los tres modelos, metadatos y métricas fijas, cargados una vez."""
    return nucleo.cargar_recursos()


@pytest.fixture(scope="session")
def caracteristicas(recursos):
    return recursos["meta"]["caracteristicas"]


@pytest.fixture(scope="session")
def demo_rica(recursos, caracteristicas):
    """Demo rica en ataques (499 flujos del test) validada y clasificada."""
    reporte = validacion.validar_y_preparar(RUTA_DEMO / "flujos_demo.csv", caracteristicas)
    assert not reporte.bloqueado, "la demo rica debe validar limpia"
    return {"reporte": reporte, "resultado": nucleo.clasificar(reporte.datos, recursos)}


@pytest.fixture(scope="session")
def demo_realista(recursos, caracteristicas):
    """Demo de proporción realista (500 flujos, 5 % de ataque)."""
    reporte = validacion.validar_y_preparar(
        RUTA_DEMO / "flujos_demo_realista.csv", caracteristicas
    )
    assert not reporte.bloqueado
    return {"reporte": reporte, "resultado": nucleo.clasificar(reporte.datos, recursos)}


@pytest.fixture(scope="session")
def demo_crudo():
    """El CSV de demo tal cual (esquema crudo), para fabricar variantes."""
    return pd.read_csv(RUTA_DEMO / "flujos_demo.csv", low_memory=False)


def como_archivo(df: pd.DataFrame) -> io.StringIO:
    """Convierte un DataFrame en un archivo CSV en memoria (como el cargador)."""
    return io.StringIO(df.to_csv(index=False))


@pytest.fixture(scope="session")
def metricas_test():
    """Macro-F1 de la evaluación única sobre el test, por variante y regla."""
    return pd.read_csv(RUTA_FINAL / "final_multiclase_macro.csv")


@pytest.fixture(scope="session")
def por_clase_test():
    return pd.read_csv(RUTA_FINAL / "final_multiclase_por_clase.csv")


@pytest.fixture(scope="session")
def confusion_final():
    return pd.read_csv(RUTA_FINAL / "final_confusion__con_puerto__umbral_bot.csv", index_col=0)
