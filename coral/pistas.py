"""Pistas didácticas: lo que hace que los errores de Coral *enseñen*.

Dos tipos de ayuda:

1. **Palabras de otros lenguajes.** Quien viene de Python o JavaScript escribe
   ``if``, ``print`` o ``&&`` por costumbre. En vez de un error genérico, Coral
   le dice la palabra equivalente en español.
2. **Errores de tipeo.** Si un nombre no existe pero se parece a uno que sí
   existe, se sugiere: "¿Quisiste decir 'imprimir'?".
"""

from difflib import get_close_matches

# Palabra de otro lenguaje -> forma correcta en Coral.
PALABRAS_INGLES = {
    "if": "si", "else": "sino", "elif": "sino si", "elsif": "sino si",
    "while": "mientras", "for": "para", "in": "en", "foreach": "para",
    "function": "funcion", "def": "funcion", "fn": "funcion", "func": "funcion", "lambda": "funcion",
    "return": "retorna", "break": "rompe", "continue": "continua",
    "true": "verdadero", "True": "verdadero", "false": "falso", "False": "falso",
    "null": "nulo", "None": "nulo", "nil": "nulo", "undefined": "nulo",
    "and": "y", "or": "o", "not": "no",
    "let": "var",
    "class": "clase", "extends": "hereda", "self": "yo", "this": "yo", "super": "padre",
    "try": "intenta", "catch": "captura", "except": "captura", "throw": "lanza", "raise": "lanza",
    "switch": "segun", "match": "segun", "case": "caso", "default": "otro",
    "import": "importa", "require": "importa", "assert": "afirma", "test": "prueba",
    "print": "imprimir", "println": "imprimir", "console": "imprimir", "len": "largo",
    "range": "rango", "str": "texto", "int": "numero", "float": "numero", "input": "entrada",
    "type": "tipo", "sum": "suma", "sorted": "ordenar", "max": "maximo", "min": "minimo",
    "abs": "absoluto", "round": "redondear", "sqrt": "raiz",
}

# Operadores de otros lenguajes que el lexer no reconoce.
OPERADORES_INGLES = {"&&": "y", "||": "o", "!": "no"}


def pista_palabra(nombre: str) -> str | None:
    """Devuelve un consejo si ``nombre`` es una palabra típica de otro lenguaje."""
    equivalente = PALABRAS_INGLES.get(nombre)
    if equivalente is None:
        return None
    return f"En Coral se escribe '{equivalente}' en lugar de '{nombre}'"


def sugerir(nombre: str, candidatos) -> str:
    """Texto ' ¿Quisiste decir X?' si hay un candidato parecido; si no, cadena vacía."""
    parecidos = get_close_matches(nombre, list(candidatos), n=1, cutoff=0.72)
    return f" ¿Quisiste decir '{parecidos[0]}'?" if parecidos else ""
