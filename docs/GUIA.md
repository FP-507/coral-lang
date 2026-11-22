# Guía del lenguaje Coral

Referencia completa de Coral 2. Todos los fragmentos se pueden pegar en el [playground](https://fp-507.github.io/coral-lang/playground/) o en un archivo `.coral`.

- [Lo básico](#lo-básico)
- [Tipos de datos](#tipos-de-datos)
- [Variables y constantes](#variables-y-constantes)
- [Operadores](#operadores)
- [Textos y plantillas](#textos-y-plantillas)
- [Condiciones](#condiciones)
- [Ciclos y rangos](#ciclos-y-rangos)
- [Funciones](#funciones)
- [Tuberías](#tuberías)
- [Clases](#clases) · [POO completa](#programación-orientada-a-objetos-completa)
- [Errores](#errores)
- [Pruebas](#pruebas)
- [Módulos](#módulos)
- [Funciones nativas](#funciones-nativas)
- [Métodos](#métodos)
- [Palabras reservadas](#palabras-reservadas)
- [Si vienes de Python o JavaScript](#si-vienes-de-python-o-javascript)

---

## Lo básico

```coral
# Los comentarios empiezan con numeral.
imprimir("Hola, mundo")
var x = 10; var y_total = 20   # el punto y coma solo hace falta para separar en una línea
```

- Los bloques van entre llaves `{ }`. La indentación no importa, pero se recomiendan 4 espacios.
- Los nombres admiten letras, números y `_`, y no pueden empezar con un número.
- Un archivo se ejecuta de arriba hacia abajo.

## Tipos de datos

| Tipo | Ejemplos | `tipo(x)` |
|---|---|---|
| número | `42`, `3.14`, `1_000_000` | `"numero"` |
| texto | `"hola"`, `'hola'` | `"texto"` |
| booleano | `verdadero`, `falso` | `"booleano"` |
| nulo | `nulo` | `"nulo"` |
| lista | `[1, "dos", [3]]` | `"lista"` |
| diccionario | `{nombre: "Ana", "edad": 20}` | `"diccionario"` |
| función | `funcion (x) => x` | `"funcion"` |
| clase | `clase Punto { ... }` | `"clase"` |
| instancia | `Punto(1, 2)` | el nombre de su clase: `"Punto"` |

**Verdad y falsedad.** Son falsos `falso`, `nulo`, `0`, `""`, `[]` y `{}`. Todo lo demás es verdadero.

**División.** `7 / 2` da `3.5`; `8 / 2` da `4` (si el resultado es exacto, queda entero).

## Variables y constantes

```coral
var edad = 20
edad += 1            # también -=
const IVA = 0.07     # IVA = 0.1 daría error: es una constante
```

- Hay que declarar con `var` antes de asignar; asignar a un nombre no declarado es un error.
- Cada bloque `{ }` crea un ámbito: una `var` declarada adentro no existe afuera.
- No se puede declarar dos veces el mismo nombre en el mismo bloque.
- `const` impide reasignar el nombre, pero una lista constante sí se puede modificar (`LISTA.agrega(1)`).
- Se pueden redefinir las nativas: `funcion suma(a, b) => a + b` es válido.

## Operadores

De menor a mayor precedencia:

| Operadores | Significado |
|---|---|
| `\|>` | tubería |
| `o` | o lógico (cortocircuito) |
| `y` | y lógico (cortocircuito) |
| `==` `!=` `es` | igualdad y tipo |
| `<` `<=` `>` `>=` | comparación (números o textos) |
| `..` | rango inclusivo |
| `+` `-` | suma y resta; `+` también une textos y listas |
| `*` `/` `%` | producto, división, resto; `"ab" * 3` repite |
| `**` | potencia (asociativa a la derecha) |
| `-x` `no x` | prefijos |

- `==` respeta el tipo: `1 == verdadero` es `falso`, `1 == 1.0` es `verdadero`.
- `y` / `o` devuelven uno de sus operandos: `nombre o "anónimo"` da un valor por defecto.
- Sumar texto y número es un error a propósito: usa una plantilla o `texto(n)`.

## Textos y plantillas

```coral
var nombre = "Ana"
imprimir("Hola {nombre}, el doble de 21 es {21 * 2}")
imprimir("Llaves literales: \{ así \}")
imprimir('Dentro de \{…\} usa las otras comillas: {"x".mayusculas()}')
```

Secuencias de escape: `\n` (salto de línea), `\t`, `\\`, `\"`, `\'`, `\{`, `\}`.

## Condiciones

```coral
si nota >= 9 {
    imprimir("excelente")
} sino si nota >= 7 {
    imprimir("aprobado")
} sino {
    imprimir("a repasar")
}

segun dia {
    caso "sábado", "domingo" { imprimir("fin de semana") }
    caso "lunes" { imprimir("a empezar") }
    otro { imprimir("día de semana") }
}

segun nota {
    caso 9..10 { imprimir("A") }   # un rango compara contra cada uno de sus elementos
    caso 7..8 { imprimir("B") }
    otro { imprimir("C") }
}
```

`segun` usa la misma igualdad que `==`. Solo se ejecuta el primer `caso` que coincide; no hace falta `rompe`.

## Ciclos y rangos

```coral
para i en 1..5 { imprimir(i) }          # 1 2 3 4 5 (inclusivo)
para i en 5..1 { imprimir(i) }          # 5 4 3 2 1
para i en rango(0, 10, 2) { imprimir(i) }  # 0 2 4 6 8 (rango() excluye el final, como Python)
para letra en "hola" { imprimir(letra) }  # recorre letras
para clave en {a: 1, b: 2} { imprimir(clave) }  # recorre claves

var n = 0
mientras verdadero {
    n += 1
    si n % 2 == 0 { continua }
    si n > 7 { rompe }
    imprimir(n)
}
```

Un `mientras` que supera un millón de vueltas se detiene con un error (protege de ciclos infinitos).

## Funciones

```coral
funcion saludar(nombre) {
    retorna "Hola {nombre}"
}

funcion doble(x) => x * 2               # forma corta: retorna la expresión
var triple = funcion (x) => x * 3       # anónima, guardada en una variable

# Clausura: la función interna recuerda 'cuenta'
funcion contador() {
    var cuenta = 0
    retorna funcion () {
        cuenta += 1
        retorna cuenta
    }
}
var c = contador()
c(); c()
imprimir(c())                           # 3
```

- Una función sin `retorna` devuelve `nulo`.
- El número de argumentos debe coincidir exactamente.
- La recursión tiene un límite de 300 llamadas anidadas, con un mensaje que sugiere revisar el caso base.

## Tuberías

`x |> f` es `f(x)` y `x |> f(a, b)` es `f(x, a, b)`: el valor de la izquierda entra como **primer argumento**.

```coral
funcion pares(lista) => lista.filtra(funcion (n) => n % 2 == 0)
funcion tomar(lista, n) => lista.rebanada(0, n)

imprimir(1..100 |> pares |> tomar(3))   # [2, 4, 6]

# También con funciones anónimas, en varias líneas:
var resultado = datos
    |> funcion (d) => d.filtra(funcion (x) => x > 0)
    |> ordenar
```

`|>` tiene la precedencia más baja: `a + 1 |> f` es `f(a + 1)`.

## Clases

```coral
clase Animal {
    funcion iniciar(nombre) {         # constructor: se llama al hacer Animal("...")
        yo.nombre = nombre            # 'yo' es la instancia (como self / this)
    }
    funcion habla() => "..."
    funcion presenta() => "{yo.nombre} dice {yo.habla()}"
    funcion como_texto() => "<{yo.nombre}>"   # cómo se imprime
}

clase Perro hereda Animal {
    funcion iniciar(nombre, raza) {
        padre.iniciar(nombre)         # llama al método de la clase padre
        yo.raza = raza
    }
    funcion habla() => "guau"
}

var p = Perro("Toby", "mestizo")
imprimir(p.presenta())                # Toby dice guau
imprimir(p es Perro, p es Animal)     # verdadero verdadero
imprimir(tipo(p), p es "Perro")       # Perro verdadero
imprimir(p)                           # <Toby>
```

- Dentro de `clase { }` solo van métodos (`funcion nombre(...)`).
- Los campos se crean al asignarlos: `yo.x = 1`. No se declaran.
- Sin `como_texto`, una instancia se imprime como `<Perro nombre="Toby" raza="mestizo">`.
- Los métodos se pueden pasar como valores: `botones.cada(yo.manejar)` mantiene su `yo`.
- `x es "numero"` también funciona con los tipos básicos.

### Programación orientada a objetos completa

Coral cubre los cuatro pilares de la POO (abstracción, encapsulamiento, herencia y polimorfismo), además de miembros de clase, sobrecarga de operadores y objetos recorribles. El ejemplo completo está en [`ejemplos/poo.coral`](../ejemplos/poo.coral).

**Clases abstractas.** Un método `abstracta funcion` no tiene cuerpo. Una clase con métodos abstractos sin implementar no se puede instanciar.

```coral
clase Figura {
    abstracta funcion area()
    funcion describe() => "área {yo.area()}"
}
clase Cuadrado hereda Figura {
    funcion iniciar(lado) { yo.lado = lado }
    funcion area() => yo.lado ** 2
}
imprimir(Cuadrado(3).describe())   # área 9
# Figura()  da error: es abstracta y le falta implementar 'area'
```

**Encapsulamiento.** Los campos y métodos que empiezan con `_` son privados: solo se usan dentro de los métodos de la clase (con `yo._x`, o con `otra._x` si `otra` es de la misma clase). Tampoco aparecen al imprimir el objeto.

```coral
clase Cuenta {
    funcion iniciar() { yo._saldo = 0 }
    funcion deposita(m) { yo._validar(m); yo._saldo += m }
    funcion saldo() => yo._saldo
    funcion _validar(m) { si m <= 0 { lanza "monto inválido" } }
}
var c = Cuenta()
c.deposita(50)
imprimir(c.saldo())      # 50
# c._saldo  da error: '_saldo' es privado de Cuenta
```

**Miembros de clase.** `const` dentro de la clase define una constante y `estatico funcion` un método que se llama sobre la clase. Ambos se heredan y también se leen desde una instancia.

```coral
clase Temperatura {
    const CERO_ABSOLUTO = -273.15
    funcion iniciar(c) { yo.c = c }
    estatico funcion desde_fahrenheit(f) => Temperatura((f - 32) * 5 / 9)
}
imprimir(Temperatura.CERO_ABSOLUTO, Temperatura.desde_fahrenheit(212).c)   # -273.15 100
```

**Sobrecarga de operadores.** Si el objeto de la izquierda define el método, el operador lo usa:

| Operador | Método | Operador | Método |
|---|---|---|---|
| `a + b` | `mas(b)` | `a == b`, `a != b` | `igual_a(b)` (si no existe: misma instancia) |
| `a - b` | `menos(b)` | `a < b`, `<=`, `>`, `>=` | `menor_que(b)` (con `igual_a`) |
| `a * b` | `por(b)` | `largo(a)` | `largo()` |
| `a / b` | `entre(b)` | `para x en a` | `elementos()` (devuelve una lista) |
| `a % b` | `modulo(b)` | `imprimir(a)`, `"{a}"` | `como_texto()` |
| `a ** b` | `potencia(b)` | `ordenar`, `minimo`, `maximo` | `menor_que(b)` |

```coral
clase Vector {
    funcion iniciar(x, z) { yo.x = x; yo.z = z }
    funcion mas(v) => Vector(yo.x + v.x, yo.z + v.z)
    funcion igual_a(v) => v es Vector y yo.x == v.x y yo.z == v.z
    funcion como_texto() => "({yo.x}, {yo.z})"
}
imprimir(Vector(1, 2) + Vector(3, 4))           # (4, 6)
imprimir(Vector(1, 2) == Vector(1, 2))          # verdadero
```

Ojo: `otro`, `y`, `o`, `en` y `es` son palabras reservadas; no sirven como nombre de parámetro.

## Errores

```coral
funcion dividir(a, b) {
    si b == 0 { lanza "No se puede dividir entre cero" }
    retorna a / b
}

intenta {
    dividir(1, 0)
} captura e {
    imprimir("Falló:", e)
}
```

- `lanza` acepta **cualquier valor**: texto, número, diccionario (`lanza {codigo: 404, mensaje: "..."}`) o una instancia.
- `captura` también atrapa los errores del propio lenguaje (índice fuera de rango, división por cero...). En ese caso `e` es el texto del mensaje.
- El nombre de la variable es opcional: `intenta { ... } captura { ... }`.
- Un `lanza` que nadie captura detiene el programa con `Error no capturado: ...`.

## Pruebas

```coral
funcion factorial(n) {
    si n <= 1 { retorna 1 }
    retorna n * factorial(n - 1)
}

prueba "factorial" {
    afirma factorial(0) == 1
    afirma factorial(5) == 120, "5! debería ser 120"
}
```

```bash
python -m coral --pruebas archivo.coral
```

```
  ✓ factorial
1 de 1 pruebas pasaron
```

- Los bloques `prueba` **no** se ejecutan al correr el archivo normalmente; solo con `--pruebas` (o con el botón *Pruebas* del playground).
- Si `afirma` compara dos valores y falla, el mensaje muestra ambos: `se esperaba 6 == 120`.
- Con `--pruebas`, el código de salida es 1 si alguna prueba falla (sirve para CI).
- `afirma` fuera de una prueba también funciona: detiene el programa si la condición es falsa.

## Módulos

```coral
# util.coral
const PI = 3.14159
funcion area(r) => PI * r ** 2
```

```coral
# programa.coral
importa "util.coral"
imprimir(area(2))
```

- La ruta es relativa al archivo que importa.
- Cada archivo se carga una sola vez aunque se importe varias veces.
- Lo definido en el módulo queda en el ámbito global.

## Funciones nativas

| Función | Descripción |
|---|---|
| `imprimir(a, b, ...)` | Muestra los valores separados por espacio |
| `entrada(mensaje)` | Pide un texto al usuario |
| `largo(x)` | Largo de texto, lista o diccionario |
| `rango(fin)` / `rango(ini, fin, paso)` | Lista de números (excluye `fin`) |
| `texto(x)` / `numero(x)` | Conversión |
| `tipo(x)` | Nombre del tipo |
| `suma(lista)`, `minimo(...)`, `maximo(...)` | Agregados (`minimo` y `maximo` aceptan una lista o varios valores) |
| `ordenar(lista)` | Copia ordenada |
| `raiz`, `absoluto`, `piso`, `techo`, `redondear(x, decimales)` | Matemática |
| `aleatorio()` / `aleatorio(a, b)` | Decimal entre 0 y 1, o entero entre a y b (incluidos) |
| `tiempo()` | Segundos desde 1970 (para medir duraciones) |

## Métodos

**Listas:** `agrega(x)`, `saca(i?)`, `contiene(x)`, `indice(x)` (−1 si no está), `une(sep)`, `invierte()`, `mapea(f)`, `filtra(f)`, `reduce(f, inicial?)`, `cada(f)`, `busca(f)` (primer elemento que cumple, o `nulo`), `cuenta(f o valor)`, `ordena(f?)` (por clave), `primero()`, `ultimo()`, `rebanada(a, b?)`, `largo()`.

**Textos:** `mayusculas()`, `minusculas()`, `divide(sep?)` (sin argumento separa por espacios; con `""` en letras), `contiene(x)`, `reemplaza(a, b)`, `recorta()`, `empieza_con(x)`, `termina_con(x)`, `indice(x)`, `rebanada(a, b?)`, `repite(n)`, `largo()`.

**Diccionarios:** `claves()`, `valores()`, `pares()`, `tiene(k)`, `obtiene(k, defecto?)`, `borra(k)`, `largo()`. Las claves que son nombres válidos también se leen como `d.clave`.

`invierte`, `ordena`, `mapea`, `filtra` y `rebanada` devuelven una lista **nueva**; `agrega`, `saca` y `borra` modifican la original.

## Palabras reservadas

`var const funcion retorna si sino mientras para en verdadero falso nulo y o no es rompe continua clase hereda yo padre estatico abstracta intenta captura lanza segun caso otro prueba afirma importa`

No se pueden usar como nombres. Cuidado con `y`, `o`, `en` y `otro`: `funcion punto(x, y)` da error; usa otro nombre.

## Si vienes de Python o JavaScript

| Python / JS | Coral |
|---|---|
| `if` / `elif` / `else` | `si` / `sino si` / `sino` |
| `while`, `for x in` | `mientras`, `para x en` |
| `def` / `function` / `lambda` | `funcion` |
| `return`, `break`, `continue` | `retorna`, `rompe`, `continua` |
| `True`, `False`, `None` / `null` | `verdadero`, `falso`, `nulo` |
| `and`, `or`, `not` / `&&`, `\|\|`, `!` | `y`, `o`, `no` |
| `class A(B)` / `class A extends B` | `clase A hereda B` |
| `self` / `this`, `super()` | `yo`, `padre` |
| `__init__` / `constructor` | `iniciar` |
| `@staticmethod` / `static` | `estatico funcion` |
| `ABC` + `@abstractmethod` / `abstract` | `abstracta funcion` |
| `self._x` / `#x` / `private` | `yo._x` (privado de verdad) |
| `__add__`, `__eq__`, `__lt__`, `__len__`, `__iter__` | `mas`, `igual_a`, `menor_que`, `largo`, `elementos` |
| `__str__` / `toString` | `como_texto` |
| `try` / `except` / `raise` | `intenta` / `captura` / `lanza` |
| `match` / `switch` | `segun` / `caso` / `otro` |
| `isinstance(x, A)` | `x es A` |
| `f"Hola {x}"` / `` `Hola ${x}` `` | `"Hola {x}"` |
| `print`, `len`, `input` | `imprimir`, `largo`, `entrada` |

Si escribes la palabra de Python o JavaScript por costumbre, Coral te dice la equivalente.
