"""Analizador sintáctico: descenso recursivo para sentencias y Pratt para expresiones."""

from . import ast as A
from .errores import ErrorSintaxis
from .lexer import Token, tokenizar

# Precedencia de operadores binarios (mayor número = se agrupa antes).
PRECEDENCIA = {
    "o": 1, "y": 2,
    "==": 3, "!=": 3,
    "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "%": 6,
    "**": 7,
}
DERECHA = {"**"}         # asociatividad a la derecha
PREFIJO = 8              # -x, no x
POSFIJO = 9              # llamadas, índices, atributos


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens, self.pos = tokens, 0

    # ---------- utilidades ----------
    @property
    def actual(self) -> Token:
        return self.tokens[self.pos]

    def avanzar(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.tipo != "FIN":
            self.pos += 1
        return tok

    def ver(self, tipo: str, valor=None) -> bool:
        return self.actual.es(tipo, valor)

    def acepta(self, tipo: str, valor=None) -> Token | None:
        return self.avanzar() if self.ver(tipo, valor) else None

    def espera(self, tipo: str, valor=None, mensaje: str | None = None) -> Token:
        if self.ver(tipo, valor):
            return self.avanzar()
        tok = self.actual
        encontrado = "el final del archivo" if tok.tipo == "FIN" else f"'{tok.valor}'"
        raise ErrorSintaxis(mensaje or f"Se esperaba '{valor or tipo}' pero se encontró {encontrado}", tok.linea, tok.columna)

    def pos_de(self, tok: Token) -> dict:
        return {"linea": tok.linea, "columna": tok.columna}

    # ---------- programa y sentencias ----------
    def programa(self) -> list[A.Nodo]:
        sentencias = []
        while not self.ver("FIN"):
            sentencias.append(self.sentencia())
        return sentencias

    def bloque(self) -> list[A.Nodo]:
        self.espera("SIMBOLO", "{")
        cuerpo = []
        while not self.ver("SIMBOLO", "}"):
            if self.ver("FIN"):
                raise ErrorSintaxis("Falta '}' para cerrar el bloque", self.actual.linea, self.actual.columna)
            cuerpo.append(self.sentencia())
        self.avanzar()
        return cuerpo

    def fin_sentencia(self):
        self.acepta("SIMBOLO", ";")

    def sentencia(self) -> A.Nodo:
        tok = self.actual
        if tok.es("CLAVE", "var"):
            self.avanzar()
            nombre = self.espera("NOMBRE", mensaje="Se esperaba un nombre de variable después de 'var'").valor
            self.espera("SIMBOLO", "=")
            valor = self.expresion()
            self.fin_sentencia()
            return A.Declaracion(nombre, valor, **self.pos_de(tok))
        if tok.es("CLAVE", "funcion") and self.tokens[self.pos + 1].tipo == "NOMBRE":
            self.avanzar()
            nombre = self.avanzar().valor
            params, cuerpo = self.parametros_y_cuerpo()
            self.fin_sentencia()
            return A.Declaracion(nombre, A.Funcion(nombre, params, cuerpo, **self.pos_de(tok)), **self.pos_de(tok))
        if tok.es("CLAVE", "si"):
            return self.si()
        if tok.es("CLAVE", "mientras"):
            self.avanzar()
            cond = self.expresion()
            return A.Mientras(cond, self.bloque(), **self.pos_de(tok))
        if tok.es("CLAVE", "para"):
            self.avanzar()
            var = self.espera("NOMBRE").valor
            self.espera("CLAVE", "en")
            iterable = self.expresion()
            return A.Para(var, iterable, self.bloque(), **self.pos_de(tok))
        if tok.es("CLAVE", "retorna"):
            self.avanzar()
            valor = None if self.ver("SIMBOLO", "}") or self.ver("SIMBOLO", ";") else self.expresion()
            self.fin_sentencia()
            return A.Retorna(valor, **self.pos_de(tok))
        if tok.es("CLAVE", "rompe"):
            self.avanzar(); self.fin_sentencia()
            return A.Rompe(**self.pos_de(tok))
        if tok.es("CLAVE", "continua"):
            self.avanzar(); self.fin_sentencia()
            return A.Continua(**self.pos_de(tok))
        expr = self.expresion()
        self.fin_sentencia()
        return A.ExprSentencia(expr, **self.pos_de(tok))

    def si(self) -> A.Si:
        tok = self.espera("CLAVE", "si")
        cond = self.expresion()
        entonces = self.bloque()
        sino = None
        if self.acepta("CLAVE", "sino"):
            sino = [self.si()] if self.ver("CLAVE", "si") else self.bloque()
        return A.Si(cond, entonces, sino, **self.pos_de(tok))

    def parametros_y_cuerpo(self) -> tuple[list[str], list[A.Nodo]]:
        self.espera("SIMBOLO", "(")
        params = []
        if not self.ver("SIMBOLO", ")"):
            while True:
                nombre = self.espera("NOMBRE", mensaje="Se esperaba el nombre de un parámetro").valor
                if nombre in params:
                    raise ErrorSintaxis(f"Parámetro repetido '{nombre}'", self.actual.linea, self.actual.columna)
                params.append(nombre)
                if not self.acepta("SIMBOLO", ","):
                    break
        self.espera("SIMBOLO", ")")
        if self.acepta("SIMBOLO", "=>"):            # funcion (x) => x * 2
            tok = self.actual
            return params, [A.Retorna(self.expresion(), **self.pos_de(tok))]
        return params, self.bloque()

    # ---------- expresiones (Pratt) ----------
    def expresion(self) -> A.Nodo:
        izq = self.binaria(0)
        if self.ver("SIMBOLO") and self.actual.valor in ("=", "+=", "-="):
            tok = self.avanzar()
            if not isinstance(izq, (A.Variable, A.Indice)):
                raise ErrorSintaxis("Solo se puede asignar a una variable o a un índice", tok.linea, tok.columna)
            return A.Asignacion(izq, tok.valor, self.expresion(), **self.pos_de(tok))
        return izq

    def operador_actual(self) -> str | None:
        tok = self.actual
        if tok.tipo == "SIMBOLO" and tok.valor in PRECEDENCIA:
            return tok.valor
        if tok.tipo == "CLAVE" and tok.valor in ("y", "o"):
            return tok.valor
        return None

    def binaria(self, min_prec: int) -> A.Nodo:
        izq = self.unaria()
        while (op := self.operador_actual()) and PRECEDENCIA[op] > min_prec:
            tok = self.avanzar()
            prec = PRECEDENCIA[op] - (1 if op in DERECHA else 0)
            der = self.binaria(prec)
            cls = A.Logica if op in ("y", "o") else A.Binaria
            izq = cls(izq, op, der, **self.pos_de(tok))
        return izq

    def unaria(self) -> A.Nodo:
        tok = self.actual
        if tok.es("SIMBOLO", "-") or tok.es("CLAVE", "no"):
            self.avanzar()
            return A.Unaria(tok.valor, self.binaria(PREFIJO - 1) if tok.valor == "no" else self.unaria(), **self.pos_de(tok))
        return self.posfija(self.primaria())

    def posfija(self, expr: A.Nodo) -> A.Nodo:
        while True:
            tok = self.actual
            if self.acepta("SIMBOLO", "("):
                args = []
                if not self.ver("SIMBOLO", ")"):
                    while True:
                        args.append(self.expresion())
                        if not self.acepta("SIMBOLO", ","):
                            break
                self.espera("SIMBOLO", ")")
                expr = A.Llamada(expr, args, **self.pos_de(tok))
            elif self.acepta("SIMBOLO", "["):
                idx = self.expresion()
                self.espera("SIMBOLO", "]")
                expr = A.Indice(expr, idx, **self.pos_de(tok))
            elif self.acepta("SIMBOLO", "."):
                nombre = self.espera("NOMBRE", mensaje="Se esperaba un nombre después de '.'").valor
                expr = A.Atributo(expr, nombre, **self.pos_de(tok))
            else:
                return expr

    def primaria(self) -> A.Nodo:
        tok = self.avanzar()
        p = self.pos_de(tok)
        if tok.tipo in ("NUM", "TEXTO"):
            return A.Literal(tok.valor, **p)
        if tok.tipo == "NOMBRE":
            return A.Variable(tok.valor, **p)
        if tok.es("CLAVE", "verdadero"):
            return A.Literal(True, **p)
        if tok.es("CLAVE", "falso"):
            return A.Literal(False, **p)
        if tok.es("CLAVE", "nulo"):
            return A.Literal(None, **p)
        if tok.es("CLAVE", "funcion"):
            params, cuerpo = self.parametros_y_cuerpo()
            return A.Funcion(None, params, cuerpo, **p)
        if tok.es("SIMBOLO", "("):
            expr = self.expresion()
            self.espera("SIMBOLO", ")")
            return expr
        if tok.es("SIMBOLO", "["):
            elementos = []
            while not self.ver("SIMBOLO", "]"):
                elementos.append(self.expresion())
                if not self.acepta("SIMBOLO", ","):
                    break
            self.espera("SIMBOLO", "]")
            return A.Lista(elementos, **p)
        if tok.es("SIMBOLO", "{"):
            pares = []
            while not self.ver("SIMBOLO", "}"):
                clave_tok = self.actual
                clave = A.Literal(self.avanzar().valor, **self.pos_de(clave_tok)) if clave_tok.tipo in ("NOMBRE", "TEXTO", "NUM") else self.expresion()
                self.espera("SIMBOLO", ":")
                pares.append((clave, self.expresion()))
                if not self.acepta("SIMBOLO", ","):
                    break
            self.espera("SIMBOLO", "}")
            return A.Diccionario(pares, **p)
        encontrado = "el final del archivo" if tok.tipo == "FIN" else f"'{tok.valor}'"
        raise ErrorSintaxis(f"Expresión inesperada: {encontrado}", tok.linea, tok.columna)


def parsear(codigo: str) -> list[A.Nodo]:
    return Parser(tokenizar(codigo)).programa()
