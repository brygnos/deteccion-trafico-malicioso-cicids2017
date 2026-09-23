"""Pruebas de los 22 requerimientos, una por una contra la columna «Prueba
prevista» de la tabla de requerimientos entregada.

Convención: cada función se llama `test_Rnn_...` y su docstring cita la prueba
prevista y el criterio. Las que no se pueden automatizar (dependen del tablero
desplegado o de una persona ajena al proyecto) están marcadas como `manual` y
se omiten mostrando la razón en el reporte. Así el mismo comando deja
constancia de qué se verificó con código y qué requiere verificación humana.

Ejecutar desde la raíz del proyecto, con el entorno de la app:
    python -m pytest -v
"""

import ast
import time

import numpy as np
import pandas as pd
import pytest

from app import nucleo, pantallas, validacion
from tests.conftest import (
    RAIZ,
    RUTA_FASE3,
    RUTA_FASE4,
    RUTA_FINAL,
    RUTA_LIMPIO,
    RUTA_TRAIN,
    como_archivo,
)

SRC = RAIZ / "src"

# Familias que el detector de anomalías sí ve (estructuralmente raras) y las
# que no ve (camufladas, porque cada flujo parece normal). Se verifican las dos.
FAMILIAS_RARAS = ["Heartbleed", "DoS slowloris", "Infiltration"]
FAMILIAS_CAMUFLADAS = ["FTP-Patator", "SSH-Patator", "PortScan", "Bot"]


def _macro(metricas, variante, regla):
    fila = metricas[(metricas.variante == variante) & (metricas.regla == regla)]
    assert len(fila) == 1, f"falta {variante}/{regla} en final_multiclase_macro.csv"
    return float(fila.macro_f1.iloc[0])


# ======================================================================
# NEGOCIO
# ======================================================================

def test_R01_clasifica_10_ataques_mas_benigno_una_clase_por_flujo(por_clase_test, demo_rica):
    """R1. Prueba prevista: evaluación única sobre el conjunto de prueba
    apartado (20 %, 499.616 flujos nunca vistos).
    Criterio: distingue benigno de 10 clases de ataque (los 3 web agrupados
    en «Web Attack») y entrega una clase por flujo; Heartbleed e Infiltration
    se cubren en el nivel binario, no en el multiclase."""
    final = por_clase_test[(por_clase_test.variante == "con_puerto")
                           & (por_clase_test.regla == "umbral_bot")]
    clases = set(final.clase)
    assert len(clases) == 11, f"se esperaban 11 clases, hay {len(clases)}"
    assert "BENIGN" in clases and "Web Attack" in clases
    assert not {"Heartbleed", "Infiltration"} & clases, "las ultra-raras no van en el multiclase"
    assert int(final.soporte.sum()) == 499_616 - 9, "test menos las 9 filas ultra-raras"

    raras = pd.read_csv(RUTA_FINAL / "final_binario_raras.csv").set_index("clase")
    assert set(raras.index) == {"Heartbleed", "Infiltration"}
    assert raras.loc["Heartbleed", "n"] == 2 and raras.loc["Infiltration", "n"] == 7

    # una clase por flujo, siempre una de las 11
    res = demo_rica["resultado"]
    assert res["clase"].notna().all()
    validas = {nucleo.nombre_visible(c) for c in clases}
    assert set(res["clase"]) <= validas


def test_R02_falsas_alarmas_benigno_menor_o_igual_0_2_pct(confusion_final):
    """R2. Prueba prevista: conteo de falsos positivos sobre el tráfico
    benigno del conjunto de prueba. Criterio: tasa ≤ 0,2 %."""
    fila = confusion_final.loc["BENIGN"]
    total = int(fila.sum())
    falsas = int(fila.drop("BENIGN").sum())
    tasa = falsas / total
    assert total == 414_468, "benignos del test"
    assert tasa <= 0.002, f"falsas alarmas {tasa:.4%} > 0,2 %"


