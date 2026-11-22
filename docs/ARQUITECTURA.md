# Arquitectura de Coral

Documento para retomar el proyecto: cómo está construido el intérprete, por qué se tomó cada decisión y cómo agregar cosas sin romper nada.

## Mapa rápido

```
coral/
├── __init__.py     API pública: ejecutar(), ejecutar_pruebas(), Interprete, errores
├── __main__.py     CLI: REPL, ejecutar archivo, --pruebas, --version
├── errores.py      ErrorCoral → ErrorSintaxis | ErrorEjecucion | ErrorPrueba
├── pistas.py       equivalencias de otros lenguajes + sugerencias por parecido
├── lexer.py        texto → lista de Token
├── ast.py          nodos del árbol (dataclasses)
├── parser.py       tokens → AST
└── interprete.py   recorre el AST y lo ejecuta
```

Flujo completo de `python -m coral programa.coral`:

1. `__main__.ejecutar_archivo` lee el archivo (utf-8-sig, por el BOM de Windows) y crea un `Interprete` con el directorio del archivo.
2. `Interprete.ejecutar` llama a `parsear(codigo)`, que a su vez llama a `tokenizar`.
3. Cada sentencia del programa pasa por `Interprete.sentencia`, y cada expresión por `Interprete.evaluar`.
4. Si algo falla, se lanza un `ErrorCoral` con línea y columna, y la CLI imprime `error.con_contexto(codigo)`.

No hay dependencias externas: solo la biblioteca estándar. Por eso el mismo código corre en el navegador con Pyodide.

## 1. Lexer (`lexer.py`)

Recorre el texto una vez con un `_Escaner` que lleva `i`, `linea` y `col`.

- **Números:** `1_000` admite guiones bajos. Un `.` solo es decimal si le sigue un dígito; así `1..5` produce `NUM ..` `NUM` y no `1.` `.5`.
- **Palabras:** si están en `PALABRAS_CLAVE` el token es `CLAVE`; si no, `NOMBRE`.
- **Símbolos:** primero se prueban los dobles (`==`, `|>`, `..`...) y luego los simples.
- **Textos y plantillas:** un texto sin `{` es un token `TEXTO`. Con `{expr}` es `PLANTILLA`, y su valor es una lista de partes: `str` (literal) o `(codigo, linea, columna)`. El código interpolado **no** se tokeniza aquí: lo parsea el parser después, y la posición guardada permite que los errores señalen el lugar exacto dentro del texto.
  - Dentro de `{…}` no se puede usar la misma comilla que abre el texto (simplifica el escaneo y el error lo explica).
  - `\{` y `\}` producen llaves literales.
- **Operadores de otros lenguajes:** `&&`, `||` y `!` (sin `=`) generan un error con la palabra de Coral equivalente (`pistas.OPERADORES_INGLES`).

## 2. Parser (`parser.py`)

Combina dos técnicas:

**Descenso recursivo para sentencias.** `sentencia()` mira el token actual; si es una palabra clave busca el método `_s_<palabra>` (por ejemplo `_s_si`, `_s_clase`). Si no lo hay, la sentencia es una expresión. Agregar una sentencia nueva consiste en escribir un método `_s_nueva` y agregar la palabra a `PALABRAS_CLAVE` del lexer.

**Pratt para expresiones.** `binaria(min_prec)` lee un operando y, mientras el siguiente operador tenga precedencia mayor que `min_prec`, lo consume y llama recursivamente con la precedencia de ese operador. La tabla `PRECEDENCIA` define todo; `DERECHA` lista los operadores asociativos a la derecha (`**`).

```
|> (1)  <  o (2)  <  y (3)  <  == != es (4)  <  < <= > >= (5)  <  .. (6)  <  + - (7)  <  * / % (8)  <  ** (9)  <  prefijos (10)
```

Detalles importantes:

