# Coral · un lenguaje de programación en español

Coral es un lenguaje de programación pequeño, dinámico y con palabras clave en español, **escrito desde cero en Python sin dependencias**: analizador léxico, parser de descenso recursivo con precedencia de operadores (Pratt), árbol de sintaxis abstracta e intérprete con clausuras.

**[Pruébalo en el navegador →](https://fp-507.github.io/coral-lang/playground/)** (corre con WebAssembly gracias a Pyodide)

![tests](https://github.com/FP-507/coral-lang/actions/workflows/tests.yml/badge.svg)

```coral
funcion quicksort(lista) {
  si largo(lista) <= 1 { retorna lista }
  var pivote = lista[0]
  var resto = []
  para i en rango(1, largo(lista)) { resto.agrega(lista[i]) }
  retorna quicksort(resto.filtra(funcion (x) => x < pivote)) + [pivote]
       + quicksort(resto.filtra(funcion (x) => x >= pivote))
}

imprimir(quicksort([38, 4, 91, 15, 62, 7]))   # [4, 7, 15, 38, 62, 91]
```

## Características

- **Tipos**: números (enteros y decimales), textos, booleanos (`verdadero`/`falso`), `nulo`, listas, diccionarios y funciones.
- **Control de flujo**: `si` / `sino si` / `sino`, `mientras`, `para x en coleccion`, `rompe`, `continua`.
- **Funciones de primera clase**: declaraciones, funciones anónimas, sintaxis corta `funcion (x) => x * 2` y **clausuras** que capturan su entorno.
- **Ámbitos de bloque**: cada `{ }` crea un ámbito nuevo; las variables se declaran con `var` y no se pueden redeclarar en el mismo bloque.
- **Métodos**: `lista.agrega`, `mapea`, `filtra`, `une`; `texto.divide`, `mayusculas`; `dict.claves`, `valores`, `tiene`.
- **Funciones nativas**: `imprimir`, `largo`, `rango`, `texto`, `numero`, `tipo`, `suma`, `ordenar`, `raiz`, `redondear`, `minimo`, `maximo`.
- **Errores claros con línea y columna**, la línea de código y una flecha:

```
Error de ejecución (línea 3, columna 20): No se puede sumar texto y numero. Usa texto() para convertir
    3 | imprimir("Tienes " + edad + " años")
      |                    ^
```

## Cómo funciona

```
código fuente ──► lexer.py ──► tokens ──► parser.py ──► AST (ast.py) ──► interprete.py ──► resultado
```

| Etapa | Archivo | Técnica |
|---|---|---|
| Análisis léxico | [`lexer.py`](coral/lexer.py) | Escáner de un solo paso con seguimiento de línea y columna |
| Análisis sintáctico | [`parser.py`](coral/parser.py) | Descenso recursivo para sentencias y **Pratt** para expresiones (precedencia y asociatividad) |
| AST | [`ast.py`](coral/ast.py) | Nodos como `dataclasses` |
| Evaluación | [`interprete.py`](coral/interprete.py) | Recorrido del árbol con `match`, entornos encadenados para ámbitos y clausuras, y control de flujo con excepciones internas |

Protecciones del intérprete: límite de recursión con mensaje propio, tope de vueltas en `mientras` y validación de tipos en cada operación.

## Uso

```bash
python -m coral                          # REPL interactivo
python -m coral ejemplos/algoritmos.coral
pip install -e . && coral programa.coral # como comando
```

## Tests

```bash
pip install pytest
pytest -v
```

28 tests cubren el lexer, la precedencia del parser, la semántica del intérprete, las clausuras, los ámbitos, 12 tipos de errores de ejecución y que todos los ejemplos corran.

## Estructura

```
coral/        lexer · parser · ast · interprete · errores · REPL (__main__)
ejemplos/     programas de ejemplo
playground/   editor web que ejecuta Coral con Pyodide
tests/
```
