// La página habla SOLO con el backend, nunca con el proveedor del modelo.
//
// No es por comodidad: la página es estática y cualquiera puede leer su código.
// Una clave de Azure aquí sería una clave publicada. Así que el navegador pide
// al backend y el backend —que corre en un servidor— llama al proveedor.
//
// Con Ollama local da igual, no hay clave. Con Azure, Foundry o Mistral no es
// negociable, y es el mismo razonamiento del paso 4 del taller (qué puede
// tocar quién) aplicado a secretos en vez de a tools.

const API = "/api";

// El historial vive aquí, en el navegador. El backend no recuerda nada entre
// peticiones: cada llamada le manda la conversación completa.
//
// Eso no es una limitación del ejemplo, es como funciona un LLM: la ventana de
// contexto es su única memoria. Lo que parece "recordar" es que alguien le
// reenvía el historial, y lo paga en tokens cada vez.
let historial = [];
let enviando = false;

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Modelos: el selector se puebla desde el backend
// ---------------------------------------------------------------------------
async function cargarModelos() {
  try {
    const r = await fetch(`${API}/modelos`);
    const { modelos, por_omision } = await r.json();
    const sel = $("modelo");
    sel.innerHTML = "";

    for (const m of modelos) {
      const o = document.createElement("option");
      o.value = m.id;
      // Un modelo configurado pero sin clave se lista deshabilitado en vez de
      // esconderse: así se ve que existe y que falta configurarlo.
      o.textContent = m.listo ? m.etiqueta : `${m.etiqueta} — sin configurar`;
      o.disabled = !m.listo;
      if (m.id === por_omision) o.selected = true;
      sel.appendChild(o);
    }

    if (!modelos.some((m) => m.listo)) {
      marcarEstado("ningún modelo disponible", true);
    } else {
      marcarEstado("listo");
    }
  } catch {
    marcarEstado("backend sin responder", true);
  }
}

function marcarEstado(texto, esError = false) {
  const e = $("estado");
  e.textContent = texto;
  e.className = esError ? "error" : "";
}

// ---------------------------------------------------------------------------
// Pintar la conversación
// ---------------------------------------------------------------------------
function pintar(rol, contenido, meta = null) {
  const div = document.createElement("div");
  div.className = `mensaje mensaje-${rol}`;

  const quien = document.createElement("div");
  quien.className = "quien";
  quien.textContent = { user: "tú", assistant: "modelo", error: "error" }[rol] || rol;
  div.appendChild(quien);

  const cuerpo = document.createElement("div");
  cuerpo.className = "cuerpo";
  cuerpo.textContent = contenido;   // textContent, no innerHTML: el modelo
  div.appendChild(cuerpo);          // devuelve texto, no marcado confiable

  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    div.appendChild(m);
  }

  $("mensajes").appendChild(div);
  $("mensajes").scrollTop = $("mensajes").scrollHeight;
  return div;
}

function pintarPensamiento(div, pensamiento) {
  // El razonamiento va plegado: es largo, y mostrarlo desplegado tapa la
  // respuesta. Pero poder abrirlo es lo que hace concreta la diferencia entre
  // "el modelo piensa" y "el agente itera", que es el bloque 1 del taller.
  const det = document.createElement("details");
  det.className = "pensamiento";
  const sum = document.createElement("summary");
  sum.textContent = `razonamiento (${pensamiento.length} caracteres)`;
  det.appendChild(sum);
  const pre = document.createElement("pre");
  pre.textContent = pensamiento;
  det.appendChild(pre);
  div.appendChild(det);
}

function actualizarContador() {
  const n = historial.length;
  $("contador").textContent = n ? `${n} mensaje(s) en el contexto` : "";
}

// ---------------------------------------------------------------------------
// Los parámetros del modelo
// ---------------------------------------------------------------------------
// La regla: un campo vacío NO se manda. Así el backend usa el valor del .env o
// el que trae el modelo, y la interfaz no tiene que saber cuáles son.
//
// Están en la interfaz y no solo en el .env porque moverlos en vivo y ver qué
// cambia es el bloque 1 del taller. Se guardan en localStorage para que
// sobrevivan a un refresco a mitad de clase.

const CAMPOS = ["p-system", "p-temp", "p-topk", "p-topp"];
const GUARDADO = "agenticai.params";

function leerParams() {
  const n = (id) => {
    const v = $(id).value.trim();
    return v === "" ? null : Number(v);
  };
  const s = $("p-system").value.trim();
  return {
    system: s === "" ? null : s,
    temperatura: n("p-temp"),
    top_k: n("p-topk"),
    top_p: n("p-topp"),
    pensar: $("pensar").checked,
  };
}

function resumenParams() {
  const p = leerParams();
  const partes = [];
  if (p.temperatura !== null) partes.push(`temp ${p.temperatura}`);
  if (p.top_k !== null) partes.push(`top_k ${p.top_k}`);
  if (p.top_p !== null) partes.push(`top_p ${p.top_p}`);
  if (p.system !== null) partes.push("system propio");
  $("params-resumen").textContent = partes.length ? `· ${partes.join(", ")}` : "· por omisión";
}

function guardarParams() {
  try {
    const d = {};
    for (const id of CAMPOS) d[id] = $(id).value;
    localStorage.setItem(GUARDADO, JSON.stringify(d));
  } catch {
    /* modo privado o storage bloqueado: no es critico */
  }
}

