"""Pantallas del tablero. Cada una explica qué muestra y cómo leerla, define
los términos técnicos en su primera aparición y distingue explícitamente qué
viene del archivo del usuario y qué es resultado fijo de la evaluación del
modelo, para que cada pantalla se entienda por sí sola."""

import io
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from app import nucleo

NIVELES = {"ok": st.success, "info": st.info, "advertencia": st.warning, "error": st.error}

# Nombres en lenguaje llano para las características más influyentes.
# Se muestran como "nombre llano (nombre técnico)".
GLOSARIO = {
    "Flow Duration": "Duración de la conversación",
    "Destination Port": "Puerta (puerto) del servicio contactado",
    "Bwd Packet Length Min": "Tamaño mínimo de los paquetes de respuesta",
    "Bwd Packet Length Mean": "Tamaño promedio de los paquetes de respuesta",
    "Bwd Packet Length Max": "Tamaño máximo de los paquetes de respuesta",
    "Fwd Packet Length Max": "Tamaño máximo de los paquetes enviados",
    "Fwd Packet Length Mean": "Tamaño promedio de los paquetes enviados",
    "Bwd Header Length": "Bytes de encabezado en las respuestas",
    "Fwd Header Length": "Bytes de encabezado en lo enviado",
    "Flow Bytes/s": "Velocidad de la conversación (bytes/segundo)",
    "Flow Packets/s": "Ritmo de paquetes por segundo",
    "Init_Win_bytes_forward": "Configuración inicial de la conexión (quien inicia)",
    "Init_Win_bytes_backward": "Configuración inicial de la conexión (quien responde)",
    "Init_Win_bytes_forward_no_aplica": "La conexión no anunció configuración inicial",
    "Init_Win_bytes_backward_no_aplica": "La respuesta no anunció configuración inicial",
    "Fwd IAT Min": "Silencio mínimo entre paquetes enviados",
    "Fwd IAT Mean": "Silencio promedio entre paquetes enviados",
    "Fwd IAT Std": "Variabilidad del ritmo de envío",
    "Flow IAT Max": "Mayor silencio dentro de la conversación",
    "Flow IAT Mean": "Silencio promedio entre paquetes",
    "Packet Length Variance": "Qué tan dispares son los tamaños de paquete",
    "Packet Length Mean": "Tamaño promedio de paquete",
    "Max Packet Length": "Tamaño del paquete más grande",
    "Min Packet Length": "Tamaño del paquete más pequeño",
    "SYN Flag Count": "Señales de inicio de conexión (SYN)",
    "RST Flag Count": "Conexiones cortadas de golpe (RST)",
    "ACK Flag Count": "Confirmaciones de recibido (ACK)",
    "Average Packet Size": "Tamaño promedio de paquete",
    "Total Fwd Packets": "Paquetes enviados por quien inicia",
    "Total Length of Fwd Packets": "Bytes enviados por quien inicia",
    "Active Mean": "Duración promedio de las ráfagas de actividad",
    "Active Max": "Ráfaga de actividad más larga",
    "Active Std": "Variabilidad de las ráfagas de actividad",
    "Active Min": "Ráfaga de actividad más corta",
    "Idle Mean": "Silencio total promedio",
    "Idle Std": "Variabilidad de los silencios largos",
    "act_data_pkt_fwd": "Paquetes enviados con datos",
    "min_seg_size_forward": "Encabezado mínimo de lo enviado",
    "Fwd Packet Length Min": "Tamaño mínimo de los paquetes enviados",
    "Flow IAT Std": "Variabilidad del ritmo de la conversación",
    "Flow IAT Min": "Silencio más corto entre paquetes",
    "Bwd IAT Total": "Silencio acumulado en las respuestas",
    "Bwd IAT Mean": "Silencio promedio entre respuestas",
    "Bwd IAT Std": "Variabilidad del ritmo de respuesta",
    "Bwd IAT Max": "Mayor silencio entre respuestas",
    "Bwd IAT Min": "Silencio más corto entre respuestas",
    "Bwd Packets/s": "Ritmo de respuestas por segundo",
    "Fwd URG Flags": "Marcas de 'dato urgente' en lo enviado",
    "FIN Flag Count": "Cierres ordenados de conexión (FIN)",
    "PSH Flag Count": "Peticiones de entrega inmediata (PSH)",
    "URG Flag Count": "Marcas de dato urgente (URG)",
    "Down/Up Ratio": "Proporción entre lo recibido y lo enviado",
}


def nombre_llano(caracteristica: str) -> str:
    llano = GLOSARIO.get(caracteristica)
    return f"{llano} ({caracteristica})" if llano else caracteristica


def registrar(evento: str, archivo: str, flujos: int, alertas: int, umbral: str) -> None:
    """Registra una acción en el historial de la sesión (R17)."""
    st.session_state.historial.append(
        {
            "Hora": datetime.now().strftime("%H:%M:%S"),
            "Evento": evento,
            "Archivo": archivo,
            "Flujos analizados": flujos,
            "Alertas": alertas,
            "Umbral de anomalía": umbral,
        }
    )


