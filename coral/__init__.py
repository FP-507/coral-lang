"""Coral: un lenguaje de programación en español, pensado para aprender.

Uso desde Python::

    from coral import ejecutar, ejecutar_pruebas
    ejecutar('imprimir("Hola {1 + 1}")')          # -> ["Hola 2"]

Módulos (en el orden en que trabajan):
    lexer.py       texto -> tokens
    parser.py      tokens -> AST (ast.py)
    interprete.py  recorre el AST y lo ejecuta
    errores.py     errores con línea, columna y contexto
    pistas.py      sugerencias "¿Quisiste decir...?" y equivalencias de otros lenguajes
"""

from .errores import ErrorCoral, ErrorEjecucion, ErrorPrueba, ErrorSintaxis
from .interprete import Interprete, mostrar

__version__ = "2.0.0"
__all__ = ["Interprete", "ErrorCoral", "ErrorSintaxis", "ErrorEjecucion", "ErrorPrueba",
           "mostrar", "ejecutar", "ejecutar_pruebas"]


def ejecutar(codigo: str, **opciones) -> list[str]:
    """Ejecuta código Coral y devuelve lo que imprimió, línea por línea.

    ``opciones`` se pasan a ``Interprete`` (entrada, directorio, semilla).
    """
    salida: list[str] = []
    Interprete(salida.append, **opciones).ejecutar(codigo)
    return salida


def ejecutar_pruebas(codigo: str, **opciones) -> tuple[list[str], list[dict]]:
    """Ejecuta el programa y luego sus bloques ``prueba``. Devuelve (salida, resultados)."""
    salida: list[str] = []
    interp = Interprete(salida.append, **opciones)
    interp.ejecutar(codigo)
    return salida, interp.ejecutar_pruebas()
