"""Tests de Coral, de abajo hacia arriba: lexer -> parser -> intérprete -> ejemplos.

Correr:  python -m pytest -q
"""

from pathlib import Path

import pytest

from coral import ErrorEjecucion, ErrorPrueba, ErrorSintaxis, ejecutar, ejecutar_pruebas
from coral import ast as A
from coral.lexer import tokenizar
from coral.parser import parsear

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos"


def salida(codigo: str) -> list[str]:
    return ejecutar(codigo)


# ---------- lexer ----------
def test_lexer_tokens_basicos():
    toks = tokenizar('var x = 3.5 # comentario\nimprimir("hola\\n")')
    tipos = [(t.tipo, t.valor) for t in toks]
    assert tipos[:4] == [("CLAVE", "var"), ("NOMBRE", "x"), ("SIMBOLO", "="), ("NUM", 3.5)]
    assert ("TEXTO", "hola\n") in tipos
    assert toks[4].linea == 2


def test_lexer_numeros_con_guion_bajo_y_simbolos_dobles():
    toks = tokenizar("1_000 <= 2 ** 3")
    assert [t.valor for t in toks[:-1]] == [1000, "<=", 2, "**", 3]


def test_lexer_texto_sin_cerrar():
    with pytest.raises(ErrorSintaxis, match="Texto sin cerrar"):
        tokenizar('imprimir("hola')


# ---------- parser ----------
def test_precedencia_y_asociatividad():
    expr = parsear("1 + 2 * 3 ** 2 ** 2")[0].expr
    assert isinstance(expr, A.Binaria) and expr.op == "+"
    potencia = expr.der.der
    assert potencia.op == "**" and potencia.der.op == "**"   # 3 ** (2 ** 2)


def test_operadores_logicos_tienen_menor_precedencia():
    expr = parsear("a < b y c o d")[0].expr
    assert isinstance(expr, A.Logica) and expr.op == "o"


def test_errores_de_sintaxis_con_posicion():
    with pytest.raises(ErrorSintaxis) as e:
        parsear("si x > 1 {\n  imprimir(x)\n")
    assert "Falta '}'" in e.value.mensaje
    with pytest.raises(ErrorSintaxis) as e:
        parsear("var = 5")
    assert e.value.linea == 1 and e.value.columna == 5
    with pytest.raises(ErrorSintaxis, match="Solo se puede asignar"):
        parsear("1 = 2")


# ---------- intérprete ----------
def test_aritmetica_y_textos():
    assert salida("imprimir(7 / 2, 8 / 2, 7 % 3, 2 ** 10, -3 + 1)") == ["3.5 4 1 1024 -2"]
    assert salida('imprimir("ab" * 3, "Hola " + "Coral", texto(5) + "!")') == ["ababab Hola Coral 5!"]


def test_comparaciones_y_logica_cortocircuito():
    assert salida("imprimir(1 == 1.0, 1 == verdadero, 'a' < 'b', no 0)") == ["verdadero falso verdadero verdadero"]
    # 'o' no evalúa el lado derecho si el izquierdo ya es verdadero
    assert salida("imprimir(verdadero o variable_que_no_existe)") == ["verdadero"]


def test_control_de_flujo():
    codigo = """
    var r = []
    para i en rango(10) {
      si i == 7 { rompe }
      si i % 2 == 0 { continua }
      r.agrega(i)
    }
    var n = 0
    mientras n < 3 { n += 1 }
    imprimir(r, n)
    """
    assert salida(codigo) == ["[1, 3, 5] 3"]


def test_ambitos_de_bloque():
    codigo = """
    var x = "global"
    si verdadero { var x = "local"; imprimir(x) }
    imprimir(x)
    """
    assert salida(codigo) == ["local", "global"]