def _sin_archivo() -> None:
    st.info(
        "**Aún no hay archivo cargado.** Usa la barra lateral: sube un CSV de "
        "flujos de red o usa uno de los dos archivos de demostración. Un "
        "*flujo* es una conversación entre dos computadores, resumida en "
        "números (cuántos paquetes, de qué tamaño, con qué ritmo); el tablero "
        "clasifica cada flujo sin mirar el contenido de la comunicación."
    )


def _nota_tres_modelos() -> None:
    """Explica por qué el clasificador de tipo reconoce 10 clases y no 14."""
    st.info(
        "**Nota:** Encontrarás que el tipo de ataque tiene 10 opciones en vez de 14 "
        "como en el dataset. Esto es porque el "
        "clasificador de tipo aprendió 10: los 3 ataques web se "
        "agrupan en la familia 'Web Attack', y **Heartbleed** (11 casos en "
        "2,8 millones de flujos) e **Infiltration** (36 casos) son demasiado "
        "escasos para aprenderlos y medirlos como clases propias con "
        "seriedad. Por esta razón la herramienta usa **tres modelos que se "
        "complementan**: si uno de esos dos ataques extremadamente raros aparece, el "
        "tipo asignado será **incorrecto por construcción** (el clasificador "
        "no conoce esa clase), pero el veredicto binario de '¿Ataque?' y la "
        "marca de anomalía sí pueden atraparlo. Es por esto que decidimos tener "
        "tres modelos y no uno."
    )


UMBRAL_POR_DEFECTO = "1%"


def umbral_actual() -> str:
    """El presupuesto de falsas alarmas vigente en la sesión."""
    return st.session_state.get("umbral_cuantil", UMBRAL_POR_DEFECTO)


def mostrar_validacion(reporte) -> None:
    """Los hallazgos de la validación, antes de cualquier clasificación."""
    for nivel, texto in reporte.mensajes:
        NIVELES.get(nivel, st.info)(texto)


# ---------------------------------------------------------------- resumen ---
def panel_resumen(recursos, estado) -> None:
    st.header("Panel de resumen")
    st.caption(
        "Aquí encontrarás el resultado global del archivo que cargaste y cuánta "
        "carga de revisión aproximada te ahorra la herramienta. Toda la información de esta pantalla "
        "sale **del archivo cargado**. ¡Prueba con los archivos demo si no tienes uno a la mano!"
    )
    if estado is None:
        _sin_archivo()
        return

    resultado = estado["resultado"]
    n = len(resultado)
    alertas = resultado[resultado["clase"] != nucleo.NOMBRE_NORMAL]
    n_alertas = len(alertas)
    reduccion = 100 * (1 - n_alertas / n) if n else 0.0

    # KPI de negocio primero: la carga de revisión, no la métrica del modelo
    st.subheader("Cuánto trabajo de revisión te ahorra")
    c1, c2, c3 = st.columns(3)
    c1.metric("Flujos cargados", f"{n:,}")
    c2.metric("Alertas priorizadas", f"{n_alertas:,}")
    c3.metric("Reducción de la carga de revisión", f"{reduccion:.1f}%")
    st.markdown(
        f"- **Sin la herramienta:** {n:,} flujos por revisar uno por uno.\n"
        f"- **Con la herramienta:** {n_alertas:,} alertas priorizadas "
        "(flujos que el modelo clasificó como algún tipo de ataque)."
    )
    st.warning(
        "Sin usar esta herramienta el analista **revisa absolutamente todo** e idealmente no se le escapa nada, "
        "a costa de un trabajo muy largo y muchas veces inviable si trabaja solo. "
        "Con esta herramienta **solo se revisa una fracción priorizada**, aceptando que el modelo pueda "
        "dejar pasar algo, pero con mucho más tiempo para indagar en esos casos puntuales sin "
        "tanta fatiga mental, es un intercambio y se debe tratar con cuidado, no hace todo el trabajo, "
        "pero lo puede facilitar mucho si se utiliza correctamente."
    )

    if n_alertas:
        st.subheader("Alertas por tipo de ataque")
        st.caption(
            "Cada barra cuenta cuántos flujos de tu archivo fueron "
            "clasificados en cada tipo de ataque."
        )
        st.bar_chart(alertas["clase"].value_counts())

    umbral = umbral_actual()
    anomalo, _ = nucleo.marcar_anomalias(resultado, recursos, umbral)
    st.subheader("Comportamiento anómalo")
    st.markdown(
        f"El detector de anomalías es un segundo modelo que aprendió solo cómo "
        f"se ve el tráfico normal y marca lo que se sale de ese patrón. En este caso señaló "
        f"**{int(anomalo.sum()):,}** flujos como anómalos al umbral actual del "
        f"**{umbral}**. El detalle, el ajuste del umbral y los límites de este "
        "detector están en la pantalla *Detección de anomalías*."
    )


