/**
 * gemelo.js — FE Engage Tactical Assistant
 * Conecta la UI del Gemelo con la API Flask:
 * • Renderizado de mapa CSS Grid + Terreno
 * • Creación y edición interactiva de unidades (Aliados y Enemigos) con autocompletado del catálogo
 * • Drag-and-drop nativo HTML5
 * • Botones [Analizar], [Turno Enemigo], [Preset Cap. 7]
 */

"use strict";

const $ = id => document.getElementById(id);

// Estado global de la UI
const state = {
  fichas: {},        // { nombre: FichaUnidad }
  dragging: null,    // nombre de la ficha que se está arrastrando
  fase: "jugador",   // "jugador" | "enemigo"
  turno: 1,
  mapaAncho: 24,
  mapaAlto: 17,
  modalModo: "crear", // "crear" | "editar"
};

// ─── Utilidad fetch ────────────────────────────────────────────────────────

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  try {
    const r = await fetch(path, opts);
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      return await r.json();
    }
    const txt = await r.text();
    return { ok: r.ok, error: txt };
  } catch (err) {
    console.error(`Error en API ${method} ${path}:`, err);
    return { ok: false, error: err.message };
  }
}

// ─── Clases de color para terreno ──────────────────────────────────────────

const CLASES_TERRENO = {
  "Llanura":      "t-llanura",
  "Bosque":       "t-bosque",
  "Muro":         "t-muro",
  "Montaña":      "t-montaña",
  "Agua":         "t-agua",
  "Agua Profunda":"t-agua",
  "Arena":        "t-arena",
  "Curación":     "t-curacion",
  "Curacion":     "t-curacion",
  "Fortaleza":    "t-curacion",
  "Trono":        "t-curacion",
  "Recarga":      "t-recarga",
  "Emblema":      "t-recarga",
  "Pozo":         "t-recarga",
};

function claseTerreno(nombre = "") {
  for (const [k, v] of Object.entries(CLASES_TERRENO)) {
    if (nombre.toLowerCase().includes(k.toLowerCase())) return v;
  }
  return "t-desconocido";
}

// ─── Construcción del grid ─────────────────────────────────────────────────

function buildGrid(ancho, alto) {
  state.mapaAncho = ancho;
  state.mapaAlto = alto;

  const grid = $("mapa-grid");
  grid.style.gridTemplateColumns = `repeat(${ancho}, var(--cell))`;
  grid.style.gridTemplateRows    = `repeat(${alto},  var(--cell))`;
  grid.innerHTML = "";

  for (let y = 0; y < alto; y++) {
    for (let x = 0; x < ancho; x++) {
      const celda = document.createElement("div");
      celda.classList.add("celda", "t-desconocido");
      celda.id = `c-${x}-${y}`;
      celda.dataset.x = x;
      celda.dataset.y = y;
      celda.dataset.tip = `${x},${y}`;

      // Eventos drag-and-drop
      celda.addEventListener("dragover", onCeldaDragOver);
      celda.addEventListener("dragleave", onCeldaDragLeave);
      celda.addEventListener("drop", onCeldaDrop);

      // Clic en celda para crear unidad si está vacía
      celda.addEventListener("click", onCeldaClick);

      grid.appendChild(celda);
    }
  }

  loadTerrenoAsync(ancho, alto);
}

async function loadTerrenoAsync(ancho, alto) {
  for (let y = 0; y < alto; y++) {
    const promises = [];
    for (let x = 0; x < ancho; x++) {
      promises.push(
        api(`/api/terreno/${x}/${y}`)
          .then(t => {
            if (t.error) return;
            const celda = $(`c-${x}-${y}`);
            if (!celda) return;
            celda.classList.remove("t-desconocido");
            celda.classList.add(claseTerreno(t.nombre));

            const perks = [`${t.nombre} | AVO +${t.avo} DEF +${t.dfn}`];
            if (t.curacion_turno) perks.push(`Cura +${t.curacion_turno} HP/turno`);
            if (t.es_antirruptura) perks.push(`Inmune Ruptura`);
            if (t.es_recarga_emblema) perks.push(`Recarga Emblema 100%`);

            celda.title = perks.join(" · ");
            let tagExtra = "";
            if (t.curacion_turno) tagExtra += ` · +${t.curacion_turno}HP Antirruptura`;
            if (t.es_recarga_emblema) tagExtra += ` · Recarga Fusión`;
            celda.dataset.tip = `${x},${y} [${t.nombre}] AVO +${t.avo}${tagExtra}`;
          })
          .catch(() => {})
      );
    }
    await Promise.all(promises);
  }
}

// ─── Tokens ────────────────────────────────────────────────────────────────

function crearToken(ficha) {
  const celda = $(`c-${ficha.x}-${ficha.y}`);
  if (!celda) return;

  // Eliminar token anterior si existe
  const viejo = document.querySelector(`.token[data-nombre="${ficha.nombre}"]`);
  if (viejo) viejo.remove();

  if (!ficha.viva) return;

  const tok = document.createElement("div");
  let claseBando = ficha.es_aliado ? (ficha.es_verde ? "aliado verde" : "aliado") : "enemigo";
  if (ficha.es_fijo) claseBando += " fijo";
  if (ficha.en_fusion || ficha.turnos_fusion > 0) claseBando += " fusion";
  if (ficha.ha_actuado) claseBando += " actuado";
  if (ficha.en_ruptura || ficha.cargas_ruptura > 0) claseBando += " en-ruptura";
  tok.className = `token ${claseBando}`;
  tok.dataset.nombre = ficha.nombre;
  tok.textContent = ficha.nombre[0].toUpperCase();

  if (ficha.en_fusion || ficha.turnos_fusion > 0) {
    const badge = document.createElement("span");
    badge.className = "token-engage-badge";
    badge.textContent = `${ficha.turnos_fusion || 3}`;
    badge.title = `Fusión activa: ${ficha.turnos_fusion || 3} turno(s) restante(s)${ficha.ataque_emblema_usado ? ' (Técnica Engage usada)' : ''}`;
    tok.appendChild(badge);
  }

  if (ficha.en_ruptura || ficha.cargas_ruptura > 0) {
    const breakBadge = document.createElement("span");
    breakBadge.className = "token-break-badge";
    breakBadge.textContent = "BRK";
    breakBadge.title = "Ruptura (Break): Desarmado para contraataques";
    tok.appendChild(breakBadge);
  }

  if (ficha.nivel_veneno > 0) {
    const poisonBadge = document.createElement("span");
    poisonBadge.className = "token-poison-badge";
    poisonBadge.textContent = "VEN" + (ficha.nivel_veneno > 1 ? ficha.nivel_veneno : "");
    poisonBadge.title = `Veneno Nivel ${ficha.nivel_veneno}: Recibe +${ficha.nivel_veneno} de daño en todos los ataques`;
    tok.appendChild(poisonBadge);
  }
  
  const hpMax = ficha.hp_max || (ficha.stats ? ficha.stats.hp : 30);
  const hpActual = ficha.hp_actual !== undefined ? ficha.hp_actual : hpMax;
  const pct = ficha.pct_hp !== undefined ? ficha.pct_hp : Math.round((hpActual / hpMax) * 100);

  let desc = `${ficha.nombre} (${ficha.es_verde ? "Aliado Verde" : (ficha.es_aliado ? "Aliado" : "Enemigo")})\nHP: ${hpActual}/${hpMax} (${pct}%)\nClase: ${ficha.clase_nombre || "Desconocida"} | Nv: ${ficha.nivel || 1}`;
  if (ficha.arma_equipada) desc += `\nArma: ${ficha.arma_equipada.nombre} (Mt ${ficha.arma_equipada.mt}, Rango ${ficha.arma_equipada.rango.join('-')})`;
  if (ficha.emblema_nombre) desc += `\nEmblema: ${ficha.emblema_nombre}`;
  const es3H = (ficha.emblema_nombre && (ficha.emblema_nombre.toLowerCase().includes("edelgard") || ficha.emblema_nombre.toLowerCase().includes("tres casas") || ficha.emblema_nombre.toLowerCase().includes("three houses")));
  if (es3H && ficha.lider_tres_casas) desc += `\n[Líder 3 Casas: ${ficha.lider_tres_casas}]`;
  if (ficha.nivel_veneno > 0) desc += `\n[VENENO NIVEL ${ficha.nivel_veneno}: Recibe +${ficha.nivel_veneno} dmg de todo ataque]`;
  if (ficha.ha_actuado) desc += `\n[HA ACTUADO ESTE TURNO - Movimiento bloqueado]`;
  if (ficha.en_ruptura || ficha.cargas_ruptura > 0) desc += `\n[RUPTURA ACTIVA: No puede contraatacar]`;
  if (ficha.en_fusion || ficha.turnos_fusion > 0) desc += `\n[MODO ENGAGE ACTIVO: ${ficha.turnos_fusion} turno(s) restante(s)${ficha.ataque_emblema_usado ? ' - Técnica Engage consumida' : ''}]`;
  else if (ficha.es_aliado && ficha.emblema_nombre) {
    const maxE = ficha.max_energia_emblema || (ficha.nivel_vinculo >= 20 ? 5 : 6);
    const curE = (ficha.energia_emblema !== undefined) ? ficha.energia_emblema : maxE;
    desc += `\n[MEDIDOR DE EMBLEMA: ${curE}/${maxE}${curE >= maxE ? ' - FUSIÓN LISTA' : ''}]`;
  }
  tok.title = desc;

  // Un aliado que ya ha actuado este turno no se puede volver a mover (pero sí se puede hacer clic para ver/editar)
  const puedeMoverse = ficha.viva && (!ficha.es_aliado || !ficha.ha_actuado);
  tok.draggable = Boolean(puedeMoverse);

  // Barra de vida mini sobre el token
  const hpBar = document.createElement("div");
  hpBar.className = "token-hp-bar";
  const hpFill = document.createElement("div");
  const hpColorClass = pct > 50 ? "hp-high" : (pct > 20 ? "hp-mid" : "hp-low");
  hpFill.className = `token-hp-fill ${hpColorClass}`;
  hpFill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  hpBar.appendChild(hpFill);
  tok.appendChild(hpBar);

  tok.addEventListener("dragstart", onTokenDragStart);
  tok.addEventListener("dragend",   onTokenDragEnd);
  
  // Clic en token para editar (siempre disponible aunque haya actuado)
  tok.addEventListener("click", (e) => {
    e.stopPropagation();
    abrirModalEdicion(ficha);
  });

  celda.appendChild(tok);
}

function autoGuardarLocal() {
  try {
    const estado = {
      fichas: Object.values(state.fichas),
      turno_actual: state.turno || 1,
      fase: state.fase || "jugador",
      guardadoEn: new Date().toISOString()
    };
    localStorage.setItem("engage_tracker_partida_local", JSON.stringify(estado));
  } catch (e) {
    console.warn("No se pudo auto-guardar en localStorage:", e);
  }
}

async function restaurarDesdeLocalStorage() {
  try {
    const raw = localStorage.getItem("engage_tracker_partida_local");
    if (!raw) return false;
    const estado = JSON.parse(raw);
    if (!estado || !Array.isArray(estado.fichas) || estado.fichas.length === 0) return false;

    const res = await api("/api/partida/importar", "POST", { partida: estado });
    if (res.ok && res.fichas) {
      state.turno = estado.turno_actual || 1;
      state.fase = estado.fase || "jugador";
      actualizarBadge();
      actualizarTokens(res.fichas);
      return true;
    }
  } catch (e) {
    console.warn("Error restaurando desde localStorage:", e);
  }
  return false;
}