def test_clausuras_y_funciones_de_orden_superior():
    codigo = """
    funcion sumador(n) => funcion (x) => x + n
    var mas10 = sumador(10)
    imprimir(mas10(5), [1, 2, 3].mapea(funcion (x) => x * x))
    """
    assert salida(codigo) == ["15 [1, 4, 9]"]


def test_listas_y_diccionarios():
    codigo = """
    var l = [3, 1, 2]
    l[0] = 10
    l[1] += 5
    var d = {nombre: "Ana", edad: 20}
    d["edad"] += 1
    imprimir(l, ordenar(l), largo(d), d.nombre, d["edad"], d.tiene("x"))
    """
    assert salida(codigo) == ['[10, 6, 2] [2, 6, 10] 2 Ana 21 falso']


def test_metodos_de_texto():
    assert salida('imprimir("a,b,c".divide(","), "Coral".mayusculas())') == ['["a", "b", "c"] CORAL']


@pytest.mark.parametrize("codigo, mensaje", [
    ("imprimir(desconocida)", "no está definida"),
    ("x = 3", "declárala primero"),
    ("var a = 1; var a = 2", "ya fue declarada"),
    ("imprimir(1 / 0)", "División por cero"),
    ("imprimir(1 + 'a')", "Usa texto()"),
    ("imprimir([1, 2][5])", "fuera de rango"),
    ("imprimir({a: 1}['b'])", "no existe"),
    ("var f = funcion (a) => a; f(1, 2)", "espera 1 argumentos"),
    ("var n = 5; n()", "no se puede llamar"),
    ("funcion r(n) => r(n + 1); r(0)", "Recursión demasiado profunda"),
    ("imprimir(largo(1, 2))", "espera 1 argumentos"),
    ("imprimir([1].vuela())", "no tiene el método"),
])
def test_errores_de_ejecucion(codigo, mensaje):
    with pytest.raises(ErrorEjecucion, match=mensaje):
        salida(codigo)


def test_error_con_contexto_senala_la_columna():
    codigo = "var x = 1\nimprimir(x + 'a')"
    with pytest.raises(ErrorEjecucion) as e:
        salida(codigo)
    texto = e.value.con_contexto(codigo)
    assert "línea 2" in texto
    assert texto.splitlines()[-1].index("^") == texto.splitlines()[-2].index("+")


# =====================================================================
# Coral 2: características nuevas
# =====================================================================
def test_plantillas_de_texto():
    assert salida('var n = "Ana"; imprimir("Hola {n}, tienes {2 * 10} años y {[1, 2].largo()} gatos")') == \
        ["Hola Ana, tienes 20 años y 2 gatos"]
    assert salida(r'imprimir("llaves literales: \{x\}")') == ["llaves literales: {x}"]
    assert salida("imprimir('anidado: {\"a\".mayusculas()}')") == ["anidado: A"]


def test_errores_en_plantillas():
    with pytest.raises(ErrorSintaxis, match="comillas distintas"):
        parsear('imprimir("x {"a"}")')
    with pytest.raises(ErrorSintaxis, match="Interpolación vacía"):
        parsear('imprimir("x {}")')
    with pytest.raises(ErrorSintaxis, match="En la interpolación"):
        parsear('imprimir("x {1 +}")')


def test_constantes_no_se_reasignan():
    assert salida("const PI = 3.14; imprimir(PI)") == ["3.14"]
    with pytest.raises(ErrorEjecucion, match="es una constante"):
        salida("const PI = 3.14; PI = 3")


def test_rangos_inclusivos():
    assert salida("imprimir(1..5, 3..1, largo(0..99))") == ["[1, 2, 3, 4, 5] [3, 2, 1] 100"]
    with pytest.raises(ErrorEjecucion, match="deben ser enteros"):
        salida("imprimir(1..2.5)")


def test_tuberias():
    codigo = "funcion doble(x) => x * 2\nfuncion suma(a, b) => a + b\nimprimir(3 |> doble |> suma(1), 1..4 |> largo)"
    assert salida(codigo) == ["7 4"]
    expr = parsear("x |> f(1)")[0].expr
    assert isinstance(expr, A.Llamada) and len(expr.args) == 2   # se convierte en f(x, 1)


