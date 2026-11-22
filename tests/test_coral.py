from pathlib import Path

import pytest

from coral import ErrorEjecucion, ErrorSintaxis, ejecutar
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


@pytest.mark.parametrize("archivo", sorted(EJEMPLOS.glob("*.coral")), ids=lambda p: p.name)
def test_ejemplos_corren_sin_errores(archivo):
    assert salida(archivo.read_text(encoding="utf-8"))