def test_R03_diez_alertas_muestran_caracteristicas_determinantes(recursos, demo_rica, caracteristicas):
    """R3. Prueba prevista: inspección de 10 alertas del archivo de
    demostración, verificando que cada una muestra sus características
    determinantes. Criterio: (a) características más influyentes en general
    y (b) las que más pesaron en cada alerta individual."""
    import shap

    # (a) lectura global disponible y con la forma esperada
    global_ = recursos["importancia"]
    assert len(global_) == 48 and {"feature", "importancia_media"} <= set(global_.columns)
    assert "Flow Duration" in set(global_.head(3).feature)

    # (b) explicación individual de 10 alertas concretas
    res = demo_rica["resultado"]
    datos = demo_rica["reporte"].datos
    alertas = res[res.clase != nucleo.NOMBRE_NORMAL].head(10)
    assert len(alertas) == 10
    explicador = shap.TreeExplainer(recursos["multiclase"])
    clases = list(recursos["multiclase"].classes_)
    for fila in alertas.itertuples():
        X = datos.loc[[fila.fila - 1], caracteristicas].astype("float32").values
        v = np.asarray(explicador.shap_values(X))[0]          # (48, 11)
        assert v.shape == (48, len(clases))
        contrib = v[:, clases.index(fila.clase)]
        top8 = np.sort(np.abs(contrib))[-8:]
        assert (top8 > 0).all(), f"fila {fila.fila}: hay pesos nulos entre los 8 principales"
        # coherencia: la clase más empujada por SHAP es la clase asignada
        empuje = v.sum(axis=0) + np.asarray(explicador.expected_value)
        assert clases[int(np.argmax(empuje))] == fila.clase


def test_R04_detector_ve_familias_raras_y_declara_las_camufladas():
    """R4. Prueba prevista: detector no supervisado entrenado únicamente
    con el tráfico benigno del lunes, evaluado sobre el resto de la semana
    y sobre el conjunto de prueba. Criterio: recall > 0,4 en las familias
    estructuralmente raras al 1 % de falsas alarmas; se documenta que no
    detecta las camufladas."""
    semana = pd.read_csv(RUTA_FASE4 / "q3_recall_por_ataque.csv")
    semana = semana[(semana.modelo == "iforest") & (semana.umbral_pct == 1.0)].set_index("clase")
    test = pd.read_csv(RUTA_FINAL / "final_iforest_recall.csv")
    test = test[test.umbral_pct == 1.0].set_index("clase")

    for fam in FAMILIAS_RARAS:
        assert semana.loc[fam, "recall"] > 0.4, f"{fam} en la semana: {semana.loc[fam, 'recall']:.2f}"
        assert test.loc[fam, "recall"] > 0.4, f"{fam} en el test: {test.loc[fam, 'recall']:.2f}"
    # el punto ciego declarado: los camuflados quedan prácticamente en cero
    for fam in FAMILIAS_CAMUFLADAS:
        assert semana.loc[fam, "recall"] < 0.05, f"{fam} debería ser invisible al detector"
    # y la pantalla lo dice explícitamente
    fuente = (RAIZ / "app" / "pantallas.py").read_text(encoding="utf-8")
    assert "punto ciego" in fuente and "camuflados" in fuente


def test_R05_supera_linea_base_trivial_y_reduce_carga_de_revision(metricas_test, demo_rica, demo_realista):
    """R5. Prueba prevista: comparación contra la línea base trivial (marcar
    todo como benigno) y estimación del esfuerzo de revisión manual para el
    mismo volumen. Criterio: supera sustancialmente la referencia 0,082 y
    reduce a segundos la priorización."""
    final = _macro(metricas_test, "con_puerto", "umbral_bot")
    piso = 0.082  # línea base del reporte técnico (sección 5.3): clasificador trivial multiclase
    assert final - piso > 0.5, f"{final} no supera sustancialmente {piso}"

    def reduccion(res):
        return 1 - (res.clase != nucleo.NOMBRE_NORMAL).sum() / len(res)

    assert reduccion(demo_realista["resultado"]) > 0.90, "proporción realista: >90 % menos revisión"
    assert reduccion(demo_rica["resultado"]) > 0.50


# ======================================================================
# DESEMPEÑO
# ======================================================================

def test_R06_macro_f1_en_prueba_mayor_o_igual_0_94(metricas_test):
    """R6. Prueba prevista: validación cruzada estratificada de 5
    particiones sobre entrenamiento y evaluación única sobre prueba.
    Criterio: macro-F1 ≥ 0,94 en el conjunto de prueba (también en la
    estimación conservadora sin el puerto)."""
    assert _macro(metricas_test, "con_puerto", "umbral_bot") >= 0.94
    assert _macro(metricas_test, "sin_identificadores", "argmax") >= 0.94


