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
  modalModo: "crear", // "crear" | "editar" | "roster" (edita el roster del navegador, no el tablero)
  nombrePrecargadoRoster: "", // último nombre volcado al modal (roster o catálogo): evita recargas repetidas
  statsEditadosManualmente: false, // true si el usuario tocó stats/HP a mano: el catálogo ya no las pisa
  fusionActivandoseEnModal: false, // true entre marcar "Activar Fusión" y guardar/cerrar el modal
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

            // No pisar el título de un objeto de mapa / casilla objetivo ya pintado
            if (celda.dataset.objetoId || celda.classList.contains("objetivo-derrota") || celda.classList.contains("objetivo-victoria")) {
              celda.title = `${celda.title} · ${perks.join(" · ")}`;
            } else {
              celda.title = perks.join(" · ");
            }
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

const NOMBRES_STAT_BOOST = { str: "Fue", mag: "Mag", dex: "Des", spd: "Vel", def: "Def", res: "Res", lck: "Sue", bld: "Com", mov: "Mov" };

function describirStatBoosts(boosts) {
  return Object.entries(boosts || {})
    .filter(([, v]) => v)
    .map(([k, v]) => `${v > 0 ? "+" : ""}${v} ${NOMBRES_STAT_BOOST[k] || k}`)
    .join(", ");
}

// Avisa de los buffs temporales otorgados por pasivas (Self-Improver, ¡Ponte detrás de mí!, ...)
function notificarEstadosOtorgados(res) {
  for (const e of (res && res.estados_otorgados) || []) {
    mostrarToast(`${e.unidad}: ${e.nombre} (${describirStatBoosts(e.stat_boosts)}) — ${e.origen}`, "ok");
  }
}

function esClaseQiAdept(ficha) {
  if (!ficha) return false;
  const clase = String(ficha.clase_nombre || (ficha.stats ? ficha.stats.clase_nombre : "") || "").toLowerCase();
  const estilo = String(ficha.estilo_combate || (ficha.stats ? ficha.stats.estilo_combate : "") || "").toLowerCase();
  const nombre = String(ficha.nombre || "").toLowerCase();
  // El estilo de combate (StyleName de Job.xml) manda: si viene y no es 気功, no es Qi Adept
  // (p.ej. "Swordmaster" contiene "master" pero es Backup).
  if (estilo && !["infantería", "infanteria", "none", "infantry"].includes(estilo)) {
    return estilo.includes("qi") || estilo.includes("adept") || estilo.includes("adepto") || estilo.includes("気功");
  }
  if (["martial monk", "martial master", "monje", "maestro marcial", "dancer", "bailar", "qi adept", "adepto"].some(k => clase.includes(k))) return true;
  if (["framme", "seadall"].some(k => nombre.includes(k))) return true;
  if (state && state.catalogo && state.catalogo.clases) {
    for (const c of Object.values(state.catalogo.clases)) {
      if (c && c.nombre && c.nombre.toLowerCase() === clase) {
        const cEstilo = String(c.estilo_combate || "").toLowerCase();
        if (cEstilo.includes("qi") || cEstilo.includes("adept") || cEstilo.includes("気功") || cEstilo.includes("artes")) return true;
      }
    }
  }
  return false;
}