- **Tubería como azúcar sintáctico.** `x |> f(a)` se transforma en `Llamada(f, [x, a])` al parsear. El intérprete no sabe que existe `|>`.
- **Asignación** se maneja en `expresion()`, fuera de Pratt: se parsea el lado izquierdo como expresión y, si viene `=`/`+=`/`-=`, se valida que sea `Variable`, `Indice` o `Atributo`.
- **Posfijos** (`f(x)`, `a[i]`, `a.b`) se encadenan en `posfija()`.
- **Diccionarios:** las claves que son `NOMBRE` se toman como texto (`{nombre: 1}` equivale a `{"nombre": 1}`).
- **Interpolaciones:** `subexpresion()` crea un `Parser` nuevo para el código entre llaves y reescribe cualquier error para que apunte a la posición del texto original.
- **Pistas en el parser:** `pista_ingles()` detecta sentencias que empiezan con `if`, `while`, `return`... seguidas de algo que confirma el uso como palabra clave, y da la palabra de Coral. Así `if x > 1 { }` explica que se escribe `si` en vez de fallar con un error genérico.
- **Palabras reservadas como nombre:** `espera("NOMBRE")` explica que `y`, `o`, `en`... son reservadas.

## 3. AST (`ast.py`)

Nodos `dataclass` que heredan de `Nodo`, que aporta `linea` y `columna` como argumentos solo por nombre y excluidos de la igualdad (los tests comparan estructura sin importar posiciones). Expresiones y sentencias están separadas en el archivo. Los nodos no tienen comportamiento: toda la lógica está en el intérprete.

## 4. Intérprete (`interprete.py`)

### Entornos

`Entorno` es un diccionario de variables más un puntero al padre. La cadena es:

```
nativas  ←  globales  ←  entorno de cada función / bloque
```

Las nativas están en un entorno propio para que el programa pueda definir su propia `suma` sin el error de "ya fue declarada". Las constantes se guardan en `Entorno.constantes` y `asignar` las protege.

### Valores en tiempo de ejecución

| Coral | Python |
|---|---|
| número, texto, booleano, nulo | `int`/`float`, `str`, `bool`, `None` |
| lista, diccionario | `list`, `dict` (mutables, se comparten por referencia) |
| función | `FuncionCoral(nodo, cierre)` |
| función nativa / método de tipo | `Nativa(nombre, fn, aridad)` |
| clase | `ClaseCoral(nombre, padre, metodos)` |
| instancia | `InstanciaCoral(clase, campos)` |
| método leído de una instancia | `MetodoLigado(funcion, instancia, clase)` |

Cuidado: en Python `bool` es subclase de `int`. Por eso existen `es_numero()` e `iguales()`, que distinguen `1` de `verdadero`.

### Control de flujo

`retorna`, `rompe`, `continua` y `lanza` lanzan excepciones privadas (`_Retorno`, `_Rompe`, `_Continua`, `_Lanzado`):

- `llamar_funcion` atrapa `_Retorno`.
- Los ciclos atrapan `_Rompe` y `_Continua`.
- `ejecutar_intenta` atrapa `_Lanzado` (valor de Coral) y `ErrorEjecucion` (error del lenguaje, se entrega como texto). No atrapa `ErrorPrueba`: un `afirma` fallido no se puede silenciar con `intenta`.
- `_con_errores_traducidos` convierte en errores legibles las señales que escapan hasta arriba (por ejemplo, un `retorna` fuera de función).

### Clases

- `crear_clase` convierte los nodos `Funcion` en `FuncionCoral` con el entorno donde se declaró la clase como cierre.
- Llamar a una clase (`instanciar`) crea una `InstanciaCoral` y llama a `iniciar` si existe en la cadena de herencia.
- `atributo()` resuelve `obj.nombre` en este orden: campo de la instancia, método de la clase (subiendo por `padre`), clave de diccionario, método nativo del tipo.
- `MetodoLigado` guarda la clase **donde está definido** el método. Al llamarlo se agregan `yo` y `__clase__` al entorno local; `padre.x` usa `__clase__.padre`, lo que hace correcto el `padre` en herencias de varios niveles.
- `mostrar()` usa `como_texto()` si la clase lo define y oculta los campos privados.
- **Miembros de clase:** `ClaseCoral` guarda además `estaticos`, `constantes` (evaluadas al declarar la clase) y `abstractos` (solo nombres). `buscar_de_clase()` los busca subiendo por la herencia; `Clase.X` y `yo.X` los encuentran.
- **Abstractas:** `instanciar` llama a `abstractos_pendientes()` y no crea el objeto si queda alguno. `buscar_metodo` se detiene si encuentra el nombre declarado como abstracto antes que una implementación.
- **Privados:** un nombre que empieza con `_` solo se puede leer o asignar si `acceso_interno()` es verdadero: el objeto es `yo`, o el código corre dentro de un método (`__clase__` en el entorno) de la clase del objeto o de una superclase. La comprobación se hace solo si el miembro existe, para que los errores de "no existe" sigan dando pistas.
- **Operadores:** `operar()` delega en `operar_objeto()` si el operando izquierdo es una instancia (`OPERADORES_OBJETO` mapea `+` a `mas`, etc.). `==` usa `igual_a` o la identidad; `<`, `<=`, `>`, `>=` se derivan de `menor_que` e `igual_a`. `_ordenar` y `minimo`/`maximo` usan ese mismo orden para listas de objetos. `largo(obj)` llama a `obj.largo()` y `para x en obj` a `obj.elementos()`.