# ----------------------------------------------------------- clasificación ---
def pantalla_clasificacion(recursos, estado) -> None:
    st.header("Clasificación")
    st.caption(
        "Aquí puedes ver cómo quedó clasificado **tu archivo** y "
        "el desempeño **fijo** del modelo en su test final (499.616 flujos "
        "de prueba que nunca vio al entrenar). Cada sección dice de cuál de "
        "las dos fuentes viene."
    )

    # ---- 1) datos vivos: el archivo del usuario ----
    st.subheader("Distribución de clases (Archivo del Usuario)")
    if estado is None:
        _sin_archivo()
    else:
        resultado = estado["resultado"]
        st.caption("Fuente: el archivo cargado en esta sesión.")
        st.bar_chart(resultado["clase"].value_counts())
        tabla = (
            resultado.groupby("clase")
            .agg(flujos=("clase", "size"), confianza_media=("confianza", "mean"))
            .sort_values("flujos", ascending=False)
            .reset_index()
            .rename(columns={"clase": "Clase", "flujos": "Flujos",
                             "confianza_media": "Confianza media"})
        )
        tabla["Confianza media"] = tabla["Confianza media"].map(lambda v: f"{v:.1%}")
        st.dataframe(tabla, hide_index=True, width="stretch")
        st.caption(
            "La **confianza** es la probabilidad que el modelo le asigna a la "
            "clase que eligió para el flujo: 99% significa que casi no duda; "
            "60% significa que la decisión estuvo reñida."
        )

    _nota_tres_modelos()

    # ---- 2) datos fijos: la evaluación del modelo ----
    st.divider()
    st.subheader("Resultado Fijo: Test Final del modelo")
    st.caption(
        "Fuente: la evaluación única sobre 499.616 flujos de prueba que el "
        "modelo nunca vio al entrenar. Estas cifras no dependen de tu archivo "
        "y no cambian."
    )
    st.markdown(
        f"**Fatiga de alertas bajo control:** el modelo mantiene las falsas "
        f"alarmas en **{nucleo.CIFRAS_OFICIALES['falsas_alarmas_pct']}** del "
        "tráfico normal (una *falsa alarma* es un flujo normal marcado como "
        "ataque: cada una *cuesta tiempo del analista*). Para lograr eso, "
        f"buscamos un desempeño alto de macro-F1 (**{nucleo.CIFRAS_OFICIALES['macro_f1_final']}**) "
        "el cual promedia qué tan bien se "
        "detecta **cada** clase, pesando igual a la más común y a la más rara. "
        "Como comparación, un modelo que dijera 'todo es normal' apenas lograría "
        f"{nucleo.CIFRAS_OFICIALES['piso_trivial']}."
    )

    metricas = recursos["metricas_clase"].copy()
    metricas["clase"] = metricas["clase"].map(nucleo.nombre_visible)
    metricas = metricas.rename(
        columns={
            "clase": "Clase",
            "recall": "Detección (recall)",
            "precision": "Acierto de la alarma (precisión)",
            "ap": "Calidad del ordenamiento (AP)",
            "soporte": "Casos en la prueba",
        }
    ).sort_values("Casos en la prueba", ascending=False)
    for col in ["Detección (recall)", "Acierto de la alarma (precisión)",
                "Calidad del ordenamiento (AP)"]:
        metricas[col] = metricas[col].round(3)
    st.dataframe(metricas, hide_index=True, width="stretch")
    st.caption(
        "Cómo leer la tabla: **Detección (recall):** de todos los casos "
        "reales de esa clase, qué fracción encontró el modelo. **Acierto de "
        "la alarma (precisión):** de todas las veces que el modelo anunció esa "
        "clase, qué fracción era correcta. **Calidad del ordenamiento (AP):** "
        "qué tan bien separa esa clase del resto si se mueve el umbral de "
        "decisión (1 = separación perfecta). **Casos en la prueba:** con "
        "cuántos ejemplos se midió; con pocos casos, la cifra es menos firme."
    )

    with st.expander("Ver la matriz de confusión (en qué se equivoca el modelo)"):
        st.caption(
            "Cada fila es la clase verdadera y cada columna la clase que el "
            "modelo predijo, sobre los flujos de la prueba. La diagonal es lo "
            "que acertó; cualquier número fuera de la diagonal es una "
            "confusión concreta (por ejemplo, tráfico normal tomado por Bot)."
        )
        confusion = recursos["confusion"].copy()
        confusion.index = [nucleo.nombre_visible(c) for c in confusion.index]
        confusion.columns = [nucleo.nombre_visible(c) for c in confusion.columns]
        st.dataframe(confusion, width="stretch")


