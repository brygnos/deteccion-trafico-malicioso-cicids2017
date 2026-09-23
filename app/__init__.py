"""Tablero de detección de tráfico de red malicioso (aplicación Streamlit).

Estructura:
- nucleo.py     : carga de modelos serializados y clasificación por lotes.
- validacion.py : ingesta y validación del archivo del usuario (R12), en
                  memoria y sin escribir nada a disco (R18).
- pantallas.py  : las pantallas del dashboard.
- streamlit_app.py (en la raíz del repo): punto de entrada y navegación.

nucleo.py y validacion.py no importan Streamlit, se prueban por separado.
"""