function actualizarTokens(fichas) {
  document.querySelectorAll(".token").forEach(t => t.remove());
  state.fichas = {};
  if (Array.isArray(fichas)) {
    fichas.forEach(f => {
      state.fichas[f.nombre] = f;
      crearToken(f);
    });
  }
  autoGuardarLocal();
}

// ─── Drag & Drop con Rango de Movimiento Táctico ───────────────────────────

async function mostrarRangoMovimiento(nombre) {
  limpiarRangoMovimiento();
  const res = await api(`/api/unidad/rango_movimiento?nombre=${encodeURIComponent(nombre)}`);
  if (res && res.ok && Array.isArray(res.casillas)) {
    res.casillas.forEach(([cx, cy]) => {
      const cel = $(`c-${cx}-${cy}`);
      if (cel) cel.classList.add("rango-movimiento");
    });
  }
}

function limpiarRangoMovimiento() {
  document.querySelectorAll(".celda.rango-movimiento").forEach(c => {
    c.classList.remove("rango-movimiento");
    c.classList.remove("drop-over");
  });
}

function onTokenDragStart(e) {
  const nombre = e.currentTarget.dataset.nombre;
  const ficha = state.fichas[nombre];
  if (ficha && ficha.es_aliado && ficha.ha_actuado) {
    e.preventDefault();
    mostrarToast(`${nombre} ya ha actuado este turno. Usa la Cronogema (Deshacer / Ctrl+Z) para cambiar su elección.`, "info");
    return;
  }
  state.dragging = nombre;
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", state.dragging);
  e.currentTarget.style.opacity = "0.5";
  
  // Iluminar halo azul con las casillas legales que puede alcanzar
  mostrarRangoMovimiento(nombre);
}

function onTokenDragEnd(e) {
  e.currentTarget.style.opacity = "";
  state.dragging = null;
  limpiarRangoMovimiento();
}

function onCeldaDragOver(e) {
  if (!state.dragging) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  e.currentTarget.classList.add("drop-over");
}

function onCeldaDragLeave(e) {
  e.currentTarget.classList.remove("drop-over");
}

async function onCeldaDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove("drop-over");
  limpiarRangoMovimiento();

  const nombre = state.dragging || e.dataTransfer.getData("text/plain");
  if (!nombre) return;

  const x = parseInt(e.currentTarget.dataset.x, 10);
  const y = parseInt(e.currentTarget.dataset.y, 10);

  const res = await api("/api/mover", "POST", { nombre, x, y });
  if (res.error) {
    mostrarToast(`${res.error}`, "error");
    return;
  }

  if (res.fichas) {
    actualizarTokens(res.fichas);
  } else if (state.fichas[nombre]) {
    state.fichas[nombre].x = x;
    state.fichas[nombre].y = y;
    if (state.fase === "jugador" && state.fichas[nombre].es_aliado) {
      state.fichas[nombre].ha_actuado = true;
    }
    crearToken(state.fichas[nombre]);
  }

  if (state.fase === "jugador") {
    setTimeout(lanzarAnalisis, 250);
  }
}

function onCeldaClick(e) {
  // Solo abrir creación si no se está arrastrando y no se hizo clic en un token existente
  if (e.target.classList.contains("token")) return;
  const x = parseInt(e.currentTarget.dataset.x, 10);
  const y = parseInt(e.currentTarget.dataset.y, 10);
  abrirModalCreacion(x, y, true);
}

// ─── Diccionario Maestro de Emblemas: Pasivas, Bonos de Sincronía y Fusión ───

const EMBLEMAS_DATA = {
  "marth": {
    nombre: "Marth",
    synchro_skills: ["Perceptive", "Break Defenses", "Unyielding"],
    synchro_boosts: { str: 2, dex: 3, spd: 2 },
    engage_skills: ["Divine Speed"],
    engage_attack: "Lodestar Rush (Acometida estelar)",
    engage_items: ["Rapier", "Mercurius"]
  },
  "sigurd": {
    nombre: "Sigurd",
    synchro_skills: ["Canter", "Momentum", "Headlong Rush"],
    synchro_boosts: { def: 2, dex: 2, bld: 2, mov: 1 },
    engage_skills: ["Gallop"],
    engage_attack: "Override (Superación)",
    engage_items: ["Ridersbane", "Brave Lance"]
  },
  "celica": {
    nombre: "Celica",
    synchro_skills: ["Resonance", "Holy Stance", "Favorite Food"],
    synchro_boosts: { mag: 3, res: 3, str: 2 },
    engage_skills: ["Echo"],
    engage_attack: "Warp Ragnarök (Tele-Ragnarök)",
    engage_items: ["Seraphim", "Recover"]
  },
  "micaiah": {
    nombre: "Micaiah",
    synchro_skills: ["Healing Light", "Silence Ward", "Cleric"],
    synchro_boosts: { mag: 3, res: 3, lck: 3 },
    engage_skills: ["Augment"],
    engage_attack: "Great Sacrifice (Gran sacrificio)",
    engage_items: ["Shine", "Nosferatu"]
  },
  "roy": {
    nombre: "Roy",
    synchro_skills: ["Hold Out", "Advance"],
    synchro_boosts: { hp: 7, str: 3, res: 2 },
    engage_skills: ["Rise Above"],
    engage_attack: "Blazing Lion (León ardiente)",
    engage_items: ["Lancereaver", "Wyrmslayer"]
  },
  "leif": {
    nombre: "Leif",
    synchro_skills: ["Vantage", "Arms Shield"],
    synchro_boosts: { bld: 3, def: 3, hp: 5 },
    engage_skills: ["Adaptable"],
    engage_attack: "Quadruple Hit (Tétragolpe)",
    engage_items: ["Killer Axe", "Master Lance"]
  },
  "lucina": {
    nombre: "Lucina",
    synchro_skills: ["Dual Strike", "Dual Assist"],
    synchro_boosts: { dex: 3, spd: 3, lck: 3 },
    engage_skills: ["Bonded Shield"],
    engage_attack: "All for One (Todos para uno)",
    engage_items: ["Noble Rapier", "Parthia"]
  },
  "lyn": {
    nombre: "Lyn",
    synchro_skills: ["Alacrity", "Speedtaker"],
    synchro_boosts: { spd: 3, dex: 3, res: 2 },
    engage_skills: ["Call Doubles"],
    engage_attack: "Astra Storm (Tormenta astral)",
    engage_items: ["Killer Bow", "Mani Katti"]
  },
  "ike": {
    nombre: "Ike",
    synchro_skills: ["Resolve", "Demolish", "Reposition"],
    synchro_boosts: { hp: 5, def: 3, str: 2 },
    engage_skills: ["Laguz Friend"],
    engage_attack: "Great Aether (Gran Éter)",
    engage_items: ["Hammer", "Urvan"]
  },
  "byleth": {
    nombre: "Byleth",
    synchro_skills: ["Divine Pulse", "Mentorship"],
    synchro_boosts: { mag: 3, lck: 3, spd: 2 },
    engage_skills: ["Instruct"],
    engage_attack: "Goddess Dance (Danza de la Diosa)",
    engage_items: ["Vajra-Mushti"]
  },
  "corrin": {
    nombre: "Corrin",
    synchro_skills: ["Draconic Hex", "Dragon Vein", "Quality Time"],
    synchro_boosts: { hp: 7, mag: 3, res: 3 },
    engage_skills: ["Dreadful Aura"],
    engage_attack: "Torrential Roar (Torrente rugiente)",
    engage_items: ["Dual Katana", "Wakizashi"]
  },
  "eirika": {
    nombre: "Eirika",
    synchro_skills: ["Lunar Brace", "Gentility", "Night and Day"],
    synchro_boosts: { mag: 3, lck: 3, def: 2 },
    engage_skills: ["Sacred Twins"],
    engage_attack: "Twin Strike (Golpe gemelo)",
    engage_items: ["Rapier", "Wind Sword"]
  },
  "ephraim": {
    nombre: "Ephraim",
    synchro_skills: ["Lunar Brace", "Gentility", "Night and Day"],
    synchro_boosts: { mag: 3, lck: 3, def: 2 },
    engage_skills: ["Sacred Twins"],
    engage_attack: "Twin Strike (Golpe gemelo)",
    engage_items: ["Rapier", "Wind Sword"]
  },
  "alear": {
    nombre: "Alear",
    synchro_skills: ["Divinely Inspiring"],
    synchro_boosts: { hp: 5, str: 2, spd: 2 },
    engage_skills: ["Dragon Blast"],
    engage_attack: "Bond Blast (Ataque de Vínculo)",
    engage_items: ["Libération", "Wille Glanz"]
  },
  "edelgard": {
    nombre: "Edelgard",
    synchro_skills: ["Gambit (Flame/Shield/Poison)", "Friendly Rivalry", "Lineage", "Weapon Sync"],
    synchro_boosts: { str: 4, dex: 3, def: 3 },
    engage_skills: ["Combat Arts (Raging Storm / Atrocity / Fallen Star)"],
    engage_attack: "Houses Unite (Unión de Casas)",
    engage_items: ["Aymr", "Areadbhar", "Failnaught"]
  },
  "three houses": {
    nombre: "Edelgard",
    synchro_skills: ["Gambit (Flame/Shield/Poison)", "Friendly Rivalry", "Lineage", "Weapon Sync"],
    synchro_boosts: { str: 4, dex: 3, def: 3 },
    engage_skills: ["Combat Arts (Raging Storm / Atrocity / Fallen Star)"],
    engage_attack: "Houses Unite (Unión de Casas)",
    engage_items: ["Aymr", "Areadbhar", "Failnaught"]
  },
  "tiki": {
    nombre: "Tiki",
    synchro_skills: ["Starsphere", "Geosphere", "Lifesphere", "Lightsphere"],
    synchro_boosts: { hp: 10, def: 4, lck: 10 },
    engage_skills: ["Draconic Form"],
    engage_attack: "Divine Blessing (Bendición Divina)",
    engage_items: ["Eternal Claw", "Tail Smash", "Fire Breath"]
  },
  "hector": {
    nombre: "Hector",
    synchro_skills: ["Quick Riposte", "Adaptability", "Heavy Attack", "Piercing Glare"],
    synchro_boosts: { str: 4, def: 5, bld: 3 },
    engage_skills: ["Impenetrable"],
    engage_attack: "Storm's Eye (Ojo de la tormenta)",
    engage_items: ["Wolf Beil", "Runesword", "Armads"]
  },
  "soren": {
    nombre: "Soren",
    synchro_skills: ["Assign Decoy (Señuelo)", "Anima Focus", "Keen Insight", "Block Recovery"],
    synchro_boosts: { mag: 4, dex: 3, res: 5 },
    engage_skills: ["Flare"],
    engage_attack: "Cataclysm (Cataclismo)",
    engage_items: ["Bolting", "Reflect", "Rexcalibur"]
  },
  "camilla": {
    nombre: "Camilla",
    synchro_skills: ["Dragon Vein", "Decisive Strike", "Groundswell", "Detoxify"],
    synchro_boosts: { hp: 7, spd: 5, res: 4 },
    engage_skills: ["Soar (+2 Mov y Vuelo)"],
    engage_attack: "Dark Inferno (Infierno oscuro)",
    engage_items: ["Bolt Axe", "Lightning", "Camilla's Axe"]
  },
  "chrom": {
    nombre: "Chrom",
    synchro_skills: ["Surprise Attack", "Rally Spectrum", "Brute Force", "Charm"],
    synchro_boosts: { str: 3, dex: 5, spd: 4 },
    engage_skills: ["Other Half (Ataques en cadena de Robin)"],
    engage_attack: "Giga Levin Sword (Gigaespada Trueno)",
    engage_items: ["Levin Sword (Robin)", "Thoron (Robin)", "Falchion (Chrom)"]
  },
  "robin": {
    nombre: "Chrom",
    synchro_skills: ["Surprise Attack", "Rally Spectrum", "Brute Force", "Charm"],
    synchro_boosts: { str: 3, dex: 5, spd: 4 },
    engage_skills: ["Other Half (Ataques en cadena de Robin)"],
    engage_attack: "Giga Levin Sword (Gigaespada Trueno)",
    engage_items: ["Levin Sword (Robin)", "Thoron (Robin)", "Falchion (Chrom)"]
  },
  "veronica": {
    nombre: "Veronica",
    synchro_skills: ["Reprisal (+Atk por HP perdido)", "SP Conversion", "Level Boost"],
    synchro_boosts: { mag: 5, res: 4, lck: 6 },
    engage_skills: ["Contract (Acción extra al aliado)"],
    engage_attack: "Summon Hero (Invocar Héroe de FEH)",
    engage_items: ["Hliðskjálf", "Fortify+", "Élivágar"]
  }
};

