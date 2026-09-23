"""Evidencia de los apéndices del reporte técnico final (reports/reporte_tecnico_final.pdf).

Apéndice A — colinealidad. Re-deriva los bloques de variables con |r| > 0,95
sobre la MISMA muestra con la que se tomó la decisión de poda 71 -> 48
(500.000 flujos del conjunto de ENTRENAMIENTO, semilla 42; ver
src/features.py), verifica que coinciden exactamente con
GRUPOS_CORRELACIONADOS y dibuja la figura 18 (nueva; no reemplaza ninguna).

Apéndice B — parámetros. Lee la configuración completa de los tres modelos
serializados en models/ (get_params) y la de los estimadores del protocolo
tal como los construye el código de src/ (no de memoria). "Explícito" significa
ESCRITO EN LA LLAMADA del código fuente: se leen las llamadas de src/ con `ast`,
de modo que un parámetro fijado a un valor igual al default (p. ej.
LocalOutlierFactor(n_neighbors=20)) cuenta como explícito. El resto quedó en el
valor por defecto de la librería.

Salidas: reports/apendices/*.csv y *.tex (fragmentos que se pegan en el
reporte) y reports/figures/18_correlaciones_train_095.png. No lee el conjunto
de prueba ni recalcula ninguna cifra oficial del proyecto.

Ejecutar desde la raíz del proyecto, con el entorno de ANÁLISIS (necesita
imblearn y los datos locales):
    .venv\\Scripts\\python.exe reports/apendices/generar_apendices.py
"""

import inspect
import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.model_selection import StratifiedKFold, train_test_split  # noqa: E402
from sklearn.neighbors import LocalOutlierFactor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.config import (  # noqa: E402
    ARCHIVO_TRAIN,
    PROPORCION_TEST,
    RANDOM_STATE,
    RUTA_FIGURAS,
)
from src.evaluacion_final import CUANTILES_UMBRAL_IF, UMBRAL_BOT  # noqa: E402
from src.experimentos import (  # noqa: E402
    OBJETIVO_BENIGN,
    OBJETIVO_SMOTE,
    TECNICAS,
    construir_pipeline,
)
from src.features import GRUPOS_CORRELACIONADOS, calcular_grupos  # noqa: E402
from src.interpretabilidad import (  # noqa: E402
    FEATURES_IDENTIFICADORAS,
    N_VALIDACION_PERMUTACION,
)
from src.no_supervisado import N_SUBMUESTRA_LOF  # noqa: E402

SALIDA = Path(__file__).resolve().parent
RUTA_MODELOS = RAIZ / "models"
FIGURA = RUTA_FIGURAS / "18_correlaciones_train_095.png"
UMBRAL_R = 0.95
N_MUESTRA = 500_000  # el mismo de src/features.py