def test_clases_herencia_y_padre():
    codigo = """
    clase Animal {
        funcion iniciar(nombre) { yo.nombre = nombre }
        funcion habla() => "..."
        funcion presenta() => "{yo.nombre} dice {yo.habla()}"
    }
    clase Perro hereda Animal {
        funcion habla() => "guau"
        funcion presenta() => padre.presenta() + "!"
    }
    var p = Perro("Toby")
    imprimir(p.presenta(), p es Animal, p es Perro, Animal("x") es Perro, tipo(p))
    imprimir(p)
    """
    assert salida(codigo) == ["Toby dice guau! verdadero verdadero falso Perro", '<Perro nombre="Toby">']


def test_como_texto_personaliza_la_impresion():
    codigo = """
    clase Punto {
        funcion iniciar(x, z) { yo.x = x; yo.z = z }
        funcion como_texto() => "({yo.x}, {yo.z})"
    }
    imprimir(Punto(1, 2), [Punto(0, 0)])
    """
    assert salida(codigo) == ["(1, 2) [(0, 0)]"]


def test_errores_de_clases_con_sugerencia():
    base = "clase C { funcion iniciar() { yo.valor = 1 } funcion calcula() => 2 }\n"
    with pytest.raises(ErrorEjecucion, match="¿Quisiste decir 'calcula'"):
        salida(base + "C().calcla()")
    with pytest.raises(ErrorEjecucion, match="no recibe argumentos"):
        salida("clase V { funcion f() => 1 }\nV(1)")
    with pytest.raises(ErrorEjecucion, match="'yo' solo existe"):
        salida("imprimir(yo)")
    with pytest.raises(ErrorSintaxis, match="solo van métodos"):
        parsear("clase X { var a = 1 }")


def test_intenta_captura_lanza():
    codigo = """
    intenta { lanza {codigo: 7} } captura e { imprimir(e.codigo) }
    intenta { imprimir(1 / 0) } captura e { imprimir("capturado:", e) }
    intenta { imprimir("sin error") } captura { imprimir("no pasa") }
    """
    assert salida(codigo) == ["7", "capturado: División por cero", "sin error"]
    with pytest.raises(ErrorEjecucion, match="Error no capturado: boom"):
        salida('lanza "boom"')


def test_segun_caso_otro():
    codigo = """
    funcion f(x) {
        segun x {
            caso 1, 2 { retorna "chico" }
            caso 3..9 { retorna "medio" }
            caso "hola" { retorna "texto" }
            otro { retorna "otro" }
        }
    }
    imprimir(f(2), f(5), f("hola"), f(100), f(verdadero))
    """
    assert salida(codigo) == ["chico medio texto otro otro"]


def test_pruebas_integradas():
    codigo = """
    funcion doble(x) => x * 2
    prueba "pasa" { afirma doble(2) == 4 }
    prueba "falla" { afirma doble(2) == 5, "doble está mal" }
    prueba "lanza" { lanza "ups" }
    imprimir("programa")
    """
    out, resultados = ejecutar_pruebas(codigo)
    assert out == ["programa"]                     # las pruebas no corren al ejecutar
    assert [r["ok"] for r in resultados] == [True, False, False]
    assert "doble está mal (se esperaba 4 == 5)" in resultados[1]["error"].mensaje
    assert "Error no capturado: ups" in resultados[2]["error"].mensaje
    with pytest.raises(ErrorPrueba, match="La condición resultó falsa"):
        salida("afirma falso")