def _tabla_falsas_alarmas_dia(recursos, etiqueta_cuantil: str) -> pd.DataFrame:
    """Tasa de falsas alarmas del detector por día/tramo al umbral elegido (R11).

    Lee el CSV de la evaluación final (test); traduce el nombre del archivo
    crudo a un nombre de tramo legible, en orden cronológico."""
    umbral_pct = float(nucleo.CUANTILES[etiqueta_cuantil]) * 100
    df = recursos["falsas_alarmas_dia"]
    df = df[np.isclose(df["umbral_pct"], umbral_pct)].copy()
    nombres = {
        "Monday-WorkingHours.pcap_ISCX.csv": "Lunes (día de calibración)",
        "Tuesday-WorkingHours.pcap_ISCX.csv": "Martes",
        "Wednesday-workingHours.pcap_ISCX.csv": "Miércoles",
        "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv": "Jueves — mañana",
        "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv": "Jueves — tarde",
        "Friday-WorkingHours-Morning.pcap_ISCX.csv": "Viernes — mañana",
        "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv": "Viernes — tarde (1)",
        "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv": "Viernes — tarde (2)",
    }
    orden = list(nombres)
    df["orden"] = df["dia"].map({d: i for i, d in enumerate(orden)})
    df = df.sort_values("orden")
    return pd.DataFrame(
        {
            "Día / tramo": df["dia"].map(nombres).fillna(df["dia"]),
            "Flujos normales evaluados": df["n_benignos"].astype(int),
            "Falsas alarmas": df["tasa_falsas_alarmas"].astype(float),
        }
    ).reset_index(drop=True)


