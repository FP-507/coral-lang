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
        """Mensaje con la línea de código y una flecha que señala la columna."""
        if not self.linea:
            return str(self)
        lineas = codigo.splitlines()
        if self.linea > len(lineas):
            return str(self)
        fuente = lineas[self.linea - 1]
        return f"{self}\n  {self.linea:>3} | {fuente}\n      | {' ' * (self.columna - 1)}^"


class ErrorSintaxis(ErrorCoral):
    tipo = "Error de sintaxis"


class ErrorEjecucion(ErrorCoral):
    tipo = "Error de ejecución"
