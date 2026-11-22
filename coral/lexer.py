"""Analizador léxico: convierte el código fuente en una lista de tokens."""

from dataclasses import dataclass

from .errores import ErrorSintaxis

PALABRAS_CLAVE = {
    "var", "funcion", "retorna", "si", "sino", "mientras", "para", "en",
    "verdadero", "falso", "nulo", "y", "o", "no", "rompe", "continua",
}

SIMBOLOS = {
    "==", "!=", "<=", ">=", "=>", "+=", "-=", "**",
    "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "{", "}", "[", "]", ",", ":", ";", ".",
}


@dataclass(frozen=True)
class Token:
    tipo: str        # NUM, TEXTO, NOMBRE, CLAVE, SIMBOLO, FIN
    valor: object
    linea: int
    columna: int

    def es(self, tipo: str, valor=None) -> bool:
        return self.tipo == tipo and (valor is None or self.valor == valor)


def tokenizar(codigo: str) -> list[Token]:
    tokens: list[Token] = []
    i, linea, col = 0, 1, 1
    n = len(codigo)

    def avanzar(k: int = 1):
        nonlocal i, linea, col
        for _ in range(k):
            if codigo[i] == "\n":
                linea, col = linea + 1, 1
            else:
                col += 1
            i += 1

    while i < n:
        c = codigo[i]
        if c in " \t\r\n":
            avanzar()
        elif c == "#":
            while i < n and codigo[i] != "\n":
                avanzar()
        elif c.isdigit():
            ini, l0, c0 = i, linea, col
            while i < n and (codigo[i].isdigit() or codigo[i] == "_"):
                avanzar()
            if i + 1 < n and codigo[i] == "." and codigo[i + 1].isdigit():
                avanzar()
                while i < n and codigo[i].isdigit():
                    avanzar()
            texto = codigo[ini:i].replace("_", "")
            tokens.append(Token("NUM", float(texto) if "." in texto else int(texto), l0, c0))
        elif c.isalpha() or c == "_":
            ini, l0, c0 = i, linea, col
            while i < n and (codigo[i].isalnum() or codigo[i] == "_"):
                avanzar()
            palabra = codigo[ini:i]
            tokens.append(Token("CLAVE" if palabra in PALABRAS_CLAVE else "NOMBRE", palabra, l0, c0))
        elif c in "\"'":
            l0, c0 = linea, col
            cierre, partes = c, []
            avanzar()
            while True:
                if i >= n or codigo[i] == "\n":
                    raise ErrorSintaxis("Texto sin cerrar", l0, c0)
                if codigo[i] == cierre:
                    avanzar()
                    break
                if codigo[i] == "\\" and i + 1 < n:
                    esc = codigo[i + 1]
                    partes.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(esc, esc))
                    avanzar(2)
                else:
                    partes.append(codigo[i])
                    avanzar()
            tokens.append(Token("TEXTO", "".join(partes), l0, c0))
        else:
            dos = codigo[i:i + 2]
            if len(dos) == 2 and dos in SIMBOLOS:
                tokens.append(Token("SIMBOLO", dos, linea, col))
                avanzar(2)
            elif c in SIMBOLOS:
                tokens.append(Token("SIMBOLO", c, linea, col))
                avanzar()
            else:
                raise ErrorSintaxis(f"Carácter inesperado '{c}'", linea, col)
    tokens.append(Token("FIN", None, linea, col))
    return tokens