def test_R07_semilla_fija_y_clasificacion_determinista(recursos, demo_rica, caracteristicas):
    """R7. Prueba prevista: re-ejecución con semilla fija (42) y comparación
    de cifras entre ejecuciones. Aquí: la semilla está declarada y dos
    clasificaciones del mismo archivo son idénticas bit a bit."""
    from src import config
    assert config.RANDOM_STATE == 42
    assert recursos["meta"]["semilla"] == 42

    datos = demo_rica["reporte"].datos
    a = nucleo.clasificar(datos, recursos)
    b = nucleo.clasificar(datos, recursos)
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.datos_locales
@pytest.mark.skipif(not RUTA_TRAIN.exists(), reason="requiere data/processed/train.parquet, que no viaja con el repo. Para generarlo, pon los 8 CSV de CIC-IDS2017 en data/raw/ y corre con el entorno del análisis: python -m src.preparacion, python -m src.limpieza y python -m src.split (ver 'Reproducir el análisis' en el README).")
def test_R07_reentrenar_detector_reproduce_umbrales_exactos(recursos, caracteristicas):
    """R7 (parte pesada): re-ejecución real de una etapa del pipeline. El
    detector de anomalías se vuelve a entrenar con el lunes benigno y la
    semilla 42, y sus umbrales por cuantiles deben coincidir decimal a
    decimal con los guardados en models/."""
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from src.config import COLUMNA_ETIQUETA, ETIQUETA_BENIGNA, RANDOM_STATE

    cuantiles = [float(q) for q in recursos["meta"]["cuantiles_detector"]]  # 0,5 / 1 / 2 %
    train = pd.read_parquet(RUTA_TRAIN, columns=caracteristicas + [COLUMNA_ETIQUETA, "archivo_origen"])
    lunes = train["archivo_origen"].astype(str).str.startswith("Monday").values
    assert (train.loc[lunes, COLUMNA_ETIQUETA] == ETIQUETA_BENIGNA).all()
    X = train.loc[lunes, caracteristicas].astype(np.float32).values
    esc = StandardScaler().fit(X)
    bosque = IsolationForest(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1).fit(esc.transform(X))
    scores = bosque.score_samples(esc.transform(X))
    for q in cuantiles:
        esperado = recursos["detector"]["umbrales"][str(q)]
        assert np.isclose(np.quantile(scores, q), esperado, rtol=0, atol=1e-12)


def test_R08_anti_fuga_un_solo_lector_del_test_y_cv_coincide_con_prueba(metricas_test):
    """R8. Prueba prevista: auditoría del código (escalado y remuestreo
    dentro del pipeline de validación cruzada; un único módulo autorizado a
    leer el conjunto de prueba) y comparación entre la validación cruzada y
    la prueba."""
    # (1) quién lee el test: solo evaluacion_final.py (la evaluación única) y
    #     preparar_demo.py, que solo toma muestras del test para armar las
    #     demostraciones. Ningún otro módulo lo lee, y
    #     preparar_demo no calcula ninguna métrica con esos flujos.
    lectores = {}
    for f in sorted(SRC.glob("*.py")):
        cod = f.read_text(encoding="utf-8")
        if "ARCHIVO_TEST" in cod and "read_parquet" in cod and f.name not in ("split.py", "config.py"):
            lectores[f.name] = cod
    assert set(lectores) == {"evaluacion_final.py", "preparar_demo.py"}, sorted(lectores)
    demo = lectores["preparar_demo.py"]
    assert "sklearn.metrics" not in demo and "_score(" not in demo and "predict" not in demo,         "preparar_demo.py no debe evaluar nada sobre el test"

    # (2) el escalado y el remuestreo están dentro del pipeline de validación cruzada
    exp = (SRC / "experimentos.py").read_text(encoding="utf-8")
    assert "from imblearn.pipeline import Pipeline" in exp
    assert '("escalado", StandardScaler())' in exp
    assert '("smote", SMOTE(' in exp

    # (3) el desempeño en prueba cae dentro del intervalo de la CV (media ± 3 desv.)
    cv = pd.read_csv(RUTA_FASE3 / "fase3_macro_f1.csv")
    cv_con = cv[(cv.modelo == "Árboles (HistGB)") & (cv.tecnica == "Pesos de clase")].iloc[0]
    cv_sin = pd.read_csv(RUTA_FASE4 / "q1_puerto_macro_f1.csv").query("variante == 'sin_puerto'").macro_f1
    assert abs(_macro(metricas_test, "con_puerto", "argmax") - cv_con.macro_f1_media) <= 3 * cv_con.macro_f1_desv
    assert abs(_macro(metricas_test, "sin_identificadores", "argmax") - cv_sin.mean()) <= 3 * cv_sin.std()