# ---------------------------------------------------------------- anomalías ---
def pantalla_anomalias(recursos, estado) -> None:
    st.header("Detección de anomalías")
    st.caption(
        "Aquí están los flujos de **tu archivo** cuyo comportamiento se "
        "sale del patrón del tráfico normal, según un detector que **nunca "
        "vio un ataque**: solo aprendió cómo se ve lo normal. Sirve para "
        "atrapar comportamientos raros que un clasificador entrenado con "
        "ejemplos no puede conocer."
    )

    st.markdown(
        "**Cómo se fija el umbral:**\n" 
        "El detector se entrena solo con el tráfico del lunes, que es 100% "
        "benigno. Luego se le pide puntuar ese mismo tráfico conocido-normal, "
        "lo que produce una distribución de qué tan normal se ve cada flujo. "
        "El umbral se fija en el percentil elegido de esa distribución: por "
        "construcción, ese porcentaje del tráfico que sabemos normal queda "
        "por debajo. Cualquier flujo que puntúe por debajo de ese corte se "
        "marca como anómalo. Es decir, este umbral sirve como un **presupuesto "
        "explícito de falsas alarmas**, donde elegir 1% significa \"acepto "
        "equivocarme en 1 de cada 100 flujos normales\"."
    )

    umbral = st.select_slider(
        "Presupuesto de falsas alarmas (umbral del detector)",
        options=list(nucleo.CUANTILES),
        value=UMBRAL_POR_DEFECTO,
        key="umbral_cuantil",
        help="Más bajo = más estricto (menos falsas alarmas, atrapa menos); "
             "más alto = más sensible (atrapa más, con más falsas alarmas). "
             "El umbral elegido aplica también a la marca de anomalía de las "
             "pantallas Alertas y Panel de resumen.",
    )

    if estado is None:
        _sin_archivo()
    else:
        resultado = estado["resultado"]
        anomalo, corte = nucleo.marcar_anomalias(resultado, recursos, umbral)
        st.metric(
            f"Flujos anómalos al umbral del {umbral}",
            f"{int(anomalo.sum()):,} de {len(resultado):,}",
        )
        if anomalo.any():
            tabla = resultado.loc[anomalo, ["fila", "clase", "confianza", "score_anomalia"]]
            tabla = tabla.sort_values("score_anomalia").rename(
                columns={"fila": "Fila del archivo", "clase": "Tipo asignado",
                         "confianza": "Confianza del tipo", "score_anomalia": "Score de anomalía"}
            )
            st.dataframe(
                tabla.style.format({"Confianza del tipo": "{:.1%}",
                                    "Score de anomalía": "{:.3f}"}),
                hide_index=True, width="stretch",
            )
            st.caption(
                "**Cómo leer la tabla:** **Score de anomalía:** qué tan normal se ve el "
                "flujo; más bajo = más raro (la tabla ordena del más raro al "
                "menos). **Tipo asignado:** lo que dijo el clasificador de "
                "tipo para ese mismo flujo; un flujo puede ser anómalo y aun "
                "así estar clasificado como Normal — justamente esos son los "
                "que este detector aporta."
            )
        else:
            st.success(
                f"Ningún flujo de tu archivo queda por debajo del umbral del "
                f"{umbral}. Puedes subir el presupuesto de falsas alarmas con "
                "el deslizador para hacer el detector más sensible."
            )

    st.warning(
        "Este detector ve "
        "lo estructuralmente raro (Heartbleed (robo de memoria con "
        "respuestas gigantes), los ataques 'lentos' tipo slowloris "
        "(conexiones eternas casi sin datos), Infiltration). Es decir, es **ciego a "
        "los ataques camuflados**: fuerza bruta de contraseñas, escaneo de "
        "puertos y Bot. El motivo es que en esos ataques cada flujo individual "
        "parece una conexión normal; lo anómalo está en el **conjunto** "
        "(miles de conexiones casi idénticas en minutos), y un detector que "
        "mira flujos de a uno no puede verlo. Para esos tipos está el "
        "clasificador supervisado."
    )

    st.divider()
    st.subheader("Resultado de la evaluación del proyecto (resultado fijo)")
    st.caption(
        "Fuente: la evaluación del proyecto como tal, no tu archivo. Con el "
        "presupuesto de falsas alarmas en 1%: el detector encontró el 89% de "
        "los flujos de Heartbleed, el 52% de slowloris y el 48% de "
        "Infiltration (sin haber visto jamás un ataque etiquetado) y un "
        "11,8% de los ataques en general (por el punto ciego de arriba)."
    )

    # ---- R11: falsas alarmas desagregadas por día (deriva temporal) ----
    st.markdown("**Falsas alarmas por día: la señal de deriva**")
    st.caption(
        "Fuente: la evaluación final sobre el conjunto de prueba (flujos que el "
        "detector nunca vio). La tabla sigue al presupuesto elegido arriba: "
        f"ahora mismo, {umbral}."
    )
    tabla_dia = _tabla_falsas_alarmas_dia(recursos, umbral)
    st.dataframe(
        tabla_dia.style.format({"Falsas alarmas": "{:.1%}"}),
        hide_index=True,
        width="stretch",
        column_config={
            "Falsas alarmas": st.column_config.ProgressColumn(
                "Falsas alarmas", min_value=0.0,
                max_value=float(max(0.12, tabla_dia["Falsas alarmas"].max())),
                format="%.1f%%",
            )
        },
    )
    peor = tabla_dia.loc[tabla_dia["Falsas alarmas"].idxmax()]
    peor_pct = f"{peor['Falsas alarmas']:.1%}".replace(".", ",")  # 9,6% en prosa
    veces = round(peor["Falsas alarmas"] / float(nucleo.CUANTILES[umbral]))
    st.markdown(
        "**Cómo leerla y por qué es importante.** El detector se calibró con el "
        "tráfico del **lunes**, que es 100% benigno: aprendió cómo se ve lo "
        "normal *ese día*. Cuando el tráfico normal de otro día se comporta "
        "distinto, el detector lo ve raro y las falsas alarmas suben aunque "
        "no haya ningún ataque. A eso se llama **deriva**: el tráfico normal "
        "cambia con el tiempo. En la tabla, casi todos los tramos quedan "
        f"cerca del presupuesto elegido, pero el tramo *{peor['Día / tramo']}* "
        f"llegó a **{peor_pct}** con un presupuesto del {umbral}: casi "
        f"{veces} veces más falsas alarmas de las aceptadas. "
        "**Lección para un despliegue real:** un detector de este tipo no se "
        "calibra una vez; hay que medir esta tabla periódicamente "
        "y **recalibrar** (re-entrenar con tráfico normal reciente) cuando la "
        "tasa se aleje del presupuesto. Esa medición continua es lo que "
        "permitiría decidir *cuándo* re-entrenar, en vez de adivinarlo."
    )


# ---------------------------------------------------------- interpretabilidad ---
@st.cache_resource(show_spinner="Preparando el explicador de alertas (solo la primera vez)…")
def _explicador(_modelo):
    import shap

    return shap.TreeExplainer(_modelo)


