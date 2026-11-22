"""Línea de comandos de Coral.

Uso:
    python -m coral                          # REPL interactivo
    python -m coral programa.coral           # ejecuta un archivo
    python -m coral --pruebas programa.coral # ejecuta sus bloques 'prueba' y reporta
    python -m coral --version
"""

import sys
from pathlib import Path

from . import __version__
from .errores import ErrorCoral
from .interprete import Interprete


def leer(ruta: Path) -> str:
    # utf-8-sig tolera el BOM que agregan algunos editores de Windows.
    return ruta.read_text(encoding="utf-8-sig")


def ejecutar_archivo(ruta: Path) -> int:
    codigo = leer(ruta)
    try:
        Interprete(directorio=str(ruta.resolve().parent)).ejecutar(codigo)
        return 0
    except ErrorCoral as e:
        print(e.con_contexto(codigo), file=sys.stderr)
        return 1


def probar_archivo(ruta: Path) -> int:
    """Corre las pruebas del archivo. Código de salida 1 si alguna falla (útil en CI)."""
    codigo = leer(ruta)
    interp = Interprete(salida=lambda _: None, directorio=str(ruta.resolve().parent))
    try:
        interp.ejecutar(codigo)
    except ErrorCoral as e:
        print(e.con_contexto(codigo), file=sys.stderr)
        return 1
    resultados = interp.ejecutar_pruebas()
    if not resultados:
        print(f"{ruta.name}: no tiene bloques 'prueba'")
        return 0
    for r in resultados:
        if r["ok"]:
            print(f"  ✓ {r['nombre']}")
        else:
            print(f"  ✗ {r['nombre']}")
            print("    " + r["error"].con_contexto(codigo).replace("\n", "\n    "))
    fallidas = sum(not r["ok"] for r in resultados)
    print(f"\n{len(resultados) - fallidas} de {len(resultados)} pruebas pasaron")
    return 1 if fallidas else 0


def repl() -> None:
    print(f"Coral {__version__} · escribe 'salir' para terminar. Los bloques terminan cuando cierras todas las llaves.")
    interp = Interprete()
    buffer = ""
    while True:
        try:
            linea = input("... " if buffer else "coral> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not buffer and linea.strip() == "salir":
            return
        buffer += linea + "\n"
        if buffer.count("{") > buffer.count("}"):       # bloque sin cerrar: seguir leyendo
            continue
        codigo, buffer = buffer, ""
        try:
            r = interp.ejecutar(codigo)
            if r is not None:
                print(interp.mostrar(r))
        except ErrorCoral as e:
            print(e.con_contexto(codigo))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args[:1] == ["--version"]:
        print(f"Coral {__version__}")
    elif args[:1] == ["--pruebas"] and len(args) == 2:
        sys.exit(probar_archivo(Path(args[1])))
    elif len(args) == 1 and not args[0].startswith("--"):
        sys.exit(ejecutar_archivo(Path(args[0])))
    elif not args:
        repl()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