let CATALOGO_EMBLEMAS = {};

async function cargarCatalogoEmblemas() {
  try {
    const res = await api("/api/catalogo/emblemas");
    if (res && res.ok && res.emblemas) {
      CATALOGO_EMBLEMAS = res.emblemas;
    }
  } catch (e) {
    console.warn("No se pudo cargar catalogo de emblemas:", e);
  }
}

function buscarEmblemaInfo(nombre) {
  if (!nombre) return null;
  const n = nombre.trim().toLowerCase();

  // 1. Buscar en catálogo compilado oficial (21 emblemas con bond_levels 1..20)
  for (const [k, v] of Object.entries(CATALOGO_EMBLEMAS)) {
    const nom = (v.nombre || "").toLowerCase();
    const ascii = (v.ascii_name || "").toLowerCase();
    const link = (v.link_name || "").toLowerCase();
    const kid = k.toLowerCase();
    if (n === nom || n === ascii || n === link || n === kid || nom.includes(n) || n.includes(nom)) {
      return v;
    }
  }

  // 2. Fallback a datos estáticos embebidos
  for (const [k, v] of Object.entries(EMBLEMAS_DATA)) {
    if (n === k || n.includes(k) || k.includes(n)) return v;
  }
  return null;
}

function obtenerDatosVinculoEmblema(eInfo, nivel) {
  if (!eInfo) return null;
  const n = Math.max(1, Math.min(20, parseInt(nivel || 1, 10)));
  if (eInfo.bond_levels && eInfo.bond_levels[String(n)]) {
    return eInfo.bond_levels[String(n)];
  }
  return {
    level: n,
    stat_boosts: eInfo.synchro_boosts || {},
    synchro_skills: (eInfo.synchro_skills || []).map(s => ({ sid: s, nombre: s })),
    engage_items: (eInfo.engage_items || []).map(i => ({ iid: i, nombre: i })),
    engage_skills: (eInfo.engage_skills || []).map(s => ({ sid: s, nombre: s })),
    max_energia_emblema: n >= 20 ? 5 : 6
  };
}

function desglosarArmaString(raw) {
  if (!raw) return { base: "", forja: "0", grabado: "" };
  let s = String(raw).trim();
  let grabado = "";
  const mGrab = s.match(/\(([^)]+)\)/);
  if (mGrab) {
    const gRaw = mGrab[1].trim();
    const gClean = gRaw.toLowerCase().replace("grabado de", "").replace("marca de", "").replace("engrave", "").trim();
    const grabadosValidos = ["Marth", "Sigurd", "Celica", "Micaiah", "Roy", "Leif", "Lucina", "Lyn", "Ike", "Byleth", "Corrin", "Eirika", "Alear"];
    for (const g of grabadosValidos) {
      if (g.toLowerCase() === gClean || gClean.includes(g.toLowerCase())) {
        grabado = g;
        break;
      }
    }
    s = s.replace(/\([^)]+\)/, "").trim();
  }
  let forja = "0";
  const mRef = s.match(/\+(\d+)/);
  if (mRef) {
    forja = String(Math.min(5, Math.max(1, parseInt(mRef[1], 10))));
    s = s.replace(/\+\d+/, "").trim();
  }
  return { base: s, forja, grabado };
}

function construirArmaString(base, forja, grabado) {
  let res = String(base || "").trim();
  if (!res) return "";
  const fNum = parseInt(forja || 0, 10);
  if (fNum > 0 && !res.includes("+" + fNum)) {
    res += `+${fNum}`;
  }
  if (grabado && !res.toLowerCase().includes(`(${grabado.toLowerCase()})`)) {
    res += ` (${grabado})`;
  }
  return res;
}

// ─── Recalcular Estadísticas de Combate Derivadas en Vivo ───────────────────

async function recalcularCombatStats() {
  const str = parseInt($("f-stat-str")?.value || 0, 10);
  const mag = parseInt($("f-stat-mag")?.value || 0, 10);
  const dex = parseInt($("f-stat-dex")?.value || 0, 10);
  const spd = parseInt($("f-stat-spd")?.value || 0, 10);
  const def = parseInt($("f-stat-def")?.value || 0, 10);
  const res = parseInt($("f-stat-res")?.value || 0, 10);
  const lck = parseInt($("f-stat-lck")?.value || 0, 10);
  const bld = parseInt($("f-stat-bld")?.value || 1, 10);

  const claseNombre = $("f-clase")?.value.trim() || "";
  const baseArma = $("f-arma")?.value.trim() || "";
  const forja = $("f-arma-forja")?.value || "0";
  const grabado = $("f-arma-grabado")?.value || "";
  const armaNombre = construirArmaString(baseArma, forja, grabado);

  let mt = 5, wt = 5, hit = 80, crit = 0, rng = "1", esMagica = false, avoBonus = 0, ddgBonus = 0;

  if (armaNombre) {
    try {
      const resData = await api(`/api/catalogo/buscar?tipo=armas&q=${encodeURIComponent(armaNombre)}`);
      if (resData && resData.resultados && resData.resultados.length > 0) {
        const a = resData.resultados[0].datos;
        if (a) {
          mt = a.mt !== undefined ? a.mt : mt;
          wt = a.wt !== undefined ? a.wt : wt;
          hit = a.hit !== undefined ? a.hit : hit;
          crit = a.crit !== undefined ? a.crit : crit;
          avoBonus = a.avo_bonus || 0;
          ddgBonus = a.ddg_bonus || 0;
          esMagica = !!a.es_magica || a.tipo === "Tomo" || a.tipo === "Bastón";
          rng = Array.isArray(a.rango) ? a.rango.join("-") : (a.rango || "1");
        }
      }
    } catch (e) {}
  }

  // Detección de respaldo para palabras clave de armas mágicas
  const nombreArmaLower = armaNombre.toLowerCase();
  const esPalabraMagica = nombreArmaLower.includes("levin") || nombreArmaLower.includes("trueno") || nombreArmaLower.includes("flame") || nombreArmaLower.includes("hurricane") || nombreArmaLower.includes("radiant") || nombreArmaLower.includes("ragnarok") || nombreArmaLower.includes("fire") || nombreArmaLower.includes("thunder") || nombreArmaLower.includes("wind") || nombreArmaLower.includes("surge") || nombreArmaLower.includes("bolganone") || nombreArmaLower.includes("thoron") || nombreArmaLower.includes("nova") || nombreArmaLower.includes("seraphim") || nombreArmaLower.includes("thani") || nombreArmaLower.includes("nosferatu") || nombreArmaLower.includes("shine") || nombreArmaLower.includes("tomo") || nombreArmaLower.includes("obscurite");

  if (esPalabraMagica) {
    esMagica = true;
  }

  // Fórmulas canónicas oficiales de FE Engage con Forja y Grabados
  const as_val = Math.max(0, spd - Math.max(0, wt - bld));
  const atk = (esMagica ? mag : str) + mt;
  const hit_val = hit + (2 * dex) + Math.floor(lck / 2);
  const avo = (2 * as_val) + Math.floor(lck / 2) + avoBonus;
  const crit_val = crit + Math.floor(dex / 2);
  const ddg = lck + ddgBonus;

  const labelAtk = $("label-cstat-atk");
  if (labelAtk) {
    labelAtk.textContent = esMagica ? "MAG. ATK" : "ATK (Ataque)";
    labelAtk.title = esMagica ? `Ataque Mágico = Magia (${mag}) + Mt (${mt})` : `Ataque Físico = Fuerza (${str}) + Mt (${mt})`;
  }

  if ($("f-cstat-atk")) $("f-cstat-atk").value = atk;
  if ($("f-cstat-hit")) $("f-cstat-hit").value = hit_val;
  if ($("f-cstat-avo")) $("f-cstat-avo").value = avo;
  if ($("f-cstat-crit")) $("f-cstat-crit").value = crit_val;
  if ($("f-cstat-ddg")) $("f-cstat-ddg").value = ddg;
  if ($("f-cstat-as")) $("f-cstat-as").value = as_val;
  if ($("f-cstat-rng")) $("f-cstat-rng").value = rng;
}

// ─── Modal de Configuración de Unidad y Potenciadores ───────────────────────

function renderizarBadgesPotenciadores() {
  const cont = $("potenciadores-badge-list");
  if (!cont) return;
  cont.innerHTML = "";
  if (!state.potenciadoresModal || state.potenciadoresModal.length === 0) return;

  state.potenciadoresModal.forEach((nom, idx) => {
    const badge = document.createElement("span");
    badge.className = "booster-badge";
    badge.innerHTML = `${nom} <span class="booster-badge-remove" title="Quitar">&times;</span>`;
    badge.querySelector(".booster-badge-remove").addEventListener("click", () => {
      state.potenciadoresModal.splice(idx, 1);
      renderizarBadgesPotenciadores();
    });
    cont.appendChild(badge);
  });
}

function abrirModalCreacion(x = 0, y = 0, esAliado = true) {
  state.modalModo = "crear";
  state.potenciadoresModal = [];
  state.prevEmblemaModal = "";
  $("modal-titulo").textContent = esAliado ? "Añadir Nuevo Aliado" : "Añadir Nuevo Enemigo";
  $("f-edit-original-name").value = "";
  $("f-x").value = x;
  $("f-y").value = y;
  $("label-pos-x").textContent = x;
  $("label-pos-y").textContent = y;

  if (esAliado) {
    $("f-bando-aliado").checked = true;
    $("seccion-aliado-extra").classList.remove("hidden");
  } else {
    $("f-bando-enemigo").checked = true;
    $("seccion-aliado-extra").classList.add("hidden");
  }

  $("f-nombre").value = esAliado ? "Alear" : `Enemigo (${x},${y})`;
  $("f-clase").value = esAliado ? "Divine Dragon" : "Sword Fighter";
  $("f-nivel").value = "10";
  $("f-hp-actual").value = "30";
  $("f-hp-max").value = "30";

  $("f-stat-str").value = "10";
  $("f-stat-mag").value = "0";
  $("f-stat-dex").value = "10";
  $("f-stat-spd").value = "10";
  $("f-stat-def").value = "8";
  $("f-stat-res").value = "5";
  $("f-stat-lck").value = "5";
  $("f-stat-bld").value = "7";
  $("f-stat-mov").value = "4";

  $("f-arma").value = esAliado ? "Libération" : "Iron Sword";
  if ($("f-arma-forja")) $("f-arma-forja").value = "0";
  if ($("f-arma-grabado")) $("f-arma-grabado").value = "";
  $("f-emblema").value = esAliado ? "Marth" : "";
  establecerLiderTresCasas("Dimitri");
  actualizarSelectorLiderTresCasas();
  state.prevEmblemaModal = esAliado ? "Marth" : "";
  state.prevNivelVinculoModal = 1;
  if ($("f-nivel-vinculo")) {
    $("f-nivel-vinculo").value = "1";
    actualizarTooltipNivelVinculo(1);
  }
  $("f-fusion").checked = false;
  $("f-fusion").disabled = !esAliado;
  $("label-fusion").style.opacity = esAliado ? "1" : "0.5";
  $("label-fusion").style.pointerEvents = esAliado ? "auto" : "none";
  $("label-fusion").title = "";
  limpiarChips("chips-pasivas");
  limpiarChips("chips-inventario");

  if (esAliado) {
    const eInfo = buscarEmblemaInfo("Marth");
    if (eInfo && eInfo.synchro_skills) {
      eInfo.synchro_skills.forEach(s => addChip("chips-pasivas", s));
    }
  }

  renderizarBadgesPotenciadores();
  recalcularCombatStats();

  $("btn-modal-eliminar").classList.add("hidden");
  $("modal-backdrop").classList.remove("hidden");
  $("f-nombre").focus();
}

