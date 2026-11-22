"""Intérprete que recorre el AST (tree-walking) con entornos encadenados y clausuras."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Callable

from . import ast as A
from .errores import ErrorEjecucion
from .parser import parsear

LIMITE_RECURSION = 300
# Cada llamada de Coral usa ~8 marcos de Python; se sube el límite para que el de Coral se alcance primero.
sys.setrecursionlimit(max(sys.getrecursionlimit(), LIMITE_RECURSION * 12 + 1000))


# ---------- señales de control de flujo ----------
class _Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


class _Rompe(Exception):
    pass


class _Continua(Exception):
    pass


# ---------- valores en tiempo de ejecución ----------
class Entorno:
    def __init__(self, padre: Entorno | None = None):
        self.vars: dict[str, object] = {}
        self.padre = padre

    def declarar(self, nombre, valor, nodo):
        if nombre in self.vars:
            raise ErrorEjecucion(f"La variable '{nombre}' ya fue declarada en este bloque", nodo.linea, nodo.columna)
        self.vars[nombre] = valor

    def buscar(self, nombre) -> Entorno | None:
        e = self
        while e is not None:
            if nombre in e.vars:
                return e
            e = e.padre
        return None

    def obtener(self, nombre, nodo):
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion(f"La variable '{nombre}' no está definida", nodo.linea, nodo.columna)
        return e.vars[nombre]

    def asignar(self, nombre, valor, nodo):
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion(f"No se puede asignar a '{nombre}': declárala primero con 'var'", nodo.linea, nodo.columna)
        e.vars[nombre] = valor


@dataclass
class FuncionCoral:
    nodo: A.Funcion
    cierre: Entorno

    @property
    def nombre(self):
        return self.nodo.nombre or "anónima"

    def __repr__(self):
        return f"<funcion {self.nombre}>"


@dataclass
class Nativa:
    nombre: str
    fn: Callable
    aridad: tuple[int, int]   # mínimo y máximo de argumentos

    def __repr__(self):
        return f"<funcion nativa {self.nombre}>"


def tipo_de(v) -> str:
    if v is None:
        return "nulo"
    if isinstance(v, bool):
        return "booleano"
    if isinstance(v, (int, float)):
        return "numero"
    if isinstance(v, str):
        return "texto"
    if isinstance(v, list):
        return "lista"
    if isinstance(v, dict):
        return "diccionario"
    return "funcion"


def mostrar(v) -> str:
    if v is None:
        return "nulo"
    if v is True:
        return "verdadero"
    if v is False:
        return "falso"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(mostrar_en_coleccion(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{mostrar_en_coleccion(k)}: {mostrar_en_coleccion(x)}" for k, x in v.items()) + "}"
    return str(v)


def mostrar_en_coleccion(v) -> str:
    return f'"{v}"' if isinstance(v, str) else mostrar(v)


def verdadero(v) -> bool:
    return not (v is None or v is False or v == 0 and not isinstance(v, bool) or v == "" or v == [] or v == {})


class Interprete:
    def __init__(self, salida: Callable[[str], None] = print):
        self.salida = salida
        self.globales = Entorno()
        self.profundidad = 0
        for nombre, fn, aridad in self._nativas():
            self.globales.vars[nombre] = Nativa(nombre, fn, aridad)

    # ---------- funciones nativas ----------
    def _nativas(self):
        def rango(a, b=None, paso=1):
            inicio, fin = (0, a) if b is None else (a, b)
            if paso == 0:
                raise ValueError("El paso de rango() no puede ser 0")
            return list(range(int(inicio), int(fin), int(paso)))

        def numero(v):
            try:
                f = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"No se puede convertir {mostrar_en_coleccion(v)} a número") from None
            return int(f) if f.is_integer() and not (isinstance(v, str) and "." in v) else f

        return [
            ("imprimir", lambda *a: self.salida(" ".join(mostrar(x) for x in a)), (0, 99)),
            ("largo", lambda v: len(v), (1, 1)),
            ("rango", rango, (1, 3)),
            ("texto", lambda v: mostrar(v), (1, 1)),
            ("numero", numero, (1, 1)),
            ("tipo", tipo_de, (1, 1)),
            ("raiz", lambda x: math.sqrt(x), (1, 1)),
            ("redondear", lambda x, d=0: round(x, int(d)) if d else int(round(x)), (1, 2)),
            ("absoluto", abs, (1, 1)),
            ("minimo", lambda *a: min(a[0] if len(a) == 1 else a), (1, 99)),
            ("maximo", lambda *a: max(a[0] if len(a) == 1 else a), (1, 99)),
            ("suma", lambda lista: sum(lista), (1, 1)),
            ("ordenar", lambda lista: sorted(lista), (1, 1)),
        ]

    def metodo(self, obj, nombre: str, nodo):
        metodos = {
            "lista": {
                "agrega": (lambda x: obj.append(x), (1, 1)),
                "saca": (lambda i=-1: obj.pop(int(i)), (0, 1)),
                "contiene": (lambda x: x in obj, (1, 1)),
                "une": (lambda sep="": sep.join(mostrar(x) for x in obj), (0, 1)),
                "invierte": (lambda: obj[::-1], (0, 0)),
                "mapea": (lambda f: [self.llamar(f, [x], nodo) for x in obj], (1, 1)),
                "filtra": (lambda f: [x for x in obj if verdadero(self.llamar(f, [x], nodo))], (1, 1)),
            },
            "texto": {
                "mayusculas": (lambda: obj.upper(), (0, 0)),
                "minusculas": (lambda: obj.lower(), (0, 0)),
                "divide": (lambda sep=" ": obj.split(sep), (0, 1)),
                "contiene": (lambda x: x in obj, (1, 1)),
                "reemplaza": (lambda a, b: obj.replace(a, b), (2, 2)),
            },
            "diccionario": {
                "claves": (lambda: list(obj.keys()), (0, 0)),
                "valores": (lambda: list(obj.values()), (0, 0)),
                "tiene": (lambda k: k in obj, (1, 1)),
            },
        }.get(tipo_de(obj), {})
        if nombre not in metodos:
            raise ErrorEjecucion(f"El tipo {tipo_de(obj)} no tiene el método '{nombre}'", nodo.linea, nodo.columna)
        fn, aridad = metodos[nombre]
        return Nativa(nombre, fn, aridad)

    # ---------- punto de entrada ----------
    def ejecutar(self, codigo: str):
        ultimo = None
        try:
            for s in parsear(codigo):
                ultimo = self.sentencia(s, self.globales)
        except RecursionError:
            self.profundidad = 0
            raise ErrorEjecucion("Recursión demasiado profunda: el programa se anidó demasiado") from None
        return ultimo

    def bloque(self, sentencias, entorno):
        for s in sentencias:
            self.sentencia(s, entorno)

    # ---------- sentencias ----------
    def sentencia(self, s, env):
        match s:
            case A.Declaracion(nombre, valor):
                env.declarar(nombre, self.evaluar(valor, env), s)
            case A.ExprSentencia(expr):
                return self.evaluar(expr, env)
            case A.Si(cond, entonces, sino):
                if verdadero(self.evaluar(cond, env)):
                    self.bloque(entonces, Entorno(env))
                elif sino is not None:
                    self.bloque(sino, Entorno(env))
            case A.Mientras(cond, cuerpo):
                vueltas = 0
                while verdadero(self.evaluar(cond, env)):
                    vueltas += 1
                    if vueltas > 1_000_000:
                        raise ErrorEjecucion("El ciclo 'mientras' superó un millón de vueltas", s.linea, s.columna)
                    try:
                        self.bloque(cuerpo, Entorno(env))
                    except _Rompe:
                        break
                    except _Continua:
                        continue
            case A.Para(var, iterable, cuerpo):
                coleccion = self.evaluar(iterable, env)
                if isinstance(coleccion, dict):
                    coleccion = list(coleccion)
                if not isinstance(coleccion, (list, str)):
                    raise ErrorEjecucion(f"No se puede recorrer un valor de tipo {tipo_de(coleccion)}", s.linea, s.columna)
                for item in list(coleccion):
                    local = Entorno(env)
                    local.vars[var] = item
                    try:
                        self.bloque(cuerpo, local)
                    except _Rompe:
                        break
                    except _Continua:
                        continue
            case A.Retorna(valor):
                raise _Retorno(None if valor is None else self.evaluar(valor, env))
            case A.Rompe():
                raise _Rompe()
            case A.Continua():
                raise _Continua()
        return None

    # ---------- expresiones ----------
    def evaluar(self, e, env):
        match e:
            case A.Literal(valor):
                return valor
            case A.Variable(nombre):
                return env.obtener(nombre, e)
            case A.Lista(elementos):
                return [self.evaluar(x, env) for x in elementos]
            case A.Diccionario(pares):
                return {self.clave(self.evaluar(k, env), k): self.evaluar(v, env) for k, v in pares}
            case A.Funcion():
                return FuncionCoral(e, env)
            case A.Unaria(op, expr):
                v = self.evaluar(expr, env)
                if op == "no":
                    return not verdadero(v)
                self.numeros(e, v)
                return -v
            case A.Logica(izq, op, der):
                v = self.evaluar(izq, env)
                if op == "o":
                    return v if verdadero(v) else self.evaluar(der, env)
                return self.evaluar(der, env) if verdadero(v) else v
            case A.Binaria(izq, op, der):
                return self.operar(op, self.evaluar(izq, env), self.evaluar(der, env), e)
            case A.Asignacion(objetivo, op, valor):
                return self.asignar(objetivo, op, valor, env, e)
            case A.Indice(obj, idx):
                return self.leer_indice(self.evaluar(obj, env), self.evaluar(idx, env), e)
            case A.Atributo(obj, nombre):
                o = self.evaluar(obj, env)
                if isinstance(o, dict) and nombre in o:
                    return o[nombre]
                return self.metodo(o, nombre, e)
            case A.Llamada(fn, args):
                return self.llamar(self.evaluar(fn, env), [self.evaluar(a, env) for a in args], e)
        raise ErrorEjecucion(f"Nodo desconocido {type(e).__name__}", e.linea, e.columna)

    def asignar(self, objetivo, op, valor_nodo, env, nodo):
        valor = self.evaluar(valor_nodo, env)
        if isinstance(objetivo, A.Variable):
            if op != "=":
                valor = self.operar(op[0], env.obtener(objetivo.nombre, objetivo), valor, nodo)
            env.asignar(objetivo.nombre, valor, objetivo)
            return valor
        cont, idx = self.evaluar(objetivo.objeto, env), self.evaluar(objetivo.indice, env)
        if op != "=":
            valor = self.operar(op[0], self.leer_indice(cont, idx, nodo), valor, nodo)
        if isinstance(cont, list):
            self.indice_valido(cont, idx, nodo)
            cont[int(idx)] = valor
        elif isinstance(cont, dict):
            cont[self.clave(idx, nodo)] = valor
        else:
            raise ErrorEjecucion(f"No se puede asignar por índice en un {tipo_de(cont)}", nodo.linea, nodo.columna)
        return valor

    def clave(self, k, nodo):
        if not isinstance(k, (str, int, float, bool)) and k is not None:
            raise ErrorEjecucion(f"Un {tipo_de(k)} no puede ser clave de diccionario", nodo.linea, nodo.columna)
        return k

    def indice_valido(self, cont, idx, nodo):
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise ErrorEjecucion("El índice debe ser un número entero", nodo.linea, nodo.columna)
        if not -len(cont) <= idx < len(cont):
            raise ErrorEjecucion(f"Índice {idx} fuera de rango (largo {len(cont)})", nodo.linea, nodo.columna)

    def leer_indice(self, cont, idx, nodo):
        if isinstance(cont, (list, str)):
            self.indice_valido(cont, idx, nodo)
            return cont[idx]
        if isinstance(cont, dict):
            if idx not in cont:
                raise ErrorEjecucion(f"La clave {mostrar_en_coleccion(idx)} no existe", nodo.linea, nodo.columna)
            return cont[idx]
        raise ErrorEjecucion(f"No se puede indexar un valor de tipo {tipo_de(cont)}", nodo.linea, nodo.columna)

    def numeros(self, nodo, *vals):
        for v in vals:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ErrorEjecucion(f"Se esperaba un número y se recibió {tipo_de(v)}", nodo.linea, nodo.columna)

    def operar(self, op, a, b, nodo):
        if op == "==":
            return a == b and tipo_de(a) == tipo_de(b)
        if op == "!=":
            return not (a == b and tipo_de(a) == tipo_de(b))
        if op == "+":
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            if isinstance(a, str) or isinstance(b, str):
                raise ErrorEjecucion(f"No se puede sumar {tipo_de(a)} y {tipo_de(b)}. Usa texto() para convertir",
                                     nodo.linea, nodo.columna)
        if op == "*" and isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool):
            return a * b
        if op in ("<", "<=", ">", ">=") and isinstance(a, str) and isinstance(b, str):
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
        self.numeros(nodo, a, b)
        if op in ("/", "%") and b == 0:
            raise ErrorEjecucion("División por cero", nodo.linea, nodo.columna)
        r = {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a / b,
             "%": lambda: a % b, "**": lambda: a ** b, "<": lambda: a < b, "<=": lambda: a <= b,
             ">": lambda: a > b, ">=": lambda: a >= b}[op]()
        if op == "/" and isinstance(r, float) and r.is_integer():
            return int(r)
        return r

    def llamar(self, fn, args, nodo):
        if isinstance(fn, Nativa):
            mn, mx = fn.aridad
            if not mn <= len(args) <= mx:
                esperado = mn if mn == mx else f"entre {mn} y {mx}"
                raise ErrorEjecucion(f"{fn.nombre}() espera {esperado} argumentos y recibió {len(args)}", nodo.linea, nodo.columna)
            try:
                return fn.fn(*args)
            except ErrorEjecucion:
                raise
            except (TypeError, ValueError, IndexError) as exc:
                raise ErrorEjecucion(f"{fn.nombre}(): {exc}", nodo.linea, nodo.columna) from None
        if not isinstance(fn, FuncionCoral):
            raise ErrorEjecucion(f"Un valor de tipo {tipo_de(fn)} no se puede llamar", nodo.linea, nodo.columna)
        params = fn.nodo.parametros
        if len(args) != len(params):
            raise ErrorEjecucion(f"{fn.nombre}() espera {len(params)} argumentos y recibió {len(args)}", nodo.linea, nodo.columna)
        self.profundidad += 1
        if self.profundidad > LIMITE_RECURSION:
            self.profundidad = 0
            raise ErrorEjecucion(f"Recursión demasiado profunda en {fn.nombre}() (más de {LIMITE_RECURSION} llamadas)",
                                 nodo.linea, nodo.columna)
        local = Entorno(fn.cierre)
        local.vars.update(zip(params, args))
        try:
            self.bloque(fn.nodo.cuerpo, local)
            return None
        except _Retorno as r:
            return r.valor
        except (_Rompe, _Continua):
            raise ErrorEjecucion("'rompe' o 'continua' fuera de un ciclo", nodo.linea, nodo.columna) from None
        finally:
            self.profundidad = max(0, self.profundidad - 1)