def pantalla_interpretabilidad(recursos, estado) -> None:
    st.header("Interpretabilidad")
    st.caption(
        "Aquí puedes ver en qué se fija el modelo para tomar sus decisiones. "
        "Primero en general, con el resultado fijo de la evaluación, y luego "
        "para **cada alerta de tu archivo**, de forma que puedas justificar "
        "una alerta ante otras personas."
    )

    # ---- 1) global (fijo) ----
    st.subheader("Resultado Fijo: Qué distingue un ataque del tráfico normal")
    st.caption(
        "Fuente: la evaluación del proyecto. Esta tabla responde a la "
        "pregunta general **¿en qué se nota que algo es un ataque?**, por eso "
        "se midió sobre el modelo que decide *ataque sí/no*. Para medirlo "
        "usamos la *importancia por permutación*, que consiste en barajar una "
        "característica a la vez (rompiendo su relación con la realidad) y "
        "medir cuánto empeora el modelo sobre flujos que nunca vio. Si empeora "
        "mucho, quiere decir que dependía de esa característica. Más abajo, "
        "para cada alerta de tu archivo, se explica la decisión del **otro** "
        "modelo, que es el que asigna el tipo de ataque."
    )
    importancia = recursos["importancia"].head(10).copy()
    importancia["Característica"] = importancia["feature"].map(nombre_llano)
    st.dataframe(
        importancia[["Característica", "importancia_media"]].rename(
            columns={"importancia_media": "Cuánto depende el modelo de ella"}
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Cuánto depende el modelo de ella": st.column_config.ProgressColumn(
                "Cuánto depende el modelo de ella",
                min_value=0.0,
                max_value=float(importancia["importancia_media"].max()),
                format="%.3f",
            )
        },
    )
    st.caption(
        "La barra indica cuánto empeora el modelo al barajar esa "
        "característica (medido en macro-F1, el puntaje que promedia qué tan "
        "bien se detecta cada clase). En general, para separar un ataque del "
        "tráfico normal lo que más pesa es la **duración** de la conversación, "
        "la **puerta contactada**, el **tamaño de los paquetes de respuesta** "
        "y el **ritmo**, es decir, el comportamiento del tráfico."
    )

    st.markdown(
        "**Prueba de la puerta (puerto de destino):** "
        "La segunda característica más influyente es la puerta del servicio "
        "contactado, y eso nos generó una duda metodológica, porque en el "
        "dataset cada ataque usa siempre su puerta típica (el ataque web la "
        "80, el de acceso remoto la 22), algo que en el mundo real nadie "
        "garantiza. Para saber si el modelo detecta comportamiento o si "
        "simplemente memorizó puertas, lo reentrenamos **sin** esa "
        "característica y el desempeño pasó de 0,970 a 0,950 en validación y "
        "de 0,967 a 0,942 en el test. Es una caída pequeña, lo que indica que "
        "el modelo sí aprende **comportamiento** y que la puerta solo le ayuda "
        "a descartar falsas alarmas en las clases más difíciles."
    )

    # ---- 2) individual (vivo) ----
    st.divider()
    st.subheader("Por qué se marcó cada alerta (Archivo del Usuario)")
    st.caption(
        "Aquí se explica la decisión del modelo que asigna el **tipo** de "
        "ataque, que es el mismo que produjo la columna 'Tipo de ataque' en "
        "la pantalla de Alertas. Por eso los pesos de abajo se leen respecto "
        "al tipo asignado a esa alerta y no respecto a 'ataque sí/no'."
    )
    if estado is None:
        _sin_archivo()
        return
    resultado = estado["resultado"]
    alertas = resultado[resultado["clase"] != nucleo.NOMBRE_NORMAL]
    if alertas.empty:
        st.info(
            "Tu archivo no generó alertas, así que no hay decisiones "
            "individuales para explicar. Puedes cargar la demo rica en ataques "
            "para ver cómo funciona esta sección."
        )
        return

    opciones = {
        f"Fila {int(f.fila)}: {f.clase} (confianza {f.confianza:.0%})": int(f.fila)
        for f in alertas.itertuples()
    }
    seleccion = st.selectbox(
        "Elige una alerta para ver qué pesó en esa decisión",
        list(opciones),
        help="La explicación se calcula en el momento para el flujo elegido "
             "(tarda milisegundos).",
    )
    fila = opciones[seleccion]
    clase_alerta = resultado.loc[resultado["fila"] == fila, "clase"].iloc[0]

    datos = estado["reporte"].datos
    X = datos.loc[[fila - 1], recursos["meta"]["caracteristicas"]].astype("float32").values

    explicador = _explicador(recursos["multiclase"])
    valores = np.asarray(explicador.shap_values(X))[0]  # (48, 11)
    clases = list(recursos["multiclase"].classes_)
    idx = clases.index(nucleo.ETIQUETA_NORMAL if clase_alerta == nucleo.NOMBRE_NORMAL else clase_alerta)
    contribucion = valores[:, idx]

    orden = np.argsort(-np.abs(contribucion))[:8]
    caracteristicas = recursos["meta"]["caracteristicas"]
    tabla = pd.DataFrame(
        {
            "Característica": [nombre_llano(caracteristicas[i]) for i in orden],
            "Valor en este flujo": [float(X[0, i]) for i in orden],
            "Peso en la decisión": [float(contribucion[i]) for i in orden],
            "Dirección": [
                f"A favor de {clase_alerta}" if contribucion[i] > 0 else "En contra"
                for i in orden
            ],
        }
    )
    st.dataframe(
        tabla.style.format({"Valor en este flujo": "{:,.2f}", "Peso en la decisión": "{:+.2f}"}),
        hide_index=True,
        width="stretch",
        column_config={
            "Característica": st.column_config.TextColumn(width="large"),
            "Dirección": st.column_config.TextColumn(width="medium"),
        },
    )
    st.caption(
        "**Cómo leer la tabla:** la técnica que usamos (SHAP) reparte la "
        "'responsabilidad' de la decisión entre las características del flujo. "
        f"Un **peso positivo** (a favor de {clase_alerta}) significa que esa "
        "característica empujó al modelo hacia esa clase, y un **peso "
        "negativo** (en contra) significa que lo empujó hacia otra. Se "
        "muestran las 8 características con más peso, junto con el valor que "
        "tenía el flujo en cada una. De esta forma cada alerta viene con una "
        "razón concreta que se puede revisar y explicar a otra persona."
    )