function abrirModalEdicion(ficha) {
  state.modalModo = "editar";
  state.potenciadoresModal = Array.isArray(ficha.potenciadores_usados) ? [...ficha.potenciadores_usados] : [];
  state.prevEmblemaModal = ficha.emblema_nombre || "";
  $("modal-titulo").textContent = `Editar Unidad: ${ficha.nombre}`;
  $("f-edit-original-name").value = ficha.nombre;
  $("f-x").value = ficha.x;
  $("f-y").value = ficha.y;
  $("label-pos-x").textContent = ficha.x;
  $("label-pos-y").textContent = ficha.y;

  if (ficha.es_aliado) {
    $("f-bando-aliado").checked = true;
    $("seccion-aliado-extra").classList.remove("hidden");
  } else {
    $("f-bando-enemigo").checked = true;
    $("seccion-aliado-extra").classList.add("hidden");
  }

  $("f-nombre").value = ficha.nombre;
  $("f-clase").value = ficha.clase_nombre || "";
  $("f-nivel").value = ficha.nivel || 10;
  
  const hpM = ficha.hp_max || (ficha.stats ? ficha.stats.hp : 30);
  const hpA = (ficha.hp_actual !== undefined && ficha.hp_actual !== null) ? ficha.hp_actual : hpM;
  $("f-hp-actual").value = hpA;
  $("f-hp-max").value = hpM;

  const st = ficha.stats || {};
  $("f-stat-str").value = st.fuerza !== undefined ? st.fuerza : 10;
  $("f-stat-mag").value = st.magia !== undefined ? st.magia : 0;
  $("f-stat-dex").value = st.destreza !== undefined ? st.destreza : 10;
  $("f-stat-spd").value = st.velocidad !== undefined ? st.velocidad : 10;
  $("f-stat-def").value = st.defensa !== undefined ? st.defensa : 8;
  $("f-stat-res").value = st.resistencia !== undefined ? st.resistencia : 5;
  $("f-stat-lck").value = st.suerte !== undefined ? st.suerte : 5;
  $("f-stat-bld").value = st.complexion !== undefined ? st.complexion : 7;
  $("f-stat-mov").value = ficha.mov !== undefined ? ficha.mov : 4;

  const rawArma = ficha.arma_equipada ? (ficha.arma_equipada.nombre || ficha.arma_equipada) : (ficha.arma ? (ficha.arma.nombre || ficha.arma) : "");
  const desglosada = desglosarArmaString(rawArma);
  $("f-arma").value = desglosada.base;
  if ($("f-arma-forja")) $("f-arma-forja").value = desglosada.forja;
  if ($("f-arma-grabado")) $("f-arma-grabado").value = desglosada.grabado;

  $("f-emblema").value = ficha.emblema_nombre || "";
  const nivV = ficha.nivel_vinculo || 1;
  if ($("f-nivel-vinculo")) {
    $("f-nivel-vinculo").value = nivV;
    actualizarTooltipNivelVinculo(nivV);
  }
  state.prevEmblemaModal = ficha.emblema_nombre || "";
  state.prevNivelVinculoModal = nivV;
  establecerLiderTresCasas(ficha.lider_tres_casas || "Dimitri");
  actualizarSelectorLiderTresCasas();

  const tieneEmblema = !!ficha.emblema_nombre;
  const enFusionActiva = (ficha.en_fusion || ficha.turnos_fusion > 0) && (ficha.turnos_fusion > 0);
  $("f-fusion").checked = ficha.en_fusion || false;
  if (enFusionActiva) {
    $("f-fusion").disabled = true;
    $("label-fusion").style.opacity = "0.7";
    $("label-fusion").title = `Fusión en curso: ${ficha.turnos_fusion} turno(s) restante(s). No se puede retirar hasta que acabe.`;
  } else {
    $("f-fusion").disabled = !tieneEmblema;
    $("label-fusion").style.opacity = tieneEmblema ? "1" : "0.5";
    $("label-fusion").style.pointerEvents = tieneEmblema ? "auto" : "none";
    $("label-fusion").title = "";
  }

  // Rellenar chips de habilidades
  limpiarChips("chips-pasivas");
  const habs = Array.isArray(ficha.habilidades) ? ficha.habilidades : (ficha.habilidades ? [ficha.habilidades] : []);
  habs.filter(Boolean).forEach(h => addChip("chips-pasivas", h));

  // Rellenar chips de inventario (todas las armas excepto la equipada principal)
  limpiarChips("chips-inventario");
  if (Array.isArray(ficha.inventario)) {
    ficha.inventario.forEach((item, idx) => {
      if (idx === 0) return; // la primera es la arma equipada, ya está en f-arma
      const nombre = item.nombre || item.arma || "";
      if (nombre) addChip("chips-inventario", nombre);
    });
  }

  renderizarBadgesPotenciadores();
  recalcularCombatStats();

  $("btn-modal-eliminar").classList.remove("hidden");
  $("modal-backdrop").classList.remove("hidden");
}

function cerrarModal() {
  $("modal-backdrop").classList.add("hidden");
}

function esEmblemaTresCasas(nombreEmblema) {
  const nombre = String(nombreEmblema || "").toLowerCase();
  return nombre.includes("edelgard") || nombre.includes("tres casas") || nombre.includes("three houses");
}

function establecerLiderTresCasas(lider) {
  const liderValido = ["Edelgard", "Dimitri", "Claude"].includes(lider) ? lider : "Dimitri";
  const input = document.querySelector(`input[name="f-lider-tres-casas"][value="${liderValido}"]`);
  if (input) input.checked = true;
}

function obtenerLiderTresCasasSeleccionado() {
  const seleccionado = document.querySelector('input[name="f-lider-tres-casas"]:checked');
  return seleccionado ? seleccionado.value : "Dimitri";
}

function actualizarSelectorLiderTresCasas() {
  const seccion = $("seccion-lider-tres-casas");
  if (!seccion) return;
  seccion.classList.toggle("hidden", !esEmblemaTresCasas($("f-emblema")?.value));
}

function actualizarTooltipNivelVinculo(nivel) {
  const inputVinculo = $("f-nivel-vinculo");
  const labelVinculo = document.querySelector('label[for="f-nivel-vinculo"]');
  const n = parseInt(nivel || 1, 10);
  let txt = "";
  if (n >= 20) {
    txt = "Nivel 20: Medidor de recarga de Emblema reducido a 5 cargas (máx 5). 4 turnos de Fusión.";
  } else if (n >= 11) {
    txt = "Nivel 11-19: +1 turno de Fusión (4 turnos). Medidor: 6 cargas.";
  } else {
    txt = "Nivel 1-10: 3 turnos de Fusión. Medidor: 6 cargas.";
  }
  if (inputVinculo) inputVinculo.title = txt;
  if (labelVinculo) labelVinculo.title = txt;
}

function sincronizarEmblemaModal() {
  const val = $("f-emblema") ? $("f-emblema").value.trim() : "";
  const nivelVal = $("f-nivel-vinculo") ? Math.max(1, Math.min(20, parseInt($("f-nivel-vinculo").value || 1, 10))) : 1;
  const tieneEmblema = val.length > 0;

  $("label-fusion").style.opacity = tieneEmblema ? "1" : "0.5";
  $("label-fusion").style.pointerEvents = tieneEmblema ? "auto" : "none";
  if (!tieneEmblema) $("f-fusion").checked = false;
  actualizarSelectorLiderTresCasas();
  actualizarTooltipNivelVinculo(nivelVal);

  const prevEmb = state.prevEmblemaModal || "";
  const prevNiv = state.prevNivelVinculoModal || 1;

  const oldE = buscarEmblemaInfo(prevEmb);
  const newE = buscarEmblemaInfo(val);

  const oldBond = (oldE && prevEmb) ? obtenerDatosVinculoEmblema(oldE, prevNiv) : null;
  const newBond = (newE && val) ? obtenerDatosVinculoEmblema(newE, nivelVal) : null;

  const cambioEmblema = (prevEmb.toLowerCase() !== val.toLowerCase());
  const cambioNivel = (prevNiv !== nivelVal);

  if (cambioEmblema || cambioNivel) {
    // 1. Revertir bonos y pasivas del estado anterior
    if (oldBond) {
      for (const [st, num] of Object.entries(oldBond.stat_boosts || {})) {
        const el = $(`f-stat-${st}`);
        if (el) el.value = Math.max(0, parseInt(el.value || 0, 10) - num);
      }
      (oldBond.synchro_skills || []).forEach(sk => {
        const sNom = sk.nombre || sk.sid || sk;
        const chip = document.querySelector(`#chips-pasivas .chip[data-valor="${sNom}"]`);
        if (chip) chip.remove();
      });
      (oldBond.engage_skills || []).forEach(sk => {
        const sNom = sk.nombre || sk.sid || sk;
        const chip = document.querySelector(`#chips-pasivas .chip[data-valor="${sNom}"]`);
        if (chip) chip.remove();
      });
      if (oldE && oldE.engage_attack) {
        const chipAtk = document.querySelector(`#chips-pasivas .chip[data-valor="${oldE.engage_attack}"]`);
        if (chipAtk) chipAtk.remove();
      }
    }

    // 2. Aplicar nuevos bonos y pasivas
    if (newBond) {
      for (const [st, num] of Object.entries(newBond.stat_boosts || {})) {
        const el = $(`f-stat-${st}`);
        if (el) el.value = parseInt(el.value || 0, 10) + num;
      }
      (newBond.synchro_skills || []).forEach(sk => {
        const sNom = sk.nombre || sk.sid || sk;
        addChip("chips-pasivas", sNom);
      });
      if ($("f-fusion") && $("f-fusion").checked) {
        (newBond.engage_skills || []).forEach(sk => {
          const sNom = sk.nombre || sk.sid || sk;
          addChip("chips-pasivas", sNom);
        });
        if (newE && newE.engage_attack) {
          addChip("chips-pasivas", `${newE.engage_attack}`);
        }
      }

      if (nivelVal === 20 && (cambioNivel || cambioEmblema)) {
        mostrarToast(`Emblema ${newE.nombre} (Nv 20): Medidor de recarga reducido a 5`, "ok");
      } else if (cambioEmblema) {
        mostrarToast(`Emblema ${newE.nombre} (Nv ${nivelVal}): Bonos y pasivas aplicados`, "ok");
      }
    }

    state.prevEmblemaModal = val;
    state.prevNivelVinculoModal = nivelVal;
    recalcularCombatStats();
  }
}