# ------------------------------------------------------------------ utilidades
def tex(s) -> str:
    """Escapa texto para LaTeX."""
    s = str(s)
    s = s.replace("\\", r"\textbackslash{}")
    for a, b in [("_", r"\_"), ("%", r"\%"), ("&", r"\&"), ("#", r"\#"),
                 ("$", r"\$"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}")]:
        s = s.replace(a, b)
    return s


def valor(v) -> str:
    """Representación legible de un valor de parámetro."""
    if callable(v) and hasattr(v, "__name__"):
        return f"función {v.__name__}"  # se parte en el .tex con \\allowbreak
    if isinstance(v, float):
        return repr(v)
    return repr(v)


def defaults_de(cls_o_func) -> dict:
    sig = inspect.signature(cls_o_func.__init__ if inspect.isclass(cls_o_func) else cls_o_func)
    return {k: p.default for k, p in sig.parameters.items() if k != "self"}


# ------------------------------------------------------------ Apéndice A: |r|
def apendice_a() -> None:
    print("[A] leyendo el conjunto de entrenamiento…", flush=True)
    train = pd.read_parquet(ARCHIVO_TRAIN)
    numericas = train.select_dtypes(include=[np.number]).columns
    print(f"    {len(train):,} flujos, {len(numericas)} variables numéricas", flush=True)

    grupos = calcular_grupos(train, UMBRAL_R, N_MUESTRA)
    tabla = [set([g["representante"], *g["eliminadas"]]) for g in GRUPOS_CORRELACIONADOS]
    assert len(grupos) == len(tabla) == 13, (len(grupos), len(tabla))
    assert all(any(t == g for g in grupos) for t in tabla), "los bloques NO coinciden con src/features.py"

    muestra = train.sample(n=min(N_MUESTRA, len(train)), random_state=RANDOM_STATE)
    num = muestra.select_dtypes(include=[np.number])
    corr = num.corr().abs()
    pares = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
    n_pares = int((pares > UMBRAL_R).sum())
    print(f"    pares con |r| > {UMBRAL_R}: {n_pares}; bloques: {len(grupos)} "
          f"(coinciden exactamente con GRUPOS_CORRELACIONADOS)", flush=True)

    # Orden de la figura: bloque a bloque (orden de la tabla), representante primero
    orden, limites, representantes = [], [], []
    for g in GRUPOS_CORRELACIONADOS:
        ini = len(orden)
        orden += [g["representante"], *g["eliminadas"]]
        limites.append((ini, len(orden)))
        representantes.append(g["representante"])
    sub = corr.loc[orden, orden].values

    # CSV con el detalle de cada bloque (r mínimo y máximo dentro del bloque)
    filas = []
    for k, (g, (a, b)) in enumerate(zip(GRUPOS_CORRELACIONADOS, limites), 1):
        bloque = sub[a:b, a:b]
        fuera = bloque[~np.eye(b - a, dtype=bool)]
        filas.append({
            "bloque": k, "representante_conservada": g["representante"],
            "eliminadas": "; ".join(g["eliminadas"]), "n_eliminadas": len(g["eliminadas"]),
            "r_abs_min_en_bloque": round(float(fuera.min()), 4),
            "r_abs_max_en_bloque": round(float(fuera.max()), 4), "razon": g["razon"],
        })
    df_bloques = pd.DataFrame(filas)
    df_bloques.to_csv(SALIDA / "bloques_correlacion_train.csv", index=False, encoding="utf-8")

    # Fragmento LaTeX: tabla textual de GRUPOS_CORRELACIONADOS
    lineas = [
        "% Generado por reports/apendices/generar_apendices.py a partir de",
        "% GRUPOS_CORRELACIONADOS (src/features.py). No editar a mano.",
        r"\begin{longtable}{C{0.6cm} L{3.0cm} L{4.2cm} L{6.3cm}}",
        r"\caption{Los 13 bloques de variables redundantes ($|r| > 0{,}95$ sobre "
        + f"{N_MUESTRA:,}".replace(",", ".") + " flujos del conjunto de entrenamiento, semilla "
        f"{RANDOM_STATE}). Texto tomado literalmente de \\texttt{{GRUPOS\\_CORRELACIONADOS}} "
        r"en \texttt{src/features.py}.}\label{tab:bloques}\\",
        r"\toprule",
        r"\textbf{\#} & \textbf{Representante conservada} & \textbf{Variables eliminadas} & \textbf{Razón de la elección} \\",
        r"\midrule", r"\endfirsthead",
        r"\toprule",
        r"\textbf{\#} & \textbf{Representante conservada} & \textbf{Variables eliminadas} & \textbf{Razón de la elección} \\",
        r"\midrule", r"\endhead",
        r"\bottomrule", r"\endfoot",
    ]
    for k, g in enumerate(GRUPOS_CORRELACIONADOS, 1):
        elim = ", ".join(f"\\texttt{{{tex(e)}}}" for e in g["eliminadas"])
        lineas.append(f"{k} & \\texttt{{{tex(g['representante'])}}} & {elim} & {tex(g['razon'])} \\\\")
    lineas.append(r"\end{longtable}")
    (SALIDA / "tabla_bloques.tex").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    # Figura 18: mapa de |r| de las 36 variables implicadas, bloque a bloque
    fig, ax = plt.subplots(figsize=(12.5, 11))
    im = ax.imshow(sub, cmap="Blues", vmin=0, vmax=1, interpolation="nearest")
    n = len(orden)
    etiquetas = [f"★ {c}" if c in representantes else c for c in orden]
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(etiquetas, rotation=90, fontsize=7.5)
    ax.set_yticklabels(etiquetas, fontsize=7.5)
    for lbl in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
        if lbl.get_text().startswith("★"):
            lbl.set_fontweight("bold")
    for a, b in limites:
        ax.add_patch(Rectangle((a - 0.5, a - 0.5), b - a, b - a, fill=False,
                               edgecolor="black", linewidth=1.6))
        for i in range(a, b):
            for j in range(a, b):
                if i != j:
                    ax.text(j, i, f"{sub[i, j]:.2f}".replace(".", ","), ha="center",
                            va="center", fontsize=5.5,
                            color="white" if sub[i, j] > 0.6 else "black")
    ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.4)
    ax.tick_params(which="minor", length=0)
    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("|correlación de Pearson|")
    n_muestra_txt = f"{N_MUESTRA:,}".replace(",", ".")
    ax.set_title(
        f"Bloques de variables redundantes (|r| > 0,95): {n_pares} pares, {len(grupos)} bloques, "
        f"{n} variables\nMuestra de {n_muestra_txt} flujos del conjunto de ENTRENAMIENTO "
        f"(semilla {RANDOM_STATE}). ★ = representante conservada",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(FIGURA, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"    figura: {FIGURA}", flush=True)


# ------------------------------------------------------- Apéndice B: parámetros
# Criterio de "explícito": el parámetro está ESCRITO en la llamada del código
# fuente (se leen las llamadas con `ast`), aunque su valor coincida con el
# valor por defecto de la librería (p. ej. LocalOutlierFactor(n_neighbors=20)).
# Comparar valor contra default —el criterio anterior— fallaba en ese caso.
FUENTES = {
    # clase -> archivos de src/ donde se instancia; todas las llamadas de una
    # clase deben escribir los mismos argumentos (se verifica).
    "HistGradientBoostingClassifier": ["src/modelo_final.py", "src/experimentos.py",
                                       "src/interpretabilidad.py", "src/evaluacion_final.py"],
    "IsolationForest": ["src/modelo_final.py", "src/no_supervisado.py", "src/evaluacion_final.py"],
    "StandardScaler": ["src/modelo_final.py", "src/experimentos.py", "src/no_supervisado.py",
                       "src/interpretabilidad.py", "src/evaluacion_final.py"],
    "LogisticRegression": ["src/experimentos.py", "src/interpretabilidad.py"],
    "SMOTE": ["src/experimentos.py"],
    "RandomUnderSampler": ["src/experimentos.py"],
    "LocalOutlierFactor": ["src/no_supervisado.py"],
    "StratifiedKFold": ["src/experimentos.py", "src/interpretabilidad.py"],
    "train_test_split": ["src/split.py"],
    "permutation_importance": ["src/interpretabilidad.py"],
}


LLAMADAS: list[dict] = []  # evidencia: cada llamada encontrada y sus argumentos


def argumentos_escritos(nombre: str, archivos: list[str]) -> set[str]:
    """Nombres de los argumentos escritos en las llamadas a `nombre` en src/.

    Recorre el árbol sintáctico de cada archivo y registra cada llamada en
    LLAMADAS (archivo:línea -> argumentos). Devuelve la unión; si distintas
    llamadas escriben conjuntos distintos, lo avisa (p. ej. LogisticRegression
    lleva class_weight en experimentos.py y no en interpretabilidad.py).
    Los argumentos posicionales (los datos) se anotan aparte.
    """
    import ast

    conjuntos = {}
    for archivo in archivos:
        arbol = ast.parse((RAIZ / archivo).read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            f = nodo.func
            llamado = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if llamado != nombre:
                continue
            escritos = {k.arg for k in nodo.keywords if k.arg is not None}
            posicionales = len(nodo.args)
            conjuntos[f"{archivo}:{nodo.lineno}"] = frozenset(escritos)
            LLAMADAS.append({"objeto": nombre, "donde": f"{archivo}:{nodo.lineno}",
                             "argumentos_con_nombre": ", ".join(sorted(escritos)),
                             "argumentos_posicionales": posicionales})
    assert conjuntos, f"no se encontró ninguna llamada a {nombre} en {archivos}"
    if len(set(conjuntos.values())) > 1:
        print(f"    aviso: llamadas a {nombre} con argumentos distintos; se usa la unión: "
              + "; ".join(f"{d} -> {sorted(a)}" for d, a in conjuntos.items()), flush=True)
    return set().union(*conjuntos.values())


def apendice_b() -> None:
    print("[B] leyendo modelos serializados y estimadores del protocolo…", flush=True)
    escritos = {clase: argumentos_escritos(clase, archivos) for clase, archivos in FUENTES.items()}
    for clase, args in escritos.items():
        print(f"    {clase}: escritos en el código -> {sorted(args)}", flush=True)
    filas: list[dict] = []
    ajustados: list[dict] = []

    def fila(modelo, est_clase, k, v, por_defecto, contexto, escrito):
        coincide = (v is por_defecto) or (v == por_defecto)
        return {
            "contexto": contexto, "modelo": modelo, "clase": est_clase, "parametro": k,
            "valor": valor(v), "valor_por_defecto": valor(por_defecto),
            "escrito_en_codigo": bool(escrito), "coincide_con_default": bool(coincide),
            "origen": "explícito" if escrito else "por defecto",
            "criterio_anterior": "por defecto" if coincide else "explícito",
            "archivos_fuente": "; ".join(FUENTES.get(est_clase, [])),
        }

    def filas_de(modelo, est, contexto):
        clase = type(est).__name__
        d = defaults_de(type(est))
        return [fila(modelo, clase, k, v, d.get(k, object()), contexto, k in escritos[clase])
                for k, v in est.get_params(deep=False).items()]

    # --- (a) los tres modelos serializados, tal como están en models/ ---
    multi = joblib.load(RUTA_MODELOS / "modelo_multiclase.joblib")
    bina = joblib.load(RUTA_MODELOS / "modelo_binario.joblib")
    det = joblib.load(RUTA_MODELOS / "detector_anomalias.joblib")
    meta = json.loads((RUTA_MODELOS / "metadatos.json").read_text(encoding="utf-8"))
    assert multi.get_params() == bina.get_params(), "los dos HistGB deberían tener la misma configuración"

    filas += filas_de("Clasificador multiclase", multi, "models/modelo_multiclase.joblib")
    filas += filas_de("Clasificador binario", bina, "models/modelo_binario.joblib")
    filas += filas_de("Detector de anomalías (bosque)", det["bosque"], "models/detector_anomalias.joblib")
    filas += filas_de("Detector de anomalías (escalador)", det["escalador"], "models/detector_anomalias.joblib")

    # --- (b) atributos ajustados: iteraciones reales y parada temprana ---
    for nombre, m in [("Clasificador multiclase", multi), ("Clasificador binario", bina)]:
        ajustados.append({
            "modelo": nombre,
            "max_iter (máximo permitido)": m.get_params()["max_iter"],
            "early_stopping (parámetro)": m.get_params()["early_stopping"],
            "do_early_stopping_ (efectivo)": bool(m.do_early_stopping_),
            "n_iter_ (iteraciones usadas)": int(m.n_iter_),
            "n_trees_per_iteration_": int(m.n_trees_per_iteration_),
            "arboles_totales": int(m.n_iter_ * m.n_trees_per_iteration_),
            "mejor_iteracion_validacion": int(np.argmax(m.validation_score_)),
            "n_features_in_": int(m.n_features_in_),
            "n_clases": len(m.classes_),
        })
    ajustados.append({
        "modelo": "Detector de anomalías (bosque)",
        "max_samples_ (flujos por árbol)": int(det["bosque"].max_samples_),
        "n_features_in_": int(det["bosque"].n_features_in_),
        "umbrales_por_cuantil": json.dumps(det["umbrales"]),
        "flujos_de_calibracion (escalador.n_samples_seen_)": int(det["escalador"].n_samples_seen_),
    })
    pd.DataFrame(ajustados).to_csv(SALIDA / "atributos_ajustados.csv", index=False, encoding="utf-8")

    # --- (c) estimadores del protocolo, construidos por el propio código de src/ ---
    for tecnica in TECNICAS:
        for modelo in ["reglog", "arboles"]:
            pipe = construir_pipeline(modelo, tecnica)
            for paso, est in pipe.named_steps.items():
                filas += filas_de(f"Matriz Fase 3: {modelo} + {tecnica} (paso '{paso}')", est,
                                  "src/experimentos.py::construir_pipeline")
    # LOF e Isolation Forest del análisis, instanciados como en src/
    lof = LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=-1)
    filas += filas_de("Contraste no supervisado: LOF", lof,
                      "src/no_supervisado.py (submuestra de %d flujos del lunes)" % N_SUBMUESTRA_LOF)
    filas += filas_de("Isolation Forest del análisis",
                      IsolationForest(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1),
                      "src/no_supervisado.py y src/evaluacion_final.py")
    # Validación cruzada, partición e importancia por permutación (no exponen get_params)
    d_cv = defaults_de(StratifiedKFold)
    for k, v in {"n_splits": 5, "shuffle": True, "random_state": RANDOM_STATE}.items():
        filas.append(fila("Validación cruzada", "StratifiedKFold", k, v, d_cv.get(k),
                          "src/experimentos.py, src/interpretabilidad.py, notebooks/02_baseline.ipynb",
                          k in escritos["StratifiedKFold"]))
    d_split = defaults_de(train_test_split)
    for k, v in {"test_size": PROPORCION_TEST, "stratify": "Label", "random_state": RANDOM_STATE}.items():
        filas.append(fila("Partición única", "train_test_split", k, v, d_split.get(k),
                          "src/split.py", k in escritos["train_test_split"]))
    d_perm = defaults_de(permutation_importance)
    for k, v in {"scoring": "f1_macro", "n_repeats": 5, "random_state": RANDOM_STATE, "n_jobs": -1}.items():
        filas.append(fila("Importancia por permutación", "permutation_importance", k, v, d_perm.get(k),
                          "src/interpretabilidad.py::importancia_permutacion",
                          k in escritos["permutation_importance"]))

    # Constantes del protocolo (no son parámetros de estimadores)
    constantes = {
        "RANDOM_STATE (semilla única)": RANDOM_STATE,
        "PROPORCION_TEST": PROPORCION_TEST,
        "OBJETIVO_SMOTE (tamaño al que se elevan las clases minoritarias)": OBJETIVO_SMOTE,
        "OBJETIVO_BENIGN (tamaño al que se reduce BENIGN en el submuestreo)": OBJETIVO_BENIGN,
        "N_SUBMUESTRA_LOF": N_SUBMUESTRA_LOF,
        "N_VALIDACION_PERMUTACION": N_VALIDACION_PERMUTACION,
        "CUANTILES_UMBRAL_IF": CUANTILES_UMBRAL_IF,
        "UMBRAL_BOT": UMBRAL_BOT,
        "FEATURES_IDENTIFICADORAS": FEATURES_IDENTIFICADORAS,
        "Umbral de colinealidad |r|": UMBRAL_R,
        "Muestra para la correlación (train)": N_MUESTRA,
        "version_sklearn (metadatos.json)": meta["version_sklearn"],
    }
    for k, v in constantes.items():
        filas.append({"contexto": "src/config.py, src/experimentos.py, src/no_supervisado.py, "
                                  "src/interpretabilidad.py, src/evaluacion_final.py, src/features.py",
                      "modelo": "Constantes del protocolo", "clase": "constante", "parametro": k,
                      "valor": valor(v), "valor_por_defecto": "", "escrito_en_codigo": True,
                      "coincide_con_default": False, "origen": "explícito",
                      "criterio_anterior": "explícito", "archivos_fuente": ""})

    df = pd.DataFrame(filas)
    df.to_csv(SALIDA / "parametros_modelos.csv", index=False, encoding="utf-8")
    pd.DataFrame(LLAMADAS).to_csv(SALIDA / "llamadas_en_codigo.csv", index=False, encoding="utf-8")
    cambios = df[df["origen"] != df["criterio_anterior"]]
    cambios.to_csv(SALIDA / "cambios_de_criterio.csv", index=False, encoding="utf-8")
    print(f"    {len(df)} filas de parámetros -> parametros_modelos.csv", flush=True)
    print(f"    {len(cambios)} filas cambian de clasificación con el criterio 'escrito en el código':", flush=True)
    for _, r in cambios.iterrows():
        print(f"      {r['modelo']:58s} {r['clase']:22s} {r['parametro']:16s} = {r['valor']:10s}"
              f" {r['criterio_anterior']} -> {r['origen']}", flush=True)

    # ------------------------------------------------------------ fragmentos LaTeX
    def libreria(est):
        if type(est).__module__.startswith("imblearn"):
            return "imbalanced-learn " + tex(__import__("imblearn").__version__)
        return "scikit-learn " + tex(meta["version_sklearn"])

    def cabecera(titulo, label, est):
        n = len(est.get_params(deep=False))
        return [f"% Generado por reports/apendices/generar_apendices.py con get_params() sobre {titulo}.",
                r"\begin{longtable}{L{3.9cm} L{3.7cm} L{3.0cm} L{2.4cm}}",
                f"\\caption{{{titulo}: \\texttt{{{tex(type(est).__name__)}}}, {n} parámetros. "
                r"En \textbf{negrilla}, los escritos en la llamada del código (aunque coincidan con el valor por defecto); "
                r"el resto quedó en el valor por defecto de " + libreria(est) + f".}}\\label{{{label}}}\\\\",
                r"\toprule", r"\textbf{Parámetro} & \textbf{Valor usado} & \textbf{Valor por defecto} & \textbf{Origen} \\",
                r"\midrule", r"\endfirsthead", r"\toprule",
                r"\textbf{Parámetro} & \textbf{Valor usado} & \textbf{Valor por defecto} & \textbf{Origen} \\",
                r"\midrule", r"\endhead", r"\bottomrule", r"\endfoot"]

    def filas_tex(est, valores_mostrados=None):
        """Una línea por parámetro. `valores_mostrados` permite mostrar un valor
        distinto del instanciado (p. ej. 'None | balanced' según la técnica)."""
        clase = type(est).__name__
        d = defaults_de(type(est))
        out = []
        for k, v in est.get_params(deep=False).items():
            por_defecto = d.get(k, object())
            escrito = k in escritos[clase]
            coincide = (v is por_defecto) or (v == por_defecto)
            if valores_mostrados and k in valores_mostrados:
                celda_v = valores_mostrados[k]
            elif valor(v).startswith("función "):
                celda_v = "\\texttt{función}\\allowbreak\\ \\texttt{" + tex(valor(v)[8:]) + "}"
            else:
                celda_v = f"\\texttt{{{tex(valor(v))}}}"
            celda_d = f"\\texttt{{{tex(valor(por_defecto))}}}"
            if escrito:
                if valores_mostrados and k in valores_mostrados:
                    origen = "explícito (según la técnica)"
                else:
                    origen = "explícito (igual al defecto)" if coincide else "explícito"
                out.append(f"\\textbf{{\\texttt{{{tex(k)}}}}} & \\textbf{{{celda_v}}} & {celda_d} & {origen} \\\\")
            else:
                out.append(f"\\texttt{{{tex(k)}}} & {celda_v} & {celda_d} & por defecto \\\\")
        return out

    def tabla(titulo, label, est, extra=None, valores_mostrados=None):
        out = cabecera(titulo, label, est) + filas_tex(est, valores_mostrados)
        if extra:
            out.append(r"\midrule")
            out.append(r"\multicolumn{4}{l}{\emph{Atributos ajustados (leídos del modelo entrenado)}} \\")
            for k, v in extra.items():
                out.append(f"\\texttt{{{tex(k)}}} & \\multicolumn{{3}}{{l}}{{\\texttt{{{tex(v)}}}}} \\\\")
        out.append(r"\end{longtable}")
        return "\n".join(out) + "\n"

    # (a) UN cuadro para los dos HistGB (misma configuración), atributos en dos columnas
    def atributos(m):
        return {
            "do_early_stopping_": bool(m.do_early_stopping_),
            "n_iter_ (iteraciones realmente usadas)": int(m.n_iter_),
            "n_trees_per_iteration_": int(m.n_trees_per_iteration_),
            "árboles totales": int(m.n_iter_ * m.n_trees_per_iteration_),
            "mejor iteración en la validación interna": int(np.argmax(m.validation_score_)),
            "n_features_in_": int(m.n_features_in_),
            "clases": len(m.classes_),
        }
    a_multi, a_bin = atributos(multi), atributos(bina)
    out = cabecera("Clasificadores multiclase y binario (misma configuración)", "tab:param-hgb", multi) + filas_tex(multi)
    out.append(r"\midrule")
    out.append(r"\emph{Atributos ajustados} & \textbf{Multiclase} & \textbf{Binario} & \\")
    for k in a_multi:
        out.append(f"\\texttt{{{tex(k)}}} & \\texttt{{{tex(a_multi[k])}}} & \\texttt{{{tex(a_bin[k])}}} & \\\\")
    out.append(r"\end{longtable}")
    frag = "\n".join(out) + "\n\n"
    frag += tabla("Detector de anomalías: bosque", "tab:param-if", det["bosque"], {
        "max_samples_ (flujos por árbol)": int(det["bosque"].max_samples_),
        "n_features_in_": int(det["bosque"].n_features_in_),
        "umbral cuantil 0,5 % / 1 % / 2 %": " / ".join(f"{det['umbrales'][q]:.4f}".replace(".", ",")
                                                      for q in ["0.005", "0.01", "0.02"]),
    })
    (SALIDA / "tablas_parametros_modelos.tex").write_text(frag, encoding="utf-8")

    # (b) los dos StandardScaler van enteramente por defecto: una frase, no dos cuadros
    sc = det["escalador"]
    params_sc = ", ".join(f"\\texttt{{{tex(k)}={tex(valor(v))}}}" for k, v in sc.get_params().items())
    frase = (
        "% Generado por reports/apendices/generar_apendices.py.\n"
        f"Los dos \\texttt{{StandardScaler}} del proyecto ---el del detector, serializado en "
        f"\\texttt{{models/}}, y el que precede a la regresión logística dentro de cada partición--- "
        f"se instancian sin argumentos y quedan enteramente por defecto ({params_sc}). "
        f"El del detector se ajustó con los {int(sc.n_samples_seen_):,} flujos benignos del lunes "
        f"(\\texttt{{n\\_samples\\_seen\\_}}) y {int(sc.n_features_in_)} variables.\n"
    ).replace(f"{int(sc.n_samples_seen_):,}", f"{int(sc.n_samples_seen_):,}".replace(",", "."))
    (SALIDA / "frase_escaladores.tex").write_text(frase, encoding="utf-8")

    # (c) estimadores del protocolo que NO están serializados
    pipe = construir_pipeline("reglog", "submuestreo_smote")
    frag_c = ""
    frag_c += tabla(
        "Regresión logística (referencia lineal)", "tab:param-reglog", pipe.named_steps["modelo"],
        valores_mostrados={"class_weight": "\\texttt{None} $\\mid$ \\texttt{'balanced'} (columna ``pesos'')"},
    ) + "\n"
    frag_c += tabla(
        "SMOTE (\\texttt{sampling\\_strategy} es la función \\texttt{estrategia\\_smote}: eleva a "
        + f"{OBJETIVO_SMOTE:,}".replace(",", ".") + " las clases con menos casos que eso)",
        "tab:param-smote", pipe.named_steps["smote"]) + "\n"
    frag_c += tabla(
        "Submuestreo aleatorio (\\texttt{sampling\\_strategy} es la función \\texttt{estrategia\\_submuestreo}: reduce BENIGN a "
        + f"{OBJETIVO_BENIGN:,}".replace(",", ".") + " casos)",
        "tab:param-rus", pipe.named_steps["submuestreo"]) + "\n"
    frag_c += tabla(
        "Local Outlier Factor (contraste; entrenado con una submuestra de "
        + f"{N_SUBMUESTRA_LOF:,}".replace(",", ".") + " flujos benignos del lunes)",
        "tab:param-lof", lof) + "\n"

    # Constantes y llamadas del protocolo (no son estimadores)
    filas_const = [
        ("Partición única", r"\texttt{train\_test\_split}", f"test\\_size={PROPORCION_TEST}; stratify=Label; random\\_state={RANDOM_STATE}", r"\path{src/split.py}"),
        ("Validación cruzada", r"\texttt{StratifiedKFold}", f"n\\_splits=5 (igual al defecto); shuffle=True; random\\_state={RANDOM_STATE}", r"\path{src/experimentos.py}, \path{src/interpretabilidad.py}, \path{notebooks/02_baseline.ipynb}"),
        ("Clasificador trivial (línea base)", r"\texttt{DummyClassifier}", "strategy='most\\_frequent'", r"\path{notebooks/02_baseline.ipynb}"),
        ("Importancia por permutación", r"\texttt{permutation\_\allowbreak importance}", f"scoring='f1\\_macro'; n\\_repeats=5 (igual al defecto); random\\_state={RANDOM_STATE}; n\\_jobs=-1; una sola partición ({N_VALIDACION_PERMUTACION:,} flujos de la validación de la primera)".replace(",", "."), r"\path{src/interpretabilidad.py}"),
        ("Modelo explicado por permutación", r"\texttt{HistGradient\allowbreak Boosting\allowbreak Classifier}", "binario; misma configuración del Cuadro~\\ref{tab:param-hgb}; ajustado con el 80\\,\\% de la primera partición", r"\path{src/interpretabilidad.py}"),
        ("Explicación por alerta", r"\texttt{shap.TreeExplainer}", "sobre el clasificador multiclase serializado; parámetros por defecto", r"\path{app/pantallas.py}"),
        ("Umbral de operación de Bot", "regla", f"alarma de Bot solo si $P(\\mathrm{{Bot}}) \\geq {str(UMBRAL_BOT).replace('.', '{,}')}$; si no, la segunda clase más probable; fijado con probabilidades out-of-fold del entrenamiento", r"\path{src/evaluacion_final.py}"),
        ("Cuantiles del detector", "constante", "; ".join(f"{100*q:g}\\,\\%" for q in CUANTILES_UMBRAL_IF).replace(".", "{,}") + " de los scores del lunes (1\\,\\% = referencia)", r"\path{src/no_supervisado.py}, \path{src/evaluacion_final.py}"),
        ("Variable identificadora retirada (prueba del puerto)", "constante", ", ".join(f"\\texttt{{{tex(f)}}}" for f in FEATURES_IDENTIFICADORAS), r"\path{src/interpretabilidad.py}"),
        ("Selección de variables", "constante", "$|r| > " + str(UMBRAL_R).replace(".", "{,}") + "$ sobre " + f"{N_MUESTRA:,}".replace(",", ".") + f" flujos del entrenamiento (semilla {RANDOM_STATE}); una representante por bloque", r"\path{src/features.py}"),
        ("Semilla única y versiones", "constante", f"RANDOM\\_STATE = {RANDOM_STATE}; scikit-learn {tex(meta['version_sklearn'])}; Python {tex(meta['version_python'])}; imbalanced-learn " + tex(__import__("imblearn").__version__), r"\path{src/config.py}, \path{models/metadatos.json}, \path{requirements*.txt}"),
    ]
    frag_c += "\n".join([
        "% Generado por reports/apendices/generar_apendices.py leyendo las constantes de src/.",
        r"\begin{longtable}{L{2.9cm} L{3.5cm} L{4.3cm} L{3.2cm}}",
        r"\caption{Parámetros del protocolo que no viven en los modelos serializados.}\label{tab:param-protocolo}\\",
        r"\toprule", r"\textbf{Componente} & \textbf{Objeto} & \textbf{Valores fijados} & \textbf{Dónde} \\", r"\midrule", r"\endfirsthead",
        r"\toprule", r"\textbf{Componente} & \textbf{Objeto} & \textbf{Valores fijados} & \textbf{Dónde} \\", r"\midrule", r"\endhead",
        r"\bottomrule", r"\endfoot",
        *[f"{a} & {b} & {c} & {d} \\\\" for a, b, c, d in filas_const],
        r"\end{longtable}", ""])
    (SALIDA / "tablas_parametros_protocolo.tex").write_text(frag_c, encoding="utf-8")
    print("    fragmentos LaTeX escritos", flush=True)


if __name__ == "__main__":
    apendice_a()
    apendice_b()
    print("Listo.", flush=True)