def test_importa_carga_una_sola_vez(tmp_path):
    (tmp_path / "mod.coral").write_text('imprimir("cargado")\nfuncion saluda() => "hola"\n', encoding="utf-8")
    codigo = 'importa "mod.coral"\nimporta "mod.coral"\nimprimir(saluda())'
    assert ejecutar(codigo, directorio=str(tmp_path)) == ["cargado", "hola"]
    with pytest.raises(ErrorEjecucion, match="No se encontró"):
        ejecutar('importa "no_existe.coral"', directorio=str(tmp_path))


def test_metodos_nuevos_de_colecciones():
    codigo = """
    var l = [5, 3, 8, 1]
    imprimir(l.reduce(funcion (a, b) => a + b), l.busca(funcion (x) => x > 4), l.cuenta(funcion (x) => x > 2))
    imprimir(l.ordena(), l.ordena(funcion (x) => -x), l.primero(), l.ultimo(), l.rebanada(1, 3), l.indice(8))
    var d = {a: 1}
    imprimir(d.obtiene("b", 0), d.borra("a"), d)
    imprimir("  hola ".recorta(), "coral".empieza_con("co"), "abc".divide(""), "ja".repite(3))
    """
    assert salida(codigo) == [
        "17 5 3",
        "[1, 3, 5, 8] [8, 5, 3, 1] 5 1 [3, 8] 2",
        "0 1 {}",
        'hola verdadero ["a", "b", "c"] jajaja',
    ]


def test_entrada_y_aleatorio_inyectables():
    assert ejecutar('imprimir("Hola", entrada("¿Nombre? "))', entrada=lambda _: "Ana") == ["Hola Ana"]
    codigo = "imprimir(aleatorio(1, 100), aleatorio(1, 100))"
    assert ejecutar(codigo, semilla=42) == ejecutar(codigo, semilla=42)


@pytest.mark.parametrize("codigo, pista", [
    ("if x > 1 { }", "'si' en lugar de 'if'"),
    ("print(1)", "'imprimir' en lugar de 'print'"),
    ("var a = verdadero && falso", "'y' en lugar de '&&'"),
    ("var a = verdadero || falso", "'o' en lugar de '||'"),
    ("while verdadero { }", "'mientras' en lugar de 'while'"),
    ("return 5", "'retorna' en lugar de 'return'"),
    ("imprimir(True)", "'verdadero' en lugar de 'True'"),
])
def test_pistas_para_quien_viene_de_otro_lenguaje(codigo, pista):
    with pytest.raises((ErrorSintaxis, ErrorEjecucion), match=pista):
        salida(codigo)


def test_sugerencia_por_error_de_tipeo():
    with pytest.raises(ErrorEjecucion, match="¿Quisiste decir 'imprimir'"):
        salida("imprmir(1)")
    with pytest.raises(ErrorEjecucion, match="¿Quisiste decir 'mayusculas'"):
        salida('"a".mayuscula()')


def test_retorna_y_rompe_fuera_de_lugar():
    with pytest.raises(ErrorEjecucion, match="dentro de una función"):
        salida("retorna 1")
    with pytest.raises(ErrorEjecucion, match="dentro de un ciclo"):
        salida("rompe")


# =====================================================================
# Programación orientada a objetos
# =====================================================================
FIGURAS = """
clase Figura {
    abstracta funcion area()
    funcion menor_que(f) => yo.area() < f.area()
}
clase Cuadrado hereda Figura {
    const LADOS = 4
    funcion iniciar(l) { yo.l = l }
    funcion area() => yo.l * yo.l
    estatico funcion unitario() => Cuadrado(1)
}
"""


def test_clase_abstracta_no_se_instancia():
    with pytest.raises(ErrorEjecucion, match="es abstracta y le falta implementar 'area'"):
        salida(FIGURAS + "Figura()")
    with pytest.raises(ErrorEjecucion, match="le falta implementar 'area'"):
        salida(FIGURAS + "clase Mala hereda Figura { funcion otra_cosa() => 1 }\nMala()")
    assert salida(FIGURAS + "imprimir(Cuadrado(3).area(), Cuadrado(3) es Figura)") == ["9 verdadero"]