def test_R09_local_50000_flujos_en_menos_de_30_segundos(recursos, demo_crudo, caracteristicas):
    """R9. Prueba prevista: medición del tiempo de clasificación con archivos
    de tamaño creciente en el tablero desplegado. Esta es la medición local
    (evidencia parcial); la definitiva se repite después del despliegue.
    Criterio: hasta 50.000 flujos en menos de 30 segundos."""
    rng = np.random.default_rng(42)
    lote = demo_crudo.iloc[rng.integers(0, len(demo_crudo), 50_000)]
    archivo = como_archivo(lote)
    t0 = time.perf_counter()
    rep = validacion.validar_y_preparar(archivo, caracteristicas)
    res = nucleo.clasificar(rep.datos, recursos)
    segundos = time.perf_counter() - t0
    assert len(res) == 50_000
    assert segundos < 30, f"50.000 flujos tardaron {segundos:.1f} s"


@pytest.mark.manual
@pytest.mark.skip(reason="R10 — manual: abrir la URL pública desde un equipo distinto al de desarrollo y medir la reanudación tras inactividad (< 1 min). Requiere el despliegue.")
def test_R10_url_publica_responde_y_reanuda_en_menos_de_un_minuto():
    """R10. Prueba prevista: acceso a la URL pública desde un equipo
    distinto al de desarrollo, sin instalación previa."""


def test_R11_falsas_alarmas_por_dia_y_deriva_documentada(recursos):
    """R11. Prueba prevista: medición de la tasa de falsas alarmas del
    detector no supervisado desagregada por día. Criterio: se reporta la tasa
    por día y se documenta la deriva como señal de re-entrenamiento."""
    fp = recursos["falsas_alarmas_dia"]
    assert set(fp.umbral_pct.unique()) == {0.5, 1.0, 2.0}
    al_1 = fp[fp.umbral_pct == 1.0]
    assert len(al_1) == 8, "8 días/tramos"
    assert 0.005 <= al_1.tasa_falsas_alarmas.median() <= 0.015, "la mayoría cerca del 1 % presupuestado"
    assert al_1.tasa_falsas_alarmas.max() > 0.05, "existe un tramo con deriva clara (9,6 %)"
    # la pantalla lo expone como tabla legible y lo explica
    tabla = pantallas._tabla_falsas_alarmas_dia(recursos, "1%")
    assert len(tabla) == 8 and "Lunes (día de calibración)" in set(tabla["Día / tramo"])
    fuente = (RAIZ / "app" / "pantallas.py").read_text(encoding="utf-8")
    assert "deriva" in fuente and "recalibrar" in fuente


# ======================================================================
# FUNCIONAL
# ======================================================================

def test_R12_cuatro_archivos_valido_faltante_vacio_invalido(demo_crudo, caracteristicas):
    """R12. Prueba prevista: carga de cuatro archivos: uno válido, uno con
    columnas faltantes, uno vacío y uno con valores inválidos. Criterio:
    reporta el problema antes de clasificar, sin interrumpirse con un error."""
    # 1. válido
    ok = validacion.validar_y_preparar(como_archivo(demo_crudo), caracteristicas)
    assert not ok.bloqueado and ok.filas_validas == 499

    # 2. columnas faltantes: se bloquea con un mensaje en llano que nombra ejemplos
    recortado = demo_crudo.drop(columns=[c for c in demo_crudo.columns if "IAT" in c])
    falt = validacion.validar_y_preparar(como_archivo(recortado), caracteristicas)
    assert falt.bloqueado and any("Faltan" in m for _, m in falt.mensajes)

    # 3. vacío (o solo con encabezado): se bloquea sin lanzar ninguna excepción
    import io
    assert validacion.validar_y_preparar(io.StringIO(""), caracteristicas).bloqueado
    assert validacion.validar_y_preparar(
        io.StringIO(",".join(demo_crudo.columns) + "\n"), caracteristicas).bloqueado

    # 4. valores inválidos: no se bloquea, se excluyen esas filas y se dice cuáles
    sucio = demo_crudo.copy().astype({" Flow Duration": "object"})
    sucio.loc[0, " Flow Duration"] = "no-es-numero"
    sucio.loc[1, " Flow Duration"] = "inf"
    inv = validacion.validar_y_preparar(como_archivo(sucio), caracteristicas)
    assert not inv.bloqueado and inv.filas_excluidas == 2 and inv.filas_validas == 497
    assert any("Filas afectadas: 1, 2" in m for _, m in inv.mensajes)

    # extra: un archivo con columna de etiqueta se acepta con un aviso, y un archivo basura no rompe nada
    etiquetado = demo_crudo.copy(); etiquetado["Label"] = "BENIGN"
    lab = validacion.validar_y_preparar(como_archivo(etiquetado), caracteristicas)
    assert not lab.bloqueado and any("etiqueta" in m for _, m in lab.mensajes)
    assert validacion.validar_y_preparar(io.BytesIO(b"\x00\x01PK\x03\x04" * 40), caracteristicas).bloqueado


