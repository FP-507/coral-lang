"""Analizador léxico: convierte el código fuente en una lista de tokens.

Recorre el texto carácter por carácter llevando la cuenta de línea y columna,
para que todos los errores posteriores puedan señalar la posición exacta.

Tipos de token:
    NUM        número entero o decimal (admite guion bajo: 1_000)
    TEXTO      texto entre comillas sin interpolación
    PLANTILLA  texto con interpolación "Hola {nombre}"; su valor es una lista de
               partes: str (texto literal) o (codigo, linea, columna)
    NOMBRE     identificador
    CLAVE      palabra reservada (ver PALABRAS_CLAVE)
    SIMBOLO    operador o signo de puntuación
    FIN        marca el final del archivo
"""

from dataclasses import dataclass

from .errores import ErrorSintaxis
from .pistas import OPERADORES_INGLES

PALABRAS_CLAVE = {
    "var", "const", "funcion", "retorna", "si", "sino", "mientras", "para", "en",
    "verdadero", "falso", "nulo", "y", "o", "no", "es", "rompe", "continua",
    "clase", "hereda", "yo", "padre",
    "intenta", "captura", "lanza",
    "segun", "caso", "otro",
    "prueba", "afirma", "importa",
}

# Los símbolos de dos caracteres se prueban antes que los de uno.
SIMBOLOS_DOBLES = {"==", "!=", "<=", ">=", "=>", "+=", "-=", "**", "|>", ".."}
SIMBOLOS_SIMPLES = set("+-*/%<>=(){}[],:;.")

ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'", "{": "{", "}": "}"}


@dataclass(frozen=True)
class Token:
    tipo: str
    valor: object
    linea: int
    columna: int

    def es(self, tipo: str, valor=None) -> bool:
        return self.tipo == tipo and (valor is None or self.valor == valor)


class _Escaner:
    """Estado del recorrido: posición actual, línea y columna."""

    def __init__(self, codigo: str):
        self.codigo, self.i, self.linea, self.col = codigo, 0, 1, 1

    @property
    def fin(self) -> bool:
        return self.i >= len(self.codigo)

    def ver(self, k: int = 0) -> str:
        j = self.i + k
        return self.codigo[j] if j < len(self.codigo) else ""

    def avanzar(self, k: int = 1) -> None:
        for _ in range(k):
            if self.codigo[self.i] == "\n":
                self.linea, self.col = self.linea + 1, 1
            else:
                self.col += 1
            self.i += 1


def _leer_texto(e: _Escaner) -> Token:
    """Lee un texto entre comillas. Si contiene {expresión} devuelve una PLANTILLA."""
    l0, c0, cierre = e.linea, e.col, e.ver()
    e.avanzar()
    partes: list = []
    actual: list[str] = []
    while True:
        if e.fin or e.ver() == "\n":
            raise ErrorSintaxis("Texto sin cerrar: falta la comilla final", l0, c0)
        c = e.ver()
        if c == cierre:
            e.avanzar()
            break
        if c == "\\" and e.ver(1):
            actual.append(ESCAPES.get(e.ver(1), e.ver(1)))
            e.avanzar(2)
        elif c == "{":
            # Interpolación: se guarda el código entre llaves para parsearlo después.
            if actual:
                partes.append("".join(actual))
                actual = []
            lc, cc = e.linea, e.col
            e.avanzar()
            profundidad, codigo = 1, []
            while True:
                if e.fin or e.ver() == "\n":
                    raise ErrorSintaxis("Falta '}' para cerrar la interpolación", lc, cc)
                d = e.ver()
                if d == cierre:
                    raise ErrorSintaxis("Dentro de {…} usa comillas distintas a las del texto", e.linea, e.col)
                if d == "{":
                    profundidad += 1
                elif d == "}":
                    profundidad -= 1
                    if profundidad == 0:
                        e.avanzar()
                        break
                codigo.append(d)
                e.avanzar()
            if not "".join(codigo).strip():
                raise ErrorSintaxis("Interpolación vacía: escribe una expresión entre las llaves", lc, cc)
            partes.append(("".join(codigo), lc, cc + 1))
        else:
            actual.append(c)
            e.avanzar()
    if actual or not partes:
        partes.append("".join(actual))
    if all(isinstance(p, str) for p in partes):
        return Token("TEXTO", "".join(partes), l0, c0)
    return Token("PLANTILLA", partes, l0, c0)


def tokenizar(codigo: str) -> list[Token]:
    e = _Escaner(codigo)
    tokens: list[Token] = []
    while not e.fin:
        c = e.ver()
        if c in " \t\r\n":
            e.avanzar()
        elif c == "#":                                   # comentario hasta fin de línea
            while not e.fin and e.ver() != "\n":
                e.avanzar()
        elif c.isdigit():
            ini, l0, c0 = e.i, e.linea, e.col
            while not e.fin and (e.ver().isdigit() or e.ver() == "_"):
                e.avanzar()
            # Un punto seguido de dígito es decimal; ".." es el operador de rango.
            if e.ver() == "." and e.ver(1).isdigit():
                e.avanzar()
                while not e.fin and e.ver().isdigit():
                    e.avanzar()
            texto = codigo[ini:e.i].replace("_", "")
            tokens.append(Token("NUM", float(texto) if "." in texto else int(texto), l0, c0))
        elif c.isalpha() or c == "_":
            ini, l0, c0 = e.i, e.linea, e.col
            while not e.fin and (e.ver().isalnum() or e.ver() == "_"):
                e.avanzar()
            palabra = codigo[ini:e.i]
            tokens.append(Token("CLAVE" if palabra in PALABRAS_CLAVE else "NOMBRE", palabra, l0, c0))
        elif c in "\"'":
            tokens.append(_leer_texto(e))
        else:
            dos = c + e.ver(1)
            if dos in SIMBOLOS_DOBLES:
                tokens.append(Token("SIMBOLO", dos, e.linea, e.col))
                e.avanzar(2)
            elif c in SIMBOLOS_SIMPLES:
                tokens.append(Token("SIMBOLO", c, e.linea, e.col))
                e.avanzar()
            else:
                op = dos if dos in OPERADORES_INGLES else c
                if op in OPERADORES_INGLES:
                    raise ErrorSintaxis(f"En Coral se escribe '{OPERADORES_INGLES[op]}' en lugar de '{op}'", e.linea, e.col)
                raise ErrorSintaxis(f"Carácter inesperado '{c}'", e.linea, e.col)
    tokens.append(Token("FIN", None, e.linea, e.col))
    return tokens
