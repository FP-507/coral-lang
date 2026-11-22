"""Coral: un lenguaje de programación pequeño con palabras clave en español."""

from .errores import ErrorCoral, ErrorEjecucion, ErrorSintaxis
from .interprete import Interprete, mostrar

__version__ = "1.0.0"
__all__ = ["Interprete", "ErrorCoral", "ErrorSintaxis", "ErrorEjecucion", "mostrar", "ejecutar"]


def ejecutar(codigo: str) -> list[str]:
    """Ejecuta código Coral y devuelve lo que imprimió, línea por línea."""
    salida: list[str] = []
    Interprete(salida.append).ejecutar(codigo)
    return salida
