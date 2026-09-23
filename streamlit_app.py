"""Tablero de detección de tráfico de red malicioso — punto de entrada.

Ejecutar localmente (desde la raíz del proyecto, con el entorno de la app):
    streamlit run streamlit_app.py

Privacidad (R18): la aplicación no guarda el archivo del usuario — lo procesa
en memoria y lo descarta al terminar la sesión.
"""

import streamlit as st

from app import nucleo, pantallas, validacion

st.set_page_config(
    page_title="Detector de tráfico malicioso",
    page_icon="🛡️",
    layout="wide",
)


@st.cache_resource(show_spinner="Cargando los modelos (solo la primera vez)…")
def _recursos(version: str) -> dict:
    """Los modelos se cargan UNA vez por servidor y se reutilizan.

    `version` entra como argumento a propósito: al cambiar la estructura de
    los recursos se sube nucleo.VERSION_RECURSOS y Streamlit descarta
    automáticamente el caché anterior.
    """
    return nucleo.cargar_recursos(version)


recursos = _recursos(nucleo.VERSION_RECURSOS)

# Red de seguridad: si un servidor lleva rato corriendo y el código cambió,
# el caché puede quedar desactualizado. Mejor un mensaje accionable que un
# KeyError en medio de una pantalla.
_faltantes = nucleo.CLAVES_REQUERIDAS - set(recursos)
if _faltantes:
    st.error(
        "**El servidor está usando datos en caché de una versión anterior "
        f"del tablero** (faltan: {', '.join(sorted(_faltantes))}).\n\n"
        "Solución: detén el servidor (Ctrl+C en la terminal donde corre) y "
        "vuelve a lanzarlo con `streamlit run streamlit_app.py`. Recargar la "
        "página no basta: el caché vive en el servidor, no en el navegador."
    )
    st.stop()

if "historial" not in st.session_state:
    st.session_state.historial = []
if "estado" not in st.session_state:
    st.session_state.estado = None  # dict con nombre, reporte y resultado
if "archivo_procesado" not in st.session_state:
    st.session_state.archivo_procesado = None
# El umbral de anomalías (presupuesto de falsas alarmas) lo crea el deslizador
# de la pantalla Detección de anomalías con su valor por defecto; las demás
# pantallas lo leen con pantallas.umbral_actual().


def _procesar(origen, nombre: str) -> None:
    """Valida y clasifica un archivo (buffer en memoria o ruta de demo)."""
    with st.spinner(f"Validando y clasificando '{nombre}'…"):
        reporte = validacion.validar_y_preparar(origen, recursos["meta"]["caracteristicas"])
        if reporte.bloqueado:
            st.session_state.estado = {"nombre": nombre, "reporte": reporte, "resultado": None}
            st.toast(f"'{nombre}' no se pudo clasificar: revisa la validación.", icon="⚠️")
            return
        resultado = nucleo.clasificar(reporte.datos, recursos)
    st.session_state.estado = {"nombre": nombre, "reporte": reporte, "resultado": resultado}
    n_alertas = int((resultado["clase"] != nucleo.NOMBRE_NORMAL).sum())
    pantallas.registrar(
        "Clasificación", nombre, reporte.filas_validas, n_alertas,
        pantallas.umbral_actual(),
    )
    st.toast(
        f"'{nombre}': {reporte.filas_validas:,} flujos clasificados, "
        f"{n_alertas:,} alertas.",
        icon="✅",
    )


def _marcar_subido_como_atendido(archivo) -> None:
    """Al elegir una demo, el archivo que siga en el cargador queda marcado
    como ya atendido: así una re-ejecución no lo re-procesa ni pisa la demo."""
    if archivo is not None:
        st.session_state.archivo_procesado = (archivo.name, archivo.size)


