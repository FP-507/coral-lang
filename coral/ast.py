"""Nodos del árbol de sintaxis abstracta (AST)."""

from dataclasses import dataclass, field


@dataclass
class Nodo:
    linea: int = field(default=0, kw_only=True, compare=False, repr=False)
    columna: int = field(default=0, kw_only=True, compare=False, repr=False)


# ---------- expresiones ----------
@dataclass
class Literal(Nodo):
    valor: object


@dataclass
class Variable(Nodo):
    nombre: str


@dataclass
class Unaria(Nodo):
    op: str
    expr: Nodo


@dataclass
class Binaria(Nodo):
    izq: Nodo
    op: str
    der: Nodo


@dataclass
class Logica(Nodo):
    izq: Nodo
    op: str          # "y" | "o"
    der: Nodo


@dataclass
class Asignacion(Nodo):
    objetivo: Nodo   # Variable o Indice
    op: str          # "=", "+=", "-="
    valor: Nodo


@dataclass
class Llamada(Nodo):
    funcion: Nodo
    args: list[Nodo]


@dataclass
class Indice(Nodo):
    objeto: Nodo
    indice: Nodo


@dataclass
class Atributo(Nodo):
    objeto: Nodo
    nombre: str


@dataclass
class Lista(Nodo):
    elementos: list[Nodo]


@dataclass
class Diccionario(Nodo):
    pares: list[tuple[Nodo, Nodo]]


@dataclass
class Funcion(Nodo):
    nombre: str | None
    parametros: list[str]
    cuerpo: list[Nodo]


# ---------- sentencias ----------
@dataclass
class Declaracion(Nodo):
    nombre: str
    valor: Nodo


@dataclass
class ExprSentencia(Nodo):
    expr: Nodo


@dataclass
class Si(Nodo):
    condicion: Nodo
    entonces: list[Nodo]
    sino: list[Nodo] | None


@dataclass
class Mientras(Nodo):
    condicion: Nodo
    cuerpo: list[Nodo]


@dataclass
class Para(Nodo):
    variable: str
    iterable: Nodo
    cuerpo: list[Nodo]


@dataclass
class Retorna(Nodo):
    valor: Nodo | None


@dataclass
class Rompe(Nodo):
    pass


@dataclass
class Continua(Nodo):
    pass
