"""Selección de features (Fase 2). La decisión se tomó solo con el conjunto de entrenamiento.

Sobre una muestra de 500.000 flujos del conjunto de entrenamiento (semilla 42)
se calcularon las correlaciones absolutas entre las 71 features numéricas del
dataset limpio. Los 45 pares con |r| > 0.95 forman 13 grupos de features que
miden (casi) lo mismo, y de cada grupo se conserva una sola representante,
elegida por interpretabilidad: el nombre más fácil de explicar a un jurado que
no es experto en redes. El resto se elimina porque dos columnas idénticas se
"reparten" la importancia en los modelos y ensucian la interpretación.

Resultado: 71 - 23 eliminadas = 48 features finales.

Los grupos se pueden volver a calcular con `calcular_grupos()` para verificar
que la lista de abajo corresponde a los datos (reproducibilidad).
"""

from collections import defaultdict

import numpy as np
import pandas as pd

from src.config import RANDOM_STATE

# Cada grupo: features con |r|>0.95 entre sí en el train, la representante
# conservada y la razón de la elección.
GRUPOS_CORRELACIONADOS = [
    {
        "representante": "Total Fwd Packets",
        "eliminadas": [
            "Total Backward Packets",
            "Subflow Fwd Packets",
            "Subflow Bwd Packets",
            "Subflow Bwd Bytes",
            "Total Length of Bwd Packets",
            "act_data_pkt_fwd",
        ],
        "razon": "Todas cuentan volumen de la conversación y se mueven juntas; "
        "'paquetes enviados por el origen' es el conteo más directo. Las "
        "'Subflow *' son alias exactos de los totales.",
    },
    {
        "representante": "Flow IAT Max",
        "eliminadas": ["Fwd IAT Max", "Idle Max", "Idle Mean", "Idle Min"],
        "razon": "Todas capturan el mayor silencio dentro de la conversación; "
        "'Flow IAT Max' es la versión global.",
    },
    {
        "representante": "Bwd Packet Length Mean",
        "eliminadas": ["Avg Bwd Segment Size", "Bwd Packet Length Max", "Bwd Packet Length Std"],
        "razon": "Tamaño de los paquetes de respuesta; 'Avg Bwd Segment Size' es "
        "un alias exacto de la media, y máximo/desviación van casi pegados a ella.",
    },
    {
        "representante": "Total Length of Fwd Packets",
        "eliminadas": ["Subflow Fwd Bytes"],
        "razon": "Alias exacto (r=1.000); se conserva el nombre directo: bytes "
        "enviados por el origen.",
    },
    {
        "representante": "Fwd Packet Length Mean",
        "eliminadas": ["Avg Fwd Segment Size"],
        "razon": "Alias exacto (r=1.000) del tamaño medio de paquete de ida.",
    },
    {
        "representante": "Fwd URG Flags",
        "eliminadas": ["CWE Flag Count"],
        "razon": "Idénticas en los datos (r=1.000); se conserva la bandera TCP "
        "estándar (URG), mejor documentada que el conteo 'CWE'.",
    },
    {
        "representante": "SYN Flag Count",
        "eliminadas": ["Fwd PSH Flags"],
        "razon": "Idénticas en los datos (r=1.000); SYN (inicio de conexión) es "
        "clave para explicar escaneos de puertos.",
    },
    {
        "representante": "RST Flag Count",
        "eliminadas": ["ECE Flag Count"],
        "razon": "Idénticas en los datos (r=1.000); RST (conexión rechazada/cortada) "
        "es la más interpretable.",
    },
    {
        "representante": "Flow Duration",
        "eliminadas": ["Fwd IAT Total"],
        "razon": "r=0.999; la duración de la conversación es la feature más "
        "fácil de explicar del dataset.",
    },
    {
        "representante": "Packet Length Mean",
        "eliminadas": ["Average Packet Size"],
        "razon": "r=0.998; son dos fórmulas casi iguales del tamaño medio de paquete.",
    },
    {
        "representante": "Max Packet Length",
        "eliminadas": ["Packet Length Std"],
        "razon": "r=0.984; el máximo es más directo de explicar que la desviación.",
    },
    {
        "representante": "Flow Packets/s",
        "eliminadas": ["Fwd Packets/s"],
        "razon": "r=0.983; se conserva el ritmo global de la conversación.",
    },
    {
        "representante": "Fwd Packet Length Max",
        "eliminadas": ["Fwd Packet Length Std"],
        "razon": "r=0.969; mismo criterio: máximo antes que desviación.",
    },
]

# Lista plana de las 23 features descartadas por redundancia
FEATURES_ELIMINADAS = [c for g in GRUPOS_CORRELACIONADOS for c in g["eliminadas"]]


def features_finales(df: pd.DataFrame) -> list[str]:
    """Features a usar en los modelos: numéricas del dataset limpio menos
    las redundantes. Se lee del DataFrame para no hardcodear columnas."""
    numericas = df.select_dtypes(include=[np.number]).columns
    return [c for c in numericas if c not in FEATURES_ELIMINADAS]


def calcular_grupos(
    df: pd.DataFrame, umbral: float = 0.95, n_muestra: int = 500_000
) -> list[set[str]]:
    """Vuelve a calcular los grupos de features correlacionadas (verificación).

    Devuelve las componentes conexas del grafo cuyos arcos son los pares de
    features numéricas con |r| > umbral, calculado sobre una muestra
    reproducible de `df` (que debe ser el conjunto de entrenamiento).
    """
    muestra = df.sample(n=min(n_muestra, len(df)), random_state=RANDOM_STATE)
    num = muestra.select_dtypes(include=[np.number])
    corr = num.corr().abs()
    pares = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
    pares_altos = pares[pares > umbral]

    padre: dict[str, str] = {}

    def find(x: str) -> str:
        padre.setdefault(x, x)
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    for a, b in pares_altos.index:
        padre[find(a)] = find(b)

    grupos = defaultdict(set)
    for col in padre:
        grupos[find(col)].add(col)
    return sorted(grupos.values(), key=len, reverse=True)