# ----------------------------------------------------------------- alertas ---
def pantalla_alertas(recursos, estado) -> None:
    st.header("Alertas")
    st.caption(
        "Aquí encontrarás la lista de flujos de **tu archivo** que vale la "
        "pena revisar, con filtros para priorizar. Una *alerta* es un flujo "
        "que el modelo clasificó como algún tipo de ataque. La marca de "
        "*anomalía* indica además si su comportamiento se sale del patrón del "
        "tráfico normal, según un segundo detector independiente."
    )
    if estado is None:
        _sin_archivo()
        return

    _nota_tres_modelos()

    resultado = estado["resultado"]
    umbral = umbral_actual()
    anomalo, _ = nucleo.marcar_anomalias(resultado, recursos, umbral)
    resultado = resultado.assign(anomalo=anomalo)
    alertas = resultado[resultado["clase"] != nucleo.NOMBRE_NORMAL].copy()
    if alertas.empty:
        st.success(
            "El modelo no clasificó ningún flujo de tu archivo como ataque. "
            "Ten en cuenta el intercambio que se explica en el Panel de "
            "resumen, esto no garantiza que no haya nada malicioso, solo que "
            "ningún flujo superó los criterios del modelo."
        )
        return

    st.markdown(f"**{len(alertas):,} alertas** de {len(resultado):,} flujos cargados.")

    f1, f2, f3 = st.columns(3)
    tipos = sorted(alertas["clase"].unique())
    tipos_sel = f1.multiselect("Tipo de ataque", tipos, default=tipos,
                               help="Deja solo los tipos que quieres revisar.")
    conf_min = f2.slider(
        "Confianza mínima", 0.0, 1.0, 0.0, 0.05,
        help="Oculta las alertas en las que el modelo tuvo más dudas. Con 0 "
             "se muestran todas.",
    )
    filtro_anomalia = f3.selectbox(
        "Marca de anomalía", ["Todas", "Solo anómalas", "Solo no anómalas"],
        help=f"Filtra según la marca del detector de anomalías (umbral actual: "
             f"{umbral}, se puede ajustar en la pantalla Detección de anomalías).",
    )

    filtradas = alertas[alertas["clase"].isin(tipos_sel) & (alertas["confianza"] >= conf_min)]
    if filtro_anomalia == "Solo anómalas":
        filtradas = filtradas[filtradas["anomalo"]]
    elif filtro_anomalia == "Solo no anómalas":
        filtradas = filtradas[~filtradas["anomalo"]]

    st.markdown(f"Mostrando **{len(filtradas):,}** alertas con el filtro aplicado.")
    tabla = filtradas.rename(
        columns={
            "fila": "Fila del archivo",
            "clase": "Tipo de ataque",
            "confianza": "Confianza",
            "clase_binaria": "¿Ataque? (modelo binario)",
            "prob_ataque": "Prob. de ataque",
            "anomalo": "Anómalo",
            "score_anomalia": "Score de anomalía",
        }
    )
    if len(filtradas) == 0:
        st.info(
            "Ningún flujo cumple con el filtro actual. Prueba aflojando alguno "
            "de los tres filtros de arriba para volver a ver alertas."
        )
    else:
        st.dataframe(
            tabla.style.format({"Confianza": "{:.1%}", "Prob. de ataque": "{:.1%}",
                                "Score de anomalía": "{:.3f}"}),
            hide_index=True, width="stretch",
        )
        st.caption(
            "**Cómo leer la tabla:** **Fila del archivo:** posición del flujo "
            "en tu CSV (la primera fila de datos es la 1), para que puedas "
            "ubicarlo en tu sistema. **Confianza:** probabilidad que el modelo "
            "le asigna al tipo de ataque elegido. **¿Ataque? y Prob. de "
            "ataque:** el veredicto de un segundo modelo más simple que solo "
            "decide si el flujo es ataque o normal. **Anómalo y Score:** el "
            "resultado del detector de anomalías, donde un score más bajo "
            "quiere decir un comportamiento más raro frente al tráfico normal."
        )

    # El filtro vigente queda disponible para la pantalla Reportes
    st.session_state["alertas_filtradas"] = tabla
    st.session_state["descripcion_filtro"] = (
        f"{len(filtradas):,} alertas (tipos: {len(tipos_sel)} de {len(tipos)}; "
        f"confianza ≥ {conf_min:.0%}; anomalía: {filtro_anomalia.lower()}; "
        f"umbral {umbral})"
    )

    # Exportación (respeta el filtro aplicado) — se genera en memoria
    csv = io.StringIO()
    tabla.to_csv(csv, index=False)
    exporto = st.download_button(
        "Descargar estas alertas en CSV",
        data=csv.getvalue().encode("utf-8-sig"),
        file_name="alertas_filtradas.csv",
        mime="text/csv",
        disabled=len(filtradas) == 0,
        help="Exporta exactamente las alertas que ves, con el filtro aplicado.",
    )
    if exporto:
        registrar("Exportación de alertas", estado["nombre"], len(resultado),
                  len(filtradas), umbral)
        st.toast(f"Exportadas {len(filtradas):,} alertas.", icon="📄")


