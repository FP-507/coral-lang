"""Jerarquía de errores de Coral.

Todos los errores visibles para quien programa en Coral heredan de ``ErrorCoral``
y guardan la posición (línea y columna) donde ocurrieron, para poder mostrar la
línea de código con una flecha que señala el problema.
"""


class ErrorCoral(Exception):
    """Error con posición en el código fuente."""

    tipo = "Error"

    def __init__(self, mensaje: str, linea: int | None = None, columna: int | None = None):
        super().__init__(mensaje)
        self.mensaje, self.linea, self.columna = mensaje, linea, columna

    def __str__(self) -> str:
        pos = f" (línea {self.linea}, columna {self.columna})" if self.linea else ""
        return f"{self.tipo}{pos}: {self.mensaje}"

    def con_contexto(self, codigo: str) -> str:
        """Mensaje con la línea de código y una flecha que señala la columna.

        Ejemplo::

            Error de ejecución (línea 2, columna 12): No se puede sumar numero y texto
                2 | imprimir(x + "a")
                  |            ^
        """
        if not self.linea:
            return str(self)
        lineas = codigo.splitlines()
        if self.linea > len(lineas):
            return str(self)
        fuente = lineas[self.linea - 1]
        return f"{self}\n  {self.linea:>3} | {fuente}\n      | {' ' * (max(self.columna, 1) - 1)}^"


class ErrorSintaxis(ErrorCoral):
    """El código no respeta la gramática de Coral (se detecta antes de ejecutar)."""

    tipo = "Error de sintaxis"


class ErrorEjecucion(ErrorCoral):
    """Algo falló mientras el programa corría (tipo incorrecto, variable inexistente...)."""

    tipo = "Error de ejecución"


class ErrorPrueba(ErrorCoral):
    """Una sentencia ``afirma`` no se cumplió dentro de un bloque ``prueba``."""

    tipo = "Prueba fallida"