function crearToken(ficha) {
  const celda = $(`c-${ficha.x}-${ficha.y}`);
  if (!celda) return;

  // Eliminar token anterior si existe
  const viejo = document.querySelector(`.token[data-nombre="${ficha.nombre}"]`);
  if (viejo) viejo.remove();

  if (!ficha.viva || (ficha.hp_actual !== undefined && ficha.hp_actual <= 0)) return;

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
  } else if (ficha.es_aliado && ficha.emblema_nombre) {
    const maxE = ficha.max_energia_emblema || (ficha.nivel_vinculo >= 20 ? 5 : 6);
    const curE = (ficha.energia_emblema !== undefined) ? ficha.energia_emblema : maxE;
    const energyBadge = document.createElement("span");
    if (curE < maxE) {
      energyBadge.className = "token-recharge-badge";
      energyBadge.textContent = `⚡${curE}/${maxE}`;
      energyBadge.title = `Medidor de Emblema: ${curE}/${maxE} cargas (Recargando - Fusión bloqueada)`;
    } else {
      energyBadge.className = "token-ready-badge";
      energyBadge.textContent = "⚡";
      energyBadge.title = `Medidor de Emblema al 100% (${curE}/${maxE}) - ¡FUSIÓN LISTA!`;
    }
    tok.appendChild(energyBadge);
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
    const plv = Math.min(3, Math.max(1, parseInt(ficha.nivel_veneno) || 1));
    poisonBadge.textContent = "☠" + "+".repeat(plv - 1);
    poisonBadge.title = `Veneno Nivel ${plv}: Recibe +${plv} de daño en todos los ataques`;
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
  for (const est of (ficha.estados_temporales || [])) {
    desc += `\n[⬆ ${est.nombre}: ${describirStatBoosts(est.stat_boosts)} hasta fase ${est.expira_fase} T${est.expira_turno}]`;
  }
  if (ficha.en_fusion || ficha.turnos_fusion > 0) desc += `\n[MODO ENGAGE ACTIVO: ${ficha.turnos_fusion} turno(s) restante(s)${ficha.ataque_emblema_usado ? ' - Técnica Engage consumida' : ''}]`;
  else if (ficha.es_aliado && ficha.emblema_nombre) {
    const maxE = ficha.max_energia_emblema || (ficha.nivel_vinculo >= 20 ? 5 : 6);
    const curE = (ficha.energia_emblema !== undefined) ? ficha.energia_emblema : maxE;
    desc += `\n[MEDIDOR DE EMBLEMA: ${curE}/${maxE}${curE >= maxE ? ' - FUSIÓN LISTA' : ''}]`;
  }
  const esQiAdept = esClaseQiAdept(ficha);
  const cgActivo = esQiAdept && (ficha.chain_guard_activo !== false) && !ficha.chain_guard_usado && (hpActual >= hpMax);
  if (esQiAdept) {
    desc += cgActivo ? "\n[🛡️ GUARDIA EN CADENA ACTIVA (Protege aliados adyacentes)]" : "\n[Guardia en Cadena: Inactiva (Requiere 100% HP y postura activa)]";
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

  // Indicador de Guardia en Cadena (Chain Guard) para Adeptos de Qi
  if (cgActivo) {
    const cgBadge = document.createElement("span");
    cgBadge.className = "token-cg-badge";
    cgBadge.textContent = "🛡️";
    cgBadge.title = "Guardia en Cadena activa: Absorbe el 1er golpe a un aliado adyacente (-20% HP propio)";
    tok.appendChild(cgBadge);
  }

  // Indicador de Piedras Resurrectoras (Rombos bajo el círculo de personaje)
  const hpStock = ficha.hp_stock !== undefined ? ficha.hp_stock : (ficha.stats ? ficha.stats.hp_stock : 0);
  if (hpStock > 0) {
    const stockContainer = document.createElement("div");
    stockContainer.className = "token-hp-stock";
    stockContainer.textContent = "◆".repeat(hpStock);
    stockContainer.title = `Piedras Resurrectoras: ${hpStock} barra(s) extra de vida`;
    tok.appendChild(stockContainer);
  }

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
    const fichasVivas = Object.values(state.fichas).filter(f => f.viva && (f.hp_actual === undefined || f.hp_actual > 0));
    const estado = {
      fichas: fichasVivas,
      turno_actual: state.turno || 1,
      fase: state.fase || "jugador",
      capitulo: state.capitulo || null,
      dificultad: ($("select-dificultad") && $("select-dificultad").value) || state.dificultad || "Hard",
      // Refuerzos aún por llegar (el servidor los pierde al reiniciarse; se reprograman al restaurar)
      refuerzos_pendientes: state.refuerzosPendientes || null,
      casillas_fuego: state.casillasFuego || [],
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
      if (estado.dificultad && $("select-dificultad")) $("select-dificultad").value = estado.dificultad;
      renderCasillasFuego(estado.casillas_fuego || []);
      await refrescarRefuerzosPendientes();
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
      if (f.viva && (f.hp_actual === undefined || f.hp_actual > 0)) {
        state.fichas[f.nombre] = f;
        crearToken(f);
      }
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
  // Casilla de un destructible (valla, caja…): editar su vida en vez de crear una unidad
  if (e.currentTarget.classList.contains("obj-destructible") && e.currentTarget.dataset.objetoId) {
    abrirModalObjeto(e.currentTarget.dataset.objetoId);
    return;
  }
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
    engage_items: ["Ridersbane (Emblema)"]
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

// Subtítulos cosméticos conocidos para los grabados (solo decorativos, no
// afectan a la lógica). Un emblema sin entrada aquí se muestra sin subtítulo
// en vez de quedar fuera del selector — así un DLC nuevo aparece igual aunque
// no se le haya asignado todavía un subtítulo.
const SUBTITULOS_GRABADO = {
  "marth": "Comienzos", "sigurd": "Cruzada", "celica": "Ecos",
  "micaiah": "Aurora", "roy": "León", "leif": "Genealogía",
  "lucina": "Despertar", "lyn": "Llama", "ike": "Fulgor",
  "byleth": "Academia", "corrin": "Destino", "eirika": "Sagrada",
  "alear": "Dragón",
};

/** Rellena dinámicamente los 5 selectores de grabado (uno por ranura de
 * inventario) a partir del catálogo real de Emblemas (base + DLC), en vez de
 * depender de la lista fija escrita a mano en el HTML — así un Emblema DLC
 * nuevo (o uno cuyo grabado se corrija) aparece sin tener que editar 5 <select>
 * repetidos. */
function poblarSelectoresGrabado() {
  const emblemasConGrabado = Object.values(CATALOGO_EMBLEMAS)
    .filter(e => e && e.engrave && e.nombre)
    .sort((a, b) => a.nombre.localeCompare(b.nombre));
  if (emblemasConGrabado.length === 0) return;

  for (let i = 0; i < 5; i++) {
    const sel = $(`inv-grabado-${i}`);
    if (!sel) continue;
    const valorActual = sel.value;
    sel.innerHTML = "";
    const optVacia = document.createElement("option");
    optVacia.value = "";
    optVacia.textContent = "(Sin grabado)";
    sel.appendChild(optVacia);
    for (const emb of emblemasConGrabado) {
      const opt = document.createElement("option");
      opt.value = emb.nombre;
      const sub = SUBTITULOS_GRABADO[emb.nombre.toLowerCase()];
      opt.textContent = sub ? `${emb.nombre} (${sub})` : emb.nombre;
      sel.appendChild(opt);
    }
    if (valorActual) sel.value = valorActual;
  }
}

function buscarEmblemaInfo(nombre) {
  if (!nombre) return null;
  const n = nombre.trim().toLowerCase();

  let match = null;
  // 1. Buscar en catálogo compilado oficial (21 emblemas con bond_levels 1..20)
  for (const [k, v] of Object.entries(CATALOGO_EMBLEMAS)) {
    const nom = (v.nombre || "").toLowerCase();
    const ascii = (v.ascii_name || "").toLowerCase();
    const link = (v.link_name || "").toLowerCase();
    const kid = k.toLowerCase();
    if (n === nom || n === ascii || n === link || n === kid || nom.includes(n) || n.includes(nom)) {
      match = Object.assign({}, v);
      break;
    }
  }

  // 2. Fallback a datos estáticos embebidos
  if (!match) {
    for (const [k, v] of Object.entries(EMBLEMAS_DATA)) {
      if (n === k || n.includes(k) || k.includes(n)) {
        match = Object.assign({}, v);
        break;
      }
    }
  }

  // 3. Garantizar engage_attack si el objeto no lo traía
  if (match && !match.engage_attack) {
    for (const [k, v] of Object.entries(EMBLEMAS_DATA)) {
      if (n === k || n.includes(k) || k.includes(n) || (match.nombre && match.nombre.toLowerCase().includes(k))) {
        if (v.engage_attack) {
          match.engage_attack = v.engage_attack;
          break;
        }
      }
    }
  }
  return match;
}

function obtenerDatosVinculoEmblema(eInfo, nivel) {
  if (!eInfo) return null;
  const n = Math.max(1, Math.min(20, parseInt(nivel || 1, 10)));
  let baseData = null;
  if (eInfo.bond_levels && eInfo.bond_levels[String(n)]) {
    baseData = eInfo.bond_levels[String(n)];
  } else if (eInfo.bond_levels) {
    const disp = Object.keys(eInfo.bond_levels)
      .map(k => parseInt(k, 10))
      .filter(k => !isNaN(k) && k <= n)
      .sort((a, b) => a - b);
    if (disp.length > 0) {
      baseData = eInfo.bond_levels[String(disp[disp.length - 1])];
    }
  }

  if (baseData) {
    return {
      ...baseData,
      engage_items: (baseData.engage_items || []).map(it => {
        const nom = (typeof it === "object" ? (it.nombre || it.iid) : it) || "";
        const nomDist = nom.endsWith("(Emblema)") ? nom : `${nom} (Emblema)`;
        return typeof it === "object" ? { ...it, nombre: nomDist } : { iid: it, nombre: nomDist };
      })
    };
  }

  // Fallback con datos embebidos respetando nivel de vínculo
  let fallbackItems = eInfo.engage_items || [];
  if (eInfo.nombre && eInfo.nombre.toLowerCase().includes("sigurd")) {
    fallbackItems = n >= 15 ? ["Ridersbane", "Brave Lance", "Tyrfing"] : (n >= 10 ? ["Ridersbane", "Brave Lance"] : ["Ridersbane"]);
  } else if (eInfo.nombre && eInfo.nombre.toLowerCase().includes("marth")) {
    fallbackItems = n >= 10 ? ["Rapier", "Mercurius"] : ["Rapier"];
  }

  return {
    level: n,
    stat_boosts: eInfo.synchro_boosts || {},
    synchro_skills: (eInfo.synchro_skills || []).map(s => ({ sid: s, nombre: s })),
    engage_items: fallbackItems.map(i => {
      const iStr = String(i);
      const nomDist = iStr.endsWith("(Emblema)") ? iStr : `${iStr} (Emblema)`;
      return { iid: iStr, nombre: nomDist };
    }),
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

// ─── Utilidades del Sistema de Inventario de 5 Ranuras ───────────────────────

function esItemBastonOObjeto(nombre) {
  if (!nombre) return false;
  const n = String(nombre).toLowerCase().trim();
  const palabras = [
    "bastón", "baston", "staff", "curar", "sanar", "recuperar", "fortalecer", "restituir",
    "heal", "mend", "recover", "physic", "fortify", "restore", "warp", "rewarp", "rescue",
    "entrap", "freeze", "silence", "fracture", "obstruct", "illume", "torch", "antorcha",
    "poción", "pocion", "vulnerary", "elixir", "antídoto", "antidoto", "pure water", "agua pura",
    "tónico", "tonico", "semilla", "seed"
  ];
  return palabras.some(p => n.includes(p));
}

function obtenerUsosMaxPorDefecto(nombre) {
  if (!nombre) return 3;
  const n = String(nombre).toLowerCase();
  if (n.includes("heal") || n.includes("curar")) return 25;
  if (n.includes("mend") || n.includes("sanar")) return 20;
  if (n.includes("recover") || n.includes("recuperar")) return 10;
  if (n.includes("physic")) return 10;
  if (n.includes("fortify") || n.includes("fortalecer")) return 5;
  if (n.includes("warp") || n.includes("rewarp") || n.includes("rescue")) return 5;
  if (n.includes("entrap") || n.includes("freeze") || n.includes("silence")) return 3;
  if (n.includes("pocion") || n.includes("poción") || n.includes("vulnerary")) return 3;
  if (n.includes("elixir") || n.includes("antidoto") || n.includes("antídoto")) return 3;
  if (n.includes("agua pura") || n.includes("pure water") || n.includes("antorcha") || n.includes("torch")) return 3;
  return 3;
}

function actualizarFilaSlot(idx) {
  const row = $(`inv-slot-row-${idx}`);
  if (!row) return;
  const inputNombre = $(`inv-nombre-${idx}`);
  const radio = $(`inv-equip-${idx}`);
  const modsWrap = $(`inv-weapon-mods-${idx}`);
  const usosWrap = $(`inv-usos-wrap-${idx}`);
  const usosInput = $(`inv-usos-${idx}`);
  const usosBadge = $(`inv-usos-max-${idx}`);

  const nombre = inputNombre ? inputNombre.value.trim() : "";
  const esBastonObjeto = esItemBastonOObjeto(nombre);

  if (esBastonObjeto) {
    row.classList.add("slot-no-equipable");
    if (radio) {
      radio.disabled = true;
      if (radio.checked) {
        radio.checked = false;
        // Reasignar equipada a la primera ranura con arma válida
        for (let j = 0; j < 5; j++) {
          if (j !== idx) {
            const nomJ = $(`inv-nombre-${j}`)?.value.trim() || "";
            if (nomJ && !esItemBastonOObjeto(nomJ)) {
              const rJ = $(`inv-equip-${j}`);
              if (rJ) { rJ.checked = true; break; }
            }
          }
        }
      }
    }
    if (modsWrap) modsWrap.classList.add("hidden");
    if (usosWrap) {
      usosWrap.classList.remove("hidden");
      const uMax = obtenerUsosMaxPorDefecto(nombre);
      if (usosInput) {
        usosInput.max = uMax;
        if (!usosInput.value || parseInt(usosInput.value, 10) > uMax || parseInt(usosInput.value, 10) <= 0) {
          usosInput.value = uMax;
        }
      }
      if (usosBadge) usosBadge.textContent = `/ ${uMax}`;
    }
  } else {
    row.classList.remove("slot-no-equipable");
    if (radio) radio.disabled = false;
    if (modsWrap) modsWrap.classList.remove("hidden");
    if (usosWrap) usosWrap.classList.add("hidden");
  }

  // Actualizar clase visual de equipado
  if (radio && radio.checked && !esBastonObjeto) {
    row.classList.add("slot-equipado");
  } else {
    row.classList.remove("slot-equipado");
  }
}

function actualizarTodosLosSlots() {
  for (let i = 0; i < 5; i++) {
    actualizarFilaSlot(i);
  }
}

function obtenerArmaEquipadaActual() {
  // 1. Si hay un arma de Emblema activa seleccionada desde la Fusión
  if (state.armaEmblemaEquipadaTemporal && $("f-fusion")?.checked) {
    return {
      nombreCompleto: state.armaEmblemaEquipadaTemporal,
      base: state.armaEmblemaEquipadaTemporal,
      forja: "0",
      grabado: "",
      esEmblema: true
    };
  }

  // 2. Buscar qué slot tiene el radio marcado
  let slotIdx = -1;
  for (let i = 0; i < 5; i++) {
    const r = $(`inv-equip-${i}`);
    if (r && r.checked) {
      slotIdx = i;
      break;
    }
  }

  // Si no hay ninguno o el seleccionado es bastón/objeto, buscar la primera arma válida
  if (slotIdx === -1 || esItemBastonOObjeto($(`inv-nombre-${slotIdx}`)?.value)) {
    for (let i = 0; i < 5; i++) {
      const nom = $(`inv-nombre-${i}`)?.value.trim() || "";
      if (nom && !esItemBastonOObjeto(nom)) {
        slotIdx = i;
        const r = $(`inv-equip-${i}`);
        if (r) r.checked = true;
        break;
      }
    }
  }

  if (slotIdx >= 0) {
    const base = $(`inv-nombre-${slotIdx}`)?.value.trim() || "";
    const forja = $(`inv-forja-${slotIdx}`)?.value || "0";
    const grabado = $(`inv-grabado-${slotIdx}`)?.value || "";
    const nombreCompleto = construirArmaString(base, forja, grabado);
    return { nombreCompleto, base, forja, grabado, esEmblema: false };
  }

  return { nombreCompleto: "Iron Sword", base: "Iron Sword", forja: "0", grabado: "", esEmblema: false };
}

function renderizarArmasFusionModal(ficha) {
  const cont = $("seccion-armas-emblema-fusion");
  const grid = $("armas-fusion-grid");
  if (!cont || !grid) return;

  const enFusion = $("f-fusion")?.checked;
  const embNom = $("f-emblema")?.value.trim() || (ficha ? ficha.emblema_nombre : "");

  if (!enFusion || !embNom) {
    cont.classList.add("hidden");
    state.armaEmblemaEquipadaTemporal = null;
    return;
  }

  const eInfo = buscarEmblemaInfo(embNom);
  if (!eInfo) {
    cont.classList.add("hidden");
    return;
  }

  const nivelV = $("f-nivel-vinculo") ? (parseInt($("f-nivel-vinculo").value, 10) || 1) : 1;
  const bond = obtenerDatosVinculoEmblema(eInfo, nivelV);
  const items = bond?.engage_items || eInfo.engage_items || [];

  if (!items || items.length === 0) {
    cont.classList.add("hidden");
    return;
  }

  cont.classList.remove("hidden");
  grid.innerHTML = "";

  items.forEach(it => {
    let nom = it.nombre || it.iid || it;
    if (typeof nom === "string" && !nom.endsWith("(Emblema)")) {
      nom = `${nom} (Emblema)`;
    }
    const card = document.createElement("div");
    card.className = "arma-fusion-card";
    const esActiva = state.armaEmblemaEquipadaTemporal === nom;
    if (esActiva) card.classList.add("activa");

    card.innerHTML = `<span>${nom}</span><span class="af-tag">${esActiva ? "Equipada" : "Usar"}</span>`;
    card.title = `Usar ${nom} para combate normal durante la fusión`;
    card.addEventListener("click", () => {
      if (state.armaEmblemaEquipadaTemporal === nom) {
        state.armaEmblemaEquipadaTemporal = null;
      } else {
        state.armaEmblemaEquipadaTemporal = nom;
      }
      renderizarArmasFusionModal(ficha);
      actualizarTodosLosSlots();
      recalcularCombatStats();
    });
    grid.appendChild(card);
  });
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

  const armaInfo = obtenerArmaEquipadaActual();
  const armaNombre = armaInfo.nombreCompleto;

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

function abrirModalCreacion(x = 0, y = 0, esAliado = true) {
  state.modalModo = "crear";
  state.nombrePrecargadoRoster = "";
  state.statsEditadosManualmente = false;
  $("row-pos-indicator").classList.remove("hidden");
  $("btn-modal-eliminar").textContent = "Eliminar Ficha";
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

  for (let i = 0; i < 5; i++) {
    const nomEl = $(`inv-nombre-${i}`);
    if (nomEl) nomEl.value = (i === 0) ? (esAliado ? "Libération" : "Iron Sword") : "";
    const forjaEl = $(`inv-forja-${i}`);
    if (forjaEl) forjaEl.value = "0";
    const grabEl = $(`inv-grabado-${i}`);
    if (grabEl) grabEl.value = "";
    const usosEl = $(`inv-usos-${i}`);
    if (usosEl) usosEl.value = "3";
    const radioEl = $(`inv-equip-${i}`);
    if (radioEl) radioEl.checked = (i === 0);
  }
  actualizarTodosLosSlots();
  renderizarArmasFusionModal(null);

  $("f-emblema").value = esAliado ? "Marth" : "";
  if ($("f-boosts-fusion")) $("f-boosts-fusion").value = "";
  establecerLiderTresCasas("Dimitri");
  actualizarSelectorLiderTresCasas();
  actualizarVisibilidadChainGuard();
  state.prevEmblemaModal = esAliado ? "Marth" : "";
  state.prevNivelVinculoModal = 1;
  if ($("f-nivel-vinculo")) {
    $("f-nivel-vinculo").value = "1";
    actualizarTooltipNivelVinculo(1);
  }
  if ($("f-energia-emblema")) $("f-energia-emblema").value = esAliado ? 6 : 0;
  $("f-fusion").checked = false;
  state.fusionActivandoseEnModal = false;
  actualizarEstadoEnergiaModal();
  if ($("f-hp-stock")) $("f-hp-stock").value = "0";
  if ($("f-chain-guard")) $("f-chain-guard").checked = true;
  limpiarChips("chips-pasivas");

  if (esAliado) {
    const eInfo = buscarEmblemaInfo("Marth");
    if (eInfo && eInfo.synchro_skills) {
      eInfo.synchro_skills.forEach(s => addChip("chips-pasivas", s));
    }
  }

  recalcularCombatStats();
  actualizarAvisoFusion();

  $("btn-modal-eliminar").classList.add("hidden");
  $("modal-backdrop").classList.remove("hidden");
  $("f-nombre").focus();
}

// Vuelca una ficha (del tablero o del roster) en todos los campos del modal.
// No toca el modo, el título ni el nombre original: eso lo decide quien abre el modal.
// "hp:5, str:3" ⇄ {hp:5, str:3}
function parsearBoostsFusion(txt) {
  const out = {};
  String(txt || "").split(/[,;]+/).forEach(par => {
    const m = par.trim().match(/^([a-z]{2,3})\s*[:=]\s*(-?\d+)$/i);
    if (m && parseInt(m[2], 10) !== 0) out[m[1].toLowerCase()] = parseInt(m[2], 10);
  });
  return out;
}
function formatearBoostsFusion(obj) {
  return Object.entries(obj || {}).filter(([, v]) => v).map(([k, v]) => `${k}:${v}`).join(", ");
}

function rellenarFormularioDesdeFicha(ficha) {
  if ($("f-boosts-fusion")) $("f-boosts-fusion").value = formatearBoostsFusion(ficha.boosts_fusion);
  state.potenciadoresModal = Array.isArray(ficha.potenciadores_usados) ? [...ficha.potenciadores_usados] : [];
  state.armaEmblemaEquipadaTemporal = null;
  state.prevEmblemaModal = ficha.emblema_nombre || "";
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

  const stockV = ficha.hp_stock !== undefined ? ficha.hp_stock : (ficha.stats ? ficha.stats.hp_stock : 0);
  if ($("f-hp-stock")) $("f-hp-stock").value = stockV;
  if ($("f-chain-guard")) $("f-chain-guard").checked = (ficha.chain_guard_activo !== false);

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

  // Limpiar los 5 slots de inventario
  for (let i = 0; i < 5; i++) {
    if ($(`inv-nombre-${i}`)) $(`inv-nombre-${i}`).value = "";
    if ($(`inv-forja-${i}`)) $(`inv-forja-${i}`).value = "0";
    if ($(`inv-grabado-${i}`)) $(`inv-grabado-${i}`).value = "";
    if ($(`inv-usos-${i}`)) $(`inv-usos-${i}`).value = "3";
    if ($(`inv-equip-${i}`)) $(`inv-equip-${i}`).checked = false;
  }

  const items = Array.isArray(ficha.inventario) ? [...ficha.inventario] : [];
  let equippedSlot = -1;

  items.slice(0, 5).forEach((item, idx) => {
    let rawStr = "";
    let forja = "0";
    let grabado = "";
    let usos = 3;
    let esEq = false;

    if (typeof item === "string") {
      const d = desglosarArmaString(item);
      rawStr = d.base;
      forja = d.forja;
      grabado = d.grabado;
    } else if (item && typeof item === "object") {
      const nomOriginal = item.nombre_base || item.nombre || item.arma || "";
      const d = desglosarArmaString(nomOriginal);
      rawStr = d.base;
      forja = String(item.refine_lvl !== undefined ? item.refine_lvl : (d.forja || "0"));
      grabado = item.grabado !== undefined && item.grabado !== null ? item.grabado : (d.grabado || "");
      usos = item.usos !== undefined && item.usos !== null ? item.usos : obtenerUsosMaxPorDefecto(rawStr);
      esEq = !!item.equipada;
    }

    if ($(`inv-nombre-${idx}`)) $(`inv-nombre-${idx}`).value = rawStr;
    if ($(`inv-forja-${idx}`)) $(`inv-forja-${idx}`).value = forja;
    if ($(`inv-grabado-${idx}`)) $(`inv-grabado-${idx}`).value = grabado;
    if ($(`inv-usos-${idx}`)) $(`inv-usos-${idx}`).value = usos;
    if (esEq) equippedSlot = idx;
  });

  // Si no había inventario cargado pero sí arma_equipada / arma
  if (items.length === 0) {
    const rawArma = ficha.arma_equipada ? (ficha.arma_equipada.nombre || ficha.arma_equipada) : (ficha.arma ? (ficha.arma.nombre || ficha.arma) : "");
    if (rawArma) {
      const d = desglosarArmaString(rawArma);
      if ($("inv-nombre-0")) $("inv-nombre-0").value = d.base;
      if ($("inv-forja-0")) $("inv-forja-0").value = d.forja;
      if ($("inv-grabado-0")) $("inv-grabado-0").value = d.grabado;
      equippedSlot = 0;
    }
  }

  // Marcar radio
  if (equippedSlot >= 0 && $(`inv-equip-${equippedSlot}`)) {
    $(`inv-equip-${equippedSlot}`).checked = true;
  } else if ($("inv-equip-0")) {
    $("inv-equip-0").checked = true;
  }

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
  actualizarVisibilidadChainGuard(ficha);

  const maxE = nivV >= 20 ? 5 : 6;
  const curE = (ficha.energia_emblema !== undefined) ? ficha.energia_emblema : maxE;
  if ($("f-energia-emblema")) {
    $("f-energia-emblema").value = curE;
  }
  $("f-fusion").checked = ficha.en_fusion || false;
  state.fusionActivandoseEnModal = false;
  actualizarEstadoEnergiaModal();

  // Rellenar chips de habilidades pasivas
  limpiarChips("chips-pasivas");
  const habs = Array.isArray(ficha.habilidades) ? ficha.habilidades : (ficha.habilidades ? [ficha.habilidades] : []);
  habs.filter(Boolean).forEach(h => addChip("chips-pasivas", h));

  // Si la unidad está en Fusión, asegurar que aparezca su ataque de emblema
  if (ficha.en_fusion || ficha.turnos_fusion > 0) {
    const eInfo = buscarEmblemaInfo(ficha.emblema_nombre);
    if (eInfo && eInfo.engage_attack) {
      const pasivasActuales = leerChips("chips-pasivas");
      if (!pasivasActuales.includes(eInfo.engage_attack)) {
        addChip("chips-pasivas", eInfo.engage_attack);
      }
    }
  }

  actualizarTodosLosSlots();
  renderizarArmasFusionModal(ficha);
  recalcularCombatStats();
  actualizarAvisoFusion();

}

function abrirModalEdicion(ficha) {
  state.modalModo = "editar";
  state.nombrePrecargadoRoster = ficha.nombre;
  state.statsEditadosManualmente = false;
  $("modal-titulo").textContent = `Editar Unidad: ${ficha.nombre}`;
  $("f-edit-original-name").value = ficha.nombre;
  $("row-pos-indicator").classList.remove("hidden");
  rellenarFormularioDesdeFicha(ficha);

  $("btn-modal-eliminar").classList.remove("hidden");
  $("btn-modal-eliminar").textContent = "Eliminar Ficha";
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

function actualizarVisibilidadChainGuard(ficha) {
  const fila = $("fila-chain-guard");
  if (!fila) return;
  const clase = $("f-clase") ? $("f-clase").value.trim() : "";
  const nombre = $("f-nombre") ? $("f-nombre").value.trim() : "";
  let esQi = false;
  if (ficha && esClaseQiAdept(ficha)) {
    esQi = true;
  } else {
    esQi = esClaseQiAdept({ clase_nombre: clase, nombre: nombre });
  }
  fila.classList.toggle("hidden", !esQi);
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

function actualizarEstadoEnergiaModal() {
  const nivV = $("f-nivel-vinculo") ? Math.max(1, Math.min(20, parseInt($("f-nivel-vinculo").value || 1, 10))) : 1;
  const maxE = nivV >= 20 ? 5 : 6;
  if ($("label-max-energia")) $("label-max-energia").textContent = `/ ${maxE}`;
  if ($("f-energia-emblema")) {
    $("f-energia-emblema").max = maxE;
    let curE = parseInt($("f-energia-emblema").value, 10);
    if (isNaN(curE)) curE = maxE;
    curE = Math.max(0, Math.min(maxE, curE));
    $("f-energia-emblema").value = curE;

    const tieneEmb = $("f-emblema") && $("f-emblema").value.trim().length > 0;
    const nomFicha = $("f-edit-original-name") ? $("f-edit-original-name").value : null;
    const fActual = nomFicha ? state.fichas[nomFicha] : null;
    const enFusionActiva = fActual && (fActual.en_fusion || fActual.turnos_fusion > 0) && (fActual.turnos_fusion > 0);

    if (enFusionActiva) {
      $("f-fusion").disabled = true;
      if ($("txt-fusion-label")) $("txt-fusion-label").textContent = `Fusión activa (${fActual.turnos_fusion}t)`;
      $("label-fusion").title = `Fusión en curso: ${fActual.turnos_fusion} turno(s) restante(s). No se puede retirar manualmente.`;
      $("label-fusion").style.opacity = "0.7";
      $("label-fusion").style.pointerEvents = "none";
      if ($("label-energia-estado")) $("label-energia-estado").textContent = "(Consumido por Fusión)";
    } else if (state.fusionActivandoseEnModal) {
      // El medidor está a 0 porque se acaba de marcar "Activar Fusión" en este
      // modal (aún sin guardar) — no es un estado de "recargando", así que no
      // se debe desmarcar ni deshabilitar el checkbox.
      $("f-fusion").checked = true;
      $("f-fusion").disabled = false;
      if ($("txt-fusion-label")) $("txt-fusion-label").textContent = "Fusión Engage activada (pendiente de guardar)";
      $("label-fusion").title = "Fusión activada. Guarda la unidad para confirmarla.";
      $("label-fusion").style.opacity = "1";
      $("label-fusion").style.pointerEvents = "auto";
      if ($("label-energia-estado")) $("label-energia-estado").textContent = "(Consumido por Fusión, pendiente de guardar)";
    } else if (!tieneEmb) {
      $("f-fusion").disabled = true;
      if ($("txt-fusion-label")) $("txt-fusion-label").textContent = "Activar Fusión";
      $("label-fusion").style.opacity = "0.5";
      $("label-fusion").style.pointerEvents = "none";
      if ($("label-energia-estado")) $("label-energia-estado").textContent = "";
    } else if (curE < maxE) {
      $("f-fusion").checked = false;
      $("f-fusion").disabled = true;
      if ($("txt-fusion-label")) $("txt-fusion-label").textContent = `⚡ Recargando (${curE}/${maxE})`;
      $("label-fusion").title = `Medidor incompleto (${curE}/${maxE}). Requiere ${maxE} cargas para activar Fusión.`;
      $("label-fusion").style.opacity = "0.6";
      $("label-fusion").style.pointerEvents = "none";
      if ($("label-energia-estado")) $("label-energia-estado").textContent = `(Recargando - faltan ${maxE - curE} cargas)`;
    } else {
      $("f-fusion").disabled = false;
      if ($("txt-fusion-label")) $("txt-fusion-label").textContent = "Activar Fusión";
      $("label-fusion").title = "Medidor completo: ¡Listo para activar Fusión!";
      $("label-fusion").style.opacity = "1";
      $("label-fusion").style.pointerEvents = "auto";
      if ($("label-energia-estado")) $("label-energia-estado").textContent = "(¡Listo para Fusión!)";
    }
  }
}

// Aviso de Rise Above (Roy): al fusionar la unidad sube 5 niveles y el juego decide
// las stats con su acumulador de crecimientos, así que la herramienta solo puede
// estimarlas. Se invita a anotar la diferencia real en "Bono de stats en Fusión".
async function actualizarAvisoFusion() {
  const box = $("aviso-fusion");
  if (!box) return;
  const emb = $("f-emblema") ? $("f-emblema").value.trim() : "";
  const info = emb ? buscarEmblemaInfo(emb) : null;
  const skillsEng = ((info && info.engage_skills) || []).map(x => (typeof x === "object" ? (x.nombre || x.sid || "") : String(x)).toLowerCase());
  const tieneRiseAbove = emb.toLowerCase().includes("roy") || skillsEng.some(x => x.includes("rise above") || x.includes("超越"));
  if (!tieneRiseAbove) { box.classList.add("hidden"); box.innerHTML = ""; return; }
  const nombre = $("f-nombre") ? $("f-nombre").value.trim() : "";
  const clase = $("f-clase") ? $("f-clase").value.trim() : "";
  let est = {};
  try {
    const r = await api(`/api/unidad/bono_fusion_estimado?nombre=${encodeURIComponent(nombre)}&clase=${encodeURIComponent(clase)}`);
    if (r && r.ok) est = r.estimado || {};
  } catch (e) { /* sin estimación */ }
  const estTxt = formatearBoostsFusion(est) || "—";
  const manual = $("f-boosts-fusion") ? $("f-boosts-fusion").value.trim() : "";
  box.innerHTML = `<b>Rise Above (Roy):</b> al fusionar, la unidad sube 5 niveles y sus stats cambian según sus crecimientos. `
    + `El valor exacto lo decide el juego; la herramienta lo <b>estima</b> (±1 por stat): <span id="txt-fusion-estimado">${estTxt}</span>`
    + `<button type="button" id="btn-fusion-usar-estimado" class="btn-hp-tool btn-blue" title="Copiar la estimación al campo para poder ajustarla">Usar estimado</button>`
    + `<br>Para calcular exacto, anota arriba la diferencia real que muestra el juego (fusionado − solo con el emblema equipado).`
    + (manual ? ` <b>Ahora se usan tus valores.</b>` : ` <b>Ahora se usa la estimación.</b>`);
  box.classList.remove("hidden");
  const btn = $("btn-fusion-usar-estimado");
  if (btn) btn.addEventListener("click", () => {
    if ($("f-boosts-fusion")) { $("f-boosts-fusion").value = formatearBoostsFusion(est); actualizarAvisoFusion(); }
  });
}

function sincronizarEmblemaModal() {
  const val = $("f-emblema") ? $("f-emblema").value.trim() : "";
  const nivelVal = $("f-nivel-vinculo") ? Math.max(1, Math.min(20, parseInt($("f-nivel-vinculo").value || 1, 10))) : 1;
  const tieneEmblema = val.length > 0;

  actualizarSelectorLiderTresCasas();
  actualizarAvisoFusion();
  actualizarTooltipNivelVinculo(nivelVal);
  actualizarEstadoEnergiaModal();

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
    renderizarArmasFusionModal(null);
    recalcularCombatStats();
  }
}

// Lee todos los campos del modal y devuelve el payload de unidad (formato /api/unidad/guardar).
// `fichaExistente` aporta el estado transitorio (fusión, ha_actuado…) que el modal no edita.
function construirPayloadDesdeModal(fichaExistente) {
  const nombre = $("f-nombre").value.trim();

  const esAliado = $("f-bando-aliado").checked;
  const x = parseInt($("f-x").value, 10);
  const y = parseInt($("f-y").value, 10);
  const nivel = parseInt($("f-nivel").value, 10) || 1;
  const hpActual = parseInt($("f-hp-actual").value, 10);
  const hpMax = parseInt($("f-hp-max").value, 10);
  const claseNombre = $("f-clase").value.trim();
  const emblemaNombre = $("f-emblema").value.trim();
  let enFusion = $("f-fusion").checked && !!emblemaNombre;

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

  // Leer chips de pasivas
  const pasivas = leerChips("chips-pasivas");

  // Construir inventario estructurado a partir de los 5 slots
  const inventario = [];
  let armaEquipadaNombre = "";

  for (let i = 0; i < 5; i++) {
    const nomEl = $(`inv-nombre-${i}`);
    const nombreItem = nomEl ? nomEl.value.trim() : "";
    if (!nombreItem) continue;

    const esBastonObjeto = esItemBastonOObjeto(nombreItem);
    const forjaVal = $(`inv-forja-${i}`) ? $(`inv-forja-${i}`).value : "0";
    const grabadoVal = $(`inv-grabado-${i}`) ? $(`inv-grabado-${i}`).value : "";
    const usosVal = $(`inv-usos-${i}`) ? parseInt($(`inv-usos-${i}`).value, 10) : 3;
    const esEq = $(`inv-equip-${i}`) ? ($(`inv-equip-${i}`).checked && !esBastonObjeto) : false;

    const fullArmaString = esBastonObjeto ? nombreItem : construirArmaString(nombreItem, forjaVal, grabadoVal);
    const uMax = esBastonObjeto ? obtenerUsosMaxPorDefecto(nombreItem) : null;

    if (esEq && !armaEquipadaNombre) {
      armaEquipadaNombre = fullArmaString;
    }

    inventario.push({
      arma: fullArmaString,
      nombre: fullArmaString,
      nombre_base: nombreItem,
      refine_lvl: esBastonObjeto ? 0 : parseInt(forjaVal || 0, 10),
      grabado: esBastonObjeto ? null : (grabadoVal || null),
      equipada: esEq,
      tipo: esBastonObjeto ? (nombreItem.toLowerCase().includes("pocion") || nombreItem.toLowerCase().includes("elixir") ? "Objeto" : "Bastón") : "Arma",
      usos: esBastonObjeto ? (isNaN(usosVal) ? uMax : usosVal) : null,
      usos_max: uMax
    });
  }

  // Si no se marcó ningún slot como equipado, equipar la primera arma válida
  if (!armaEquipadaNombre) {
    const primerArma = inventario.find(it => !esItemBastonOObjeto(it.nombre_base));
    if (primerArma) {
      primerArma.equipada = true;
      armaEquipadaNombre = primerArma.arma;
    } else {
      armaEquipadaNombre = "Espada de Hierro";
    }
  }

  const estabaEnFusion = fichaExistente && (fichaExistente.en_fusion || fichaExistente.turnos_fusion > 0) && (fichaExistente.turnos_fusion > 0);
  if (estabaEnFusion) {
    enFusion = true;
  }
  const haActuado = fichaExistente ? !!fichaExistente.ha_actuado : false;
  const cargasRuptura = fichaExistente ? (fichaExistente.cargas_ruptura || 0) : 0;
  const esVolador = fichaExistente ? !!fichaExistente.es_volador : undefined;
  const nivelVeneno = fichaExistente ? (fichaExistente.nivel_veneno || 0) : 0;
  const lider3H = obtenerLiderTresCasasSeleccionado();

  const hpStockInput = $("f-hp-stock") ? parseInt($("f-hp-stock").value, 10) : 0;
  const hpStock = isNaN(hpStockInput) ? 0 : Math.max(0, Math.min(3, hpStockInput));
  const chainGuardActivo = $("f-chain-guard") ? $("f-chain-guard").checked : true;

  const maxEnergia = nivelVinculo >= 20 ? 5 : 6;
  const energiaEmblemaInput = $("f-energia-emblema") ? parseInt($("f-energia-emblema").value, 10) : NaN;
  let energiaEmblema = isNaN(energiaEmblemaInput) ? (fichaExistente && fichaExistente.energia_emblema !== undefined ? fichaExistente.energia_emblema : maxEnergia) : energiaEmblemaInput;
  if (enFusion && (!fichaExistente || !fichaExistente.en_fusion)) {
    energiaEmblema = 0;
  }
  energiaEmblema = Math.max(0, Math.min(maxEnergia, energiaEmblema));

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
    hp_stock: hpStock,
    chain_guard_activo: chainGuardActivo,
    clase_nombre: claseNombre,
    arma_nombre: armaEquipadaNombre,
    emblema_nombre: emblemaNombre,
    energia_emblema: energiaEmblema,
    max_energia_emblema: maxEnergia,
    en_fusion: enFusion,
    turnos_fusion: estabaEnFusion ? fichaExistente.turnos_fusion : undefined,
    ataque_emblema_usado: fichaExistente ? fichaExistente.ataque_emblema_usado : undefined,
    nivel_vinculo: nivelVinculo,
    mov: mov,
    potenciadores_usados: state.potenciadoresModal || [],
    boosts_fusion: $("f-boosts-fusion") ? parsearBoostsFusion($("f-boosts-fusion").value) : {},
    stats: {
      hp: isNaN(hpActual) ? hpMax : hpActual,
      hp_max: isNaN(hpMax) ? undefined : hpMax,
      hp_stock: hpStock,
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
  return payload;

}

async function guardarUnidadDesdeModal() {
  const nombre = $("f-nombre").value.trim();
  if (!nombre) {
    mostrarToast("Introduce un nombre para la unidad", "error");
    return;
  }

  if (state.modalModo === "roster") {
    guardarEntradaRosterDesdeModal(nombre);
    return;
  }

  // Si editó el nombre de una unidad existente, eliminar la anterior
  const nombreOriginal = $("f-edit-original-name").value;
  if (nombreOriginal && nombreOriginal !== nombre) {
    await api("/api/unidad/eliminar", "POST", { nombre: nombreOriginal });
    const viejo = document.querySelector(`.token[data-nombre="${nombreOriginal}"]`);
    if (viejo) viejo.remove();
    delete state.fichas[nombreOriginal];
  }

  const fichaExistente = state.fichas[nombreOriginal || nombre];
  const payload = construirPayloadDesdeModal(fichaExistente);

  const res = await api("/api/unidad/guardar", "POST", payload);
  if (res.ok && res.ficha) {
    state.fichas[nombre] = res.ficha;
    state.fusionActivandoseEnModal = false;
    crearToken(res.ficha);
    autoGuardarLocal();
    cerrarModal();
    mostrarToast(`Unidad '${nombre}' guardada con éxito.`, "ok");
    if (res.estados_otorgados && res.estados_otorgados.length) {
      // Otras fichas (p.ej. Alcryst) pueden haber recibido un buff: refrescar el tablero completo
      const est = await api("/api/estado", "GET");
      if (est && est.fichas) actualizarTokens(est.fichas);
      notificarEstadosOtorgados(res);
    }
  } else {
    mostrarToast(`Error: ${res.error || "No se pudo guardar"}`, "error");
  }
}

async function eliminarUnidadDesdeModal() {
  const nombre = $("f-edit-original-name").value || $("f-nombre").value.trim();
  if (!nombre) return;

  if (state.modalModo === "roster") {
    eliminarEntradaRoster(nombre);
    cerrarModal();
    abrirRoster();
    mostrarToast(`'${nombre}' eliminado del roster.`, "info");
    return;
  }

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

  // Botones rápidos de Piedras Resurrectoras
  if ($("btn-stock-0")) $("btn-stock-0").addEventListener("click", () => { $("f-hp-stock").value = 0; });
  if ($("btn-stock-1")) $("btn-stock-1").addEventListener("click", () => { $("f-hp-stock").value = 1; });
  if ($("btn-stock-2")) $("btn-stock-2").addEventListener("click", () => { $("f-hp-stock").value = 2; });
  if ($("btn-stock-3")) $("btn-stock-3").addEventListener("click", () => { $("f-hp-stock").value = 3; });

  if ($("f-clase")) {
    $("f-clase").addEventListener("input", () => actualizarVisibilidadChainGuard());
    $("f-clase").addEventListener("change", () => actualizarVisibilidadChainGuard());
  }
  if ($("f-nombre")) {
    $("f-nombre").addEventListener("input", () => actualizarVisibilidadChainGuard());
    $("f-nombre").addEventListener("change", () => actualizarVisibilidadChainGuard());
  }

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
        actualizarVisibilidadChainGuard();

        if (res.arma_nombre && (!$("inv-nombre-0").value || $("inv-nombre-0").value.trim() === "")) {
          const dArma = desglosarArmaString(res.arma_nombre);
          $("inv-nombre-0").value = dArma.base;
          if ($("inv-forja-0")) $("inv-forja-0").value = dArma.forja;
          if ($("inv-grabado-0")) $("inv-grabado-0").value = dArma.grabado;
          $("inv-equip-0").checked = true;
          actualizarFilaSlot(0);
        }

        recalcularCombatStats();
        mostrarToast(`Datos de ${res.nombre} (Nv ${res.nivel}) cargados del catálogo`, "info");
      }
    } catch (e) {
      console.warn("Error en autoRellenarStatsDesdeCatalogo:", e);
    }
  }

  // Política de prioridad de los datos del modal (de mayor a menor):
  //   1. Lo que el usuario ha escrito a mano en esta sesión del modal (statsEditadosManualmente).
  //   2. El roster del navegador (al escribir el nombre de un aliado guardado).
  //   3. El catálogo (stats base por personaje/clase/nivel): solo al CREAR una unidad
  //      o cuando se cambia el nombre a otro personaje. Editar clase/nivel de una
  //      unidad existente ya no toca sus stats. Nunca salta por un simple blur.
  function catalogoPermitido() {
    if (state.statsEditadosManualmente) return false;
    return state.modalModo === "crear";
  }

  // Al cambiar el nombre: si está en el roster del navegador se precarga entero;
  // si no, se rellenan las stats base del catálogo (solo si el catálogo tiene permiso).
  async function autoRellenarDesdeRosterOCatalogo() {
    const nombre = $("f-nombre")?.value.trim() || "";
    const esAliado = $("f-bando-aliado")?.checked ?? true;
    if (nombre === state.nombrePrecargadoRoster) return;   // no ha cambiado de personaje
    if (esAliado && nombre) {
      const entrada = obtenerEntradaRoster(nombre);
      if (entrada) {
        const x = parseInt($("f-x").value, 10) || 0;
        const y = parseInt($("f-y").value, 10) || 0;
        rellenarFormularioDesdeFicha({ ...entrada, x, y, es_aliado: true });
        state.nombrePrecargadoRoster = entrada.nombre;
        state.statsEditadosManualmente = true;   // datos del roster: el catálogo no los pisa
        mostrarToast(`Datos de ${entrada.nombre} cargados de tu roster`, "info");
        return;
      }
      // Venía de una precarga del roster y el nuevo nombre no está guardado: al crear,
      // volver a los valores por defecto para no arrastrar clase/emblema/inventario ajenos.
      if (state.nombrePrecargadoRoster && state.modalModo === "crear") {
        const x = parseInt($("f-x").value, 10) || 0;
        const y = parseInt($("f-y").value, 10) || 0;
        abrirModalCreacion(x, y, true);
        $("f-nombre").value = nombre;
      }
      state.nombrePrecargadoRoster = "";
    }
    // Cambiar a otro personaje en modo edición/roster también es "nueva unidad": catálogo permitido
    if (state.modalModo === "crear" || !state.statsEditadosManualmente) {
      state.nombrePrecargadoRoster = nombre;
      await autoRellenarStatsDesdeCatalogo();
    }
  }

  // Listeners de autorellenado: solo al CAMBIAR el nombre (nunca por blur), y
  // clase/nivel solo mientras se crea una unidad nueva sin stats tocadas a mano.
  $("f-nombre").addEventListener("change", autoRellenarDesdeRosterOCatalogo);
  const autoRellenarSiPermitido = () => { if (catalogoPermitido()) autoRellenarStatsDesdeCatalogo(); };
  $("f-clase").addEventListener("change", autoRellenarSiPermitido);
  $("f-nivel").addEventListener("change", autoRellenarSiPermitido);
  $("f-nivel").addEventListener("input", () => {
    clearTimeout(state.timerNivel);
    state.timerNivel = setTimeout(autoRellenarSiPermitido, 350);
  });

  // Botón explícito: rellenar desde el catálogo cuando el usuario lo pida
  if ($("f-boosts-fusion")) {
    $("f-boosts-fusion").addEventListener("change", actualizarAvisoFusion);
  }

  if ($("btn-stats-catalogo")) {
    $("btn-stats-catalogo").addEventListener("click", async () => {
      await autoRellenarStatsDesdeCatalogo();
      state.statsEditadosManualmente = false;
    });
  }

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

  if ($("f-energia-emblema")) {
    $("f-energia-emblema").addEventListener("input", actualizarEstadoEnergiaModal);
    $("f-energia-emblema").addEventListener("change", actualizarEstadoEnergiaModal);
  }
  if ($("btn-energia-0")) {
    $("btn-energia-0").addEventListener("click", () => {
      if ($("f-energia-emblema")) $("f-energia-emblema").value = 0;
      actualizarEstadoEnergiaModal();
      mostrarToast("Medidor de Emblema vaciado (0 cargas)", "info");
    });
  }
  if ($("btn-energia-mas1")) {
    $("btn-energia-mas1").addEventListener("click", () => {
      if ($("f-energia-emblema")) {
        const cur = parseInt($("f-energia-emblema").value || 0, 10);
        $("f-energia-emblema").value = cur + 1;
      }
      actualizarEstadoEnergiaModal();
    });
  }
  if ($("btn-energia-max")) {
    $("btn-energia-max").addEventListener("click", () => {
      const nivV = $("f-nivel-vinculo") ? (parseInt($("f-nivel-vinculo").value, 10) || 1) : 1;
      const maxE = nivV >= 20 ? 5 : 6;
      if ($("f-energia-emblema")) $("f-energia-emblema").value = maxE;
      actualizarEstadoEnergiaModal();
      mostrarToast(`Medidor de Emblema al máximo (${maxE}/${maxE})`, "ok");
    });
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
      state.fusionActivandoseEnModal = true;
      if ($("f-energia-emblema")) $("f-energia-emblema").value = 0;
      actualizarEstadoEnergiaModal();
      if (bond && bond.engage_skills) {
        bond.engage_skills.forEach(sk => addChip("chips-pasivas", sk.nombre || sk.sid || sk));
      }
      if (eInfo.engage_attack) {
        addChip("chips-pasivas", `${eInfo.engage_attack}`);
      }
      renderizarArmasFusionModal(null);
      mostrarToast(`Fusión Engage con ${eInfo.nombre} activada!`, "ok");
    } else {
      state.fusionActivandoseEnModal = false;
      actualizarEstadoEnergiaModal();
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
      state.armaEmblemaEquipadaTemporal = null;
      renderizarArmasFusionModal(null);
      mostrarToast(`Fusión desactivada`, "info");
    }
    recalcularCombatStats();
  });

  // Listeners para estadísticas de combate en vivo. Tocar cualquier stat a mano
  // bloquea el autorrellenado del catálogo hasta que se reabra el modal.
  ["f-stat-str", "f-stat-mag", "f-stat-dex", "f-stat-spd", "f-stat-def", "f-stat-res", "f-stat-lck", "f-stat-bld", "f-stat-mov"].forEach(id => {
    const el = $(id);
    if (el) {
      el.addEventListener("input", () => { state.statsEditadosManualmente = true; recalcularCombatStats(); });
      el.addEventListener("change", recalcularCombatStats);
    }
  });
  ["f-hp-actual", "f-hp-max"].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener("input", () => { state.statsEditadosManualmente = true; });
  });

  // Listeners y autocompletados para las 5 ranuras de inventario
  for (let i = 0; i < 5; i++) {
    setupAutocomplete(`inv-nombre-${i}`, "list-armas", "armas");

    const nomInput = $(`inv-nombre-${i}`);
    if (nomInput) {
      nomInput.addEventListener("input", () => {
        actualizarFilaSlot(i);
        recalcularCombatStats();
      });
      nomInput.addEventListener("change", () => {
        actualizarFilaSlot(i);
        recalcularCombatStats();
      });
    }

    const forjaSelect = $(`inv-forja-${i}`);
    if (forjaSelect) {
      forjaSelect.addEventListener("change", () => {
        recalcularCombatStats();
      });
    }

    const grabadoSelect = $(`inv-grabado-${i}`);
    if (grabadoSelect) {
      grabadoSelect.addEventListener("change", () => {
        recalcularCombatStats();
      });
    }

    const usosInput = $(`inv-usos-${i}`);
    if (usosInput) {
      usosInput.addEventListener("change", () => {
        recalcularCombatStats();
      });
    }

    const radioEquip = $(`inv-equip-${i}`);
    if (radioEquip) {
      radioEquip.addEventListener("change", () => {
        state.armaEmblemaEquipadaTemporal = null;
        actualizarTodosLosSlots();
        renderizarArmasFusionModal(null);
        recalcularCombatStats();
      });
    }

    const btnClear = document.querySelector(`.btn-clear-slot[data-slot="${i}"]`);
    if (btnClear) {
      btnClear.addEventListener("click", () => {
        if ($(`inv-nombre-${i}`)) $(`inv-nombre-${i}`).value = "";
        if ($(`inv-forja-${i}`)) $(`inv-forja-${i}`).value = "0";
        if ($(`inv-grabado-${i}`)) $(`inv-grabado-${i}`).value = "";
        if ($(`inv-usos-${i}`)) $(`inv-usos-${i}`).value = "3";
        actualizarFilaSlot(i);
        recalcularCombatStats();
      });
    }
  }

  // Autocompletados de campos simples
  setupAutocomplete("f-nombre", "list-personajes", "personajes");
  setupAutocomplete("f-clase", "list-clases", "clases");
  setupAutocomplete("f-emblema", "list-emblemas", "emblemas");

  // Chip input: habilidades pasivas
  setupChipInput("f-pasivas", "chips-pasivas", "habilidades");

  // Botones de la toolbar
  $("btn-add-aliado").addEventListener("click", () => abrirModalCreacion(4, 8, true));
  $("btn-add-enemigo").addEventListener("click", () => abrirModalCreacion(16, 8, false));
  
  $("btn-preset-cap7").addEventListener("click", async () => {
    const selDif = $("select-dificultad");
    const dificultad = selDif ? selDif.value : "Hard";
    const res = await api("/api/preset/actual", "POST", { dificultad });
    if (res.ok && res.fichas) {
      state.dificultad = dificultad;
      await refrescarRefuerzosPendientes();
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

  // Gestión de Escuadrón Persistente (localStorage del navegador)
  $("btn-guardar-squad").addEventListener("click", () => {
    const n = guardarEscuadronLocal();
    if (n > 0) {
      mostrarToast(`Escuadrón guardado en este navegador (${n} aliados)`, "ok");
    } else {
      mostrarToast("No hay aliados vivos en el mapa que guardar", "error");
    }
  });

  $("btn-desplegar-squad").addEventListener("click", async () => {
    const escuadron = cargarEscuadronLocal();
    if (!escuadron.length) {
      mostrarToast("No hay escuadrón guardado en este navegador", "error");
      return;
    }
    const res = await api("/api/escuadron/desplegar", "POST", { escuadron });
    if (res.ok && res.fichas) {
      actualizarTokens(res.fichas);
      mostrarToast(`${res.mensaje || "Escuadrón desplegado"}`, "ok");
      setTimeout(lanzarAnalisis, 250);
    } else {
      mostrarToast(`${res.error || "No hay escuadrón guardado"}`, "error");
    }
  });

  // Roster de aliados
  $("btn-roster").addEventListener("click", abrirRoster);
  $("btn-roster-close").addEventListener("click", cerrarRoster);
  $("roster-backdrop").addEventListener("click", (e) => { if (e.target.id === "roster-backdrop") cerrarRoster(); });
  $("btn-roster-nuevo").addEventListener("click", () => abrirModalRoster(null));
  $("btn-roster-exportar").addEventListener("click", exportarRoster);
  $("input-importar-roster").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const n = importarRoster(JSON.parse(ev.target.result));
        renderizarRoster();
        mostrarToast(`Roster importado: ${n} aliados`, "ok");
      } catch (err) {
        mostrarToast("Archivo de roster no válido", "error");
      }
      e.target.value = "";
    };
    reader.readAsText(file);
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
    refrescarObjetosMapa();
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
    avisarRefuerzosProximoTurno();
    notificarEstadosOtorgados(res);
    notificarRecargaEmblema(res);
    notificarEfectosArea(res);
    refrescarObjetosMapa(res);
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
    notificarRefuerzos(res);
    notificarEfectosArea(res);
    refrescarRefuerzosPendientes();
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
    refrescarObjetosMapa();
    mostrarToast("Tablero reiniciado al Turno 1", "ok");
    setTimeout(lanzarAnalisis, 350);
  }
});