async function guardarUnidadDesdeModal() {
  const nombre = $("f-nombre").value.trim();
  if (!nombre) {
    mostrarToast("Introduce un nombre para la unidad", "error");
    return;
  }

  const esAliado = $("f-bando-aliado").checked;
  const x = parseInt($("f-x").value, 10);
  const y = parseInt($("f-y").value, 10);
  const nivel = parseInt($("f-nivel").value, 10) || 1;
  const hpActual = parseInt($("f-hp-actual").value, 10);
  const hpMax = parseInt($("f-hp-max").value, 10);
  const claseNombre = $("f-clase").value.trim();
  const baseArma = $("f-arma").value.trim();
  const forja = $("f-arma-forja") ? $("f-arma-forja").value : "0";
  const grabado = $("f-arma-grabado") ? $("f-arma-grabado").value : "";
  const armaNombre = construirArmaString(baseArma, forja, grabado);
  const emblemaNombre = $("f-emblema").value.trim();
  const enFusion = $("f-fusion").checked && !!emblemaNombre;

  const nivelVinculo = $("f-nivel-vinculo") ? (parseInt($("f-nivel-vinculo").value, 10) || 1) : 1;
  const str = parseInt($("f-stat-str").value, 10) || 0;
  const mag = parseInt($("f-stat-mag").value, 10) || 0;
  const dex = parseInt($("f-stat-dex").value, 10) || 0;
  const spd = parseInt($("f-stat-spd").value, 10) || 0;
  const def = parseInt($("f-stat-def").value, 10) || 0;
  const res_stat = parseInt($("f-stat-res").value, 10) || 0;
  const lck = parseInt($("f-stat-lck").value, 10) || 0;
  const bld = parseInt($("f-stat-bld").value, 10) || 1;
  const mov = parseInt($("f-stat-mov").value, 10) || 4;

  // Leer chips
  const pasivas = leerChips("chips-pasivas");
  const inventarioExtra = leerChips("chips-inventario");

  // Si editó el nombre de una unidad existente, eliminar la anterior
  const nombreOriginal = $("f-edit-original-name").value;
  if (nombreOriginal && nombreOriginal !== nombre) {
    await api("/api/unidad/eliminar", "POST", { nombre: nombreOriginal });
    const viejo = document.querySelector(`.token[data-nombre="${nombreOriginal}"]`);
    if (viejo) viejo.remove();
    delete state.fichas[nombreOriginal];
  }

  // Construir inventario completo: arma principal equipada + extras
  const inventario = [];
  if (armaNombre) inventario.push({ arma: armaNombre, equipada: true });
  inventarioExtra.forEach(nombre_item => inventario.push({ arma: nombre_item, equipada: false }));

  const fichaExistente = state.fichas[nombreOriginal || nombre];
  const estabaEnFusion = fichaExistente && (fichaExistente.en_fusion || fichaExistente.turnos_fusion > 0) && (fichaExistente.turnos_fusion > 0);
  if (estabaEnFusion) {
    enFusion = true;
  }
  const haActuado = fichaExistente ? !!fichaExistente.ha_actuado : false;
  const cargasRuptura = fichaExistente ? (fichaExistente.cargas_ruptura || 0) : 0;
  const esVolador = fichaExistente ? !!fichaExistente.es_volador : undefined;
  const nivelVeneno = fichaExistente ? (fichaExistente.nivel_veneno || 0) : 0;
  const lider3H = obtenerLiderTresCasasSeleccionado();

  const payload = {
    nombre,
    es_aliado: esAliado,
    x, y,
    nivel,
    ha_actuado: haActuado,
    cargas_ruptura: cargasRuptura,
    nivel_veneno: nivelVeneno,
    lider_tres_casas: lider3H,
    es_volador: esVolador,
    hp_actual: isNaN(hpActual) ? undefined : hpActual,
    hp_max: isNaN(hpMax) ? undefined : hpMax,
    clase_nombre: claseNombre,
    arma_nombre: armaNombre,
    emblema_nombre: emblemaNombre,
    en_fusion: enFusion,
    turnos_fusion: estabaEnFusion ? fichaExistente.turnos_fusion : undefined,
    ataque_emblema_usado: fichaExistente ? fichaExistente.ataque_emblema_usado : undefined,
    nivel_vinculo: nivelVinculo,
    mov: mov,
    potenciadores_usados: state.potenciadoresModal || [],
    stats: {
      hp: isNaN(hpActual) ? hpMax : hpActual,
      hp_max: isNaN(hpMax) ? undefined : hpMax,
      fuerza: str,
      magia: mag,
      destreza: dex,
      velocidad: spd,
      defensa: def,
      resistencia: res_stat,
      suerte: lck,
      complexion: bld
    },
    habilidades: pasivas,
    inventario
  };

  const res = await api("/api/unidad/guardar", "POST", payload);
  if (res.ok && res.ficha) {
    state.fichas[nombre] = res.ficha;
    crearToken(res.ficha);
    autoGuardarLocal();
    cerrarModal();
    mostrarToast(`Unidad '${nombre}' guardada con éxito.`, "ok");
  } else {
    mostrarToast(`Error: ${res.error || "No se pudo guardar"}`, "error");
  }
}

async function eliminarUnidadDesdeModal() {
  const nombre = $("f-edit-original-name").value || $("f-nombre").value.trim();
  if (!nombre) return;

  await api("/api/unidad/eliminar", "POST", { nombre });
  const tok = document.querySelector(`.token[data-nombre="${nombre}"]`);
  if (tok) tok.remove();
  delete state.fichas[nombre];
  autoGuardarLocal();
  cerrarModal();
  mostrarToast(`Ficha '${nombre}' eliminada.`, "info");
}

// ─── Sistema de Chips (tags) para habilidades e inventario ────────────────────

/** Crea un chip en el contenedor indicado */
function addChip(containerId, texto) {
  const texto_limpio = (texto || "").trim();
  if (!texto_limpio) return;
  const container = $(containerId);
  if (!container) return;

  // Evitar duplicados en el mismo contenedor
  const existentes = leerChips(containerId);
  if (existentes.map(s => s.toLowerCase()).includes(texto_limpio.toLowerCase())) return;

  const chip = document.createElement("span");
  chip.className = "chip";
  chip.dataset.valor = texto_limpio;
  chip.innerHTML = `${texto_limpio}<button class="chip-remove" title="Eliminar" type="button">&times;</button>`;
  chip.querySelector(".chip-remove").addEventListener("click", () => chip.remove());
  container.appendChild(chip);
}

/** Devuelve un array con los valores de todos los chips del contenedor */
function leerChips(containerId) {
  const container = $(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll(".chip")).map(c => c.dataset.valor).filter(Boolean);
}

/** Vacía todos los chips de un contenedor */
function limpiarChips(containerId) {
  const container = $(containerId);
  if (container) container.innerHTML = "";
}

/** Conecta un input de texto a su chip-container: Enter o coma añade chip */
function setupChipInput(inputId, containerId, tipo) {
  const input = $(inputId);
  if (!input) return;
  const listId = input.getAttribute("list") || inputId.replace("f-", "list-");
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = input.value.trim().replace(/,+$/, "");
      if (val) {
        addChip(containerId, val);
        input.value = "";
      }
    }
  });
  // También añadir cuando el input pierde el foco y tiene contenido
  input.addEventListener("blur", () => {
    const val = input.value.trim().replace(/,+$/, "");
    if (val) {
      addChip(containerId, val);
      input.value = "";
    }
  });
  // Autocompletado
  if (tipo) setupAutocomplete(inputId, listId, tipo);
}

// ─── Autocompletado con debounce contra /api/catalogo/buscar ───────────────

function setupAutocomplete(inputId, datalistId, tipo) {
  const input = $(inputId);
  const list = $(datalistId);
  if (!input || !list) return;

  let timeout = null;
  input.addEventListener("input", () => {
    clearTimeout(timeout);
    const q = input.value.trim();
    if (q.length < 2) return;

    timeout = setTimeout(async () => {
      try {
        const data = await api(`/api/catalogo/buscar?tipo=${tipo}&q=${encodeURIComponent(q)}`);
        if (data.resultados) {
          list.innerHTML = "";
          data.resultados.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.nombre;
            if (item.categoria === "armas" && item.datos) {
              const us = item.datos.usos_max ? ` (${item.datos.usos_max} usos)` : '';
              const avoTxt = item.datos.avo_bonus ? ` Avo+${item.datos.avo_bonus}` : '';
              const ddgTxt = item.datos.ddg_bonus ? ` Ddg+${item.datos.ddg_bonus}` : '';
              opt.label = `${item.datos.tipo}${us} | Mt ${item.datos.mt} Wt ${item.datos.wt} Hit ${item.datos.hit} Crit ${item.datos.crit || 0}${avoTxt}${ddgTxt}`;
            } else if (item.categoria === "clases" && item.datos) {
              opt.label = `Estilo: ${item.datos.estilo_combate} | Mov ${item.datos.mov}`;
            } else if (item.categoria === "habilidades" && item.datos) {
              const boosts = [];
              if (item.datos.stat_boosts) {
                for (const [s, v] of Object.entries(item.datos.stat_boosts)) {
                  if (v) boosts.push(`${s.toUpperCase()}+${v}`);
                }
              }
              opt.label = boosts.length ? boosts.join(" ") : "Habilidad Pasiva";
            } else if (item.categoria === "emblemas") {
              opt.label = "Emblema";
            }
            list.appendChild(opt);
          });
        }
      } catch (err) {}
    }, 250);
  });
}

