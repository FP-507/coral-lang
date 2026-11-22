// Carga el paquete coral (los .py del repositorio) dentro de Pyodide y lo ejecuta en el navegador.
const MODULOS = ["__init__", "errores", "lexer", "ast", "parser", "interprete"];
const EJEMPLOS = {
  "Hola, Coral": `# Tu primer programa en Coral
var nombre = "Panamá"
imprimir("¡Hola, " + nombre + "!")

var cuadrados = rango(1, 6).mapea(funcion (n) => n * n)
imprimir("Cuadrados:", cuadrados)
imprimir("Suma:", suma(cuadrados))
`,
  "Algoritmos": null,   // se cargan desde ../ejemplos
  "Clausuras": null,
  "Error con contexto": `# Coral señala la línea y columna exacta del error
var edad = 17
imprimir("Tienes " + edad + " años")
`,
};
const ARCHIVOS = { "Algoritmos": "../ejemplos/algoritmos.coral", "Clausuras": "../ejemplos/clausuras.coral" };

const $ = (s) => document.querySelector(s);
const codigo = $("#codigo"), salida = $("#salida"), boton = $("#ejecutar");
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
  pyodide.runPython(`
import sys
sys.path.insert(0, "/")
from coral import Interprete, ErrorCoral

def correr(codigo, escribir):
    try:
        Interprete(escribir).ejecutar(codigo)
        return None
    except ErrorCoral as e:
        return e.con_contexto(codigo)
`);
  salida.innerHTML = '<span class="info">Listo. Escribe código y presiona Ejecutar.</span>\n';
  boton.disabled = false;
  boton.textContent = "▶ Ejecutar";
}

function ejecutar() {
  if (!pyodide) return;
  salida.textContent = "";
  const t0 = performance.now();
  const error = pyodide.globals.get("correr")(codigo.value, (linea) => escribir(linea));
  if (error) escribir(error, "err");
  if (!salida.textContent) escribir("(el programa no imprimió nada)", "info");
  $("#tiempo").textContent = `${(performance.now() - t0).toFixed(0)} ms`;
}

boton.addEventListener("click", ejecutar);
codigo.addEventListener("input", numerar);
codigo.addEventListener("scroll", () => { $("#lineas").scrollTop = codigo.scrollTop; });
codigo.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ejecutar(); }
  if (e.key === "Tab") {
    e.preventDefault();
    const { selectionStart: a, selectionEnd: b } = codigo;
    codigo.setRangeText("  ", a, b, "end");
    numerar();
  }
});

iniciar().catch((err) => escribir("No se pudo cargar el intérprete: " + err, "err"));
