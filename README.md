# Proyecto Final MIAD: detección de tráfico de red malicioso

El tablero está publicado en [[PENDIENTE: URL]].

Este repositorio tiene un **tablero web** que clasifica el tráfico de red (normal o
alguno de los tipos de ataque) usando el dataset **CIC-IDS2017**. Detrás del
tablero hay un análisis que planteamos como un problema de **clasificación con
desbalance de clases e interpretabilidad**.

## Guía de lectura

Aquí encontrarás qué abrir según lo que busques:

| Si buscas | Abre |
|---|---|
| Usar el tablero | La URL pública ([[PENDIENTE: URL]]) y sus dos demos integradas, ver [Probar el tablero con las demos](#probar-el-tablero-con-las-demos). Para abrirlo en tu equipo, sigue [Correr el tablero paso a paso](#correr-el-tablero-paso-a-paso). |
| Cómo se usa | [docs/manual_usuario.md](docs/manual_usuario.md), el manual de usuario, con las ventajas, limitaciones y advertencias del tablero y sus casos de uso paso a paso. |
| El detalle técnico | [reports/reporte_tecnico_final.pdf](reports/reporte_tecnico_final.pdf), el reporte técnico de experimentos. Los resultados sobre el conjunto de prueba están en la sección 7.1, el estado de implementación en la 8 y las conclusiones en la 9, y los apéndices tienen la evidencia de colinealidad y la configuración de parámetros. |
| Qué se cumplió | [docs/tabla_requerimientos_diligenciada.xlsx](docs/tabla_requerimientos_diligenciada.xlsx), la tabla de los 22 requerimientos con el resultado, el estado y la evidencia de cada uno. |
| El diagrama de la solución | [docs/diagrama_esquematico.png](docs/diagrama_esquematico.png), con la construcción de los modelos y la operación del tablero. |
| Verificar las pruebas | `python -m pytest -v`, ver [Pruebas de los requerimientos](#pruebas-de-los-requerimientos) y [tests/README.md](tests/README.md). Sin los datos del análisis se omiten las versiones pesadas de R7 (reproducibilidad) y R13 (depuración de datos), y el resultado esperado es 17 pasadas y 8 omitidas. |
| Reproducir el análisis | La sección [Reproducir el análisis](#reproducir-el-análisis). |

## Probar el tablero con las demos

El tablero acepta un archivo propio de flujos de red con el formato de
**CICFlowMeter**, pero para evaluar el proyecto recomendamos usar las dos demos
que ya vienen integradas. No hace falta descargar ni subir nada, se cargan con
un botón.

Las dos demos son muestras pequeñas del dataset original CIC-IDS2017, tomadas
del **conjunto de prueba**, es decir, de flujos que los modelos nunca vieron al
entrenar (las genera `src/preparar_demo.py` a partir de
`data/processed/test.parquet`). Vienen en el mismo formato crudo de
CICFlowMeter que tendría un archivo real, sin la columna de etiqueta.

| Demo | Archivo | Flujos | Ataque | Tipos de ataque | Para qué sirve |
|---|---|---|---|---|---|
| Demo rica en ataques | `data/demo/flujos_demo.csv` | 499 | 39,9 % | 14 | Muestra todo lo que el sistema detecta, incluidos los ataques más raros |
| Demo de proporción realista | `data/demo/flujos_demo_realista.csv` | 500 | 5,0 % | 10 | Muestra cuánto trabajo de revisión le ahorra al analista en un lote parecido al tráfico real |

Las etiquetas verdaderas de cada flujo están aparte, en
`data/demo/etiquetas_demo.csv` y `data/demo/etiquetas_demo_realista.csv`. El
tablero no lee esos archivos, están para que puedas comprobar los resultados:
la columna `fila` de las etiquetas corresponde a la columna "Fila del archivo"
que muestra el tablero, así que basta con buscar el mismo número.

**Paso a paso:**

1. Abre el tablero, con la URL pública cuando esté desplegado o en tu equipo
   siguiendo [Correr el tablero paso a paso](#correr-el-tablero-paso-a-paso).
2. En la barra lateral, debajo del cargador de archivos, busca "¿Sin archivo a
   la mano? Prueba con una demostración:" y haz clic en **Demo rica en ataques**
   o en **Demo de proporción realista**.
3. El tablero valida y clasifica la demo en unos segundos, y en la barra
   lateral aparece "Archivo activo" con el nombre de la demo.
4. Recorre las pantallas desde la lista "Pantallas" de la barra lateral: Panel
   de resumen, Clasificación, Detección de anomalías, Interpretabilidad, Alertas
   y Reportes.
5. Para cambiar de demo haz clic en el otro botón. Si quieres comprobar un
   flujo, anota su número en la columna "Fila del archivo" de la pantalla
   Alertas y búscalo en el archivo de etiquetas de esa demo.

## Datos

- **CIC-IDS2017**, del Canadian Institute for Cybersecurity:
  https://www.unb.ca/cic/datasets/ids-2017.html. Su proveedor pide citarlo así:
  Sharafaldin, Lashkari & Ghorbani (2018), ICISSP.
- Para reproducir el análisis hay que poner los 8 CSV (`*.pcap_ISCX.csv`) en
  `data/raw/`, porque los datos no se versionan. **El tablero no los necesita.**

## Estructura

```
├── README.md            este archivo
├── streamlit_app.py     el tablero, punto de entrada
├── app/                 núcleo del tablero: modelos, validación y pantallas
├── models/              los 3 modelos serializados y sus metadatos (1,3 MB)
├── tests/
│   ├── test_requerimientos.py   pruebas de los 22 requerimientos (python -m pytest)
│   ├── conftest.py              datos y modelos compartidos por las pruebas
│   ├── README.md                qué verifica cada prueba
│   ├── generar_lote_r9.py       arma el lote de 50.000 flujos para medir el tiempo de respuesta
│   └── __init__.py              permite importar las pruebas como paquete
├── data/
│   ├── demo/            las dos demos y sus etiquetas (versionadas)
│   └── raw/ interim/ processed/   datos del análisis (no se versionan)
├── docs/
│   ├── manual_usuario.md                    manual de usuario del tablero
│   ├── diagrama_esquematico.png             diagrama de construcción y operación
│   ├── generar_diagrama.py                  script que dibuja el diagrama
│   ├── tabla_requerimientos_diligenciada.xlsx   tabla de requerimientos con su resultado
│   └── capturas/                            capturas de pantalla del manual
├── notebooks/           01_eda · 02_baseline · 03_desbalance ·
│                        04_interpretabilidad · 05_no_supervisado · 06_evaluacion_final
├── src/                 pipeline del análisis, más modelo_final y preparar_demo
├── reports/
│   ├── reporte_tecnico_final.pdf         reporte técnico de experimentos
│   ├── apendices/                        script, tablas y CSV de los apéndices A y B
│   ├── figures/                          las 18 figuras
│   └── resultados_fase3/ _fase4/ _final/ resultados numéricos en CSV
├── pytest.ini                   configuración de las pruebas
├── requirements.in              dependencias directas del tablero (de aquí sale requirements.txt)
├── requirements.txt             entorno del tablero (liviano, todo fijado)
├── requirements-analisis.txt    entorno del análisis (freeze completo)
└── .gitignore                   lo que no se versiona (datos, entornos, archivos locales)
```

## Entornos y dependencias

Hay dos archivos porque el tablero necesita poco y el análisis mucho:
`requirements.txt` es liviano y es lo que instala el hosting, y
`requirements-analisis.txt` es el entorno completo con el que se entrenaron los
modelos, que además trae todo lo del tablero.
Si solo quieres usar el tablero o correr las pruebas, instala
`requirements.txt`; si quieres reproducir el análisis (notebooks y `src/`),
instala `requirements-analisis.txt`.

`requirements.txt` no se edita a mano. Se genera desde `requirements.in` (las
dependencias directas del tablero) con el comando que está en su encabezado,
resuelto para Linux, que es la plataforma del hosting, y restringido a las
versiones de `requirements-analisis.txt`. Así, todo paquete que esté en los dos
archivos queda en la misma versión.

> **Regla no negociable:** `scikit-learn` tiene que ser **idéntico en los dos
> archivos** (hoy: `1.9.0`), porque de esa versión depende que carguen los
> modelos de `models/`. Si se actualiza, se cambia en `requirements-analisis.txt`
> y en `requirements.in`, se regenera `requirements.txt` y se vuelven a generar
> los modelos con `python -m src.modelo_final`.
>
> **Despliegue:** hay que elegir **Python 3.13** en los ajustes avanzados del
> hosting, que es la misma versión con la que se congeló el entorno.

## Correr el tablero paso a paso

Este procedimiento arranca desde cero y no necesita saber nada de Streamlit. Se
necesita **Python 3.13** instalado. En Windows los comandos se escriben en
**PowerShell** (busca "PowerShell" en el menú Inicio) y en Mac y Linux en la
**Terminal**. No hace falta "activar" ningún entorno, porque se llama
directamente al programa dentro de la carpeta del entorno, que es la forma más
segura.

**1. Ir a la carpeta del proyecto.** Todo se ejecuta desde la raíz, que es la
carpeta que contiene `streamlit_app.py`. Abre la terminal en la carpeta donde
guardaste el proyecto y entra en él:

```bash
cd MIAD_ProyectoFinal
```

**2. Crear el entorno de la app (solo la primera vez).** Un "entorno" es una
copia aislada de Python con las versiones exactas que necesita el tablero.

En Windows:

```powershell
python -m venv .venv-app
.venv-app\Scripts\python.exe -m pip install -r requirements.txt
```

En Mac y Linux:

```bash
python3 -m venv .venv-app
.venv-app/bin/python -m pip install -r requirements.txt
```

Tarda unos minutos y descarga ~300 MB. Si Windows responde `Python was not
found`, escribe en la primera línea la ruta completa del Python instalado en tu
equipo en lugar de `python` (con Anaconda o Miniconda es el `python.exe` que
está en la carpeta donde se instaló).

> **Plataformas:** el tablero y el análisis se instalan en Windows, en Linux y
> en Mac con procesador Apple, y en los tres se resuelven exactamente las mismas
> versiones. En un **Mac con procesador Intel** no se puede instalar ninguno de
> los dos entornos, porque SHAP depende de `numba` y `numba` ya no publica
> versiones para esa plataforma con Python 3.13. En ese caso usa la URL pública
> del tablero.

**3. Lanzar el tablero** (cada vez que quieras usarlo):

En Windows:

```powershell
.venv-app\Scripts\streamlit.exe run streamlit_app.py
```

En Mac y Linux:

```bash
.venv-app/bin/streamlit run streamlit_app.py
```

**4. Abrir la URL** que aparece en la consola, normalmente
`http://localhost:8501`. La primera carga tarda unos segundos porque carga los
modelos, y las siguientes son inmediatas. La consola tiene que quedarse abierta
mientras uses el tablero. Una vez abierto, la forma más rápida de probarlo es
con las demos (ver [Probar el tablero con las demos](#probar-el-tablero-con-las-demos)).

**5. Detenerlo:** en la consola, pulsa `Ctrl + C`. El servidor solo se detiene
con `Ctrl + C` o al cerrar la consola; cerrar la pestaña del navegador no lo
detiene.

### Si algo falla

| Síntoma | Causa | Solución |
|---|---|---|
| `'streamlit' is not recognized…`, `command not found` o `No module named streamlit` | Se llamó a `streamlit` directamente, y el Python del sistema no lo tiene, solo el del entorno. | Usa la ruta completa como en el paso 3. Si la carpeta `.venv-app` no existe, vuelve al paso 2. |
| `Python was not found; run without arguments to install from the Microsoft Store` | `python` no está en el PATH de esta máquina (lo intercepta el alias de la tienda de Microsoft). | En el paso 2 usa la ruta completa del Python instalado en tu equipo (ver la nota del paso 2). |
| `Error: Invalid value: File does not exist: streamlit_app.py` | Estás en otra carpeta. | Haz `cd` a la raíz del proyecto (paso 1) y vuelve a lanzar el tablero. |
| La consola dice `http://localhost:8502` (u otro número distinto de 8501) | Ya tienes otro tablero corriendo en el 8501, en otra consola abierta. Streamlit no avisa y simplemente usa el siguiente puerto. | Usa la URL que muestra esta consola, o cierra la otra instancia (`Ctrl + C` en su consola) y vuelve a lanzar el tablero. Tener dos instancias con código distinto da resultados confusos. |
| Error raro (`KeyError`, pantalla a medias) en una pestaña que abriste hace días | Es una pestaña vieja conectada a un servidor que ya no existe o que quedó con código antiguo en memoria. | Cierra esa pestaña, detén cualquier tablero abierto (`Ctrl + C`), vuelve a lanzarlo y abre la URL nueva. Recargar la página no alcanza si el servidor es viejo. |
| Prefieres "activar" el entorno y `Activate.ps1` da `running scripts is disabled` | La política de PowerShell bloquea los scripts `.ps1`, y `activate.bat` no funciona en PowerShell (solo en cmd). | No hace falta activar: usa las rutas directas de estas instrucciones. Si aun así quieres activarlo: `Set-ExecutionPolicy -Scope Process Bypass` y luego `.\.venv-app\Scripts\Activate.ps1`. |
| Al instalar (paso 2) en Windows: `Could not install packages due to an OSError: [Errno 2] No such file or directory` con una ruta muy larga | Windows limita las rutas a 260 caracteres y algunos paquetes traen archivos internos con rutas largas, así que falla si el proyecto está en una carpeta muy profunda. | Mueve la carpeta del proyecto a una ruta corta (por ejemplo, una carpeta `proyectos` directamente en la raíz del disco), borra la carpeta `.venv-app` y repite el paso 2. |
| Advertencia amarilla al abrir: "Los modelos se guardaron con scikit-learn X y este servidor ejecuta Y" | El entorno tiene otra versión de scikit-learn. | Reinstala exactamente `requirements.txt` en `.venv-app` (segunda línea del paso 2). |
| Cambiaste código en `app/` o `models/` y no se ven los cambios | El servidor guarda los modelos en memoria y no los vuelve a cargar solo. | Detén el tablero (`Ctrl + C`) y vuelve a lanzarlo. |

## Cómo usar el proyecto (tres niveles)

1. **Usar el tablero y leer** (no requiere datos). Lanza el tablero y pruébalo
   con las dos demos de la barra lateral. Los notebooks se entregan **ya
   ejecutados**, con las tablas y figuras incluidas, y el reporte técnico tiene
   los mismos resultados.
2. **Verificar y volver a ejecutar lo liviano.** `python -m pytest -v` corre las
   pruebas de los 22 requerimientos en ~10 s, y los notebooks `03` a `06` leen
   solo los CSVs de `reports/resultados_*/` y corren en segundos.
3. **Reproducción completa desde los CSV crudos** (opcional; requiere ~8 GB de
   RAM y descargar el dataset): ver [Reproducir el análisis](#reproducir-el-análisis).

## Pruebas de los requerimientos

Desde la raíz, con el Python del entorno de la app. En Windows:

```powershell
.venv-app\Scripts\python.exe -m pytest -v
```

En Mac y Linux:

```bash
.venv-app/bin/python -m pytest -v
```

Cada prueba verifica un requerimiento (de R1 a R22) según su "prueba prevista".
19 son automáticas y 6 se documentan como manuales, porque dependen del
despliegue o de una persona ajena al proyecto, y aparecen como omitidas con su
razón. Dos de las automáticas (las versiones pesadas de R7 y R13) necesitan los
datos del análisis en `data/`; en una copia sin esos datos también se omiten, y
el resultado esperado es 17 pasadas y 8 omitidas. El detalle está en
[tests/README.md](tests/README.md).

## Reproducir el análisis

Para esto se necesita el entorno completo del análisis, que es distinto al de
la app. En Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-analisis.txt
```

En Mac y Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-analisis.txt
```

Los pasos se lanzan con el Python de ese entorno y en este orden
(`.venv\Scripts\python.exe -m src.preparacion` en Windows o
`.venv/bin/python -m src.preparacion` en Mac y Linux, etc.; abajo se abrevia
como `python`):

```bash
python -m src.preparacion        # 1. consolida los 8 CSV                (~3 min)
python -m src.limpieza           # 2. aplica la limpieza aprobada        (~2 min)
python -m src.split              # 3. split 80/20 único (se niega a repetirse)
python -m src.experimentos       # 4. matriz de desbalance (Fase 3)      (~40-90 min*)
python -m src.resultados         # 5. condensa la Fase 3 a CSVs          (~1 min)
python -m src.interpretabilidad  # 6. pregunta 1 + experimento del puerto (~15 min*)
python -m src.no_supervisado     # 7. pregunta 3 (Isolation Forest/LOF)  (~10 min*)
python -m src.evaluacion_final   # 8. ÚNICA evaluación sobre el test     (~2 min*)
python -m src.modelo_final       # 9. serializa los modelos del tablero  (~1 min)
python -m src.preparar_demo      # 10. genera los archivos de demo       (~1 min)
python reports/apendices/generar_apendices.py  # 11. apéndices A y B del reporte técnico (~1 min)
```

> El paso 8 se ejecutó **una sola vez** (es una regla del proyecto) y su
> checkpoint impide volver a calcularlo por accidente.

\* Tiempos medidos en una máquina de 24 núcleos y 32 GB de RAM; en un equipo
modesto pueden tomar varias horas en total. Son cómputos que se hacen **una
sola vez** y guardan su avance: si se interrumpen, al volver a lanzarlos no
repiten lo que ya calcularon. Los notebooks se ejecutan en orden, de `01_eda` a
`06_evaluacion_final`, con `jupyter lab` desde el entorno del análisis. **`01` y
`02` necesitan los datos locales** (pasos 1 a 3; `02` vuelve a entrenar sus
líneas base, ~15 min), mientras que **`03` a `06` leen los CSVs versionados** y
corren en segundos.

## Reproducibilidad

`RANDOM_STATE = 42` en todo el proyecto. El conjunto de prueba se apartó una
sola vez y se evaluó una única vez, y todo el remuestreo ocurre dentro de
pipelines de `imblearn` durante la validación cruzada. Las pruebas R7 y R8 lo
verifican con código.
