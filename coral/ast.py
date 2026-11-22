"""Nodos del árbol de sintaxis abstracta (AST).

El parser convierte los tokens en estos nodos y el intérprete los recorre.
Cada nodo guarda ``linea`` y ``columna`` (sin participar en la comparación de
igualdad) para que los errores de ejecución señalen la posición exacta.

Convención: las *expresiones* producen un valor; las *sentencias* se ejecutan
por su efecto (declarar, repetir, retornar...).
"""

from dataclasses import dataclass, field


@dataclass
class Nodo:
    linea: int = field(default=0, kw_only=True, compare=False, repr=False)
    columna: int = field(default=0, kw_only=True, compare=False, repr=False)


# =====================================================================
# Expresiones
# =====================================================================
@dataclass
class Literal(Nodo):
    """Número, texto, verdadero, falso o nulo."""
    valor: object


@dataclass
class Plantilla(Nodo):
    """Texto con interpolación: "Hola {nombre}". Partes: str literal o Nodo."""
    partes: list


@dataclass
class Variable(Nodo):
    nombre: str


@dataclass
class Unaria(Nodo):
    op: str          # "-" | "no"
    expr: Nodo


@dataclass
class Binaria(Nodo):
    """Operación aritmética, de comparación, de rango (..) o de tipo (es)."""
    izq: Nodo
    op: str
    der: Nodo


@dataclass
class Logica(Nodo):
    """'y' / 'o' con evaluación en cortocircuito."""
    izq: Nodo
    op: str
    der: Nodo


@dataclass
class Asignacion(Nodo):
    objetivo: Nodo   # Variable, Indice o Atributo
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
class Padre(Nodo):
    """padre.metodo: método de la clase padre, ligado a la instancia actual."""
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


# =====================================================================
# Sentencias
# =====================================================================
@dataclass
class Declaracion(Nodo):
    """var nombre = valor  |  const NOMBRE = valor"""
    nombre: str
    valor: Nodo
    constante: bool = False


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


@dataclass
class Clase(Nodo):
    """clase Nombre [hereda Padre] { ... }

    El cuerpo admite métodos de instancia, ``estatico funcion``, ``abstracta funcion``
    (sin cuerpo) y ``const NOMBRE = valor``.
    """
    nombre: str
    padre: Nodo | None
    metodos: list[Funcion]
    estaticos: list[Funcion] = field(default_factory=list)
    constantes: list[tuple[str, Nodo]] = field(default_factory=list)
    abstractos: list[str] = field(default_factory=list)


@dataclass
class Intenta(Nodo):
    """intenta { ... } captura [nombre] { ... }"""
    cuerpo: list[Nodo]
    variable: str | None
    manejo: list[Nodo]


@dataclass
class Lanza(Nodo):
    valor: Nodo


@dataclass
class Segun(Nodo):
    """segun valor { caso a, b { ... } ... otro { ... } }"""
    valor: Nodo
    casos: list[tuple[list[Nodo], list[Nodo]]]
    otro: list[Nodo] | None


@dataclass
class Prueba(Nodo):
    """prueba "nombre" { ... }  (solo se ejecuta con --pruebas)"""
    nombre: str
    cuerpo: list[Nodo]


@dataclass
class Afirma(Nodo):
    condicion: Nodo
    mensaje: Nodo | None


@dataclass
class Importa(Nodo):
    ruta: str
