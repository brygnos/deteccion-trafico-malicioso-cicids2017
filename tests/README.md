# Pruebas de los requerimientos

Cada prueba verifica **un requerimiento de la tabla entregada (de R1 a R22)**
siguiendo su columna «Prueba prevista». El nombre de cada función empieza con el
código del requerimiento (`test_R12_...`) y su docstring cita la prueba prevista
y el criterio de aceptación, así que la salida del comando sirve como evidencia
fila por fila al diligenciar la tabla.

## Un solo comando

Desde la **raíz del proyecto**, con el Python del entorno de la app
(`.venv-app\Scripts\python.exe` en Windows y `.venv-app/bin/python` en Mac y
Linux; ver el README principal):

```bash
python -m pytest -v
```

Tarda unos 10 segundos y solo necesita lo que viaja con el repositorio
(`models/`, `data/demo/`, `reports/resultados_*/`). Las dos pruebas marcadas
`datos_locales` (las versiones pesadas de R7 y R13) solo se ejecutan si están
los datos grandes en `data/`; si no, se omiten y su mensaje explica cómo
generar esos datos.

## Qué se verifica con código y qué requiere una persona

| Req. | Automatizada | Qué comprueba |
|---|---|---|
| R1 | ✅ | 11 clases en la evaluación final (benigno + 10), Heartbleed e Infiltration fuera del multiclase y presentes en el binario; una clase por flujo |
| R2 | ✅ | Falsas alarmas sobre los 414.468 benignos del test ≤ 0,2 % |
| R3 | ✅ | La importancia global está disponible, y SHAP explica 10 alertas de la demo con 8 pesos no nulos y una clase coherente |
| R4 | ✅ | Recall > 0,4 en Heartbleed, slowloris e Infiltration al 1 % (en la semana y en el test); las camufladas quedan < 0,05 y la pantalla lo dice |
| R5 | ✅ | El macro-F1 final supera 0,082 por más de 0,5, y la reducción de carga es > 90 % en la demo realista |
| R6 | ✅ | Macro-F1 en test ≥ 0,94, también sin el puerto |
| R7 | ✅ (+ pesada) | La semilla 42 está declarada, dos clasificaciones salen idénticas, y volver a entrenar el detector reproduce los umbrales decimal a decimal |
| R8 | ✅ | Solo `evaluacion_final.py` evalúa el test (`preparar_demo.py` solo toma muestras del test para armar las demos); el escalado y el remuestreo van dentro del pipeline; la prueba queda dentro de CV ± 3σ |
| R9 | ✅ parcial | 50.000 flujos en < 30 s **en local**; la medición definitiva se hace sobre el tablero desplegado |
| R10 | ⏸ manual | Abrir la URL pública desde otro equipo; reanudación < 1 min |
| R11 | ✅ | Está el CSV por día (8 tramos × 3 umbrales), con mediana ≈ 1 % y un tramo > 5 %; la pantalla lo muestra y explica la deriva |
| R12 | ✅ | Los cuatro archivos: válido, columnas faltantes, vacío y valores inválidos (más uno con etiqueta y uno con basura binaria) |
| R13 | ✅ (+ pesada) | No quedan Inf/NaN después de depurar lo subido; el Parquet limpio tiene 2.498.078 filas y ningún valor no finito |
| R14 | ✅ | Cada flujo trae clase binaria, multiclase y confianza en [0, 1] |
| R15 | ✅ | El conteo de anómalos crece al pasar de 0,5 % a 1 % y a 2 %, y los cortes salen del detector |
| R16 | ⏸ manual | Contar clics: resumen 1, métricas 2, explicación de una alerta 3, exportar filtrado 3 |
| R17 | ✅ | El CSV exportado refleja exactamente el filtro (tipo, confianza, anomalía), y las métricas también se exportan |
| R18 | ✅ | Procesar un archivo no crea ningún archivo en disco, y las 48 características son numéricas y sin IPs, IDs ni contenido |
| R19 | ⏸ no verificable | Integración SIEM: es deseable, y en esta versión la vía es la exportación CSV |
| R20 | ⏸ manual | Una persona ajena al proyecto completa el recorrido de cargar, revisar y exportar sin ayuda |
| R21 | ✅ parcial + ⏸ | Las 6 pantallas abren con título y una descripción de lo que muestran, las que tienen tablas traen su guía «Cómo leer» y las métricas tienen su explicación en llano (se revisa sobre el código, sin exigir frases exactas); la revisión por una persona ajena es manual |
| R22 | ⏸ manual | Abrir el tablero desplegado en Chrome, Firefox y Edge |

Las manuales aparecen en la salida como `SKIPPED` con la razón completa, para
que el mismo reporte deje constancia de lo que falta verificar con una persona o
con el despliegue.