# ------------------------------------------------------------ barra lateral ---
with st.sidebar:
    st.title("🛡️ Detector de tráfico malicioso")
    st.caption(
        "Carga un archivo de flujos de red y obtén, para cada flujo, si es un "
        "ataque, de qué tipo y con qué confianza. Un *flujo* es una "
        "conversación entre dos computadores resumida en números; el tablero "
        "nunca ve el contenido de las comunicaciones."
    )

    # Verificación de versión (los modelos dependen de la versión exacta)
    if recursos["version_sklearn_activa"] != recursos["version_sklearn_modelos"]:
        st.warning(
            f"⚠️ Los modelos se guardaron con scikit-learn "
            f"{recursos['version_sklearn_modelos']} y este servidor ejecuta "
            f"{recursos['version_sklearn_activa']}. Pueden fallar o dar "
            "resultados distintos: instala la versión exacta de requirements.txt."
        )

    pantalla = st.radio(
        "Pantallas",
        ["Panel de resumen", "Clasificación", "Detección de anomalías",
         "Interpretabilidad", "Alertas", "Reportes"],
    )

    st.divider()
    st.subheader("Cargar archivo")
    archivo = st.file_uploader(
        "CSV de flujos de red",
        type=["csv"],
        help="Un CSV es un archivo de tabla que abre cualquier hoja de "
             "cálculo. Debe tener el formato que produce CICFlowMeter, la "
             "herramienta estándar y gratuita que convierte tráfico de red "
             "capturado en una tabla de flujos con sus medidas (tamaños, "
             "tiempos, conteos). La aplicación no guarda tu archivo: lo "
             "procesa en memoria y lo descarta al terminar la sesión.",
    )
    st.caption(
        "El archivo debe venir de **CICFlowMeter** (la herramienta que "
        "convierte tráfico de red en una tabla de flujos medibles). Si le "
        "falta alguna medida que el modelo necesita, el tablero te dirá cuál "
        "antes de clasificar."
    )
    if archivo is not None and st.session_state.archivo_procesado != (archivo.name, archivo.size):
        _procesar(archivo, archivo.name)
        st.session_state.archivo_procesado = (archivo.name, archivo.size)

    st.caption("¿Sin archivo a la mano? Prueba con una demostración:")
    if st.button(
        "Demo rica en ataques",
        help="~500 flujos reales de la prueba del modelo, con los 14 tipos de "
             "ataque del dataset (40% de ataque): muestra todo lo que la "
             "herramienta detecta. El clasificador de tipo reconoce 10 de esos "
             "14; la pantalla Clasificación explica por qué y qué pasa con los "
             "otros.",
        width="stretch",
    ):
        _procesar(nucleo.RUTA_DEMO / "flujos_demo.csv", "Demo rica en ataques")
        _marcar_subido_como_atendido(archivo)
    if st.button(
        "Demo de proporción realista",
        help="~500 flujos con solo 5% de ataque, la proporción típica de un "
             "lote real: muestra cuánto trabajo de revisión te ahorra.",
        width="stretch",
    ):
        _procesar(nucleo.RUTA_DEMO / "flujos_demo_realista.csv", "Demo de proporción realista")
        _marcar_subido_como_atendido(archivo)

    if st.session_state.estado is not None:
        st.caption(f"Archivo activo: **{st.session_state.estado['nombre']}**")

    st.divider()
    st.caption(
        "🔒 **Privacidad:** la aplicación no guarda tu archivo: lo procesa en "
        "memoria y lo descarta al terminar la sesión. El modelo solo usa "
        "medidas del tráfico (tamaños, tiempos, conteos), no el contenido de "
        "las comunicaciones."
    )

# ------------------------------------------------------------------ cuerpo ---
estado = st.session_state.estado
if estado is not None:
    with st.expander(
        f"Validación del archivo '{estado['nombre']}'",
        expanded=(estado["resultado"] is None),
    ):
        st.caption(
            "Antes de clasificar, el tablero revisa el archivo y explica qué "
            "encontró. Si algo impide clasificar, se dice aquí, sin errores "
            "crípticos."
        )
        pantallas.mostrar_validacion(estado["reporte"])

estado_util = estado if (estado is not None and estado["resultado"] is not None) else None

if pantalla == "Panel de resumen":
    pantallas.panel_resumen(recursos, estado_util)
elif pantalla == "Clasificación":
    pantallas.pantalla_clasificacion(recursos, estado_util)
elif pantalla == "Detección de anomalías":
    pantallas.pantalla_anomalias(recursos, estado_util)
elif pantalla == "Interpretabilidad":
    pantallas.pantalla_interpretabilidad(recursos, estado_util)
elif pantalla == "Alertas":
    pantallas.pantalla_alertas(recursos, estado_util)
elif pantalla == "Reportes":
    pantallas.pantalla_reportes(recursos, estado_util)