def test_R13_sin_valores_invalidos_tras_depurar(demo_crudo, caracteristicas):
    """R13. Prueba prevista: ejecución del script de limpieza sobre el
    consolidado, con verificación automática de que no quedan valores
    infinitos ni faltantes. Aquí: la misma regla aplicada a lo que sube el
    usuario (la parte reproducible sin los datos grandes)."""
    sucio = demo_crudo.copy().astype({"Flow Bytes/s": "object"})
    sucio.loc[3, "Flow Bytes/s"] = "inf"
    sucio.loc[4, "Flow Bytes/s"] = ""
    rep = validacion.validar_y_preparar(como_archivo(sucio), caracteristicas)
    vals = rep.datos[caracteristicas].to_numpy(dtype=float)
    assert np.isfinite(vals).all(), "quedaron Inf/NaN tras la depuración"
    # y el script de limpieza del análisis falla a propósito si quedaran
    lim = (SRC / "limpieza.py").read_text(encoding="utf-8")
    assert "raise ValueError" in lim and "Inf/NaN" in lim


@pytest.mark.datos_locales
@pytest.mark.skipif(not RUTA_LIMPIO.exists(), reason="requiere data/interim/cicids2017_limpio.parquet, que no viaja con el repo. Para generarlo, pon los 8 CSV de CIC-IDS2017 en data/raw/ y corre con el entorno del análisis: python -m src.preparacion y python -m src.limpieza (ver 'Reproducir el análisis' en el README).")
def test_R13_consolidado_limpio_sin_inf_nan_y_con_11_69_pct_menos(caracteristicas):
    """R13 (parte pesada): el Parquet limpio real no tiene Inf/NaN y refleja
    la eliminación del 11,69 % de duplicados (de 2.830.743 a 2.498.078 flujos)."""
    df = pd.read_parquet(RUTA_LIMPIO, columns=[c for c in caracteristicas if not c.endswith("_no_aplica")])
    assert len(df) == 2_498_078
    assert np.isfinite(df.to_numpy(dtype=np.float32)).all()


def test_R14_cada_flujo_recibe_binaria_multiclase_y_confianza(demo_rica, recursos):
    """R14. Prueba prevista: clasificación del archivo de demostración,
    verificando que cada flujo recibe clase binaria, clase multiclase y nivel
    de confianza."""
    res = demo_rica["resultado"]
    assert len(res) == 499
    assert set(res.clase_binaria.unique()) <= {"Ataque", nucleo.NOMBRE_NORMAL}
    visibles = {nucleo.nombre_visible(c) for c in recursos["multiclase"].classes_}
    assert set(res.clase.unique()) <= visibles
    assert res.confianza.between(0, 1).all() and (res.confianza > 0).all()
    assert res.prob_ataque.between(0, 1).all()
    assert res[["clase", "clase_binaria", "confianza", "prob_ataque"]].notna().all().all()


def test_R15_umbral_ajustable_cambia_el_conteo(demo_rica, recursos):
    """R15. Prueba prevista: movimiento del control de umbral (de 0,5 % a 2 %)
    verificando que el conteo de flujos marcados como anómalos cambia en
    consecuencia."""
    res = demo_rica["resultado"]
    conteos, cortes = {}, {}
    for etiqueta in nucleo.CUANTILES:
        marca, corte = nucleo.marcar_anomalias(res, recursos, etiqueta)
        conteos[etiqueta], cortes[etiqueta] = int(marca.sum()), corte
    assert conteos["0,5%"] < conteos["1%"] < conteos["2%"], conteos
    assert len(set(cortes.values())) == 3
    assert cortes["1%"] == recursos["detector"]["umbrales"]["0.01"], "el corte sale del detector, no se recalcula"