# ---------------------------------------------------------------- reportes ---
def pantalla_reportes(recursos, estado) -> None:
    st.header("Reportes")
    st.caption(
        "Aquí encontrarás las descargas disponibles (siempre en CSV, un "
        "formato de tabla que se abre con cualquier hoja de cálculo) y el "
        "historial de lo que has hecho en esta sesión."
    )
    st.info(
        "**Nota:** la herramienta no exporta en PDF, ya que el CSV cubre la "
        "necesidad y así se mantiene liviana. Además, el historial **no se "
        "guarda entre sesiones**: al cerrar el navegador se borra junto con "
        "tu archivo, así que si necesitas conservar algún resultado, "
        "descárgalo antes de salir."
    )

    st.subheader("Descargas")
    umbral = umbral_actual()
    if estado is None:
        st.caption("Carga un archivo para habilitar las descargas de resultados.")
    else:
        resultado = estado["resultado"]
        anomalo, _ = nucleo.marcar_anomalias(resultado, recursos, umbral)
        completo = resultado.assign(anomalo=anomalo).rename(
            columns={"fila": "Fila del archivo", "clase": "Tipo asignado",
                     "confianza": "Confianza", "clase_binaria": "¿Ataque?",
                     "prob_ataque": "Prob. de ataque", "anomalo": "Anómalo",
                     "score_anomalia": "Score de anomalía"}
        )
        c1, c2 = st.columns(2)

        buf = io.StringIO()
        completo.to_csv(buf, index=False)
        if c1.download_button(
            f"Resultados completos ({len(completo):,} flujos)",
            data=buf.getvalue().encode("utf-8-sig"),
            file_name="resultados_completos.csv", mime="text/csv",
            width="stretch",
            help="Todos los flujos clasificados de tu archivo, con la marca "
                 f"de anomalía al umbral actual ({umbral}).",
        ):
            registrar("Exportación de resultados", estado["nombre"],
                      len(completo), int((completo["Tipo asignado"] != nucleo.NOMBRE_NORMAL).sum()),
                      umbral)
            st.toast("Resultados completos exportados.", icon="📄")

        filtradas = st.session_state.get("alertas_filtradas")
        if filtradas is not None and len(filtradas) > 0:
            buf2 = io.StringIO()
            filtradas.to_csv(buf2, index=False)
            if c2.download_button(
                f"Alertas con el filtro de la pantalla Alertas "
                f"({len(filtradas):,})",
                data=buf2.getvalue().encode("utf-8-sig"),
                file_name="alertas_filtradas.csv", mime="text/csv",
                width="stretch",
                help=st.session_state.get("descripcion_filtro", ""),
            ):
                registrar("Exportación de alertas", estado["nombre"],
                          len(resultado), len(filtradas), umbral)
                st.toast(f"Exportadas {len(filtradas):,} alertas.", icon="📄")
        else:
            c2.caption(
                "Para exportar solo una parte de las alertas, aplica primero "
                "un filtro en la pantalla Alertas y aquí aparecerá la descarga "
                "con ese filtro."
            )

    metricas = recursos["metricas_clase"].copy()
    metricas["clase"] = metricas["clase"].map(nucleo.nombre_visible)
    buf3 = io.StringIO()
    metricas.to_csv(buf3, index=False)
    st.download_button(
        "Métricas del modelo por clase (resultado fijo de la evaluación)",
        data=buf3.getvalue().encode("utf-8-sig"),
        file_name="metricas_modelo.csv", mime="text/csv",
        help="El desempeño del modelo en su test final, por clase. No "
             "depende de tu archivo.",
    )

    st.subheader("Historial de la sesión")
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial),
                     hide_index=True, width="stretch")
        st.caption(
            "Cada fila es una acción de esta sesión, con lo que se clasificó "
            "o exportó, cuántos flujos y alertas había y con qué umbral de "
            "anomalía (el presupuesto de falsas alarmas elegido en la "
            "pantalla Detección de anomalías)."
        )
    else:
        st.caption("Aún no hay acciones en esta sesión.")
