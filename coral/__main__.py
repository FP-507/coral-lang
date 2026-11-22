"""Uso:
    python -m coral                 # REPL interactivo
    python -m coral programa.coral  # ejecuta un archivo
"""

import sys
from pathlib import Path

from . import __version__
from .errores import ErrorCoral
from .interprete import Interprete, mostrar


def ejecutar_archivo(ruta: Path) -> int:
    codigo = ruta.read_text(encoding="utf-8-sig")   # tolera el BOM que agregan algunos editores de Windows
    try:
        Interprete().ejecutar(codigo)
        return 0
    except ErrorCoral as e:
        print(e.con_contexto(codigo), file=sys.stderr)
        return 1


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
        if buffer.count("{") > buffer.count("}"):
            continue
        codigo, buffer = buffer, ""
        try:
            r = interp.ejecutar(codigo)
            if r is not None:
                print(mostrar(r))
        except ErrorCoral as e:
            print(e.con_contexto(codigo))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        sys.exit(ejecutar_archivo(Path(sys.argv[1])))
    repl()


if __name__ == "__main__":
    main()