@pytest.mark.manual
@pytest.mark.skip(reason="R16 — manual: recorrido de navegación contando clics (resumen: 1, métricas: 2, explicación de una alerta: 3, exportar filtrado: 3).")
def test_R16_resultados_clave_en_tres_clics_o_menos():
    """R16. Prueba prevista: recorrido de navegación contando los clics
    hasta cada resultado clave. Criterio: ≤ 3 clics."""


def test_R17_filtrar_y_exportar_refleja_el_filtro(demo_rica, recursos):
    """R17. Prueba prevista: filtrado de la cola de alertas y descarga del
    archivo, verificando que refleja el filtro aplicado. Criterio: filtra por
    tipo, confianza y marca de anomalía; exporta resultados y métricas en CSV."""
    import io
    res = demo_rica["resultado"]
    anomalo, _ = nucleo.marcar_anomalias(res, recursos, "1%")
    res = res.assign(anomalo=anomalo)
    alertas = res[res.clase != nucleo.NOMBRE_NORMAL]

    tipos = ["DoS Hulk", "PortScan"]
    filtro = alertas[alertas.clase.isin(tipos) & (alertas.confianza >= 0.9) & (~alertas.anomalo)]
    assert 0 < len(filtro) < len(alertas)

    buf = io.StringIO(); filtro.to_csv(buf, index=False)
    exportado = pd.read_csv(io.StringIO(buf.getvalue()))
    assert len(exportado) == len(filtro)
    assert set(exportado.clase) <= set(tipos) and (exportado.confianza >= 0.9).all()
    assert not exportado.anomalo.any()

    # las métricas fijas también se pueden exportar
    buf2 = io.StringIO(); recursos["metricas_clase"].to_csv(buf2, index=False)
    assert len(pd.read_csv(io.StringIO(buf2.getvalue()))) == 11


def test_R18_no_escribe_el_archivo_en_disco_y_usa_solo_metadatos(demo_crudo, caracteristicas, recursos):
    """R18. Prueba prevista: verificación de que la aplicación no escribe el
    archivo cargado en disco y de que ninguna característica usada contiene
    contenido del tráfico."""
    ignorar = (".venv", ".venv-app", "__pycache__", ".git", ".pytest_cache")

    def instantanea():
        return {p for p in RAIZ.rglob("*") if p.is_file() and not any(s in p.parts for s in ignorar)}

    antes = instantanea()
    rep = validacion.validar_y_preparar(como_archivo(demo_crudo), caracteristicas)
    nucleo.clasificar(rep.datos, recursos)
    nuevos = instantanea() - antes
    assert not nuevos, f"la clasificación creó archivos: {sorted(map(str, nuevos))[:5]}"

    # solo metadatos de comportamiento: nada de IPs, identificadores de flujo,
    # marcas de tiempo ni contenido; todas las características son numéricas
    prohibidas = ("source ip", "destination ip", "src ip", "dst ip", "flow id", "timestamp",
                  "payload", "content", "url", "host", "user agent")
    for c in caracteristicas:
        assert not any(p in c.lower() for p in prohibidas), c
    assert all(np.issubdtype(rep.datos[c].dtype, np.number) for c in caracteristicas)


@pytest.mark.manual
@pytest.mark.skip(reason="R19 — deseable, no verificable en este prototipo: requiere una API de scoring y un entorno SIEM de pruebas. La exportación CSV es la vía de esta iteración.")
def test_R19_integracion_siem():
    """R19. Prueba prevista: no verificable en este prototipo."""


# ======================================================================
# USABILIDAD
# ======================================================================

@pytest.mark.manual
@pytest.mark.skip(reason="R20 — manual: una persona ajena al proyecto, sin conocimientos de programación, completa cargar → revisar alertas → exportar sin asistencia.")
def test_R20_usuario_ajeno_completa_el_recorrido_sin_ayuda():
    """R20. Prueba prevista: demostración con una persona ajena al proyecto."""


PANTALLAS = ["panel_resumen", "pantalla_clasificacion", "pantalla_anomalias",
             "pantalla_interpretabilidad", "pantalla_alertas", "pantalla_reportes"]


