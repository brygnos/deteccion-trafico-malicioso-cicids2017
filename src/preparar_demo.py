"""Archivos de demostración del tablero (prototipo).

Produce en data/demo/ dos demostraciones, cada una con sus etiquetas aparte:

- flujos_demo.csv: ~500 flujos con muchos tipos de ataque (40% de ataque y los
  14 tipos presentes), para mostrar todo lo que la herramienta detecta.
- flujos_demo_realista.csv: ~500 flujos con ~5% de ataque, que es la
  proporción realista de un lote típico, para mostrar cuánto trabajo ahorra
  (así la reducción de la carga de revisión de R5 no queda subestimada).

Las dos salen del conjunto de prueba (el modelo nunca vio esos flujos, así que
la demostración es honesta) y se guardan en el esquema crudo completo de
CICFlowMeter: los nombres originales con sus espacios, la columna
'Fwd Header Length' repetida, las 8 columnas constantes y el código -1 de
Init_Win_bytes restaurado, y sin la columna de etiqueta. Las etiquetas
verdaderas quedan en etiquetas_demo*.csv, archivos que el tablero nunca lee y
que sirven solo para verificar y narrar la demostración.

Es material de demostración: aquí no se calcula ninguna métrica ni se ajusta
nada. Requiere data/raw/ (lee el encabezado y los dtypes reales de un CSV
crudo para reconstruir el esquema).

Ejecutar desde la raíz del proyecto:
    python -m src.preparar_demo
"""

import numpy as np
import pandas as pd

from src.config import ARCHIVO_TEST, COLUMNA_ETIQUETA, RANDOM_STATE, RUTA_DATOS
from src.carga import listar_archivos_crudos

RUTA_DEMO = RUTA_DATOS / "demo"

# Demo "rica en ataques" (~40%): muestra la variedad de lo que se detecta,
# con las clases raras incluidas para narrar el detector de anomalías.
COMPOSICION = {
    "BENIGN": 300,
    "DoS Hulk": 40,
    "DDoS": 30,
    "PortScan": 30,
    "DoS GoldenEye": 15,
    "FTP-Patator": 10,
    "DoS slowloris": 10,
    "DoS Slowhttptest": 10,
    "SSH-Patator": 10,
    "Bot": 20,
    "Web Attack - Brute Force": 12,
    "Web Attack - XSS": 6,
    "Web Attack - Sql Injection": 2,
    "Infiltration": 3,
    "Heartbleed": 1,
}

# Demo "realista" (~5% de ataque): la proporción típica de un lote real, para
# que la reducción de carga de revisión (R5) se vea en su magnitud verdadera.
COMPOSICION_REALISTA = {
    "BENIGN": 475,
    "DoS Hulk": 8,
    "PortScan": 5,
    "DDoS": 4,
    "DoS GoldenEye": 2,
    "FTP-Patator": 1,
    "SSH-Patator": 1,
    "DoS slowloris": 1,
    "Bot": 1,
    "Web Attack - Brute Force": 1,
    "Infiltration": 1,
}

SENTINELAS = ["Init_Win_bytes_forward", "Init_Win_bytes_backward"]


def _normalizar(nombre: str) -> str:
    return " ".join(str(nombre).split())


def generar(composicion: dict, nombre_flujos: str, nombre_etiquetas: str) -> None:
    """Genera una demostración (flujos sin etiqueta + etiquetas aparte)."""
    archivo_flujos = RUTA_DEMO / nombre_flujos
    archivo_etiquetas = RUTA_DEMO / nombre_etiquetas

    # 1. Muestra estratificada del conjunto de prueba (semilla fija)
    test = pd.read_parquet(ARCHIVO_TEST)
    partes = []
    for clase, n in composicion.items():
        filas = test[test[COLUMNA_ETIQUETA] == clase]
        if len(filas) < n:
            raise ValueError(f"{clase}: se pidieron {n} y el test solo tiene {len(filas)}")
        partes.append(filas.sample(n=n, random_state=RANDOM_STATE))
    muestra = (
        pd.concat(partes)
        .sample(frac=1, random_state=RANDOM_STATE)  # barajar el orden
        .reset_index(drop=True)
    )

    # 2. Restaurar el código -1 donde el indicador dice "no aplica"
    muestra = muestra.copy()
    for col in SENTINELAS:
        indicador = f"{col}_no_aplica"
        muestra[col] = np.where(muestra[indicador] == 1, -1, muestra[col])

    # 3. Esquema crudo real: encabezado, dtypes y valores constantes tomados
    #    de un CSV crudo (no se hardcodea nada)
    ruta_cruda = listar_archivos_crudos()[0]
    crudo = pd.read_csv(ruta_cruda, nrows=5000, low_memory=False)
    columnas_crudas = [c for c in crudo.columns if _normalizar(c).rstrip(".1") != "Label"]

    demo = pd.DataFrame(index=muestra.index)
    for col_cruda in columnas_crudas:
        n = _normalizar(col_cruda)
        base = n[:-2] if n.endswith(".1") else n  # pandas renombra la repetida
        if base in muestra.columns:
            valores = muestra[base].to_numpy()
        else:
            unicos = crudo[col_cruda].unique()
            if len(unicos) != 1:
                raise ValueError(f"columna cruda no mapeable: {col_cruda!r}")
            valores = np.full(len(muestra), unicos[0])  # las 8 constantes
        if pd.api.types.is_integer_dtype(crudo[col_cruda]):
            valores = np.round(valores).astype(np.int64)
        demo[col_cruda] = valores

    # Restaurar el nombre repetido tal como viene en el CSV original
    demo.columns = [c[:-2] if _normalizar(c).endswith(".1") else c for c in demo.columns]

    demo.to_csv(archivo_flujos, index=False)
    # La fila se numera desde 1, igual que la columna "Fila del archivo" del tablero
    etiquetas = muestra[[COLUMNA_ETIQUETA]].rename(columns={COLUMNA_ETIQUETA: "etiqueta_real"})
    etiquetas.index = etiquetas.index + 1
    etiquetas.to_csv(archivo_etiquetas, index_label="fila")

    n_ataque = int((muestra[COLUMNA_ETIQUETA] != "BENIGN").sum())
    print(f"{nombre_flujos}: {len(demo)} filas x {demo.shape[1]} columnas "
          f"({archivo_flujos.stat().st_size / 1024:.0f} KB) | "
          f"{n_ataque} ataques ({100 * n_ataque / len(demo):.1f}%)")
    print(f"{nombre_etiquetas}: {len(muestra)} etiquetas (el tablero nunca lo lee)")
    print(muestra[COLUMNA_ETIQUETA].value_counts().to_string())
    print()


def main() -> None:
    RUTA_DEMO.mkdir(parents=True, exist_ok=True)
    generar(COMPOSICION, "flujos_demo.csv", "etiquetas_demo.csv")
    generar(COMPOSICION_REALISTA, "flujos_demo_realista.csv", "etiquetas_demo_realista.csv")


if __name__ == "__main__":
    main()
