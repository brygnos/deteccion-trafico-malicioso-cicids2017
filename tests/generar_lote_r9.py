"""Genera el lote de 50.000 flujos para medir R9 (tiempo de respuesta y volumen
soportado) en el tablero desplegado.

Repite las filas de la demo rica en ataques (data/demo/flujos_demo.csv) hasta
llegar a 50.000 flujos y guarda el resultado en data/interim/lote_r9_50k.csv,
que no se versiona. Copia las líneas tal cual, sin pasar por pandas, para que
el lote conserve exactamente el formato de CICFlowMeter de la demo.

El lote sirve solo para medir tiempos: sus flujos son copias de la demo, así
que no dice nada nuevo sobre el desempeño del modelo.

Ejecutar desde la raíz del proyecto (sirve cualquier Python 3):
    python tests/generar_lote_r9.py
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "data" / "demo" / "flujos_demo.csv"
DESTINO = RAIZ / "data" / "interim" / "lote_r9_50k.csv"
FILAS_OBJETIVO = 50_000


def main() -> None:
    lineas = ORIGEN.read_text(encoding="utf-8").splitlines()
    encabezado, filas = lineas[0], [l for l in lineas[1:] if l.strip()]

    copias, resto = divmod(FILAS_OBJETIVO, len(filas))
    lote = filas * copias + filas[:resto]

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text("\n".join([encabezado, *lote]) + "\n", encoding="utf-8")

    n_filas = f"{len(lote):,}".replace(",", ".")                    # 50.000
    megas = f"{DESTINO.stat().st_size / 2**20:.1f}".replace(".", ",")  # decimal con coma
    print(f"{n_filas} filas ({copias} copias completas de las {len(filas)} filas de la demo "
          f"y {resto} más) en {DESTINO.relative_to(RAIZ).as_posix()}: {megas} MB")


if __name__ == "__main__":
    main()
