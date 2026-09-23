"""Genera docs/diagrama_esquematico.png, el diagrama esquemático del prototipo.

Muestra lo que está construido, en dos franjas:

1. Construcción (se hizo una sola vez): de los 8 CSV crudos de CIC-IDS2017 a
   los tres modelos serializados en models/.
2. Operación (cada vez que se usa el tablero): del archivo del usuario, o de
   una de las demos, a las alertas priorizadas que filtra y exporta el analista.

Las cifras que existen en archivos del repositorio se leen de ellos
(models/metadatos.json, data/demo/ y el tamaño de models/). Las del dataset
completo no viajan con el repositorio y se copian del reporte técnico
(secciones 1, 4 y 5.1) y de tests/test_requerimientos.py, donde también se
verifican.

Ejecutar desde la raíz del proyecto, con el entorno del análisis:
    python docs/generar_diagrama.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "diagrama_esquematico.png"

# --- Cifras leídas de los archivos del repositorio ---------------------------
META = json.loads((RAIZ / "models" / "metadatos.json").read_text(encoding="utf-8"))
N_VARIABLES = len(META["caracteristicas"])                                   # 48
N_DERIVADAS = sum(c.endswith("_no_aplica") for c in META["caracteristicas"])  # 2
N_CLASES = len(META["clases_multiclase"])                                     # 11
UMBRAL_BOT = META["umbral_bot"]                                               # 0.999
CUANTILES = [float(q) * 100 for q in META["cuantiles_detector"]]              # 0,5 / 1 / 2


def _filas(nombre: str) -> int:
    with open(RAIZ / "data" / "demo" / nombre, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # sin el encabezado


FILAS_DEMO_RICA = _filas("flujos_demo.csv")               # 499
FILAS_DEMO_REALISTA = _filas("flujos_demo_realista.csv")  # 500
# En MB de 1.024 x 1.024 bytes, la misma convención del README (1,3 MB)
MB_MODELOS = sum(p.stat().st_size for p in (RAIZ / "models").glob("*")) / 2**20

# --- Cifras del dataset completo (reporte técnico §1, §4 y §5.1) -------------
FLUJOS_CRUDOS = 2_830_743
FLUJOS_LIMPIOS = 2_498_078
FLUJOS_ENTRENAMIENTO = 1_998_462
FLUJOS_PRUEBA = 499_616
VARIABLES_LIMPIAS = 71
FLUJOS_LUNES = 394_236  # tráfico benigno del lunes en el entrenamiento


def miles(n: int) -> str:
    """2830743 -> '2.830.743' (miles con punto, como en el resto del proyecto)."""
    return f"{n:,}".replace(",", ".")


def dec(x: float, d: int = 1) -> str:
    """Decimal con coma y sin ceros sobrantes: 0.5 -> '0,5', 1.0 -> '1'."""
    texto = f"{x:.{d}f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


# --- Estilo -----------------------------------------------------------------
COLORES = {
    "datos": ("#EEF1F5", "#6B7A90"),
    "proceso": ("#E3EEFB", "#2F6DB5"),
    "modelo": ("#E3F4EA", "#2E8B57"),
    "salida": ("#FFF1DC", "#C77C12"),
    "persona": ("#F1E8FA", "#7A4DB0"),
}
TINTA = "#1F2933"
GRIS = "#5B6573"


def caja(ax, x, y, w, h, titulo, cuerpo, tipo, discontinua=False):
    relleno, borde = COLORES[tipo]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.9",
        linewidth=1.6, edgecolor=borde, facecolor=relleno,
        linestyle="--" if discontinua else "-", zorder=2,
    ))
    ax.text(x + w / 2, y + h - 1.1, titulo, ha="center", va="top",
            fontsize=10.5, fontweight="bold", color=TINTA, zorder=3)
    ax.text(x + w / 2, y + h - 3.6, cuerpo, ha="center", va="top",
            fontsize=8.6, color=TINTA, linespacing=1.35, zorder=3)
    return (x, y, w, h)


def flecha(ax, origen, destino, texto=None, curva=0.0, desplazamiento=(0, 0.9),
           discontinua=False):
    ax.add_patch(FancyArrowPatch(
        origen, destino, arrowstyle="-|>", mutation_scale=15, linewidth=1.5,
        color=GRIS, connectionstyle=f"arc3,rad={curva}", zorder=1,
        linestyle="--" if discontinua else "-",
        shrinkA=2, shrinkB=2,
    ))
    if texto:
        mx = (origen[0] + destino[0]) / 2 + desplazamiento[0]
        my = (origen[1] + destino[1]) / 2 + desplazamiento[1]
        ax.text(mx, my, texto, ha="center", va="bottom", fontsize=8,
                color=GRIS, style="italic", zorder=3)


def derecha(b):
    x, y, w, h = b
    return (x + w + 0.3, y + h / 2)


def izquierda(b):
    x, y, w, h = b
    return (x - 0.3, y + h / 2)


def franja(ax, y, h, titulo, subtitulo):
    ax.add_patch(FancyBboxPatch(
        (0.8, y), 98.4, h, boxstyle="round,pad=0,rounding_size=1.2",
        linewidth=0, facecolor="#F7F8FA", zorder=0,
    ))
    ax.text(2.0, y + h - 1.0, titulo, ha="left", va="top", fontsize=13,
            fontweight="bold", color=TINTA)
    ax.text(2.0, y + h - 3.4, subtitulo, ha="left", va="top", fontsize=9.5,
            color=GRIS)


def main() -> None:
    fig, ax = plt.subplots(figsize=(18, 10.6))
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.95)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    fig.suptitle("Diagrama esquemático del Detector de tráfico malicioso",
                 fontsize=16, fontweight="bold", color=TINTA, y=0.99)

    # ================= 1. Construcción =================
    franja(ax, 32.5, 27.0, "1. Construcción",
           "Se hizo una sola vez, con el dataset CIC-IDS2017. Su resultado son los modelos guardados en models/.")

    w, h, y = 14.2, 13.5, 38.0
    xs = [2.2, 18.6, 35.0, 51.4, 67.8, 84.2]
    a1 = caja(ax, xs[0], y, w, h, "Datos crudos",
              "8 archivos CSV de CIC-IDS2017,\nuno por día o tramo\n"
              f"de la semana simulada\n\n{miles(FLUJOS_CRUDOS)} flujos", "datos")
    a2 = caja(ax, xs[1], y, w, h, "Limpieza",
              "Se quitan los flujos\nduplicados y los que tienen\nvalores infinitos o faltantes\n\n"
              f"Quedan {miles(FLUJOS_LIMPIOS)} flujos\ny {VARIABLES_LIMPIAS} variables", "proceso")
    a3 = caja(ax, xs[2], y, w, h, "Partición única",
              f"Entrenamiento: {miles(FLUJOS_ENTRENAMIENTO)}\nflujos (80%)\n\n"
              f"Prueba: {miles(FLUJOS_PRUEBA)} flujos\n(20%), apartados hasta\nla evaluación final", "proceso")
    a4 = caja(ax, xs[3], y, w, h, "Reducción de variables",
              f"De {VARIABLES_LIMPIAS} a {N_VARIABLES} variables:\nse deja una por cada grupo\nde variables que miden\ncasi lo mismo\n\n"
              "Decidida solo con\nel entrenamiento", "proceso")
    a5 = caja(ax, xs[4], y, w, h, "Entrenamiento",
              f"Multiclase: tipo de ataque\n({N_CLASES} clases, pesos de clase)\n\n"
              "Binario: ataque o no ataque\n\n"
              f"Detector de anomalías: solo\ncon el lunes normal\n({miles(FLUJOS_LUNES)} flujos)", "proceso")
    a6 = caja(ax, xs[5], y, w, h, "Modelos guardados",
              f"Los tres modelos\n(models/, {dec(MB_MODELOS)} MB)\n\n"
              f"Con sus metadatos: {N_VARIABLES}\nvariables, regla de Bot\n({dec(UMBRAL_BOT, 3)}) y umbrales del\n"
              f"detector ({' / '.join(dec(c) for c in CUANTILES)}%)", "modelo")
    for i, j in [(a1, a2), (a2, a3), (a3, a4), (a4, a5), (a5, a6)]:
        flecha(ax, derecha(i), izquierda(j))

    # El conjunto de prueba, aparte: evaluación única y origen de las demos
    prueba = caja(ax, xs[2] - 0.2, 33.6, w + 16.8, 3.2, "", "", "datos", discontinua=True)
    ax.text(prueba[0] + prueba[2] / 2, prueba[1] + prueba[3] / 2,
            "El conjunto de prueba se usó una sola vez, para la evaluación final,\n"
            "y de él se tomaron las dos demos del tablero",
            ha="center", va="center", fontsize=8.3, color=GRIS, style="italic", zorder=3)

    # ================= 2. Operación =================
    franja(ax, 1.0, 29.5, "2. Operación",
           "Cada vez que alguien usa el tablero. Todo ocurre en memoria: el archivo del usuario no se guarda.")

    yb, hb = 5.3, 17.2
    b1 = caja(ax, 2.2, yb, 14.2, hb, "Archivo de entrada",
              "Un CSV de flujos sin\netiquetar, con el esquema\nde CICFlowMeter\n\no una de las dos demos\n"
              f"integradas ({FILAS_DEMO_RICA} y {FILAS_DEMO_REALISTA} flujos)", "datos")
    b2 = caja(ax, 18.6, yb, 14.2, hb, "Validación del esquema",
              f"¿Están las {N_VARIABLES - N_DERIVADAS} medidas\nque el modelo necesita?\n\n"
              "Si falta alguna, lo dice\nen lenguaje llano y\nno clasifica", "proceso")
    b3 = caja(ax, 35.0, yb, 14.2, hb, "Depuración",
              "Excluye las filas con\nvalores faltantes, infinitos\no texto, y dice cuáles son\n\n"
              f"Deriva {N_DERIVADAS} indicadores y deja\nlas {N_VARIABLES} variables listas", "proceso")

    # Los tres modelos en paralelo
    xm, wm, hm = 53.0, 14.6, 5.1
    m1 = caja(ax, xm, 17.4, wm, hm, "Clasificador multiclase", "Tipo de ataque y confianza", "modelo")
    m2 = caja(ax, xm, 11.35, wm, hm, "Clasificador binario", "Ataque o no ataque", "modelo")
    m3 = caja(ax, xm, 5.3, wm, hm, "Detector de anomalías", "Marca de anomalía", "modelo")

    b5 = caja(ax, 71.6, yb, 12.4, hb, "Alertas priorizadas",
              "Cada flujo con su tipo,\nconfianza, veredicto\nbinario y marca de\nanomalía\n\n"
              "Cada alerta explicada\ncon las 8 variables\nque más pesaron", "salida")
    b6 = caja(ax, 86.6, yb, 12.0, hb, "Analista",
              "Filtra por tipo de\nataque, confianza y\nmarca de anomalía\n\n"
              "Exporta en CSV y\ndecide qué investigar", "persona")

    flecha(ax, derecha(b1), izquierda(b2))
    flecha(ax, derecha(b2), izquierda(b3))
    for m in (m1, m2, m3):
        flecha(ax, derecha(b3), izquierda(m))
        flecha(ax, derecha(m), izquierda(b5))
    flecha(ax, derecha(b5), izquierda(b6))

    # Los modelos guardados se cargan en el tablero
    x6, y6, w6, h6 = a6
    flecha(ax, (x6 + w6 / 2, y6 - 0.4), (xm + wm / 2 + 3.0, 17.4 + hm + 0.4),
           texto="los tres modelos se cargan al abrir el tablero", curva=-0.18,
           desplazamiento=(-9.0, -0.4))

    # Leyenda de colores
    etiquetas = [("datos", "Datos"), ("proceso", "Proceso"), ("modelo", "Modelos"),
                 ("salida", "Resultado"), ("persona", "Persona")]
    for i, (tipo, texto) in enumerate(etiquetas):
        relleno, borde = COLORES[tipo]
        x0 = 2.2 + i * 8.4
        ax.add_patch(FancyBboxPatch((x0, 1.9), 1.6, 1.2, boxstyle="round,pad=0.1",
                                    facecolor=relleno, edgecolor=borde, linewidth=1.2))
        ax.text(x0 + 2.2, 2.5, texto, va="center", fontsize=8.5, color=GRIS)

    fig.savefig(SALIDA, dpi=170, bbox_inches="tight", facecolor="white")
    print(f"Guardado {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
