// Playground de Coral.
// Descarga los .py del paquete coral (los mismos del repositorio, sin copia ni
// compilación), los escribe en el sistema de archivos virtual de Pyodide y los
// ejecuta en el navegador. Si se cambia el intérprete, el playground lo refleja
// automáticamente al publicar en GitHub Pages.

// Módulos del paquete que se cargan en Pyodide. Si se agrega un módulo nuevo a coral/, sumarlo aquí.
const MODULOS = ["__init__", "errores", "pistas", "lexer", "ast", "parser", "interprete"];

// Ejemplos del selector. null = se descarga desde ../ejemplos (ver ARCHIVOS).
const EJEMPLOS = {
  "Hola, Coral": `# Tu primer programa en Coral
var nombre = "Panamá"
imprimir("¡Hola, {nombre}!")          # plantillas: {expresión} dentro del texto

var cuadrados = (1..5).mapea(funcion (n) => n * n)
imprimir("Cuadrados del 1 al 5:", cuadrados)
imprimir("Suma: {suma(cuadrados)}")

# Tubería: los datos fluyen de izquierda a derecha
funcion pares(lista) => lista.filtra(funcion (n) => n % 2 == 0)
imprimir(1..20 |> pares |> largo, "números pares entre 1 y 20")
`,
  "POO completa": null,
  "Clases y herencia": null,
  "Errores: intenta / captura": null,
  "Tuberías, rangos y segun": null,
  "Pruebas integradas": null,
  "Algoritmos": null,
  "Clausuras": null,
  "Errores que enseñan": `# ¿Vienes de Python o JavaScript? Coral te explica la palabra en español.
# Ejecuta, lee el error, corrígelo y vuelve a ejecutar.

var precios = [3, 7, 12]
var total = 0
para p en precios {
    total += p
}
print("Total:", total)

# Después prueba con estos errores:
#   imprmir(total)            -> ¿Quisiste decir 'imprimir'?
#   si total > 10 && verdadero { }
#   imprimir("Total: " + total)
`,
};
const ARCHIVOS = {
  "POO completa": "../ejemplos/poo.coral",
  "Clases y herencia": "../ejemplos/clases.coral",
  "Errores: intenta / captura": "../ejemplos/errores.coral",
  "Tuberías, rangos y segun": "../ejemplos/tuberias.coral",
  "Pruebas integradas": "../ejemplos/pruebas.coral",
  "Algoritmos": "../ejemplos/algoritmos.coral",
  "Clausuras": "../ejemplos/clausuras.coral",
};

const $ = (s) => document.querySelector(s);
const codigo = $("#codigo"), salida = $("#salida"), boton = $("#ejecutar"), botonPruebas = $("#pruebas");
let pyodide;

function numerar() {
  const n = codigo.value.split("\n").length;
  $("#lineas").textContent = Array.from({ length: n }, (_, i) => i + 1).join("\n");
}

function escribir(texto, clase = "ok") {
  const span = document.createElement("span");
  span.className = clase;
  span.textContent = texto + "\n";
  salida.append(span);
}

async function cargarEjemplo(nombre) {
  let texto = EJEMPLOS[nombre];
  if (texto === null) texto = await (await fetch(ARCHIVOS[nombre])).text();
  codigo.value = texto;
  numerar();
}

async function iniciar() {
  const sel = $("#ejemplo");
  sel.innerHTML = Object.keys(EJEMPLOS).map((n) => `<option>${n}</option>`).join("");
  sel.addEventListener("change", () => cargarEjemplo(sel.value));
  await cargarEjemplo(sel.value);

  pyodide = await loadPyodide();
  pyodide.FS.mkdir("/coral");
  for (const m of MODULOS) {
    const src = await (await fetch(`../coral/${m}.py`)).text();
    pyodide.FS.writeFile(`/coral/${m}.py`, src);
  }
  // util.coral queda disponible para probar:  importa "util.coral"
  pyodide.FS.mkdir("/ejemplos");
  pyodide.FS.writeFile("/ejemplos/util.coral", await (await fetch("../ejemplos/util.coral")).text());

  pyodide.runPython(`
import sys
sys.path.insert(0, "/")
from js import prompt
from coral import Interprete, ErrorCoral

def nuevo(escribir):
    # entrada() usa el cuadro de diálogo del navegador; directorio permite 'importa "util.coral"'.
    return Interprete(escribir, entrada=lambda m: prompt(m) or "", directorio="/ejemplos")

def correr(codigo, escribir):
    try:
        nuevo(escribir).ejecutar(codigo)
        return None
    except ErrorCoral as e:
        return e.con_contexto(codigo)

def correr_pruebas(codigo, escribir):
    """Devuelve [error] o una lista de [ok, texto] por prueba."""
    interp = nuevo(escribir)
    try:
        interp.ejecutar(codigo)
    except ErrorCoral as e:
        return [[False, e.con_contexto(codigo)]]
    return [[r["ok"], ("✓ " if r["ok"] else "✗ ") + r["nombre"] +
             ("" if r["ok"] else "\\n" + r["error"].con_contexto(codigo))] for r in interp.ejecutar_pruebas()]
`);
  salida.innerHTML = '<span class="info">Listo. Escribe código y presiona Ejecutar.</span>\n';
  boton.disabled = botonPruebas.disabled = false;
  boton.textContent = "▶ Ejecutar";
}

function medir(accion) {
  if (!pyodide) return;
  salida.textContent = "";
  const t0 = performance.now();
  accion();
  $("#tiempo").textContent = `${(performance.now() - t0).toFixed(0)} ms`;
}

function ejecutar() {
  medir(() => {
    const error = pyodide.globals.get("correr")(codigo.value, (linea) => escribir(linea));
    if (error) escribir(error, "err");
    if (!salida.textContent) escribir("(el programa no imprimió nada)", "info");
  });
}

function ejecutarPruebas() {
  medir(() => {
    const resultados = pyodide.globals.get("correr_pruebas")(codigo.value, () => {}).toJs();
    if (!resultados.length) {
      escribir('Este programa no tiene bloques  prueba "nombre" { afirma ... }', "info");
      return;
    }
    for (const [ok, texto] of resultados) escribir(texto, ok ? "pass" : "err");
    const pasaron = resultados.filter(([ok]) => ok).length;
    escribir(`\n${pasaron} de ${resultados.length} pruebas pasaron`, pasaron === resultados.length ? "pass" : "err");
  });
}

boton.addEventListener("click", ejecutar);
botonPruebas.addEventListener("click", ejecutarPruebas);
codigo.addEventListener("input", numerar);
codigo.addEventListener("scroll", () => { $("#lineas").scrollTop = codigo.scrollTop; });
codigo.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ejecutar(); }
  if (e.key === "Tab") {
    e.preventDefault();
    const { selectionStart: a, selectionEnd: b } = codigo;
    codigo.setRangeText("    ", a, b, "end");
    numerar();
  }
});

iniciar().catch((err) => escribir("No se pudo cargar el intérprete: " + err, "err"));