function initModalEvents() {
  $("btn-modal-close").addEventListener("click", cerrarModal);
  $("btn-modal-cancelar").addEventListener("click", cerrarModal);
  $("btn-modal-guardar").addEventListener("click", guardarUnidadDesdeModal);
  $("btn-modal-eliminar").addEventListener("click", eliminarUnidadDesdeModal);

  // Botones rápidos de ajuste de HP en el modal
  $("btn-hp-pocion").addEventListener("click", () => {
    const max = parseInt($("f-hp-max").value, 10) || 30;
    const cur = parseInt($("f-hp-actual").value, 10) || 0;
    $("f-hp-actual").value = Math.min(max, cur + 15);
  });
  $("btn-hp-full").addEventListener("click", () => {
    const max = parseInt($("f-hp-max").value, 10) || 30;
    $("f-hp-actual").value = max;
  });
  $("btn-hp-menos5").addEventListener("click", () => {
    const cur = parseInt($("f-hp-actual").value, 10) || 0;
    $("f-hp-actual").value = Math.max(0, cur - 5);
  });

  // ─── Autorellenado Inteligente de Atributos desde el Catálogo ────────────────
  async function autoRellenarStatsDesdeCatalogo() {
    const nombre = $("f-nombre")?.value.trim() || "";
    if (!nombre || nombre.length < 2) return;

    const clase = $("f-clase")?.value.trim() || "";
    const nivel = parseInt($("f-nivel")?.value, 10) || 0;
    const esAliado = $("f-bando-aliado")?.checked ?? true;
    const emblema = $("f-emblema")?.value.trim() || "";

    try {
      const res = await api("/api/unidad/resolver_preview", "POST", {
        nombre: nombre,
        clase_nombre: clase,
        nivel: nivel,
        es_aliado: esAliado,
        emblema_nombre: emblema,
        nivel_vinculo: $("f-nivel-vinculo") ? (parseInt($("f-nivel-vinculo").value, 10) || 1) : 1,
        potenciadores_usados: state.potenciadoresModal || []
      });

      if (res && res.ok && res.stats) {
        if (res.clase_nombre && (!$("f-clase").value || $("f-clase").value.trim() === "")) {
          $("f-clase").value = res.clase_nombre;
        }
        if (res.nivel && (!$("f-nivel").value || $("f-nivel").value === "10" || $("f-nivel").value === "" || $("f-nivel").value === "0")) {
          $("f-nivel").value = res.nivel;
        }
        if (res.hp_max) {
          $("f-hp-max").value = res.hp_max;
          if (state.modalModo === "crear" || parseInt($("f-hp-actual").value, 10) > res.hp_max || parseInt($("f-hp-actual").value, 10) === 30) {
            $("f-hp-actual").value = res.hp_actual || res.hp_max;
          }
        }
        if (res.stats.fuerza !== undefined) $("f-stat-str").value = res.stats.fuerza;
        if (res.stats.magia !== undefined) $("f-stat-mag").value = res.stats.magia;
        if (res.stats.destreza !== undefined) $("f-stat-dex").value = res.stats.destreza;
        if (res.stats.velocidad !== undefined) $("f-stat-spd").value = res.stats.velocidad;
        if (res.stats.defensa !== undefined) $("f-stat-def").value = res.stats.defensa;
        if (res.stats.resistencia !== undefined) $("f-stat-res").value = res.stats.resistencia;
        if (res.stats.suerte !== undefined) $("f-stat-lck").value = res.stats.suerte;
        if (res.stats.complexion !== undefined) $("f-stat-bld").value = res.stats.complexion;
        if (res.mov !== undefined) $("f-stat-mov").value = res.mov;

        if (res.arma_nombre && (!$("f-arma").value || $("f-arma").value.trim() === "")) {
          const dArma = desglosarArmaString(res.arma_nombre);
          $("f-arma").value = dArma.base;
          if ($("f-arma-forja")) $("f-arma-forja").value = dArma.forja;
          if ($("f-arma-grabado")) $("f-arma-grabado").value = dArma.grabado;
        }

        recalcularCombatStats();
        mostrarToast(`Datos de ${res.nombre} (Nv ${res.nivel}) cargados del catálogo`, "info");
      }
    } catch (e) {
      console.warn("Error en autoRellenarStatsDesdeCatalogo:", e);
    }
  }

  // Listeners de autorellenado al elegir/cambiar Nombre, Clase o Nivel
  $("f-nombre").addEventListener("change", autoRellenarStatsDesdeCatalogo);
  $("f-nombre").addEventListener("blur", () => {
    if ($("f-nombre").value.trim().length >= 3) autoRellenarStatsDesdeCatalogo();
  });
  $("f-clase").addEventListener("change", autoRellenarStatsDesdeCatalogo);
  $("f-clase").addEventListener("blur", () => {
    if ($("f-clase").value.trim().length >= 3) autoRellenarStatsDesdeCatalogo();
  });
  $("f-nivel").addEventListener("change", autoRellenarStatsDesdeCatalogo);
  $("f-nivel").addEventListener("input", () => {
    clearTimeout(state.timerNivel);
    state.timerNivel = setTimeout(autoRellenarStatsDesdeCatalogo, 350);
  });

  // Toggle de radio buttons para mostrar/ocultar sección extra de aliado
  $("f-bando-aliado").addEventListener("change", () => {
    $("seccion-aliado-extra").classList.remove("hidden");
  });
  $("f-bando-enemigo").addEventListener("change", () => {
    $("seccion-aliado-extra").classList.add("hidden");
  });

  // Habilitar checkbox de fusión, auto-aplicar pasivas y modificadores del Emblema
  $("f-emblema").addEventListener("input", sincronizarEmblemaModal);
  $("f-emblema").addEventListener("change", sincronizarEmblemaModal);
  if ($("f-nivel-vinculo")) {
    $("f-nivel-vinculo").addEventListener("input", sincronizarEmblemaModal);
    $("f-nivel-vinculo").addEventListener("change", sincronizarEmblemaModal);
  }

  $("f-fusion").addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    const nombreOriginal = $("f-edit-original-name") ? $("f-edit-original-name").value : "";
    const fichaExistente = state.fichas[nombreOriginal];
    if (fichaExistente && (fichaExistente.en_fusion || fichaExistente.turnos_fusion > 0) && fichaExistente.turnos_fusion > 0 && !isChecked) {
      e.target.checked = true;
      mostrarToast(`La fusión no puede retirarse manualmente. Quedan ${fichaExistente.turnos_fusion} turno(s).`, "info");
      return;
    }
    const eInfo = buscarEmblemaInfo($("f-emblema").value);
    if (!eInfo) return;
    const nivelVal = $("f-nivel-vinculo") ? (parseInt($("f-nivel-vinculo").value, 10) || 1) : 1;
    const bond = obtenerDatosVinculoEmblema(eInfo, nivelVal);

    if (isChecked) {
      if (bond && bond.engage_skills) {
        bond.engage_skills.forEach(sk => addChip("chips-pasivas", sk.nombre || sk.sid || sk));
      }
      if (eInfo.engage_attack) {
        addChip("chips-pasivas", `${eInfo.engage_attack}`);
      }
      mostrarToast(`Fusión Engage con ${eInfo.nombre} activada!`, "ok");
    } else {
      if (bond && bond.engage_skills) {
        bond.engage_skills.forEach(sk => {
          const sNom = sk.nombre || sk.sid || sk;
          const chip = document.querySelector(`#chips-pasivas .chip[data-valor="${sNom}"]`);
          if (chip) chip.remove();
        });
      }
      if (eInfo.engage_attack) {
        const chipAtk = document.querySelector(`#chips-pasivas .chip[data-valor="${eInfo.engage_attack}"]`);
        if (chipAtk) chipAtk.remove();
      }
      mostrarToast(`Fusión desactivada`, "info");
    }
    recalcularCombatStats();
  });

  // Listeners para recalcular estadísticas de combate en vivo
  ["f-stat-str", "f-stat-mag", "f-stat-dex", "f-stat-spd", "f-stat-def", "f-stat-res", "f-stat-lck", "f-stat-bld", "f-stat-mov", "f-arma", "f-arma-forja", "f-arma-grabado"].forEach(id => {
    const el = $(id);
    if (el) {
      el.addEventListener("input", recalcularCombatStats);
      el.addEventListener("change", recalcularCombatStats);
    }
  });

  // Autocompletados de campos simples
  setupAutocomplete("f-nombre", "list-personajes", "personajes");
  setupAutocomplete("f-clase", "list-clases", "clases");
  setupAutocomplete("f-arma", "list-armas", "armas");
  setupAutocomplete("f-emblema", "list-emblemas", "emblemas");

  // Chip inputs: habilidades e inventario
  setupChipInput("f-pasivas", "chips-pasivas", "habilidades");
  setupChipInput("f-inventario", "chips-inventario", "armas");

  // Botones de potenciadores rápidos en el modal
  document.querySelectorAll(".btn-booster").forEach(btn => {
    btn.addEventListener("click", () => {
      const stat = btn.dataset.stat;
      const val = parseInt(btn.dataset.val, 10) || 1;
      const nom = btn.dataset.nom;

      if (stat === "hp") {
        $("f-hp-max").value = parseInt($("f-hp-max").value || 30, 10) + val;
        $("f-hp-actual").value = parseInt($("f-hp-actual").value || 30, 10) + val;
      } else if (stat === "mov") {
        $("f-stat-mov").value = parseInt($("f-stat-mov").value || 4, 10) + val;
      } else if (stat === "tonico") {
        ["str", "mag", "dex", "spd", "def", "res"].forEach(s => {
          const el = $(`f-stat-${s}`);
          if (el) el.value = parseInt(el.value || 0, 10) + 2;
        });
      } else {
        const el = $(`f-stat-${stat}`);
        if (el) el.value = parseInt(el.value || 0, 10) + val;
      }

      if (!state.potenciadoresModal) state.potenciadoresModal = [];
      state.potenciadoresModal.push(nom);
      renderizarBadgesPotenciadores();
      recalcularCombatStats();
      mostrarToast(`Potenciador aplicado: ${nom}`, "ok");
    });
  });

  // Botones de la toolbar
  $("btn-add-aliado").addEventListener("click", () => abrirModalCreacion(4, 8, true));
  $("btn-add-enemigo").addEventListener("click", () => abrirModalCreacion(16, 8, false));
  
  $("btn-preset-cap7").addEventListener("click", async () => {
    const selDif = $("select-dificultad");
    const dificultad = selDif ? selDif.value : "Hard";
    const res = await api("/api/preset/capitulo7", "POST", { dificultad });
    if (res.ok && res.fichas) {
      actualizarTokens(res.fichas);
      mostrarToast(`${res.mensaje || "Preset cargado con éxito"}`, "ok");
      setTimeout(lanzarAnalisis, 250);
    }
  });

  if ($("select-dificultad")) {
    $("select-dificultad").addEventListener("change", () => {
      $("btn-preset-cap7").click();
    });
  }

  $("btn-limpiar").addEventListener("click", async () => {
    const res = await api("/api/tablero/limpiar", "POST", {});
    actualizarTokens([]);
    $("analisis-scroll").innerHTML = "";
    localStorage.removeItem("engage_tracker_partida_local");
    mostrarToast("Tablero limpio: todas las fichas eliminadas", "info");
  });

  // Gestión de Escuadrón Persistente
  $("btn-guardar-squad").addEventListener("click", async () => {
    const res = await api("/api/escuadron/guardar", "POST", {});
    if (res.ok) {
      mostrarToast(`${res.mensaje || "Escuadrón guardado con éxito"}`, "ok");
    } else {
      mostrarToast(`Error al guardar escuadrón: ${res.error}`, "error");
    }
  });

  $("btn-desplegar-squad").addEventListener("click", async () => {
    const res = await api("/api/escuadron/desplegar", "POST", {});
    if (res.ok && res.fichas) {
      actualizarTokens(res.fichas);
      mostrarToast(`${res.mensaje || "Escuadrón desplegado"}`, "ok");
      setTimeout(lanzarAnalisis, 250);
    } else {
      mostrarToast(`${res.error || "No hay escuadrón guardado"}`, "error");
    }
  });

  // Exportar / Importar Partida en JSON
  $("btn-exportar-partida").addEventListener("click", async () => {
    const res = await api("/api/partida/exportar", "GET");
    if (res.ok && res.partida) {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(res.partida, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `partida_engage_turno${res.partida.turno_actual || 1}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      mostrarToast("Archivo de partida descargado", "ok");
    }
  });

  $("input-importar-partida").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (evt) => {
      try {
        const partida = JSON.parse(evt.target.result);
        const res = await api("/api/partida/importar", "POST", { partida });
        if (res.ok && res.fichas) {
          actualizarTokens(res.fichas);
          state.turno = partida.turno_actual || 1;
          state.fase = partida.fase || "jugador";
          actualizarBadge();
          mostrarToast(`Partida importada con éxito (${res.fichas.length} unidades)`, "ok");
          setTimeout(lanzarAnalisis, 250);
        } else {
          mostrarToast(`Error al importar: ${res.error}`, "error");
        }
      } catch (err) {
        mostrarToast("El archivo seleccionado no es un JSON válido", "error");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  });
}

// ─── Botones de Análisis y Turnos ──────────────────────────────────────────

async function lanzarAnalisis() {
  const panel = $("analisis-scroll");
  panel.innerHTML = '<div class="loader">Calculando peor caso y amenazas…</div>';

  try {
    const perfil = $("perfil-select") ? $("perfil-select").value : "seguro";
    const data = await api("/api/analizar", "POST", { perfil });

    const countBadge = $("analisis-badge-count");
    if (countBadge) {
      if (data && data.resultados && data.resultados.length > 0) {
        countBadge.textContent = data.resultados.length;
        countBadge.classList.remove("hidden");
      } else {
        countBadge.classList.add("hidden");
      }
    }

    panel.innerHTML = "";
    if (!data || !data.resultados || data.resultados.length === 0) {
      const msg = (data && data.error)
        ? `Error en análisis: ${data.error}`
        : 'No hay unidades configuradas con stats y armas. Haz clic en el mapa para añadir fichas o pulsa [Preset Cap. 7].';
      panel.innerHTML = `<p style="color:var(--text-dim);padding:8px;font-size:12px;">${msg}</p>`;
      return;
    }

    data.resultados.forEach(r => renderResultado(panel, r));
  } catch (err) {
    console.error("Error en lanzarAnalisis:", err);
    panel.innerHTML = `<p style="color:var(--red);padding:8px;font-size:12px;">Error al calcular el análisis: ${err.message}</p>`;
  }
}

$("btn-analizar").addEventListener("click", lanzarAnalisis);

// ── Cronogema (Deshacer / Time Crystal) ──────────────────────────────────
$("btn-deshacer").addEventListener("click", async () => {
  const res = await api("/api/tablero/deshacer", "POST", {});
  if (res.ok) {
    if (res.fichas) {
      actualizarTokens(res.fichas);
    }
    state.turno = res.turno || state.turno;
    state.fase = res.fase || state.fase;
    actualizarBadge();
    mostrarToast(res.mensaje || "⏱️ Acción deshecha con la Cronogema", "info");
    setTimeout(lanzarAnalisis, 250);
  } else {
    mostrarToast(res.mensaje || "No hay más acciones previas para deshacer", "error");
  }
});

// Atajo de teclado: Ctrl+Z / Cmd+Z para Cronogema (Deshacer)
window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
    if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      return;
    }
    e.preventDefault();
    $("btn-deshacer").click();
  }
});

// ── Reactivar Acciones de Turno ──────────────────────────────────────────
$("btn-reactivar").addEventListener("click", async () => {
  const res = await api("/api/turno/reiniciar_acciones", "POST", {});
  if (res.ok && res.fichas) {
    actualizarTokens(res.fichas);
    mostrarToast("Acciones reactivadas para todos los aliados", "ok");
    setTimeout(lanzarAnalisis, 250);
  }
});

$("btn-turno-fin").addEventListener("click", async () => {
  if (state.fase === "jugador") {
    const res = await api("/api/turno/inicio_fase_enemigo", "POST");
    if (res && res.ok) {
      state.fase = res.fase || "enemigo";
      actualizarBadge();
      if (res.fichas) {
        actualizarTokens(res.fichas);
      }
    }
    $("btn-turno-fin").textContent = "Confirmar Turno Enemigo";
    $("btn-turno-fin").style.color = "var(--red)";
    mostrarToast("Fase Enemiga: puedes aplicar los ataques enemigos previstos o mover sus tokens.", "info");
    setTimeout(lanzarAnalisis, 250);
  } else {
    const res = await api("/api/turno/fin", "POST");
    if (res && res.ok) {
      state.fase = res.fase;
      state.turno = res.turno;
      actualizarBadge();
      if (res.fichas) {
        actualizarTokens(res.fichas);
      }
    }
    $("btn-turno-fin").textContent = "Turno Enemigo";
    $("btn-turno-fin").style.color = "";
    mostrarToast(`Turno ${state.turno} — Fase del jugador`, "ok");
    setTimeout(lanzarAnalisis, 350);
  }
});

$("btn-reset").addEventListener("click", async () => {
  const res = await api("/api/reset", "POST", {});
  if (res && res.ok) {
    state.turno = res.turno || 1;
    state.fase = res.fase || "jugador";
    actualizarBadge();
    actualizarTokens(res.fichas || []);
    $("analisis-scroll").innerHTML = "";
    localStorage.removeItem("engage_tracker_partida_local");
    mostrarToast("Tablero reiniciado al Turno 1", "ok");
    setTimeout(lanzarAnalisis, 350);
  }
});

// ─── Ejecución Interactiva de Jugadas y Combate ────────────────────────────

async function ejecutarJugada(r) {
  const payload = {
    atacante: r.aliado,
    defensor: r.enemigo,
    arma_nombre: r.arma_recomendada,
    pos_destino: r.pos_sugerida,
    pos_canter: r.pos_canter || null
  };

  const res = await api("/api/combate/ejecutar", "POST", payload);
  if (res.error) {
    mostrarToast(`${res.error}`, "error");
    return;
  }

  if (res.fichas) {
    actualizarTokens(res.fichas);
  }

  const atk = res.atacante;
  const dfn = res.defensor;
  const c = res.combate;
  const atkInfo = c.atacante;
  const kill = dfn.hp_actual <= 0;

  let toastMsg = "";
  if (kill) {
    toastMsg = `${atk.nombre} atacó a ${dfn.nombre} con ${r.arma_recomendada || 'Arma'} (${atkInfo.daño_total_ronda} dmg) -> ¡${dfn.nombre} DERROTADO!`;
  } else {
    toastMsg = `${atk.nombre} infligió ${atkInfo.daño_total_ronda} dmg a ${dfn.nombre}. Queda en ${dfn.hp_actual}/${dfn.hp_max} HP.`;
  }

  const resComb = c && c.resultado ? c.resultado : {};
  const smash = resComb.smash || null;
  if (resComb.aplica_ruptura && !kill && !(smash && smash.rompio_por_choque)) {
    toastMsg += ` ¡Ruptura! ${dfn.nombre} pierde la guardia (no podrá contraatacar).`;
  }

  if (smash && smash.ocurrido) {
    if (smash.empujado && smash.nueva_pos) {
      toastMsg += ` ¡Smash! ${dfn.nombre} empujado a (${smash.nueva_pos[0]}, ${smash.nueva_pos[1]}).`;
    } else if (smash.rompio_por_choque) {
      toastMsg += ` ¡Smash! ${dfn.nombre} chocó contra obstáculo y sufrió RUPTURA (Break).`;
    }
  }

  if (res.canter_aplicado) {
    toastMsg += ` Canter: refugio en (${res.canter_aplicado[0]}, ${res.canter_aplicado[1]}).`;
  } else if (res.aviso_canter) {
    toastMsg += ` ${res.aviso_canter}`;
  }

  mostrarToast(toastMsg, kill ? "ok" : "info");

  // Re-evaluar automáticamente tras el combate para continuar ofreciendo jugadas con los aliados restantes
  setTimeout(lanzarAnalisis, 400);
}

async function ejecutarAtaqueEnemigo(r) {
  const payload = {
    atacante: r.enemigo,
    defensor: r.aliado,
    arma_nombre: r.arma_recomendada || "",
    pos_destino: r.pos_sugerida || null
  };

  const res = await api("/api/combate/ejecutar", "POST", payload);
  if (res.error) {
    mostrarToast(`${res.error}`, "error");
    return;
  }

  if (res.fichas) {
    actualizarTokens(res.fichas);
  }

  const dfn = res.defensor;
  const kill = dfn.hp_actual <= 0;
  mostrarToast(
    `${r.enemigo} atacó a ${r.aliado}. ${r.aliado} queda en ${dfn.hp_actual}/${dfn.hp_max} HP.`,
    kill ? "error" : "info"
  );

  setTimeout(lanzarAnalisis, 400);
}

async function ejecutarCuracion(r) {
  if (r.pos_sugerida) {
    const movRes = await api("/api/mover", "POST", {
      nombre: r.aliado,
      x: r.pos_sugerida[0],
      y: r.pos_sugerida[1]
    });
    if (movRes.error) {
      mostrarToast(`No se pudo colocar al curandero: ${movRes.error}`, "error");
      return;
    }
    if (movRes.fichas) actualizarTokens(movRes.fichas);
  }
  const obj = state.fichas[r.objetivo];
  if (obj) {
    const cur = r.curacion_estimada || 10;
    const nuevoHp = Math.min(obj.hp_max, (obj.hp_actual || obj.stats?.hp || 0) + cur);
    const res = await api("/api/unidad/ajustar_hp", "POST", { nombre: r.objetivo, hp_actual: nuevoHp });
    if (res.fichas) actualizarTokens(res.fichas);
  }
  await api("/api/unidad/alternar_actuado", "POST", { nombre: r.aliado });
  mostrarToast(`${r.aliado} usó ${r.baston} en ${r.objetivo} (+${r.curacion_estimada} HP)`, "ok");
  setTimeout(lanzarAnalisis, 400);
}

async function ejecutarPocion(r) {
  const ali = state.fichas[r.aliado];
  if (ali) {
    const cur = (r.item && r.item.toLowerCase().includes("elixir")) ? 15 : 10;
    const nuevoHp = Math.min(ali.hp_max, (ali.hp_actual || ali.stats?.hp || 0) + cur);
    const res = await api("/api/unidad/ajustar_hp", "POST", { nombre: r.aliado, hp_actual: nuevoHp });
    if (res.fichas) actualizarTokens(res.fichas);
  }
  await api("/api/unidad/alternar_actuado", "POST", { nombre: r.aliado });
  mostrarToast(`${r.aliado} usó ${r.item} (+HP recuperados)`, "ok");
  setTimeout(lanzarAnalisis, 400);
}

// ─── Render de resultados ──────────────────────────────────────────────────

function renderResultado(container, r) {
  if (r.error) {
    const card = document.createElement("div");
    card.className = "riesgo-card riesgo-moderado";
    card.innerHTML = `<header>${r.aliado} vs ${r.enemigo}</header><p style="font-size:11px;color:var(--text-dim);">${r.error}</p>`;
    container.appendChild(card);
    return;
  }

  const v = r.veredicto || {};
  const nivel = v.nivel_riesgo || "bajo";

  const card = document.createElement("div");
  card.className = `riesgo-card riesgo-${nivel}`;

  const header = document.createElement("header");
  let icon = "";
  if (r.tipo_analisis === "amenaza_enemiga") icon = "";
  else if (r.tipo_analisis === "oportunidad_jugador") icon = "";

  header.innerHTML = `
    <span>${icon} ${r.aliado} vs ${r.enemigo}</span>
    <span class="badge badge-${nivel}">${nivel.toUpperCase()}</span>
  `;
  card.appendChild(header);

  if (v.motivos && v.motivos.length > 0) {
    const ul = document.createElement("ul");
    ul.className = "motivos-list";
    v.motivos.forEach(m => {
      const li = document.createElement("li");
      li.textContent = m;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  if (v.peor_caso_espacial && v.peor_caso_espacial.pos_optima) {
    const pe = v.peor_caso_espacial;
    const div = document.createElement("div");
    div.className = "peor-caso-box";
    div.innerHTML = `<b>Peor caso IA:</b> atacará desde (${pe.pos_optima[0]}, ${pe.pos_optima[1]}) haciendo ${pe.daño_proyectado} de daño a dist. ${pe.distancia_ataque}.`;
    card.appendChild(div);
  }

  if (r.chain_attacks && r.chain_attacks.length > 0) {
    const isEnemy = (r.tipo_analisis === "amenaza_enemiga");
    const chainBox = document.createElement("div");
    chainBox.className = `chain-attack-box ${isEnemy ? 'enemy-chain' : ''}`;
    r.chain_attacks.forEach(ca => {
      const item = document.createElement("div");
      item.className = "chain-attack-item";
      const targetName = isEnemy ? r.aliado : r.enemigo;
      item.innerHTML = `<b>Chain Attack (80% Hit):</b> La unidad <b>${ca.nombre}</b> puede realizar ataque en cadena contra <b>${targetName}</b> haciendo <b>${ca.daño} dmg</b> (10% HP).`;
      chainBox.appendChild(item);
    });
    const sub = document.createElement("div");
    sub.className = "chain-attack-sub";
    sub.textContent = isEnemy ? "Y luego el ataque del enemigo:" : "Y luego el ataque normal del aliado:";
    chainBox.appendChild(sub);
    card.appendChild(chainBox);
  }

  // Pasivas activas de combate y proximidad
  if (r.pasivas_activas && r.pasivas_activas.length > 0) {
    const passBox = document.createElement("div");
    passBox.className = "passivas-box";
    passBox.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin:6px 0;padding:4px 8px;background:rgba(218,165,32,0.12);border-left:3px solid #daa520;border-radius:4px;font-size:11px;";
    passBox.innerHTML = `<span style="font-weight:bold;color:#ffd700;">Pasivas:</span> ` +
      r.pasivas_activas.map(p => `<span class="badge" style="background:#2a2510;border:1px solid #b8860b;color:#ffd700;padding:1px 6px;border-radius:3px;">${p}</span>`).join(" ");
    card.appendChild(passBox);
  }

  // Bonificaciones de apoyo (C, B, A)
  if (r.apoyos_activos && r.apoyos_activos.length > 0) {
    const suppBox = document.createElement("div");
    suppBox.className = "apoyos-box";
    suppBox.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 6px 0;padding:4px 8px;background:rgba(70,130,180,0.12);border-left:3px solid #4682b4;border-radius:4px;font-size:11px;";
    suppBox.innerHTML = `<span style="font-weight:bold;color:#87cefa;">Apoyos:</span> ` +
      r.apoyos_activos.map(ap => `<span class="badge" style="background:#102030;border:1px solid #4682b4;color:#87cefa;padding:1px 6px;border-radius:3px;">${ap.aliado} (Rango ${ap.rango}): +${ap.hit} Hit, +${ap.avo} Avo</span>`).join(" ");
    card.appendChild(suppBox);
  }

  // Banner especial táctico de Emblema
  if (r.tactica_emblema === "burst") {
    const embBox = document.createElement("div");
    embBox.style.cssText = "margin:4px 0 6px 0;padding:4px 8px;background:linear-gradient(90deg, rgba(138,43,226,0.25), rgba(75,0,130,0.15));border-left:3px solid #9932cc;border-radius:4px;font-size:11px;font-weight:bold;color:#da70d6;";
    embBox.innerHTML = `<b>BURST DE EMBLEMA SUGERIDO:</b> Fusión de Emblema lista para rematar al Jefe sin contraataque peligroso.`;
    card.appendChild(embBox);
  }

  // Badge de exposición a líneas de peligro enemigas (Danger Zone de Engage)
  if (r.tipo_analisis === "oportunidad_jugador" && r.num_amenazas_destino !== undefined) {
    const dangerBox = document.createElement("div");
    dangerBox.style.cssText = "display:inline-flex;align-items:center;gap:6px;margin:3px 0 6px 0;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;";
    if (r.num_amenazas_destino === 0) {
      dangerBox.style.background = "rgba(40, 167, 69, 0.18)";
      dangerBox.style.border = "1px solid #28a745";
      dangerBox.style.color = "#a3e635";
      dangerBox.innerHTML = `Casilla 100% segura (0 enemigos alcanzan esta casilla tras atacar)`;
    } else if (r.num_amenazas_destino === 1) {
      dangerBox.style.background = "rgba(255, 193, 7, 0.18)";
      dangerBox.style.border = "1px solid #ffc107";
      dangerBox.style.color = "#fde047";
      const nomE = (r.amenazas_en_destino && r.amenazas_en_destino[0]) || "1 enemigo";
      dangerBox.innerHTML = `Al alcance de 1 enemigo tras atacar: ${nomE}`;
    } else {
      dangerBox.style.background = "rgba(220, 53, 69, 0.22)";
      dangerBox.style.border = "1px solid #dc3545";
      dangerBox.style.color = "#f87171";
      const listaE = (r.amenazas_en_destino || []).slice(0, 3).join(", ");
      dangerBox.innerHTML = `Al alcance de ${r.num_amenazas_destino} enemigos tras atacar (${listaE})`;
    }
    card.appendChild(dangerBox);
  }

  if (r.recomendacion) {
    const p = document.createElement("p");
    p.className = "recomendacion-txt";
    p.textContent = r.recomendacion;
    card.appendChild(p);
  }

  // Si el aliado tiene el Emblema Tres Casas, permitir alternar de líder directamente desde la tarjeta
  const fichaAli = state.fichas ? state.fichas[r.aliado] : null;
  const es3H = fichaAli && (
    (fichaAli.emblema_nombre || "").toLowerCase().includes("edelgard") ||
    (fichaAli.emblema_nombre || "").toLowerCase().includes("three houses") ||
    (fichaAli.emblema_nombre || "").toLowerCase().includes("tres casas") ||
    (fichaAli.emblema_nombre || "").toLowerCase().includes("brazalete")
  );
  if (es3H && r.tipo_analisis === "oportunidad_jugador") {
    const liderActivo = fichaAli.lider_tres_casas || "Dimitri";
    const div3H = document.createElement("div");
    div3H.style.cssText = "display:flex;align-items:center;gap:6px;margin:4px 0 6px 0;padding:4px 8px;background:rgba(218,165,32,0.12);border:1px solid rgba(218,165,32,0.3);border-radius:4px;font-size:11px;";
    div3H.innerHTML = `<span style="color:#ffd700;font-weight:bold;">Líder 3H:</span>`;
    [
      { id: "Edelgard", label: "Edelgard (Hachas)" },
      { id: "Dimitri",  label: "Dimitri (Lanzas)" },
      { id: "Claude",   label: "Claude (Arcos)" }
    ].forEach(lObj => {
      const btnL = document.createElement("button");
      btnL.type = "button";
      const activo = (lObj.id.toLowerCase() === (liderActivo || "").toLowerCase());
      btnL.className = activo ? "btn-primary" : "btn-secondary";
      btnL.style.cssText = "padding:2px 8px;font-size:10px;line-height:1.2;cursor:pointer;";
      btnL.textContent = lObj.label;
      btnL.title = `Cambiar líder activo a ${lObj.id} para Weapon Sync y Gambits`;
      btnL.addEventListener("click", async (e) => {
        e.stopPropagation();
        const res = await api("/api/unidad/alternar_lider_tres_casas", "POST", { nombre: r.aliado, lider: lObj.id });
        if (res && res.ok) {
          if (res.fichas) actualizarTokens(res.fichas);
          mostrarToast(`Líder Tres Casas cambiado a ${lObj.id} (${r.aliado})`, "ok");
          lanzarAnalisis();
        }
      });
      div3H.appendChild(btnL);
    });
    card.appendChild(div3H);
  }

  // Botones de acción según el tipo de análisis
  if (r.tipo_analisis === "oportunidad_jugador") {
    const actionBar = document.createElement("div");
    actionBar.className = "card-action-bar";
    const btnExec = document.createElement("button");
    btnExec.type = "button";
    btnExec.className = "btn-ejecutar-jugada";

    let labelPos = "";
    if (r.pos_sugerida && Array.isArray(r.pos_sugerida)) {
      labelPos = ` [Mover a (${r.pos_sugerida[0]},${r.pos_sugerida[1]})]`;
    }
    const labelCanter = r.pos_canter ? ` -> Canter (${r.pos_canter[0]},${r.pos_canter[1]})` : "";
    btnExec.innerHTML = `<b>Ejecutar Jugada</b>${labelPos}${labelCanter}`;
    btnExec.title = `Mueve a ${r.aliado} a la casilla óptima y ataca a ${r.enemigo} con ${r.arma_recomendada || 'Arma'}`;
    btnExec.addEventListener("click", () => ejecutarJugada(r));
    actionBar.appendChild(btnExec);
    card.appendChild(actionBar);
  } else if (r.tipo_analisis === "apoyo_curacion") {
    const actionBar = document.createElement("div");
    actionBar.className = "card-action-bar";
    const btnHeal = document.createElement("button");
    btnHeal.type = "button";
    btnHeal.className = "btn-ejecutar-jugada";
    btnHeal.style.background = "linear-gradient(135deg, #1e7e34, #28a745)";
    btnHeal.innerHTML = `<b>Usar ${r.baston || 'Bastón'}</b> en ${r.objetivo} (+${r.curacion_estimada} HP)`;
    btnHeal.addEventListener("click", () => ejecutarCuracion(r));
    actionBar.appendChild(btnHeal);
    card.appendChild(actionBar);
  } else if (r.tipo_analisis === "uso_pocion") {
    const actionBar = document.createElement("div");
    actionBar.className = "card-action-bar";
    const btnPot = document.createElement("button");
    btnPot.type = "button";
    btnPot.className = "btn-ejecutar-jugada";
    btnPot.style.background = "linear-gradient(135deg, #d39e00, #ffc107);color:#111;";
    btnPot.innerHTML = `<b>Usar ${r.item || 'Poción'}</b> (+HP)`;
    btnPot.addEventListener("click", () => ejecutarPocion(r));
    actionBar.appendChild(btnPot);
    card.appendChild(actionBar);
  } else if (r.tipo_analisis === "amenaza_enemiga") {
    // El botón de aplicar ataque enemigo SOLO se muestra durante la Fase Enemiga
    if (state.fase === "enemigo") {
      const actionBar = document.createElement("div");
      actionBar.className = "card-action-bar";
      const btnDmg = document.createElement("button");
      btnDmg.type = "button";
      btnDmg.className = "btn-recibir-daño";
      btnDmg.innerHTML = `Aplicar Ataque Enemigo`;
      btnDmg.title = `Aplica el ataque de ${r.enemigo} sobre ${r.aliado} restando HP en el tablero`;
      btnDmg.addEventListener("click", () => ejecutarAtaqueEnemigo(r));
      actionBar.appendChild(btnDmg);
      card.appendChild(actionBar);
    }
  }

  container.appendChild(card);
}

// ─── Badge y Toast ─────────────────────────────────────────────────────────

function actualizarBadge() {
  const faseLabel = state.fase === "jugador" ? "Fase Jugador" : "Fase Enemigo";
  $("turno-badge").innerHTML = `Turno <span>${state.turno}</span> · ${faseLabel}`;
}

function mostrarToast(msg, tipo = "info") {
  const t = document.createElement("div");
  t.className = `toast toast-${tipo}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("show"), 10);
  setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => t.remove(), 300);
  }, 2500);
}

// ─── Inicialización ────────────────────────────────────────────────────────

async function init() {
  await cargarCatalogoEmblemas();
  const estado = await api("/api/estado");
  const ancho = estado.mapa ? estado.mapa.ancho : 24;
  const alto  = estado.mapa ? estado.mapa.alto  : 17;

  state.turno = estado.turno || 1;
  state.fase  = estado.fase  || "jugador";
  actualizarBadge();

  buildGrid(ancho, alto);
  initModalEvents();

  const restaurado = await restaurarDesdeLocalStorage();
  if (!restaurado && estado.fichas) {
    actualizarTokens(estado.fichas);
  }
}

document.addEventListener("DOMContentLoaded", init);