### Pruebas

`prueba` no se ejecuta: `sentencia()` guarda `(nodo, entorno)` en `self.pruebas`. `ejecutar_pruebas()` corre cada una en un entorno hijo de donde fue declarada (ve las funciones del archivo) y devuelve `{nombre, ok, error}`. `ejecutar_afirma` evalúa por separado los dos lados de una comparación para poder decir *se esperaba 4 == 5*.

### Módulos

`importar()` resuelve la ruta relativa a `self.directorio`, ejecuta el archivo en los globales, lo marca en `self.importados` y cambia temporalmente `directorio` para que los imports anidados sean relativos a su propio archivo. Los errores de un módulo se reescriben con el nombre del archivo y la línea original, y señalan el `importa`.

### Protecciones

| Riesgo | Protección |
|---|---|
| Recursión infinita | `LIMITE_RECURSION = 300`, y el límite de Python se sube para que el de Coral salte primero |
| Ciclo infinito | `LIMITE_VUELTAS = 1_000_000` en `mientras` |
| Rango gigante | `LIMITE_RANGO = 1_000_000` elementos |
| Potencias enormes | `OverflowError` se traduce a error de Coral |
| Errores de Python dentro de nativas | `llamar_nativa` los traduce (`_explicar`) |

## 5. Pistas (`pistas.py`)

- `PALABRAS_INGLES`: palabra de otro lenguaje → palabra de Coral. Se usa en el parser (sentencias que empiezan con `if`...) y en el intérprete (variable no definida llamada `print`).
- `sugerir(nombre, candidatos)`: usa `difflib.get_close_matches` con un umbral de 0.72; se usa para variables, métodos de tipos, campos y métodos de clases, y claves de diccionario.

## 6. Playground (`playground/`)

`playground.js` descarga los `.py` de `coral/` (lista `MODULOS`) y los escribe en el sistema de archivos virtual de Pyodide; no hay copia del intérprete. **Si se agrega un módulo nuevo a `coral/`, hay que sumarlo a `MODULOS`.** `entrada()` usa `prompt()` del navegador y `ejemplos/util.coral` se copia a `/ejemplos` para que `importa` funcione. Pyodide 0.26 trae Python 3.12; el código debe seguir siendo compatible con 3.10 (lo comprueba la CI).

## Cómo agregar...

**Una función nativa:** agregar una tupla `(nombre, fn, (min_args, max_args))` en `Interprete._nativas`. Los errores `TypeError`/`ValueError` que lance se traducen solos. Documentarla en `docs/GUIA.md`.

**Un método de lista, texto o diccionario:** agregarlo al diccionario correspondiente en `_metodos_de`. Para llamar a una función de Coral desde el método se usa `f(fn, argumentos...)`.

**Un operador:** agregarlo al lexer (`SIMBOLOS_DOBLES` o `SIMBOLOS_SIMPLES`), a `PRECEDENCIA` en el parser y a `Interprete.operar`.

**Una sentencia:** palabra en `PALABRAS_CLAVE`, nodo en `ast.py`, método `_s_palabra` en el parser, `case` en `Interprete.sentencia`, test y guía.

**Una pista para otro lenguaje:** sumar la palabra a `PALABRAS_INGLES`.

Siempre: un test en `tests/test_coral.py` y, si es visible para quien programa, un ejemplo y una entrada en la guía.

## Pendientes e ideas

- Desestructuración (`var [a, b] = lista`) y parámetros con valor por defecto.
- Interfaces (`implementa`) para declarar contratos sin herencia.
- Un `importa` con alias (`importa "util.coral" como u`) para no ensuciar el ámbito global.
- Resaltado de sintaxis en el playground y una extensión para VS Code.
- Compilar a bytecode en vez de recorrer el árbol, si alguna vez el rendimiento importa.
