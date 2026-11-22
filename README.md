# Coral · un lenguaje de programación en español

Coral es un lenguaje dinámico con palabras clave en español, **escrito desde cero en Python sin dependencias**: analizador léxico, parser Pratt, árbol de sintaxis e intérprete con clausuras, programación orientada a objetos completa, excepciones y un sistema de pruebas propio.

**[Pruébalo en el navegador →](https://fp-507.github.io/coral-lang/playground/)** (corre con WebAssembly gracias a Pyodide)

![tests](https://github.com/FP-507/coral-lang/actions/workflows/tests.yml/badge.svg)

```coral
clase Producto {
    funcion iniciar(nombre, precio) {
        yo.nombre = nombre
        yo.precio = precio
    }
    funcion como_texto() => "{yo.nombre} (${yo.precio})"
}

const CATALOGO = [Producto("café", 4.5), Producto("té", 3), Producto("cacao", 6)]

funcion caros(lista) => lista.filtra(funcion (p) => p.precio > 4)
funcion por_precio(lista) => lista.ordena(funcion (p) => p.precio)

imprimir(CATALOGO |> caros |> por_precio)     # [café ($4.5), cacao ($6)]

prueba "solo quedan los caros" {
    afirma largo(caros(CATALOGO)) == 2
}
```

## ¿Qué hace diferente a Coral?

No intenta ser "Python traducido". Está pensado para **aprender a programar en español** y tiene cinco cosas que pocos lenguajes juntan:

1. **Errores que enseñan.** Cada error dice la línea y la columna, muestra el código con una flecha y, cuando puede, explica qué hacer:
   ```
   Error de ejecución (línea 5, columna 1): 'print' no está definida. En Coral se escribe 'imprimir' en lugar de 'print'
       5 | print("Total:", total)
         | ^
   ```
   Reconoce las palabras de Python y JavaScript (`if`, `while`, `def`, `self`, `&&`, `||`, `True`...) y sugiere el nombre correcto ante errores de tipeo: `imprmir(1)` → *¿Quisiste decir 'imprimir'?*
2. **Pruebas integradas en el lenguaje.** `prueba "nombre" { afirma ... }` vive junto al código; `python -m coral --pruebas archivo.coral` las corre y explica cada fallo (*se esperaba 4 == 5*). No hace falta ninguna biblioteca.
3. **Tuberías `|>`.** Los datos se leen de izquierda a derecha: `datos |> limpiar |> ordenar |> tomar(3)` en vez de `tomar(ordenar(limpiar(datos)), 3)`.
4. **POO completa y en español.** Clases abstractas, encapsulamiento real (`_saldo` no se puede tocar desde afuera), métodos estáticos, herencia con `padre` y sobrecarga de operadores con nombres legibles: `a + b` llama a `a.mas(b)`.
5. **Plantillas y rangos legibles.** `"Hola {nombre}, tienes {edad + 1}"`, `para i en 1..10`, `caso 7..9 { ... }`.

## Características

| Área | Qué incluye |
|---|---|
| Tipos | número, texto, booleano (`verdadero`/`falso`), `nulo`, lista, diccionario, función, clase e instancia |
| Variables | `var`, `const` (no se reasigna), ámbitos de bloque |
| Control | `si`/`sino si`/`sino`, `mientras`, `para x en ...`, `rompe`, `continua`, `segun`/`caso`/`otro` |
| Funciones | de primera clase, anónimas, forma corta `funcion (x) => x * 2`, clausuras, tuberías `\|>` |
| POO | `clase`, `hereda`, `yo`, `padre.metodo()`, constructor `iniciar`, clases y métodos `abstracta`, métodos `estatico`, constantes de clase, campos y métodos privados (`_nombre`), sobrecarga de operadores (`mas`, `igual_a`, `menor_que`...), objetos recorribles (`elementos()`), `como_texto()` y operador `es` |
| Errores | `intenta`/`captura`/`lanza` (se puede lanzar cualquier valor) |
| Pruebas | `prueba`, `afirma` con explicación del fallo, `--pruebas` con código de salida para CI |
| Módulos | `importa "util.coral"` (ruta relativa, se carga una sola vez) |
| Biblioteca | más de 50 funciones y métodos: `mapea`, `filtra`, `reduce`, `ordena`, `busca`, `divide`, `reemplaza`, `obtiene`... |

La referencia completa está en **[docs/GUIA.md](docs/GUIA.md)**.

## Cómo funciona

```
código ──► lexer.py ──► tokens ──► parser.py ──► AST (ast.py) ──► interprete.py ──► resultado
                                                                    │
                          errores.py (posición y contexto) ◄────────┤
                          pistas.py (¿quisiste decir…?)    ◄────────┘
```

| Etapa | Archivo | Técnica |
|---|---|---|
| Análisis léxico | [`lexer.py`](coral/lexer.py) | Escáner de un paso con línea y columna; las plantillas guardan el código interpolado para parsearlo después |
| Análisis sintáctico | [`parser.py`](coral/parser.py) | Descenso recursivo para sentencias y **Pratt** para expresiones; `\|>` se reescribe como llamada al parsear |
| AST | [`ast.py`](coral/ast.py) | Nodos `dataclass` con posición |
| Evaluación | [`interprete.py`](coral/interprete.py) | Recorrido del árbol con `match`, entornos encadenados, control de flujo con excepciones internas, clases sin metaprogramación |
| Ayuda | [`pistas.py`](coral/pistas.py) | Tabla de equivalencias de otros lenguajes y sugerencias con `difflib` |

Las decisiones de diseño y cómo agregar algo nuevo están en **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

## Uso

```bash
python -m coral                                  # REPL interactivo
python -m coral ejemplos/clases.coral            # ejecuta un archivo
python -m coral --pruebas ejemplos/pruebas.coral # corre sus pruebas
pip install -e . && coral programa.coral         # como comando
```

## Ejemplos

| Archivo | Muestra |
|---|---|
| [`algoritmos.coral`](ejemplos/algoritmos.coral) | Fibonacci, quicksort, criba de primos |
| [`clausuras.coral`](ejemplos/clausuras.coral) | Contadores, composición de funciones |
| [`clases.coral`](ejemplos/clases.coral) | Cuenta bancaria con herencia, `padre`, `como_texto` y errores |
| [`poo.coral`](ejemplos/poo.coral) | Los cuatro pilares de la POO: figuras abstractas, encapsulamiento, estáticos, operadores y objetos recorribles |
| [`errores.coral`](ejemplos/errores.coral) | `intenta`/`captura`/`lanza` con valores y diccionarios |
| [`tuberias.coral`](ejemplos/tuberias.coral) | `\|>`, rangos, `segun` y plantillas |
| [`pruebas.coral`](ejemplos/pruebas.coral) | Bloques `prueba` y `afirma` |
| [`util.coral`](ejemplos/util.coral) + [`uso_importa.coral`](ejemplos/uso_importa.coral) | Módulos con `importa` |

## Tests

```bash
pip install pytest
pytest -q
```

64 tests cubren el lexer, la precedencia del parser, la semántica del intérprete, la POO (abstractas, privados, estáticos, operadores), excepciones, pruebas integradas, módulos, las pistas para quien viene de otro lenguaje, más de 20 tipos de errores y que todos los ejemplos corran con sus pruebas en verde. La CI los corre en Python 3.10 y 3.13.

## Estructura

```
coral/        lexer · parser · ast · interprete · errores · pistas · CLI (__main__)
docs/         GUIA.md (el lenguaje) · ARQUITECTURA.md (el intérprete por dentro)
ejemplos/     programas de ejemplo (cada uno con sus pruebas)
playground/   editor web que ejecuta Coral con Pyodide
tests/        suite de pytest
```

---

Proyecto personal de [Fidel Pizart](https://fp-507.github.io/Portafolio/).
