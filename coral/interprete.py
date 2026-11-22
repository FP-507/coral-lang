"""Intérprete de Coral: recorre el AST (tree-walking) y lo ejecuta.

Ideas centrales, por si hay que retomarlo:

* **Entornos encadenados.** Cada bloque crea un ``Entorno`` hijo; buscar una
  variable sube por la cadena de padres. Una función guarda el entorno donde se
  creó (``cierre``), y eso es lo que hace funcionar las clausuras.
* **Control de flujo con excepciones internas.** ``retorna``, ``rompe``,
  ``continua`` y ``lanza`` se implementan con excepciones de Python privadas
  (``_Retorno``, ``_Rompe``, ``_Continua``, ``_Lanzado``) que el ciclo o la
  función correspondiente atrapa.
* **Clases sin magia.** ``ClaseCoral`` guarda sus métodos; ``InstanciaCoral``
  guarda sus campos. Al leer ``obj.metodo`` se devuelve un ``MetodoLigado`` que,
  al llamarse, define ``yo`` (la instancia) y la clase donde se definió el método
  (para que ``padre.metodo`` sepa desde dónde subir).
* **Errores que enseñan.** Todo error lleva línea y columna; si un nombre no
  existe se sugiere el más parecido y, si es una palabra de otro lenguaje
  (``print``, ``self``...), se dice cuál es la de Coral (ver ``pistas.py``).
* **Pruebas integradas.** Los bloques ``prueba`` se registran al ejecutar el
  archivo pero solo corren con ``ejecutar_pruebas()`` (``python -m coral --pruebas``).
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from . import ast as A
from .errores import ErrorCoral, ErrorEjecucion, ErrorPrueba
from .parser import parsear
from .pistas import pista_palabra, sugerir

LIMITE_RECURSION = 300          # llamadas anidadas de Coral permitidas
LIMITE_VUELTAS = 1_000_000      # vueltas máximas de un 'mientras' (evita colgar el playground)
LIMITE_RANGO = 1_000_000        # elementos máximos de un rango a..b
# Cada llamada de Coral usa varios marcos de Python; se sube el límite para que
# el de Coral se alcance antes que el RecursionError de Python.
sys.setrecursionlimit(max(sys.getrecursionlimit(), LIMITE_RECURSION * 15 + 1000))

COMPARACIONES = ("==", "!=", "<", "<=", ">", ">=")


# =====================================================================
# Señales internas de control de flujo (nunca llegan al usuario)
# =====================================================================
class _Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


class _Rompe(Exception):
    pass


class _Continua(Exception):
    pass


class _Lanzado(Exception):
    """Un ``lanza valor`` que todavía no fue capturado."""

    def __init__(self, valor, nodo):
        self.valor, self.nodo = valor, nodo


# =====================================================================
# Entornos (ámbitos de variables)
# =====================================================================
class Entorno:
    def __init__(self, padre: Entorno | None = None):
        self.vars: dict[str, object] = {}
        self.constantes: set[str] = set()
        self.padre = padre

    def declarar(self, nombre, valor, nodo, constante=False):
        if nombre in self.vars:
            raise ErrorEjecucion(f"'{nombre}' ya fue declarada en este bloque", nodo.linea, nodo.columna)
        self.vars[nombre] = valor
        if constante:
            self.constantes.add(nombre)

    def buscar(self, nombre) -> Entorno | None:
        e = self
        while e is not None:
            if nombre in e.vars:
                return e
            e = e.padre
        return None

    def nombres(self) -> set[str]:
        """Todos los nombres visibles desde aquí (para las sugerencias)."""
        vistos, e = set(), self
        while e is not None:
            vistos.update(n for n in e.vars if not n.startswith("__"))
            e = e.padre
        return vistos

    def obtener(self, nombre, nodo):
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion(self.mensaje_no_definida(nombre), nodo.linea, nodo.columna)
        return e.vars[nombre]

    def mensaje_no_definida(self, nombre) -> str:
        if nombre == "yo":
            return "'yo' solo existe dentro de los métodos de una clase"
        pista = pista_palabra(nombre)
        if pista:
            return f"'{nombre}' no está definida. {pista}"
        return f"'{nombre}' no está definida.{sugerir(nombre, self.nombres())}"

    def asignar(self, nombre, valor, nodo):
        e = self.buscar(nombre)
        if e is None:
            raise ErrorEjecucion(f"No se puede asignar a '{nombre}': declárala primero con 'var'", nodo.linea, nodo.columna)
        if nombre in e.constantes:
            raise ErrorEjecucion(f"'{nombre}' es una constante y no se puede reasignar", nodo.linea, nodo.columna)
        e.vars[nombre] = valor


# =====================================================================
# Valores de Coral en tiempo de ejecución
# =====================================================================
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
    """Función escrita en Python y expuesta a Coral."""
    nombre: str
    fn: Callable
    aridad: tuple[int, int]   # mínimo y máximo de argumentos

    def __repr__(self):
        return f"<funcion nativa {self.nombre}>"


@dataclass(eq=False)
class ClaseCoral:
    nombre: str
    padre: ClaseCoral | None
    metodos: dict[str, FuncionCoral]

    def buscar_metodo(self, nombre) -> tuple[FuncionCoral, ClaseCoral] | None:
        """Busca el método subiendo por la herencia; devuelve (función, clase que lo define)."""
        clase = self
        while clase is not None:
            if nombre in clase.metodos:
                return clase.metodos[nombre], clase
            clase = clase.padre
        return None

    def nombres_metodos(self) -> set[str]:
        nombres, clase = set(), self
        while clase is not None:
            nombres.update(clase.metodos)
            clase = clase.padre
        return nombres

    def hereda_de(self, otra: ClaseCoral) -> bool:
        clase = self
        while clase is not None:
            if clase is otra:
                return True
            clase = clase.padre
        return False

    def __repr__(self):
        return f"<clase {self.nombre}>"


@dataclass(eq=False)
class InstanciaCoral:
    clase: ClaseCoral
    campos: dict[str, object] = field(default_factory=dict)

    def __repr__(self):
        return f"<{self.clase.nombre}>"


@dataclass
class MetodoLigado:
    """Método leído desde una instancia: al llamarlo, ``yo`` es esa instancia."""
    funcion: FuncionCoral
    instancia: InstanciaCoral
    clase: ClaseCoral          # clase donde está definido (para 'padre')

    @property
    def nombre(self):
        return f"{self.clase.nombre}.{self.funcion.nombre}"

    def __repr__(self):
        return f"<metodo {self.nombre}>"


# =====================================================================
# Utilidades sobre valores
# =====================================================================
def tipo_de(v) -> str:
    """Nombre del tipo tal como lo ve quien programa en Coral."""
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
    if isinstance(v, InstanciaCoral):
        return v.clase.nombre
    if isinstance(v, ClaseCoral):
        return "clase"
    return "funcion"


def es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def iguales(a, b) -> bool:
    """Igualdad de Coral: respeta el tipo (1 == verdadero es falso)."""
    if tipo_de(a) != tipo_de(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(iguales(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(iguales(a[k], b[k]) for k in a)
    if isinstance(a, (InstanciaCoral, ClaseCoral)):
        return a is b
    return a == b


def mostrar(v, convertir: Callable | None = None) -> str:
    """Texto con que se imprime un valor. ``convertir`` resuelve instancias con como_texto()."""
    if v is None:
        return "nulo"
    if v is True:
        return "verdadero"
    if v is False:
        return "falso"
    if isinstance(v, float):
        if math.isinf(v):
            return "infinito" if v > 0 else "-infinito"
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_en_coleccion(x, convertir) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{_en_coleccion(k, convertir)}: {_en_coleccion(x, convertir)}" for k, x in v.items()) + "}"
    if isinstance(v, InstanciaCoral) and convertir:
        return convertir(v)
    return str(v)


def _en_coleccion(v, convertir=None) -> str:
    return f'"{v}"' if isinstance(v, str) else mostrar(v, convertir)


def mostrar_en_coleccion(v) -> str:
    return _en_coleccion(v)


def verdadero(v) -> bool:
    """Reglas de verdad: nulo, falso, 0, "", [] y {} son falsos; todo lo demás es verdadero."""
    if v is None or v is False:
        return False
    if es_numero(v):
        return v != 0
    if isinstance(v, (str, list, dict)):
        return len(v) > 0
    return True


# =====================================================================
# Intérprete
# =====================================================================
class Interprete:
    """Ejecuta programas Coral.

    Parámetros inyectables (para tests y para el playground web):
        salida      función que recibe cada línea impresa (por defecto print)
        entrada     función que pide texto al usuario (por defecto input)
        directorio  carpeta base para resolver ``importa "archivo.coral"``
        semilla     semilla de aleatorio(), para resultados reproducibles
    """

    def __init__(self, salida: Callable[[str], None] = print, entrada: Callable[[str], str] = input,
                 directorio: str | None = None, semilla: int | None = None):
        self.salida, self.entrada = salida, entrada
        self.directorio = directorio or os.getcwd()
        self.azar = random.Random(semilla)
        # Las nativas viven en un entorno padre de los globales: así el programa
        # puede definir su propia 'suma' o 'promedio' sin chocar con ellas.
        self.nativas = Entorno()
        for nombre, fn, aridad in self._nativas():
            self.nativas.vars[nombre] = Nativa(nombre, fn, aridad)
        self.globales = Entorno(self.nativas)
        self.profundidad = 0
        self.pruebas: list[tuple[A.Prueba, Entorno]] = []
        self.importados: set[str] = set()

    # -----------------------------------------------------------------
    # Punto de entrada
    # -----------------------------------------------------------------
    def ejecutar(self, codigo: str):
        """Ejecuta un programa completo y devuelve el valor de la última expresión."""
        return self._con_errores_traducidos(lambda: self._ejecutar_programa(parsear(codigo), self.globales))

    def _ejecutar_programa(self, sentencias, env):
        ultimo = None
        for s in sentencias:
            ultimo = self.sentencia(s, env)
        return ultimo

    def _con_errores_traducidos(self, accion):
        """Convierte las señales internas que escaparon en errores claros para el usuario."""
        try:
            return accion()
        except RecursionError:
            raise ErrorEjecucion("Recursión demasiado profunda: el programa se anidó demasiado") from None
        except _Lanzado as l:
            raise ErrorEjecucion(f"Error no capturado: {self.mostrar(l.valor)}", l.nodo.linea, l.nodo.columna) from None
        except _Retorno:
            raise ErrorEjecucion("'retorna' solo puede usarse dentro de una función") from None
        except (_Rompe, _Continua):
            raise ErrorEjecucion("'rompe' y 'continua' solo pueden usarse dentro de un ciclo") from None
        finally:
            self.profundidad = 0

    def ejecutar_pruebas(self) -> list[dict]:
        """Corre los bloques ``prueba`` registrados. Cada resultado: {nombre, ok, error}."""
        resultados = []
        for prueba, env in self.pruebas:
            try:
                self._con_errores_traducidos(lambda: self.bloque(prueba.cuerpo, Entorno(env)))
                resultados.append({"nombre": prueba.nombre, "ok": True, "error": None})
            except ErrorCoral as e:
                resultados.append({"nombre": prueba.nombre, "ok": False, "error": e})
        return resultados

    def mostrar(self, v) -> str:
        return mostrar(v, self._texto_instancia)

    def _texto_instancia(self, inst: InstanciaCoral) -> str:
        """Usa el método como_texto() si la clase lo define; si no, <Clase campo=valor>."""
        encontrado = inst.clase.buscar_metodo("como_texto")
        if encontrado:
            fn, clase = encontrado
            return self.mostrar(self.llamar(MetodoLigado(fn, inst, clase), [], fn.nodo))
        campos = " ".join(f"{k}={_en_coleccion(v, self._texto_instancia)}" for k, v in inst.campos.items())
        return f"<{inst.clase.nombre}{' ' + campos if campos else ''}>"

    def bloque(self, sentencias, entorno):
        for s in sentencias:
            self.sentencia(s, entorno)

    # -----------------------------------------------------------------
    # Funciones nativas (globales)
    # -----------------------------------------------------------------
    def _nativas(self):
        def rango(a, b=None, paso=1):
            inicio, fin = (0, a) if b is None else (a, b)
            if paso == 0:
                raise ValueError("el paso no puede ser 0")
            return list(range(int(inicio), int(fin), int(paso)))

        def numero(v):
            try:
                f = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"no se puede convertir {_en_coleccion(v)} a número") from None
            return int(f) if f.is_integer() and not (isinstance(v, str) and "." in v) else f

        def aleatorio(a=None, b=None):
            if a is None:
                return self.azar.random()
            inicio, fin = (0, a) if b is None else (a, b)
            return self.azar.randint(int(inicio), int(fin))

        def entrada(mensaje=""):
            return self.entrada(self.mostrar(mensaje) if mensaje != "" else "")

        def extremo(fn):
            def calcular(*a):
                valores = a[0] if len(a) == 1 and isinstance(a[0], list) else list(a)
                if not valores:
                    raise ValueError("la lista está vacía")
                return fn(valores)
            return calcular

        return [
            ("imprimir", lambda *a: self.salida(" ".join(self.mostrar(x) for x in a)), (0, 99)),
            ("entrada", entrada, (0, 1)),
            ("largo", lambda v: len(v), (1, 1)),
            ("rango", rango, (1, 3)),
            ("texto", lambda v: self.mostrar(v), (1, 1)),
            ("numero", numero, (1, 1)),
            ("tipo", tipo_de, (1, 1)),
            ("raiz", lambda x: math.sqrt(x), (1, 1)),
            ("redondear", lambda x, d=0: round(x, int(d)) if d else int(round(x)), (1, 2)),
            ("absoluto", abs, (1, 1)),
            ("piso", lambda x: math.floor(x), (1, 1)),
            ("techo", lambda x: math.ceil(x), (1, 1)),
            ("minimo", extremo(min), (1, 99)),
            ("maximo", extremo(max), (1, 99)),
            ("suma", lambda lista: sum(lista), (1, 1)),
            ("ordenar", lambda lista: self._ordenar(lista, None, None), (1, 1)),
            ("aleatorio", aleatorio, (0, 2)),
            ("tiempo", time.time, (0, 0)),
        ]

    def _ordenar(self, lista, clave, nodo):
        try:
            if clave is None:
                return sorted(lista)
            return sorted(lista, key=lambda x: self.llamar(clave, [x], nodo))
        except TypeError:
            raise ValueError("no se pueden ordenar valores de tipos distintos") from None

    # -----------------------------------------------------------------
    # Métodos de los tipos básicos: lista.metodo(), texto.metodo()...
    # -----------------------------------------------------------------
    def _metodos_de(self, obj, nodo) -> dict:
        f = lambda fn, *x: self.llamar(fn, list(x), nodo)        # llama una función de Coral
        if isinstance(obj, list):
            def reduce(fn, inicial=None):
                elementos = list(obj)
                if inicial is None:
                    if not elementos:
                        raise ValueError("reduce() de una lista vacía necesita un valor inicial")
                    inicial = elementos.pop(0)
                acumulado = inicial
                for x in elementos:
                    acumulado = f(fn, acumulado, x)
                return acumulado

            def cuenta(criterio=None):
                if criterio is None:
                    return len(obj)
                if isinstance(criterio, (FuncionCoral, Nativa, MetodoLigado)):
                    return sum(1 for x in obj if verdadero(f(criterio, x)))
                return sum(1 for x in obj if iguales(x, criterio))

            def cada(fn):
                for x in list(obj):
                    f(fn, x)

            def elemento(i):
                if not obj:
                    raise ValueError("la lista está vacía")
                return obj[i]

            return {
                "agrega": (lambda x: obj.append(x), (1, 1)),
                "saca": (lambda i=-1: obj.pop(int(i)), (0, 1)),
                "contiene": (lambda x: any(iguales(x, y) for y in obj), (1, 1)),
                "indice": (lambda x: next((i for i, y in enumerate(obj) if iguales(x, y)), -1), (1, 1)),
                "une": (lambda sep="": sep.join(self.mostrar(x) for x in obj), (0, 1)),
                "invierte": (lambda: obj[::-1], (0, 0)),
                "mapea": (lambda fn: [f(fn, x) for x in obj], (1, 1)),
                "filtra": (lambda fn: [x for x in obj if verdadero(f(fn, x))], (1, 1)),
                "reduce": (reduce, (1, 2)),
                "cada": (cada, (1, 1)),
                "busca": (lambda fn: next((x for x in obj if verdadero(f(fn, x))), None), (1, 1)),
                "cuenta": (cuenta, (0, 1)),
                "ordena": (lambda fn=None: self._ordenar(obj, fn, nodo), (0, 1)),
                "primero": (lambda: elemento(0), (0, 0)),
                "ultimo": (lambda: elemento(-1), (0, 0)),
                "rebanada": (lambda a, b=None: obj[int(a):None if b is None else int(b)], (1, 2)),
                "largo": (lambda: len(obj), (0, 0)),
            }
        if isinstance(obj, str):
            return {
                "mayusculas": (lambda: obj.upper(), (0, 0)),
                "minusculas": (lambda: obj.lower(), (0, 0)),
                # divide() separa por espacios; divide("") separa en letras.
                "divide": (lambda sep=None: obj.split() if sep is None else list(obj) if sep == "" else obj.split(sep), (0, 1)),
                "contiene": (lambda x: x in obj, (1, 1)),
                "reemplaza": (lambda a, b: obj.replace(a, b), (2, 2)),
                "recorta": (lambda: obj.strip(), (0, 0)),
                "empieza_con": (lambda x: obj.startswith(x), (1, 1)),
                "termina_con": (lambda x: obj.endswith(x), (1, 1)),
                "indice": (lambda x: obj.find(x), (1, 1)),
                "rebanada": (lambda a, b=None: obj[int(a):None if b is None else int(b)], (1, 2)),
                "repite": (lambda n: obj * int(n), (1, 1)),
                "largo": (lambda: len(obj), (0, 0)),
            }
        if isinstance(obj, dict):
            return {
                "claves": (lambda: list(obj.keys()), (0, 0)),
                "valores": (lambda: list(obj.values()), (0, 0)),
                "pares": (lambda: [[k, v] for k, v in obj.items()], (0, 0)),
                "tiene": (lambda k: k in obj, (1, 1)),
                "obtiene": (lambda k, defecto=None: obj.get(k, defecto), (1, 2)),
                "borra": (lambda k: obj.pop(k, None), (1, 1)),
                "largo": (lambda: len(obj), (0, 0)),
            }
        return {}

    def atributo(self, obj, nombre: str, nodo):
        """Resuelve obj.nombre: campo de instancia, método de clase, clave de diccionario o método nativo."""
        if isinstance(obj, InstanciaCoral):
            if nombre in obj.campos:
                return obj.campos[nombre]
            encontrado = obj.clase.buscar_metodo(nombre)
            if encontrado:
                return MetodoLigado(encontrado[0], obj, encontrado[1])
            opciones = set(obj.campos) | obj.clase.nombres_metodos()
            raise ErrorEjecucion(f"{obj.clase.nombre} no tiene el campo ni el método '{nombre}'.{sugerir(nombre, opciones)}",
                                 nodo.linea, nodo.columna)
        if isinstance(obj, dict) and nombre in obj:
            return obj[nombre]
        metodos = self._metodos_de(obj, nodo)
        if nombre not in metodos:
            raise ErrorEjecucion(f"El tipo {tipo_de(obj)} no tiene el método '{nombre}'.{sugerir(nombre, metodos)}",
                                 nodo.linea, nodo.columna)
        fn, aridad = metodos[nombre]
        return Nativa(nombre, fn, aridad)

    # -----------------------------------------------------------------
    # Sentencias
    # -----------------------------------------------------------------
    def sentencia(self, s, env):
        match s:
            case A.Declaracion(nombre, valor, constante):
                env.declarar(nombre, self.evaluar(valor, env), s, constante)
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
                    if vueltas > LIMITE_VUELTAS:
                        raise ErrorEjecucion("El ciclo 'mientras' superó un millón de vueltas: ¿falta actualizar la condición?",
                                             s.linea, s.columna)
                    try:
                        self.bloque(cuerpo, Entorno(env))
                    except _Rompe:
                        break
                    except _Continua:
                        continue
            case A.Para(var, iterable, cuerpo):
                self.ejecutar_para(s, var, self.evaluar(iterable, env), cuerpo, env)
            case A.Retorna(valor):
                raise _Retorno(None if valor is None else self.evaluar(valor, env))
            case A.Rompe():
                raise _Rompe()
            case A.Continua():
                raise _Continua()
            case A.Clase():
                env.declarar(s.nombre, self.crear_clase(s, env), s)
            case A.Intenta(cuerpo, variable, manejo):
                self.ejecutar_intenta(cuerpo, variable, manejo, env)
            case A.Lanza(valor):
                raise _Lanzado(self.evaluar(valor, env), s)
            case A.Segun(valor, casos, otro):
                self.ejecutar_segun(self.evaluar(valor, env), casos, otro, env)
            case A.Prueba():
                self.pruebas.append((s, env))
            case A.Afirma(cond, mensaje):
                self.ejecutar_afirma(s, cond, mensaje, env)
            case A.Importa(ruta):
                self.importar(ruta, s)
        return None

    def ejecutar_para(self, s, var, coleccion, cuerpo, env):
        if isinstance(coleccion, dict):
            coleccion = list(coleccion)
        if not isinstance(coleccion, (list, str)):
            raise ErrorEjecucion(f"No se puede recorrer un valor de tipo {tipo_de(coleccion)}", s.linea, s.columna)
        for item in list(coleccion):           # copia: modificar la lista dentro del ciclo no lo rompe
            local = Entorno(env)
            local.vars[var] = item
            try:
                self.bloque(cuerpo, local)
            except _Rompe:
                break
            except _Continua:
                continue

    def crear_clase(self, s: A.Clase, env) -> ClaseCoral:
        padre = None
        if s.padre is not None:
            padre = self.evaluar(s.padre, env)
            if not isinstance(padre, ClaseCoral):
                raise ErrorEjecucion(f"Solo se puede heredar de una clase, y '{s.padre.nombre}' es {tipo_de(padre)}",
                                     s.padre.linea, s.padre.columna)
        return ClaseCoral(s.nombre, padre, {m.nombre: FuncionCoral(m, env) for m in s.metodos})

    def ejecutar_intenta(self, cuerpo, variable, manejo, env):
        try:
            self.bloque(cuerpo, Entorno(env))
            return
        except _Lanzado as l:
            valor = l.valor
        except ErrorEjecucion as e:       # los errores del propio lenguaje también se capturan, como texto
            valor = e.mensaje
        local = Entorno(env)
        if variable:
            local.vars[variable] = valor
        self.bloque(manejo, local)

    def ejecutar_segun(self, valor, casos, otro, env):
        for opciones, cuerpo in casos:
            for opcion in opciones:
                o = self.evaluar(opcion, env)
                # 'caso 1..5' compara contra cada elemento del rango (si el valor no es una lista)
                coincide = iguales(valor, o) or (isinstance(o, list) and not isinstance(valor, list)
                                                 and any(iguales(valor, x) for x in o))
                if coincide:
                    self.bloque(cuerpo, Entorno(env))
                    return
        if otro is not None:
            self.bloque(otro, Entorno(env))

    def ejecutar_afirma(self, s, cond, mensaje, env):
        # En comparaciones se evalúa cada lado por separado para explicar el fallo.
        if isinstance(cond, A.Binaria) and cond.op in COMPARACIONES:
            izq, der = self.evaluar(cond.izq, env), self.evaluar(cond.der, env)
            if verdadero(self.operar(cond.op, izq, der, cond)):
                return
            detalle = f"se esperaba {_en_coleccion(izq, self._texto_instancia)} {cond.op} {_en_coleccion(der, self._texto_instancia)}"
        else:
            if verdadero(self.evaluar(cond, env)):
                return
            detalle = "la condición resultó falsa"
        texto = self.mostrar(self.evaluar(mensaje, env)) + f" ({detalle})" if mensaje else detalle.capitalize()
        raise ErrorPrueba(texto, s.linea, s.columna)

    def importar(self, ruta, s):
        """Ejecuta otro archivo .coral en el ámbito global (una sola vez por archivo)."""
        completa = os.path.abspath(os.path.join(self.directorio, ruta))
        if completa in self.importados:
            return
        try:
            with open(completa, encoding="utf-8-sig") as f:
                codigo = f.read()
        except OSError:
            raise ErrorEjecucion(f"No se encontró el archivo '{ruta}' para importar", s.linea, s.columna) from None
        self.importados.add(completa)
        anterior, self.directorio = self.directorio, os.path.dirname(completa)
        try:
            self._ejecutar_programa(parsear(codigo), self.globales)
        except ErrorCoral as e:
            # La posición original es de otro archivo: se informa en el mensaje y se señala el 'importa'.
            donde = f" (línea {e.linea})" if e.linea else ""
            raise type(e)(f"En '{ruta}'{donde}: {e.mensaje}", s.linea, s.columna) from None
        finally:
            self.directorio = anterior

    # -----------------------------------------------------------------
    # Expresiones
    # -----------------------------------------------------------------
    def evaluar(self, e, env):
        match e:
            case A.Literal(valor):
                return valor
            case A.Plantilla(partes):
                return "".join(p if isinstance(p, str) else self.mostrar(self.evaluar(p, env)) for p in partes)
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
                return self.atributo(self.evaluar(obj, env), nombre, e)
            case A.Padre(nombre):
                return self.metodo_padre(nombre, env, e)
            case A.Llamada(fn, args):
                return self.llamar(self.evaluar(fn, env), [self.evaluar(a, env) for a in args], e)
        raise ErrorEjecucion(f"Nodo desconocido {type(e).__name__}", e.linea, e.columna)

    def metodo_padre(self, nombre, env, nodo):
        clase_env = env.buscar("__clase__")
        if clase_env is None:
            raise ErrorEjecucion("'padre' solo se puede usar dentro de un método", nodo.linea, nodo.columna)
        clase = clase_env.vars["__clase__"]
        if clase.padre is None:
            raise ErrorEjecucion(f"La clase {clase.nombre} no hereda de ninguna otra", nodo.linea, nodo.columna)
        encontrado = clase.padre.buscar_metodo(nombre)
        if not encontrado:
            raise ErrorEjecucion(f"La clase {clase.padre.nombre} no tiene el método '{nombre}'."
                                 f"{sugerir(nombre, clase.padre.nombres_metodos())}", nodo.linea, nodo.columna)
        return MetodoLigado(encontrado[0], env.obtener("yo", nodo), encontrado[1])

    def asignar(self, objetivo, op, valor_nodo, env, nodo):
        valor = self.evaluar(valor_nodo, env)
        if isinstance(objetivo, A.Variable):
            if op != "=":
                valor = self.operar(op[0], env.obtener(objetivo.nombre, objetivo), valor, nodo)
            env.asignar(objetivo.nombre, valor, objetivo)
            return valor
        if isinstance(objetivo, A.Atributo):
            obj = self.evaluar(objetivo.objeto, env)
            if op != "=":
                valor = self.operar(op[0], self.atributo(obj, objetivo.nombre, nodo), valor, nodo)
            if isinstance(obj, InstanciaCoral):
                obj.campos[objetivo.nombre] = valor
            elif isinstance(obj, dict):
                obj[objetivo.nombre] = valor
            else:
                raise ErrorEjecucion(f"No se pueden agregar campos a un {tipo_de(obj)}", nodo.linea, nodo.columna)
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
                raise ErrorEjecucion(f"La clave {_en_coleccion(idx)} no existe.{sugerir(str(idx), map(str, cont))}",
                                     nodo.linea, nodo.columna)
            return cont[idx]
        raise ErrorEjecucion(f"No se puede indexar un valor de tipo {tipo_de(cont)}", nodo.linea, nodo.columna)

    def numeros(self, nodo, *vals):
        for v in vals:
            if not es_numero(v):
                raise ErrorEjecucion(f"Se esperaba un número y se recibió {tipo_de(v)}", nodo.linea, nodo.columna)

    def operar(self, op, a, b, nodo):
        if op == "==":
            return iguales(a, b)
        if op == "!=":
            return not iguales(a, b)
        if op == "es":
            return self.es_tipo(a, b, nodo)
        if op == "..":
            return self.rango_inclusivo(a, b, nodo)
        if op == "+":
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            if isinstance(a, str) or isinstance(b, str):
                raise ErrorEjecucion(f"No se puede sumar {tipo_de(a)} y {tipo_de(b)}. "
                                     "Usa texto() para convertir o una plantilla: \"valor: {x}\"", nodo.linea, nodo.columna)
        if op == "*" and isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool):
            return a * b
        if op in ("<", "<=", ">", ">=") and isinstance(a, str) and isinstance(b, str):
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
        self.numeros(nodo, a, b)
        if op in ("/", "%") and b == 0:
            raise ErrorEjecucion("División por cero", nodo.linea, nodo.columna)
        try:
            r = {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a / b,
                 "%": lambda: a % b, "**": lambda: a ** b, "<": lambda: a < b, "<=": lambda: a <= b,
                 ">": lambda: a > b, ">=": lambda: a >= b}[op]()
        except OverflowError:
            raise ErrorEjecucion("El resultado es demasiado grande", nodo.linea, nodo.columna) from None
        if isinstance(r, complex):
            raise ErrorEjecucion("El resultado no es un número real", nodo.linea, nodo.columna)
        if op == "/" and isinstance(r, float) and r.is_integer():
            return int(r)
        return r

    def es_tipo(self, valor, tipo, nodo) -> bool:
        """``x es Clase`` (con herencia) o ``x es "texto"`` (nombre de tipo)."""
        if isinstance(tipo, ClaseCoral):
            return isinstance(valor, InstanciaCoral) and valor.clase.hereda_de(tipo)
        if isinstance(tipo, str):
            if isinstance(valor, InstanciaCoral):
                clase = valor.clase
                while clase is not None:
                    if clase.nombre == tipo:
                        return True
                    clase = clase.padre
                return tipo == "objeto"
            return tipo_de(valor) == tipo
        raise ErrorEjecucion(f"A la derecha de 'es' va una clase o un nombre de tipo, no {tipo_de(tipo)}",
                             nodo.linea, nodo.columna)

    def rango_inclusivo(self, a, b, nodo) -> list:
        """1..5 = [1, 2, 3, 4, 5];  5..1 = [5, 4, 3, 2, 1]."""
        for v in (a, b):
            if not isinstance(v, int) or isinstance(v, bool):
                raise ErrorEjecucion(f"Los extremos de un rango deben ser enteros, no {tipo_de(v)}", nodo.linea, nodo.columna)
        if abs(b - a) + 1 > LIMITE_RANGO:
            raise ErrorEjecucion(f"El rango {a}..{b} es demasiado grande", nodo.linea, nodo.columna)
        return list(range(a, b + 1)) if a <= b else list(range(a, b - 1, -1))

    # -----------------------------------------------------------------
    # Llamadas
    # -----------------------------------------------------------------
    def llamar(self, fn, args, nodo):
        if isinstance(fn, Nativa):
            return self.llamar_nativa(fn, args, nodo)
        if isinstance(fn, ClaseCoral):
            return self.instanciar(fn, args, nodo)
        if isinstance(fn, MetodoLigado):
            return self.llamar_funcion(fn.funcion, args, nodo, {"yo": fn.instancia, "__clase__": fn.clase}, fn.nombre)
        if isinstance(fn, FuncionCoral):
            return self.llamar_funcion(fn, args, nodo, {}, fn.nombre)
        raise ErrorEjecucion(f"Un valor de tipo {tipo_de(fn)} no se puede llamar", nodo.linea, nodo.columna)

    def llamar_nativa(self, fn: Nativa, args, nodo):
        mn, mx = fn.aridad
        if not mn <= len(args) <= mx:
            esperado = mn if mn == mx else f"entre {mn} y {mx}"
            raise ErrorEjecucion(f"{fn.nombre}() espera {esperado} argumentos y recibió {len(args)}", nodo.linea, nodo.columna)
        try:
            return fn.fn(*args)
        except (ErrorCoral, _Lanzado, _Retorno, _Rompe, _Continua):
            raise
        except (TypeError, ValueError, IndexError, AttributeError, OverflowError) as exc:
            raise ErrorEjecucion(f"{fn.nombre}(): {self._explicar(exc)}", nodo.linea, nodo.columna) from None

    @staticmethod
    def _explicar(exc: Exception) -> str:
        """Traduce los errores típicos de Python que pueden escaparse de una nativa."""
        texto = str(exc)
        if isinstance(exc, TypeError):
            return "tipo de argumento incorrecto"
        if isinstance(exc, IndexError):
            return "índice fuera de rango"
        if "math domain error" in texto:
            return "valor fuera del dominio de la función"
        return texto

    def instanciar(self, clase: ClaseCoral, args, nodo) -> InstanciaCoral:
        inst = InstanciaCoral(clase)
        encontrado = clase.buscar_metodo("iniciar")
        if encontrado:
            self.llamar(MetodoLigado(encontrado[0], inst, encontrado[1]), args, nodo)
        elif args:
            raise ErrorEjecucion(f"{clase.nombre}() no recibe argumentos porque la clase no define 'iniciar'",
                                 nodo.linea, nodo.columna)
        return inst

    def llamar_funcion(self, fn: FuncionCoral, args, nodo, extras: dict, nombre: str):
        params = fn.nodo.parametros
        if len(args) != len(params):
            raise ErrorEjecucion(f"{nombre}() espera {len(params)} argumentos y recibió {len(args)}", nodo.linea, nodo.columna)
        self.profundidad += 1
        if self.profundidad > LIMITE_RECURSION:
            raise ErrorEjecucion(f"Recursión demasiado profunda en {nombre}() (más de {LIMITE_RECURSION} llamadas). "
                                 "¿Falta el caso base?", nodo.linea, nodo.columna)
        local = Entorno(fn.cierre)
        local.vars.update(extras)
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