// ─── Ejecución Interactiva de Jugadas y Combate ────────────────────────────

async function ejecutarJugada(r) {
  const payload = {
    atacante: r.aliado,
    defensor: r.enemigo,
    arma_nombre: r.objeto_id ? "" : r.arma_recomendada,
    objeto_id: r.objeto_id || "",
    pos_destino: r.pos_sugerida,
    pos_canter: r.pos_canter || null,
    requiere_fusion: !!r.requiere_fusion,
    es_engage_attack: !!(r.es_engage_attack || (r.arma_recomendada && (r.arma_recomendada.toLowerCase().includes("rush") || r.arma_recomendada.toLowerCase().includes("override") || r.arma_recomendada.toLowerCase().includes("blazing") || r.arma_recomendada.toLowerCase().includes("ragnarok"))))
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
  notificarRecargaEmblema(res);
  notificarEfectosArea(res);
  if (res.objetos) refrescarObjetosMapa(res);
  // Un ataque de área puede haber cambiado a varias unidades y al atacante: refrescar todo
  if (res.objetivos_extra && res.objetivos_extra.length || res.pos_final_area) {
    const est = await api("/api/estado", "GET");
    if (est && est.fichas) actualizarTokens(est.fichas);
  }

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
  notificarEstadosOtorgados(res);

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
  const resUso = await api("/api/unidad/usar_objeto", "POST", { nombre: r.aliado, item_nombre: r.baston });
  if (resUso.fichas) actualizarTokens(resUso.fichas);
  notificarRecargaEmblema(resUso);
  if (resUso.objetos) refrescarObjetosMapa(resUso);
  mostrarToast(`${r.aliado} usó ${r.baston} en ${r.objetivo} (+${r.curacion_estimada} HP)`, "ok");
  setTimeout(lanzarAnalisis, 400);
}

async function ejecutarPocion(r) {
  const ali = state.fichas[r.aliado];
  if (ali) {
    // Curación del datamine (Poción 15, Elixir 30…) calculada por el análisis
    const cur = (r.curacion_estimada !== undefined && r.curacion_estimada !== null) ? r.curacion_estimada : 15;
    const nuevoHp = Math.min(ali.hp_max, (ali.hp_actual || ali.stats?.hp || 0) + cur);
    const res = await api("/api/unidad/ajustar_hp", "POST", { nombre: r.aliado, hp_actual: nuevoHp });
    if (res.fichas) actualizarTokens(res.fichas);
  }
  const resUso = await api("/api/unidad/usar_objeto", "POST", { nombre: r.aliado, item_nombre: r.item });
  if (resUso.fichas) actualizarTokens(resUso.fichas);
  notificarRecargaEmblema(resUso);
  if (resUso.objetos) refrescarObjetosMapa(resUso);
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
  let headerText = `${r.aliado} vs ${r.enemigo}`;
  if (r.tipo_analisis === "apoyo_curacion") {
    headerText = `💚 ${r.aliado} → ${r.objetivo || 'Aliado'} (Curación)`;
  } else if (r.tipo_analisis === "uso_pocion") {
    headerText = `🧪 ${r.aliado} (Supervivencia)`;
  } else if (r.tipo_analisis === "combo_ataque") {
    headerText = `⚔️ ${r.aliado} → ${r.enemigo} (Preparar Baja)`;
  } else if (r.tipo_analisis === "vanguardia_segura") {
    headerText = `🛡️ Avance Seguro`;
  } else if (r.tipo_analisis === "objetivo_victoria") {
    headerText = `🏁 ${r.aliado} → Casilla de victoria`;
  } else if (r.plan_jefe) {
    headerText = `👑 ${r.aliado} vs ${r.enemigo} (Asalto al jefe ${r.plan_jefe.orden}/${r.plan_jefe.total})`;
  } else if (r.plan_baja) {
    headerText = `⚔️ ${r.aliado} vs ${r.enemigo} (Baja conjunta ${r.plan_baja.orden}/${r.plan_baja.total})`;
  } else if (r.defensa_objetivo) {
    headerText = `🛡️ ${r.aliado} vs ${r.enemigo} (Defensa)`;
  }

  header.innerHTML = `
    <span>${icon}${headerText}</span>
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
  if (r.tipo_analisis === "oportunidad_jugador" || r.tipo_analisis === "combo_ataque") {
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
    if (r.tipo_analisis === "combo_ataque") {
      btnExec.style.background = "linear-gradient(135deg, #4a148c, #7b1fa2)";
      btnExec.innerHTML = `⚔️ <b>Preparar Baja</b>${labelPos}${labelCanter} · Remata <b>${r.aliado_rematador || 'Aliado'}</b>`;
      btnExec.title = `Mueve a ${r.aliado} para desgastar a ${r.enemigo} con ${r.arma_recomendada || 'Arma'} y dejarlo a tiro de ${r.aliado_rematador || 'Aliado'}`;
    } else {
      if (r.requiere_fusion) {
        btnExec.style.background = "linear-gradient(135deg, #00838f, #00acc1)";
        btnExec.innerHTML = `⚡ <b>Fusionar y Atacar</b>${labelPos}${labelCanter}`;
        btnExec.title = `Activa la Fusión de Emblema con ${r.aliado} y ataca a ${r.enemigo} con ${r.arma_recomendada || 'Arma'}`;
      } else {
        btnExec.innerHTML = `<b>Ejecutar Jugada</b>${labelPos}${labelCanter}`;
        btnExec.title = `Mueve a ${r.aliado} a la casilla óptima y ataca a ${r.enemigo} con ${r.arma_recomendada || 'Arma'}`;
      }
    }
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
  } else if (r.tipo_analisis === "objetivo_victoria") {
    const actionBar = document.createElement("div");
    actionBar.className = "card-action-bar";
    const btnMover = document.createElement("button");
    btnMover.type = "button";
    btnMover.className = "btn-ejecutar-jugada";
    btnMover.innerHTML = `🏁 <b>Mover a (${r.pos_sugerida[0]},${r.pos_sugerida[1]})</b>`;
    btnMover.title = `Mueve a ${r.aliado} a la casilla de victoria`;
    btnMover.addEventListener("click", async () => {
      const res = await api("/api/mover", "POST", { nombre: r.aliado, x: r.pos_sugerida[0], y: r.pos_sugerida[1] });
      if (res.error) { mostrarToast(res.error, "error"); return; }
      if (res.fichas) actualizarTokens(res.fichas);
      mostrarToast(`${r.aliado} en la casilla de victoria: ¡mapa completado!`, "ok");
    });
    actionBar.appendChild(btnMover);
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
  poblarSelectoresGrabado();
  let estado = await api("/api/estado");

  // Si la partida guardada en el navegador era de otro capítulo, cargar ese mapa primero
  try {
    const raw = localStorage.getItem("engage_tracker_partida_local");
    const guardado = raw ? JSON.parse(raw) : null;
    if (guardado && guardado.capitulo && estado.mapa && guardado.capitulo !== estado.mapa.capitulo) {
      const sel = await api("/api/mapa/seleccionar", "POST", { capitulo: guardado.capitulo });
      if (sel && sel.ok) estado = sel.estado;
    }
  } catch (e) { /* sin partida local */ }

  aplicarMapaCargado(estado);
  initModalEvents();
  initModalObjeto();
  initNavCapitulo();
  await migrarEscuadronLegado();

  const restaurado = await restaurarDesdeLocalStorage();
  if (!restaurado && estado.fichas) {
    actualizarTokens(estado.fichas);
  }
}


// ─── Roster de aliados y escuadrón (localStorage del navegador) ─────────────
// El roster guarda la "build" de cada aliado (clase, nivel, stats, inventario, emblema,
// vínculo, pasivas, potenciadores). El escuadrón guarda además las posiciones del último
// despliegue. Ninguno de los dos pasa por el servidor salvo al desplegar.

const ROSTER_KEY = "engage_tracker_roster";
const ESCUADRON_KEY = "engage_tracker_escuadron";
const ROSTER_MIGRADO_KEY = "engage_tracker_roster_migrado";

function cargarRoster() {
  try {
    const raw = localStorage.getItem(ROSTER_KEY);
    const obj = raw ? JSON.parse(raw) : {};
    return (obj && typeof obj === "object" && !Array.isArray(obj)) ? obj : {};
  } catch (e) {
    return {};
  }
}

function guardarRoster(roster) {
  try {
    localStorage.setItem(ROSTER_KEY, JSON.stringify(roster));
  } catch (e) {
    console.warn("No se pudo guardar el roster en localStorage:", e);
  }
}

function claveRoster(nombre) {
  return String(nombre || "").trim().toLowerCase();
}

function obtenerEntradaRoster(nombre) {
  return cargarRoster()[claveRoster(nombre)] || null;
}

// Reduce una ficha del tablero (o un payload del modal) a su build persistente:
// HP al máximo, energía llena, sin fusión ni estado de turno.
function normalizarEntradaRoster(f) {
  const st = f.stats || {};
  const hpMax = f.hp_max || st.hp_max || st.hp || 30;
  const hpStock = f.hp_stock !== undefined ? f.hp_stock : (st.hp_stock || 0);
  const nivelVinculo = f.nivel_vinculo || 1;
  const maxEnergia = nivelVinculo >= 20 ? 5 : 6;
  return {
    nombre: String(f.nombre || "").trim(),
    es_aliado: true,
    nivel: f.nivel || 1,
    clase_nombre: f.clase_nombre || "",
    hp_max: hpMax,
    hp_actual: hpMax,
    hp_stock: hpStock,
    chain_guard_activo: f.chain_guard_activo !== false,
    arma_nombre: f.arma_nombre || (f.arma_equipada && (f.arma_equipada.nombre || f.arma_equipada)) || (f.arma && (f.arma.nombre || f.arma)) || "",
    emblema_nombre: f.emblema_nombre || "",
    nivel_vinculo: nivelVinculo,
    energia_emblema: maxEnergia,
    max_energia_emblema: maxEnergia,
    en_fusion: false,
    turnos_fusion: 0,
    ataque_emblema_usado: false,
    ha_actuado: false,
    cargas_ruptura: 0,
    nivel_veneno: 0,
    lider_tres_casas: f.lider_tres_casas || "Dimitri",
    es_volador: f.es_volador,
    mov: f.mov !== undefined ? f.mov : 4,
    potenciadores_usados: Array.isArray(f.potenciadores_usados) ? [...f.potenciadores_usados] : [],
    boosts_fusion: { ...(f.boosts_fusion || {}) },
    stats: {
      hp: hpMax,
      hp_max: hpMax,
      hp_stock: hpStock,
      fuerza: st.fuerza || 0,
      magia: st.magia || 0,
      destreza: st.destreza || 0,
      velocidad: st.velocidad || 0,
      defensa: st.defensa || 0,
      resistencia: st.resistencia || 0,
      suerte: st.suerte || 0,
      complexion: st.complexion || 1
    },
    habilidades: Array.isArray(f.habilidades) ? [...f.habilidades] : (f.habilidades ? [f.habilidades] : []),
    inventario: Array.isArray(f.inventario) ? JSON.parse(JSON.stringify(f.inventario)) : []
  };
}

// Huecos genéricos del preset ("Aliado 3"): van al escuadrón por su posición, pero no al roster.
function esAliadoGenerico(nombre) {
  return /^aliado(\s|$)/i.test(String(nombre || "").trim());
}

function upsertRoster(fichas) {
  const roster = cargarRoster();
  let n = 0;
  (fichas || []).forEach(f => {
    if (!f || !f.nombre || f.es_aliado === false || esAliadoGenerico(f.nombre)) return;
    roster[claveRoster(f.nombre)] = normalizarEntradaRoster(f);
    n++;
  });
  guardarRoster(roster);
  return n;
}

function eliminarEntradaRoster(nombre) {
  const roster = cargarRoster();
  delete roster[claveRoster(nombre)];
  guardarRoster(roster);
}

// Escuadrón: aliados vivos del tablero con su posición, deduplicados por nombre.
function guardarEscuadronLocal() {
  const vistos = new Set();
  const aliados = Object.values(state.fichas)
    .filter(f => f.es_aliado && f.viva && (f.hp_actual === undefined || f.hp_actual > 0))
    .filter(f => { const k = claveRoster(f.nombre); if (vistos.has(k)) return false; vistos.add(k); return true; });
  if (!aliados.length) return 0;
  try {
    localStorage.setItem(ESCUADRON_KEY, JSON.stringify({
      capitulo: state.capitulo || null,
      guardadoEn: new Date().toISOString(),
      aliados
    }));
  } catch (e) {
    console.warn("No se pudo guardar el escuadrón en localStorage:", e);
  }
  upsertRoster(aliados);
  return aliados.length;
}

function cargarEscuadronLocal() {
  try {
    const raw = localStorage.getItem(ESCUADRON_KEY);
    const obj = raw ? JSON.parse(raw) : null;
    return (obj && Array.isArray(obj.aliados)) ? obj.aliados : [];
  } catch (e) {
    return [];
  }
}

// Primera apertura tras el cambio: vuelca el escuadrón legado del servidor al navegador.
async function migrarEscuadronLegado() {
  try {
    if (localStorage.getItem(ROSTER_MIGRADO_KEY)) return;
    if (Object.keys(cargarRoster()).length === 0 && cargarEscuadronLocal().length === 0) {
      const res = await api("/api/escuadron/cargar", "GET");
      const aliados = (res && res.ok && Array.isArray(res.escuadron)) ? res.escuadron : [];
      if (aliados.length) {
        localStorage.setItem(ESCUADRON_KEY, JSON.stringify({ capitulo: 7, guardadoEn: new Date().toISOString(), aliados }));
        upsertRoster(aliados);
        mostrarToast(`Escuadrón anterior migrado a este navegador (${aliados.length} aliados)`, "info");
      }
    }
    localStorage.setItem(ROSTER_MIGRADO_KEY, "1");
  } catch (e) {
    console.warn("No se pudo migrar el escuadrón legado:", e);
  }
}

// ── UI del roster ──
function abrirRoster() {
  renderizarRoster();
  $("roster-backdrop").classList.remove("hidden");
}

function cerrarRoster() {
  $("roster-backdrop").classList.add("hidden");
}

function renderizarRoster() {
  const cont = $("roster-lista");
  cont.innerHTML = "";
  const entradas = Object.values(cargarRoster()).sort((a, b) => a.nombre.localeCompare(b.nombre));
  if (!entradas.length) {
    cont.innerHTML = '<div class="roster-vacio">Aún no hay aliados guardados. Usa "Guardar" en el escuadrón o "+ Nuevo aliado".</div>';
    return;
  }
  entradas.forEach(e => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "roster-item";
    const nom = document.createElement("span");
    nom.className = "roster-item-nombre";
    nom.textContent = e.nombre;
    const meta = document.createElement("span");
    meta.className = "roster-item-meta";
    meta.textContent = `${e.clase_nombre || "—"} · Nv ${e.nivel || 1}`;
    const emb = document.createElement("span");
    emb.className = "roster-item-emblema";
    emb.textContent = e.emblema_nombre ? `◆ ${e.emblema_nombre}` : "";
    btn.append(nom, meta, emb);
    btn.addEventListener("click", () => abrirModalRoster(e));
    cont.appendChild(btn);
  });
}

// Abre el modal de unidad en modo roster: guarda/borra en localStorage, no en el tablero.
function abrirModalRoster(entrada) {
  cerrarRoster();
  if (entrada) {
    state.modalModo = "roster";
    state.nombrePrecargadoRoster = entrada.nombre;
    state.statsEditadosManualmente = false;
    $("modal-titulo").textContent = `Aliado del roster: ${entrada.nombre}`;
    $("f-edit-original-name").value = entrada.nombre;
    rellenarFormularioDesdeFicha({ ...entrada, x: 0, y: 0, es_aliado: true });
    $("btn-modal-eliminar").classList.remove("hidden");
    $("modal-backdrop").classList.remove("hidden");
  } else {
    abrirModalCreacion(0, 0, true);
    state.modalModo = "roster";
    $("modal-titulo").textContent = "Nuevo aliado del roster";
    $("btn-modal-eliminar").classList.add("hidden");
  }
  $("row-pos-indicator").classList.add("hidden");
  $("btn-modal-eliminar").textContent = "Quitar del roster";
}

function guardarEntradaRosterDesdeModal(nombre) {
  const nombreOriginal = $("f-edit-original-name").value;
  const payload = construirPayloadDesdeModal(null);
  const roster = cargarRoster();
  if (nombreOriginal && claveRoster(nombreOriginal) !== claveRoster(nombre)) {
    delete roster[claveRoster(nombreOriginal)];
  }
  roster[claveRoster(nombre)] = normalizarEntradaRoster(payload);
  guardarRoster(roster);
  cerrarModal();
  abrirRoster();
  mostrarToast(`'${nombre}' guardado en el roster.`, "ok");
}

function exportarRoster() {
  const entradas = Object.values(cargarRoster());
  if (!entradas.length) {
    mostrarToast("El roster está vacío", "error");
    return;
  }
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ roster: entradas }, null, 2));
  const a = document.createElement("a");
  a.setAttribute("href", dataStr);
  a.setAttribute("download", "roster_engage.json");
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// Acepta {roster:[...]}, una lista de fichas, o un escuadrón/partida exportados ({fichas:[...]}).
function importarRoster(data) {
  let lista = [];
  if (Array.isArray(data)) lista = data;
  else if (data && Array.isArray(data.roster)) lista = data.roster;
  else if (data && Array.isArray(data.fichas)) lista = data.fichas;
  else if (data && Array.isArray(data.aliados)) lista = data.aliados;
  else if (data && typeof data === "object") lista = Object.values(data);
  const validas = lista.filter(f => f && typeof f === "object" && f.nombre && f.es_aliado !== false);
  if (!validas.length) throw new Error("sin aliados");
  return upsertRoster(validas);
}

// ─── Navegación entre capítulos ────────────────────────────────────────────

// Reconstruye el tablero a partir de un bloque `estado` de la API (mapa + turno + fase)
function aplicarMapaCargado(estado) {
  const mapa = estado.mapa || {};
  state.capitulo = mapa.capitulo || state.capitulo || null;
  state.turno = estado.turno || 1;
  state.fase  = estado.fase  || "jugador";
  if (estado.refuerzos_pendientes) state.refuerzosPendientes = estado.refuerzos_pendientes;
  if (estado.dificultad) state.dificultad = estado.dificultad;
  actualizarBadge();
  buildGrid(mapa.ancho || 24, mapa.alto || 17);
  renderObjetosMapa(mapa.objetos || []);
  renderCasillasObjetivo(mapa.casillas_objetivo || []);
  renderCasillasFuego(estado.casillas_fuego || []);
  actualizarNavCapitulo(mapa);
}

function actualizarNavCapitulo(info) {
  if (!info || !info.capitulo) return;
  $("label-capitulo").textContent = `Cap. ${info.capitulo}`;
  $("label-capitulo").title = info.nombre || `Capítulo ${info.capitulo}`;
  $("btn-cap-prev").disabled = (info.anterior === null || info.anterior === undefined);
  $("btn-cap-next").disabled = (info.siguiente === null || info.siguiente === undefined);
  $("btn-cap-prev").title = info.anterior ? `Capítulo ${info.anterior}` : "No hay mapa anterior";
  $("btn-cap-next").title = info.siguiente ? `Capítulo ${info.siguiente}` : "No hay mapa siguiente";
}

async function cambiarCapitulo(direccion) {
  const res = await api("/api/mapa/seleccionar", "POST", { direccion });
  if (!res || !res.ok) {
    mostrarToast((res && res.error) || "No se pudo cambiar de capítulo", "error");
    return;
  }
  // El servidor vacía el tablero al cambiar de mapa: no arrastrar fichas del capítulo anterior
  localStorage.removeItem("engage_tracker_partida_local");
  state.fichas = {};
  $("analisis-scroll").innerHTML = "";
  $("btn-turno-fin").textContent = "Turno Enemigo";
  $("btn-turno-fin").style.color = "";
  aplicarMapaCargado(res.estado);
  actualizarTokens(res.estado.fichas || []);
  mostrarToast(`${res.nombre || "Capítulo " + res.capitulo} cargado`, "ok");
}

function initNavCapitulo() {
  $("btn-cap-prev").addEventListener("click", () => cambiarCapitulo(-1));
  $("btn-cap-next").addEventListener("click", () => cambiarCapitulo(1));
}

// ─── Objetos de mapa y casillas objetivo ───────────────────────────────────

const ETIQUETA_OBJETO = { recarga_emblema: "Pozo de Emblema (recarga 100% al terminar la acción aquí)", arma_usable: "Arma usable", destructible: "Destructible" };

function renderObjetosMapa(objetos) {
  state.objetosMapa = Array.isArray(objetos) ? objetos : [];
  // Limpiar marcas previas
  document.querySelectorAll(".celda .obj-marca, .celda .obj-usos").forEach(el => el.remove());
  document.querySelectorAll(".celda").forEach(c => {
    c.classList.remove("obj-recarga_emblema", "obj-arma_usable", "obj-destructible");
    delete c.dataset.objetoId;
  });
  for (const o of objetos || []) {
    if (!o.activo) continue;   // agotado / destruido: desaparece icono y efecto
    for (const [x, y] of o.casillas || []) {
      const celda = $(`c-${x}-${y}`);
      if (!celda) continue;
      celda.classList.add(`obj-${o.tipo}`);
      celda.dataset.objetoId = o.id;
      // El pozo de Emblema es de 1 uso: basta el marco azul (está o no está).
      // Armas usables y destructibles sí muestran icono y usos / HP restantes.
      let detalle = "";
      if (o.tipo !== "recarga_emblema") {
        const marca = document.createElement("div");
        marca.className = "obj-marca";
        celda.appendChild(marca);
        if (o.usos !== null && o.usos !== undefined) detalle = `${o.usos} uso${o.usos === 1 ? "" : "s"}`;
        if (o.vida !== null && o.vida !== undefined) detalle = `${o.vida}/${o.vida_max} HP`;
      }
      if (detalle) {
        const usos = document.createElement("div");
        usos.className = "obj-usos";
        usos.textContent = detalle;
        celda.appendChild(usos);
      }
      const p = o.propiedades || {};
      let desc = `${o.nombre || ETIQUETA_OBJETO[o.tipo] || o.tipo}`;
      if (o.tipo === "arma_usable") desc += ` (${p.arma_permitida || "Arco"}, alcance ${p.distancia_min || 3}-${p.distancia_max || 7}, Hit +20, 1 golpe sin contraataque)`;
      else if (o.tipo === "recarga_emblema") desc += ` — ${ETIQUETA_OBJETO.recarga_emblema}`;
      celda.title = detalle ? `${desc} · ${detalle}` : desc;
    }
  }
}

// ─── Destructibles: edición manual de vida (ataques enemigos / aliados) ──────
// Un destructible es un único objeto aunque ocupe varias casillas: todas comparten `vida`.

state.objetosMapa = state.objetosMapa || [];

async function abrirModalObjeto(idObjeto) {
  let obj = (state.objetosMapa || []).find(o => String(o.id) === String(idObjeto));
  if (!obj) {
    const r = await api("/api/mapa/objetos");
    if (r && r.ok) {
      state.objetosMapa = r.objetos;
      obj = r.objetos.find(o => String(o.id) === String(idObjeto));
    }
  }
  if (!obj || !obj.activo) return;
  const vidaMax = obj.vida_max !== null && obj.vida_max !== undefined ? obj.vida_max : null;
  $("objeto-id").value = obj.id;
  $("objeto-titulo").textContent = `${obj.nombre || "Destructible"} (${(obj.casillas || []).map(c => `${c[0]},${c[1]}`).join(" · ")})`;
  $("objeto-hint").textContent = (obj.casillas || []).length > 1
    ? "Ocupa varias casillas: comparten una única vida. Al llegar a 0 desaparece y sus casillas quedan libres."
    : "Al llegar a 0 desaparece y su casilla queda libre.";
  $("objeto-vida").value = obj.vida !== null && obj.vida !== undefined ? obj.vida : 1;
  $("objeto-vida").max = vidaMax !== null ? vidaMax : 999;
  $("objeto-vida-max").textContent = vidaMax !== null ? vidaMax : "—";
  $("objeto-backdrop").classList.remove("hidden");
  $("objeto-vida").focus();
}

function cerrarModalObjeto() {
  $("objeto-backdrop").classList.add("hidden");
}

async function aplicarVidaObjeto(vida) {
  const id = $("objeto-id").value;
  if (!id) return;
  const res = await api("/api/mapa/objeto/danar", "POST", { id, vida: Math.max(0, parseInt(vida, 10) || 0) });
  if (!res || !res.ok) {
    mostrarToast((res && res.error) || "No se pudo actualizar el objeto", "error");
    return;
  }
  const obj = res.objeto || {};
  renderObjetosMapa(res.objetos);
  cerrarModalObjeto();
  if (obj.activo === false) {
    mostrarToast(`${obj.nombre || "Destructible"} destruido: sus casillas quedan libres`, "ok");
    // El terreno base vuelve a verse: refrescar las casillas que ocupaba
    const ent = (state.objetosMapa || []).find(o => String(o.id) === String(id));
    (ent && ent.casillas || []).forEach(([x, y]) => refrescarTerrenoCasilla(x, y));
  } else {
    mostrarToast(`${obj.nombre || "Destructible"}: ${obj.vida}/${obj.vida_max} HP`, "info");
  }
  state.objetosMapa = res.objetos;
}

async function refrescarTerrenoCasilla(x, y) {
  const t = await api(`/api/terreno/${x}/${y}`);
  const celda = $(`c-${x}-${y}`);
  if (!celda || !t || t.error) return;
  celda.className = "celda " + claseTerreno(t.nombre);
  celda.title = `${t.nombre} | AVO +${t.avo} DEF +${t.dfn}`;
  celda.dataset.tip = `${x},${y} [${t.nombre}] AVO +${t.avo}`;
}

function initModalObjeto() {
  $("btn-objeto-close").addEventListener("click", cerrarModalObjeto);
  $("btn-objeto-cancelar").addEventListener("click", cerrarModalObjeto);
  $("objeto-backdrop").addEventListener("click", (e) => { if (e.target.id === "objeto-backdrop") cerrarModalObjeto(); });
  const ajustar = (d) => {
    const max = parseInt($("objeto-vida").max, 10) || 999;
    const cur = parseInt($("objeto-vida").value, 10) || 0;
    $("objeto-vida").value = Math.max(0, Math.min(max, cur + d));
  };
  $("btn-objeto-menos5").addEventListener("click", () => ajustar(-5));
  $("btn-objeto-menos10").addEventListener("click", () => ajustar(-10));
  $("btn-objeto-full").addEventListener("click", () => { $("objeto-vida").value = $("objeto-vida").max; });
  $("btn-objeto-guardar").addEventListener("click", () => aplicarVidaObjeto($("objeto-vida").value));
  $("btn-objeto-destruir").addEventListener("click", () => aplicarVidaObjeto(0));
  $("objeto-vida").addEventListener("keydown", (e) => { if (e.key === "Enter") aplicarVidaObjeto($("objeto-vida").value); });
}

function renderCasillasObjetivo(casillas) {
  document.querySelectorAll(".celda").forEach(c => c.classList.remove("objetivo-derrota", "objetivo-victoria"));
  for (const c of casillas || []) {
    const celda = $(`c-${c.x}-${c.y}`);
    if (!celda) continue;
    celda.classList.add(`objetivo-${c.objetivo}`);
    celda.title = (c.objetivo === "derrota")
      ? "DERROTA si un enemigo termina aquí su movimiento"
      : "VICTORIA si un aliado llega aquí";
  }
}

// ─── Fuego (Blazing Lion) ──────────────────────────────────────────────────

function renderCasillasFuego(casillas) {
  document.querySelectorAll(".celda.fuego").forEach(c => {
    c.classList.remove("fuego");
    const m = c.querySelector(".fuego-marca");
    if (m) m.remove();
  });
  for (const c of casillas || []) {
    const celda = $(`c-${c.x}-${c.y}`);
    if (!celda) continue;
    celda.classList.add("fuego");
    const marca = document.createElement("div");
    marca.className = "fuego-marca";
    marca.title = `En llamas hasta el turno ${c.expira_turno}: 10 dmg a quien empiece su fase aquí, movimiento +1`;
    celda.appendChild(marca);
  }
  state.casillasFuego = casillas || [];
}

// Tras un combate o cambio de fase: fuego actualizado, objetivos extra y quemaduras
function notificarEfectosArea(res) {
  if (!res) return;
  if (Array.isArray(res.casillas_fuego)) renderCasillasFuego(res.casillas_fuego);
  if (Array.isArray(res.objetivos_extra) && res.objetivos_extra.length) {
    const txt = res.objetivos_extra.map(e => `${e.nombre} (${e.daño} dmg${e.muere ? ", derrotado" : ""})`).join(", ");
    mostrarToast(`Ataque de área: también alcanza a ${txt}`, "ok");
  }
  if (res.pos_final_area) {
    mostrarToast(`Override: atraviesa la línea y acaba en (${res.pos_final_area[0]},${res.pos_final_area[1]})`, "info");
  }
  if (Array.isArray(res.quemados) && res.quemados.length) {
    mostrarToast(`🔥 Fuego: ${res.quemados.map(q => `${q.unidad} −${q.daño} HP`).join(", ")}`, "error");
  }
  if (Array.isArray(res.curados_terreno) && res.curados_terreno.length) {
    mostrarToast(`💚 Terreno curativo: ${res.curados_terreno.map(q => `${q.unidad} +${q.curacion} HP`).join(", ")}`, "ok");
  }
}

// ─── Refuerzos enemigos ────────────────────────────────────────────────────

function notificarRefuerzos(res) {
  const lista = (res && res.refuerzos_desplegados) || [];
  if (!lista.length) return;
  const txt = lista.map(f => `${f.nombre}${(f.habilidades || []).includes("Void Curse") ? " (Void Curse)" : ""}`).join(", ");
  mostrarToast(`⚠ Refuerzos enemigos (turno ${res.turno}): ${txt}`, "error");
}

// Sincroniza en el cliente los refuerzos pendientes (para que la partida local los conserve)
async function refrescarRefuerzosPendientes() {
  const r = await api("/api/refuerzos");
  if (!r || !r.ok) return null;
  const porTurno = {};
  (r.refuerzos || []).forEach(u => {
    const { turno, ...datos } = u;
    (porTurno[String(turno)] = porTurno[String(turno)] || []).push(datos);
  });
  state.refuerzosPendientes = porTurno;
  autoGuardarLocal();
  return r;
}

// Al cerrar la fase de jugador, avisar de lo que aparecerá al empezar el turno siguiente
async function avisarRefuerzosProximoTurno() {
  const r = await refrescarRefuerzosPendientes();
  if (!r || !r.ok) return;
  const proximo = (r.refuerzos || []).filter(u => u.turno === (r.turno_actual + 1));
  if (!proximo.length) return;
  const txt = proximo.map(u => `${u.nombre} en (${u.x},${u.y})`).join(", ");
  mostrarToast(`Al empezar el turno ${r.turno_actual + 1} llegan refuerzos: ${txt}`, "info");
}

// Vuelve a pedir el estado de los objetos (tras acciones que pueden consumirlos)
async function refrescarObjetosMapa(res) {
  if (res && Array.isArray(res.objetos)) {
    renderObjetosMapa(res.objetos);
    return;
  }
  const r = await api("/api/mapa/objetos");
  if (r && r.ok) renderObjetosMapa(r.objetos);
}

function notificarRecargaEmblema(res) {
  const lista = [];
  if (res && res.recarga_emblema) lista.push(res.recarga_emblema);
  if (res && Array.isArray(res.recargas_emblema)) lista.push(...res.recargas_emblema);
  for (const r of lista) {
    mostrarToast(`${r.unidad}: medidor de Emblema recargado al 100%${r.pozo ? " — el pozo se ha agotado" : ""}`, "ok");
  }
}

document.addEventListener("DOMContentLoaded", init);