function cargarParams() {
  try {
    const d = JSON.parse(localStorage.getItem(GUARDADO) || "{}");
    for (const id of CAMPOS) if (d[id] !== undefined) $(id).value = d[id];
  } catch {
    /* idem */
  }
  sincronizarTemp();
  resumenParams();
}

// El deslizador y la casilla numérica muestran lo mismo. El deslizador es para
// arrastrarlo en vivo durante la demo; la casilla, para poder dejarla vacía.
function sincronizarTemp(desde) {
  if (desde === "rango") $("p-temp").value = $("p-temp-rango").value;
  else $("p-temp-rango").value = $("p-temp").value === "" ? 0 : $("p-temp").value;
}

$("p-temp-rango").addEventListener("input", () => {
  sincronizarTemp("rango");
  guardarParams();
  resumenParams();
});

for (const id of CAMPOS) {
  $(id).addEventListener("input", () => {
    if (id === "p-temp") sincronizarTemp();
    guardarParams();
    resumenParams();
  });
}

$("p-demo").addEventListener("click", () => {
  // Los valores que hacen visible el no determinismo. Medidos: con top_k 20 y
  // top_p 0.95 (los del modelo), temperatura 1.5 devuelve la misma palabra
  // siempre. Ver planeacion/hallazgos.md
  $("p-temp").value = "1.5";
  $("p-topk").value = "100";
  $("p-topp").value = "1.0";
  sincronizarTemp();
  guardarParams();
  resumenParams();
});

$("p-reset").addEventListener("click", () => {
  for (const id of CAMPOS) $(id).value = "";
  sincronizarTemp();
  guardarParams();
  resumenParams();
});

// ---------------------------------------------------------------------------
// Enviar
// ---------------------------------------------------------------------------
async function enviar(texto) {
  if (enviando || !texto.trim()) return;
  enviando = true;
  $("enviar").disabled = true;
  $("texto").value = "";

  historial.push({ role: "user", content: texto });
  pintar("user", texto);
  actualizarContador();

  const pensando = pintar("assistant", "…", "esperando al modelo");

  try {
    // Solo mandamos los parámetros que el usuario puso. Los nulos se filtran,
    // así el backend aplica el valor del .env o el del modelo.
    const p = leerParams();
    const cuerpo = { mensajes: historial, modelo: $("modelo").value, pensar: p.pensar };
    for (const k of ["system", "temperatura", "top_k", "top_p"]) {
      if (p[k] !== null && !Number.isNaN(p[k])) cuerpo[k] = p[k];
    }

    const r = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    const d = await r.json();
    pensando.remove();

    if (d.error) {
      // El error se muestra en el chat en vez de en la consola: si pasa
      // durante el taller, el asistente tiene que poder leerlo.
      pintar("error", d.error, `${d.modelo} · ${d.segundos}s`);
    } else {
      const usados = [];
      if (cuerpo.temperatura !== undefined) usados.push(`temp ${cuerpo.temperatura}`);
      if (cuerpo.top_k !== undefined) usados.push(`top_k ${cuerpo.top_k}`);
      if (cuerpo.top_p !== undefined) usados.push(`top_p ${cuerpo.top_p}`);
      const meta = [`${d.modelo}`, `${d.segundos}s`, ...usados].join(" · ");
      const div = pintar("assistant", d.contenido, meta);
      if (d.pensamiento) pintarPensamiento(div, d.pensamiento);
      historial.push({ role: "assistant", content: d.contenido });
      actualizarContador();
    }
  } catch (e) {
    pensando.remove();
    pintar("error", `No pude hablar con el backend: ${e.message}`);
  } finally {
    enviando = false;
    $("enviar").disabled = false;
    $("texto").focus();
  }
}

$("entrada").addEventListener("submit", (e) => {
  e.preventDefault();
  enviar($("texto").value);
});

// Enter envía, Shift+Enter hace salto de línea. En un chat es lo que la gente
// espera, y pedirle que use el botón para cada mensaje cansa rápido.
$("texto").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    enviar($("texto").value);
  }
});

$("limpiar").addEventListener("click", () => {
  historial = [];
  $("mensajes").innerHTML = "";
  actualizarContador();
  $("texto").focus();
});

// ---------------------------------------------------------------------------
// La traza: sondeo cada segundo
// ---------------------------------------------------------------------------
// Sondeo y no WebSockets: son veinte líneas contra cien, y en una página de
// taller nadie nota la diferencia. Elegir la opción simple donde no importa es
// parte de lo que el taller debería modelar.
let ultimaTraza = 0;

async function refrescarTrazas() {
  try {
    const r = await fetch(`${API}/trazas?desde=${ultimaTraza}`);
    const { trazas } = await r.json();
    if (trazas.length) $("traza-vacia").hidden = true;
    for (const t of trazas) {
      ultimaTraza = t.n;
      const li = document.createElement("li");
      li.className = `evento evento-${t.evento}`;
      const b = document.createElement("b");
      b.textContent = t.agente;
      li.appendChild(b);
      li.appendChild(document.createTextNode(` ${t.evento}`));
      if (Object.keys(t.detalle || {}).length) {
        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(t.detalle, null, 1);
        li.appendChild(pre);
      }
      $("pasos").appendChild(li);
    }
  } catch {
    /* el backend puede estar reiniciando; la traza no es critica */
  }
}

// TODO (taller, paso 3): pintar el tablero del centro con el estado del dominio
// TODO (taller, paso 5): mostrar en la traza QUIEN hizo cada cosa

cargarModelos();
cargarParams();
setInterval(refrescarTrazas, 1000);
refrescarTrazas();
$("texto").focus();
