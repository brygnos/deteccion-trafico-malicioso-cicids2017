"""Formato de los números que se muestran en el tablero.

Todo número visible usa la convención del proyecto: coma decimal y punto de
miles (0,975 y 499.616). Los CSV que se descargan conservan el punto decimal,
porque son un formato para otras herramientas, así que esta función se usa solo
para lo que se muestra en pantalla.
"""


def formatear(valor, decimales: int = 0, porcentaje: bool = False, signo: bool = False) -> str:
    """Número con coma decimal y punto de miles.

    `porcentaje` recibe una fracción y la muestra sobre 100, y `signo` antepone
    el + a los positivos. Por ejemplo: formatear(499616) da '499.616',
    formatear(0.9747, 3) da '0,975', formatear(0.954, 1, porcentaje=True) da
    '95,4%' y formatear(0.42, 2, signo=True) da '+0,42'.
    """
    numero = float(valor) * 100 if porcentaje else float(valor)
    texto = f"{numero:{'+' if signo else ''},.{decimales}f}"
    texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return texto + ("%" if porcentaje else "")
