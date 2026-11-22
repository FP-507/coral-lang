"""Analizador sintáctico: tokens -> AST.

Dos técnicas combinadas:

* **Descenso recursivo** para las sentencias: cada palabra clave (si, mientras,
  clase, intenta...) tiene su método.
* **Pratt (precedence climbing)** para las expresiones: cada operador binario
  tiene una precedencia y una asociatividad, y ``binaria(min_prec)`` agrupa
  correctamente ``1 + 2 * 3 ** 2`` sin una regla de gramática por nivel.

Para agregar un operador nuevo basta con sumarlo a PRECEDENCIA (y al lexer si
usa caracteres nuevos) y darle significado en ``Interprete.operar``.
"""

from . import ast as A
from .errores import ErrorCoral, ErrorSintaxis
from .lexer import Token, tokenizar
from .pistas import pista_palabra

# Mayor número = se agrupa antes. "|>" es el más débil: a + 1 |> f equivale a f(a + 1).
PRECEDENCIA = {
    "|>": 1,
    "o": 2, "y": 3,
    "==": 4, "!=": 4, "es": 4,
    "<": 5, "<=": 5, ">": 5, ">=": 5,
    "..": 6,
    "+": 7, "-": 7,
    "*": 8, "/": 8, "%": 8,
    "**": 9,
}
DERECHA = {"**"}                       # asociatividad a la derecha: 2 ** 3 ** 2 = 2 ** 9
OPERADORES_CLAVE = {"y", "o", "es"}    # operadores que el lexer entrega como CLAVE
PREFIJO = 10                           # precedencia de -x y no x


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens, self.pos = tokens, 0

    # =================================================================
    # Utilidades de lectura
    # =================================================================
    @property
    def actual(self) -> Token:
        return self.tokens[self.pos]

    def siguiente(self, k: int = 1) -> Token:
        return self.tokens[min(self.pos + k, len(self.tokens) - 1)]

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
        if tipo == "NOMBRE" and tok.tipo == "CLAVE":
            # Caso típico: usar 'y', 'o' o 'en' como nombre de variable.
            raise ErrorSintaxis(f"'{tok.valor}' es una palabra reservada de Coral y no puede usarse como nombre",
                                tok.linea, tok.columna)
        raise ErrorSintaxis(mensaje or f"Se esperaba '{valor or tipo}' pero se encontró {self.describir(tok)}",
                            tok.linea, tok.columna)

    @staticmethod
    def describir(tok: Token) -> str:
        return "el final del archivo" if tok.tipo == "FIN" else f"'{tok.valor}'"

    @staticmethod
    def en(tok: Token) -> dict:
        return {"linea": tok.linea, "columna": tok.columna}

    # =================================================================
    # Programa y bloques
    # =================================================================
    def programa(self) -> list[A.Nodo]:
        sentencias = []
        while not self.ver("FIN"):
            sentencias.append(self.sentencia())
        return sentencias

    def bloque(self) -> list[A.Nodo]:
        self.espera("SIMBOLO", "{", mensaje=f"Se esperaba '{{' para abrir el bloque pero se encontró {self.describir(self.actual)}")
        cuerpo = []
        while not self.ver("SIMBOLO", "}"):
            if self.ver("FIN"):
                raise ErrorSintaxis("Falta '}' para cerrar el bloque", self.actual.linea, self.actual.columna)
            cuerpo.append(self.sentencia())
        self.avanzar()
        return cuerpo

    def fin_sentencia(self):
        """El punto y coma es opcional; sirve para separar sentencias en una misma línea."""
        self.acepta("SIMBOLO", ";")

    # =================================================================
    # Sentencias
    # =================================================================
    def sentencia(self) -> A.Nodo:
        tok = self.actual
        p = self.en(tok)
        if tok.tipo == "CLAVE":
            metodo = getattr(self, f"_s_{tok.valor}", None)
            if metodo:
                return metodo()
        self.pista_ingles(tok)
        expr = self.expresion()
        self.fin_sentencia()
        return A.ExprSentencia(expr, **p)

    def pista_ingles(self, tok: Token) -> None:
        """Si la sentencia empieza con 'if', 'while', 'def'... explica la palabra en Coral."""
        if tok.tipo != "NOMBRE":
            return
        pista = pista_palabra(tok.valor)
        sig = self.siguiente()
        uso_como_palabra = sig.tipo in ("NOMBRE", "NUM", "TEXTO", "PLANTILLA", "CLAVE") or sig.es("SIMBOLO", "{")
        if pista and uso_como_palabra:
            raise ErrorSintaxis(pista, tok.linea, tok.columna)

    def _s_var(self, constante: bool = False) -> A.Declaracion:
        tok = self.avanzar()
        palabra = "const" if constante else "var"
        nombre = self.espera("NOMBRE", mensaje=f"Se esperaba un nombre después de '{palabra}'").valor
        self.espera("SIMBOLO", "=", mensaje=f"Falta '=' para dar un valor a '{nombre}'")
        valor = self.expresion()
        self.fin_sentencia()
        return A.Declaracion(nombre, valor, constante, **self.en(tok))

    def _s_const(self) -> A.Declaracion:
        return self._s_var(constante=True)

    def _s_funcion(self) -> A.Nodo:
        if self.siguiente().tipo != "NOMBRE":       # funcion anónima usada como expresión
            expr = self.expresion()
            self.fin_sentencia()
            return A.ExprSentencia(expr, **self.en(self.actual))
        tok = self.avanzar()
        nombre = self.avanzar().valor
        params, cuerpo = self.parametros_y_cuerpo()
        self.fin_sentencia()
        return A.Declaracion(nombre, A.Funcion(nombre, params, cuerpo, **self.en(tok)), **self.en(tok))

    def _s_si(self) -> A.Si:
        tok = self.espera("CLAVE", "si")
        cond = self.expresion()
        entonces = self.bloque()
        sino = None
        if self.acepta("CLAVE", "sino"):
            sino = [self._s_si()] if self.ver("CLAVE", "si") else self.bloque()
        return A.Si(cond, entonces, sino, **self.en(tok))

    def _s_mientras(self) -> A.Mientras:
        tok = self.avanzar()
        cond = self.expresion()
        return A.Mientras(cond, self.bloque(), **self.en(tok))

    def _s_para(self) -> A.Para:
        tok = self.avanzar()
        var = self.espera("NOMBRE", mensaje="Se esperaba el nombre de la variable del ciclo después de 'para'").valor
        self.espera("CLAVE", "en", mensaje="Falta 'en': se escribe  para elemento en coleccion { ... }")
        iterable = self.expresion()
        return A.Para(var, iterable, self.bloque(), **self.en(tok))

    def _s_retorna(self) -> A.Retorna:
        tok = self.avanzar()
        valor = None if self.ver("SIMBOLO", "}") or self.ver("SIMBOLO", ";") else self.expresion()
        self.fin_sentencia()
        return A.Retorna(valor, **self.en(tok))

    def _s_rompe(self) -> A.Rompe:
        tok = self.avanzar(); self.fin_sentencia()
        return A.Rompe(**self.en(tok))

    def _s_continua(self) -> A.Continua:
        tok = self.avanzar(); self.fin_sentencia()
        return A.Continua(**self.en(tok))

    def _s_clase(self) -> A.Clase:
        tok = self.avanzar()
        nombre = self.espera("NOMBRE", mensaje="Se esperaba el nombre de la clase").valor
        padre = None
        if self.acepta("CLAVE", "hereda"):
            ptok = self.espera("NOMBRE", mensaje="Se esperaba el nombre de la clase padre después de 'hereda'")
            padre = A.Variable(ptok.valor, **self.en(ptok))
        self.espera("SIMBOLO", "{")
        clase = A.Clase(nombre, padre, [], **self.en(tok))
        while not self.ver("SIMBOLO", "}"):
            mtok = self.actual
            if self.acepta("CLAVE", "const"):                       # constante de clase: Clase.NOMBRE
                cnombre = self.espera("NOMBRE", mensaje="Se esperaba un nombre después de 'const'").valor
                self.espera("SIMBOLO", "=", mensaje=f"Falta '=' para dar un valor a '{cnombre}'")
                clase.constantes.append((cnombre, self.expresion()))
                self.fin_sentencia()
                continue
            estatico = bool(self.acepta("CLAVE", "estatico"))
            abstracto = not estatico and bool(self.acepta("CLAVE", "abstracta"))
            ftok = self.actual
            if not ftok.es("CLAVE", "funcion") or self.siguiente().tipo != "NOMBRE":
                raise ErrorSintaxis("Dentro de una clase solo van métodos (funcion, estatico funcion, abstracta funcion) "
                                    "y constantes (const)", ftok.linea, ftok.columna)
            self.avanzar()
            mnombre = self.avanzar().valor
            if abstracto:
                # Un método abstracto no tiene cuerpo: las subclases deben implementarlo.
                self.parametros()
                clase.abstractos.append(mnombre)
            else:
                params, cuerpo = self.parametros_y_cuerpo()
                funcion = A.Funcion(mnombre, params, cuerpo, **self.en(mtok))
                (clase.estaticos if estatico else clase.metodos).append(funcion)
            self.fin_sentencia()
        self.avanzar()
        return clase

    def _s_intenta(self) -> A.Intenta:
        tok = self.avanzar()
        cuerpo = self.bloque()
        self.espera("CLAVE", "captura", mensaje="Después del bloque 'intenta' va 'captura error { ... }'")
        variable = self.acepta("NOMBRE")
        return A.Intenta(cuerpo, variable.valor if variable else None, self.bloque(), **self.en(tok))

    def _s_lanza(self) -> A.Lanza:
        tok = self.avanzar()
        valor = self.expresion()
        self.fin_sentencia()
        return A.Lanza(valor, **self.en(tok))

    def _s_segun(self) -> A.Segun:
        tok = self.avanzar()
        valor = self.expresion()
        self.espera("SIMBOLO", "{")
        casos, otro = [], None
        while not self.ver("SIMBOLO", "}"):
            if self.acepta("CLAVE", "caso"):
                opciones = [self.expresion()]
                while self.acepta("SIMBOLO", ","):
                    opciones.append(self.expresion())
                casos.append((opciones, self.bloque()))
            elif self.acepta("CLAVE", "otro"):
                otro = self.bloque()
            else:
                t = self.actual
                raise ErrorSintaxis(f"Dentro de 'segun' van bloques 'caso' u 'otro', no {self.describir(t)}", t.linea, t.columna)
        self.avanzar()
        if not casos:
            raise ErrorSintaxis("'segun' necesita al menos un 'caso'", tok.linea, tok.columna)
        return A.Segun(valor, casos, otro, **self.en(tok))

    def _s_prueba(self) -> A.Prueba:
        tok = self.avanzar()
        nombre = self.espera("TEXTO", mensaje='Se esperaba el nombre de la prueba entre comillas: prueba "suma" { ... }').valor
        return A.Prueba(nombre, self.bloque(), **self.en(tok))

    def _s_afirma(self) -> A.Afirma:
        tok = self.avanzar()
        cond = self.expresion()
        mensaje = self.expresion() if self.acepta("SIMBOLO", ",") else None
        self.fin_sentencia()
        return A.Afirma(cond, mensaje, **self.en(tok))

    def _s_importa(self) -> A.Importa:
        tok = self.avanzar()
        ruta = self.espera("TEXTO", mensaje='Se esperaba la ruta entre comillas: importa "util.coral"').valor
        self.fin_sentencia()
        return A.Importa(ruta, **self.en(tok))

    def parametros_y_cuerpo(self) -> tuple[list[str], list[A.Nodo]]:
        params = self.parametros()
        if self.acepta("SIMBOLO", "=>"):            # forma corta: funcion (x) => x * 2
            tok = self.actual
            return params, [A.Retorna(self.expresion(), **self.en(tok))]
        return params, self.bloque()

    def parametros(self) -> list[str]:
        """Lee '(a, b, c)' y devuelve los nombres."""
        self.espera("SIMBOLO", "(")
        params = []
        if not self.ver("SIMBOLO", ")"):
            while True:
                t = self.espera("NOMBRE", mensaje="Se esperaba el nombre de un parámetro")
                if t.valor in params:
                    raise ErrorSintaxis(f"Parámetro repetido '{t.valor}'", t.linea, t.columna)
                params.append(t.valor)
                if not self.acepta("SIMBOLO", ","):
                    break
        self.espera("SIMBOLO", ")")
        return params

    # =================================================================
    # Expresiones (Pratt)
    # =================================================================
    def expresion(self) -> A.Nodo:
        izq = self.binaria(0)
        if self.ver("SIMBOLO") and self.actual.valor in ("=", "+=", "-="):
            tok = self.avanzar()
            if not isinstance(izq, (A.Variable, A.Indice, A.Atributo)):
                raise ErrorSintaxis("Solo se puede asignar a una variable, un índice o un atributo", tok.linea, tok.columna)
            return A.Asignacion(izq, tok.valor, self.expresion(), **self.en(tok))
        return izq

    def operador_actual(self) -> str | None:
        tok = self.actual
        if tok.tipo == "SIMBOLO" and tok.valor in PRECEDENCIA:
            return tok.valor
        if tok.tipo == "CLAVE" and tok.valor in OPERADORES_CLAVE:
            return tok.valor
        return None

    def binaria(self, min_prec: int) -> A.Nodo:
        izq = self.unaria()
        while (op := self.operador_actual()) and PRECEDENCIA[op] > min_prec:
            tok = self.avanzar()
            der = self.binaria(PRECEDENCIA[op] - (1 if op in DERECHA else 0))
            p = self.en(tok)
            if op == "|>":
                # Tubería: x |> f(a) se convierte en f(x, a); x |> f en f(x).
                izq = A.Llamada(der.funcion, [izq, *der.args], **p) if isinstance(der, A.Llamada) else A.Llamada(der, [izq], **p)
            elif op in ("y", "o"):
                izq = A.Logica(izq, op, der, **p)
            else:
                izq = A.Binaria(izq, op, der, **p)
        return izq

    def unaria(self) -> A.Nodo:
        tok = self.actual
        if tok.es("SIMBOLO", "-") or tok.es("CLAVE", "no"):
            self.avanzar()
            operando = self.binaria(PREFIJO - 1) if tok.valor == "no" else self.unaria()
            return A.Unaria(tok.valor, operando, **self.en(tok))
        return self.posfija(self.primaria())

    def posfija(self, expr: A.Nodo) -> A.Nodo:
        """Llamadas f(x), índices a[i] y atributos a.b, encadenables: a.b(1)[0]."""
        while True:
            tok = self.actual
            if self.acepta("SIMBOLO", "("):
                args = []
                if not self.ver("SIMBOLO", ")"):
                    while True:
                        args.append(self.expresion())
                        if not self.acepta("SIMBOLO", ","):
                            break
                self.espera("SIMBOLO", ")", mensaje="Falta ')' para cerrar la llamada")
                expr = A.Llamada(expr, args, **self.en(tok))
            elif self.acepta("SIMBOLO", "["):
                idx = self.expresion()
                self.espera("SIMBOLO", "]")
                expr = A.Indice(expr, idx, **self.en(tok))
            elif self.acepta("SIMBOLO", "."):
                nombre = self.espera("NOMBRE", mensaje="Se esperaba un nombre después de '.'").valor
                expr = A.Atributo(expr, nombre, **self.en(tok))
            else:
                return expr

    def primaria(self) -> A.Nodo:
        tok = self.avanzar()
        p = self.en(tok)
        if tok.tipo in ("NUM", "TEXTO"):
            return A.Literal(tok.valor, **p)
        if tok.tipo == "PLANTILLA":
            return A.Plantilla([self.subexpresion(parte) if isinstance(parte, tuple) else parte for parte in tok.valor], **p)
        if tok.tipo == "NOMBRE":
            return A.Variable(tok.valor, **p)
        if tok.tipo == "CLAVE":
            if tok.valor in ("verdadero", "falso", "nulo"):
                return A.Literal({"verdadero": True, "falso": False, "nulo": None}[tok.valor], **p)
            if tok.valor == "yo":
                return A.Variable("yo", **p)
            if tok.valor == "padre":
                self.espera("SIMBOLO", ".", mensaje="'padre' se usa así: padre.metodo(...)")
                return A.Padre(self.espera("NOMBRE").valor, **p)
            if tok.valor == "funcion":
                params, cuerpo = self.parametros_y_cuerpo()
                return A.Funcion(None, params, cuerpo, **p)
        if tok.es("SIMBOLO", "("):
            expr = self.expresion()
            self.espera("SIMBOLO", ")", mensaje="Falta ')' para cerrar el paréntesis")
            return expr
        if tok.es("SIMBOLO", "["):
            elementos = []
            while not self.ver("SIMBOLO", "]"):
                elementos.append(self.expresion())
                if not self.acepta("SIMBOLO", ","):
                    break
            self.espera("SIMBOLO", "]", mensaje="Falta ']' para cerrar la lista")
            return A.Lista(elementos, **p)
        if tok.es("SIMBOLO", "{"):
            pares = []
            while not self.ver("SIMBOLO", "}"):
                ct = self.actual
                # Las claves sin comillas se toman como texto: {nombre: "Ana"}.
                clave = A.Literal(self.avanzar().valor, **self.en(ct)) if ct.tipo in ("NOMBRE", "TEXTO", "NUM") else self.expresion()
                self.espera("SIMBOLO", ":", mensaje="Falta ':' entre la clave y el valor")
                pares.append((clave, self.expresion()))
                if not self.acepta("SIMBOLO", ","):
                    break
            self.espera("SIMBOLO", "}", mensaje="Falta '}' para cerrar el diccionario")
            return A.Diccionario(pares, **p)
        if tok.tipo == "CLAVE":
            raise ErrorSintaxis(f"'{tok.valor}' es una palabra reservada y no puede ir aquí", tok.linea, tok.columna)
        raise ErrorSintaxis(f"Expresión inesperada: {self.describir(tok)}", tok.linea, tok.columna)

    def subexpresion(self, parte: tuple) -> A.Nodo:
        """Parsea el código de una interpolación {…}; los errores apuntan al texto original."""
        codigo, linea, col = parte
        try:
            sub = Parser(tokenizar(codigo))
            expr = sub.expresion()
            if not sub.ver("FIN"):
                raise ErrorSintaxis(f"Sobra {sub.describir(sub.actual)} dentro de la interpolación")
            return expr
        except ErrorCoral as e:
            raise ErrorSintaxis(f"En la interpolación {{{codigo}}}: {e.mensaje}", linea, col) from None


def parsear(codigo: str) -> list[A.Nodo]:
    return Parser(tokenizar(codigo)).programa()