def test_metodos_estaticos_y_constantes_de_clase():
    assert salida(FIGURAS + "imprimir(Cuadrado.unitario().area(), Cuadrado.LADOS, Cuadrado(2).LADOS)") == ["1 4 4"]
    with pytest.raises(ErrorEjecucion, match="es un método de instancia"):
        salida(FIGURAS + "Cuadrado.area()")
    with pytest.raises(ErrorEjecucion, match="¿Quisiste decir 'LADOS'"):
        salida(FIGURAS + "Cuadrado.LADO")
    with pytest.raises(ErrorEjecucion, match="no se pueden reasignar"):
        salida(FIGURAS + "Cuadrado.LADOS = 5")


def test_encapsulamiento_con_guion_bajo():
    codigo = """
    clase Caja {
        funcion iniciar(v) { yo._v = v }
        funcion valor() => yo._v
        funcion igual_a(c) => yo._v == c._v
    }
    imprimir(Caja(3).valor(), Caja(3) == Caja(3), Caja(3) != Caja(4), Caja(1))
    """
    assert salida(codigo) == ["3 verdadero verdadero <Caja>"]
    with pytest.raises(ErrorEjecucion, match="'_v' es privado de Caja"):
        salida("clase Caja { funcion iniciar() { yo._v = 1 } }\nimprimir(Caja()._v)")
    with pytest.raises(ErrorEjecucion, match="es privado"):
        salida("clase Caja { funcion iniciar() { yo._v = 1 } }\nvar c = Caja()\nc._v = 2")


def test_sobrecarga_de_operadores_y_orden():
    codigo = """
    clase Dinero {
        funcion iniciar(c) { yo.c = c }
        funcion mas(d) => Dinero(yo.c + d.c)
        funcion por(k) => Dinero(yo.c * k)
        funcion igual_a(d) => d es Dinero y yo.c == d.c
        funcion menor_que(d) => yo.c < d.c
        funcion como_texto() => "${yo.c}"
    }
    var a = Dinero(5)
    imprimir(a + Dinero(2), a * 3, a == Dinero(5), a == 5, a < Dinero(9), a >= Dinero(9), a <= Dinero(5))
    imprimir(ordenar([Dinero(3), Dinero(1), Dinero(2)]), maximo([Dinero(3), Dinero(8)]))
    """
    assert salida(codigo) == ["$7 $15 verdadero falso verdadero falso verdadero", "[$1, $2, $3] $8"]
    with pytest.raises(ErrorEjecucion, match="define el método menos"):
        salida("clase X { }\nX() - X()")


def test_objetos_recorribles_y_largo():
    codigo = """
    clase Rango3 {
        funcion elementos() => [1, 2, 3]
        funcion largo() => 3
    }
    var t = 0
    para n en Rango3() { t += n }
    imprimir(t, largo(Rango3()))
    """
    assert salida(codigo) == ["6 3"]
    with pytest.raises(ErrorEjecucion, match="debe definir elementos"):
        salida("clase X { }\npara i en X() { }")


def test_pistas_de_poo_de_otros_lenguajes():
    with pytest.raises(ErrorEjecucion, match="'como_texto' en lugar de '__str__'"):
        salida("clase X { }\nX().__str__()")
    with pytest.raises(ErrorSintaxis, match="solo van métodos"):
        parsear("clase X { var a = 1 }")


# =====================================================================
# Ejemplos: todos corren y sus pruebas pasan
# =====================================================================
@pytest.mark.parametrize("archivo", sorted(EJEMPLOS.glob("*.coral")), ids=lambda p: p.name)
def test_ejemplos_corren_y_sus_pruebas_pasan(archivo):
    _, resultados = ejecutar_pruebas(archivo.read_text(encoding="utf-8"), directorio=str(EJEMPLOS))
    fallidas = [(r["nombre"], str(r["error"])) for r in resultados if not r["ok"]]
    assert not fallidas