LLAMADAS_DE_TEXTO = {"caption", "markdown", "info", "warning", "success", "error", "write", "toast"}


def _textos_visibles(nodo) -> list[str]:
    """La prosa que el tablero muestra dentro de `nodo` del árbol sintáctico:
    los literales que se pasan a st.caption, st.markdown, st.info, etc., y a
    los textos de ayuda (help=...). La concatenación implícita ya viene unida
    y de los f-strings se toman sus partes fijas, así que una frase partida en
    varias líneas del código se lee completa. Deja fuera docstrings,
    comentarios y nombres de columnas."""
    def literales(expr):
        return [n.value for n in ast.walk(expr)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]

    textos = []
    for llamada in (n for n in ast.walk(nodo) if isinstance(n, ast.Call)):
        if getattr(llamada.func, "attr", None) in LLAMADAS_DE_TEXTO:
            for arg in [*llamada.args, *(k.value for k in llamada.keywords)]:
                textos += literales(arg)
        else:
            for k in llamada.keywords:
                if k.arg == "help":
                    textos += literales(k.value)
    return textos


def test_R21_cada_pantalla_dice_que_muestra_y_como_leerlo():
    """R21. Prueba prevista: revisión de los textos de la interfaz por una
    persona ajena (parte manual). Aquí, la parte verificable por código:
    cada una de las seis pantallas abre con su título y, justo debajo, un
    texto que explica qué muestra (la redacción es libre: «Aquí encontrarás…»,
    «Aquí puedes ver…»); las pantallas con tablas de resultados traen su guía
    «Cómo leer»; y los términos técnicos de las métricas tienen su explicación
    en lenguaje llano. Se verifica sobre el árbol sintáctico de pantallas.py y
    no sobre frases exactas, para que reescribir los textos no rompa la prueba
    mientras se conserve lo que exige el requerimiento."""
    arbol = ast.parse((RAIZ / "app" / "pantallas.py").read_text(encoding="utf-8"))
    funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
    assert set(PANTALLAS) <= set(funciones), set(PANTALLAS) - set(funciones)

    # 1) título + descripción de qué muestra la pantalla
    for nombre in PANTALLAS:
        primeras = funciones[nombre].body[:2]
        llamadas = [n.value for n in primeras
                    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
        metodos = [getattr(c.func, "attr", None) for c in llamadas]
        assert metodos == ["header", "caption"], (
            f"{nombre} no abre con título y descripción (abre con {metodos})")
        descripcion = " ".join(_textos_visibles(llamadas[1]))
        assert len(descripcion) >= 80, f"la descripción de {nombre} es muy corta: {descripcion!r}"

    # 2) guía de lectura en las pantallas con tablas de resultados
    for nombre in ["pantalla_clasificacion", "pantalla_anomalias",
                   "pantalla_interpretabilidad", "pantalla_alertas"]:
        assert "Cómo leer" in " ".join(_textos_visibles(funciones[nombre])), (
            f"{nombre} no trae su guía «Cómo leer»")

    # 3) cada pantalla que usa un término técnico lo explica en llano en esa
    #    misma pantalla (no basta con que la explicación esté en otra)
    glosas = {"macro-F1": "promedia qué tan bien se detecta", "recall": "Detección",
              "precisión": "Acierto de la alarma", "SHAP": "responsabilidad",
              "Score de anomalía": "más bajo = más raro"}
    usados = set()
    for nombre in PANTALLAS:
        texto = " ".join(_textos_visibles(funciones[nombre]))
        for termino, glosa in glosas.items():
            if termino in texto:
                usados.add(termino)
                assert glosa in texto, (
                    f"{nombre} usa '{termino}' sin su explicación en llano ('{glosa}')")
    assert usados == set(glosas), f"términos que ya no aparecen en ninguna pantalla: {set(glosas) - usados}"


@pytest.mark.manual
@pytest.mark.skip(reason="R21 (parte humana) — revisión de los textos por una persona ajena al proyecto.")
def test_R21_revision_de_textos_por_persona_ajena():
    """R21, la parte que requiere a una persona ajena al proyecto."""


@pytest.mark.manual
@pytest.mark.skip(reason="R22 — manual: abrir el tablero desplegado en Chrome, Firefox y Edge de escritorio.")
def test_R22_funciona_en_chrome_firefox_y_edge():
    """R22. Prueba prevista: apertura del tablero en Chrome, Firefox y Edge
    de escritorio."""
