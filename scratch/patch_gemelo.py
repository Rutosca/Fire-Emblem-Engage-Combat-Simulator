path = r"c:\Rubén\Proyectos\Engage_tracker\static\gemelo.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update token badges in crearToken
old_token_badge = '''  if (ficha.en_fusion || ficha.turnos_fusion > 0) {
    const badge = document.createElement("span");
    badge.className = "token-engage-badge";
    badge.textContent = "ENG";
    badge.title = "Fusión con Emblema Activa";
    tok.appendChild(badge);
  }'''

new_token_badge = '''  if (ficha.en_fusion || ficha.turnos_fusion > 0) {
    const badge = document.createElement("span");
    badge.className = "token-engage-badge";
    badge.textContent = `ENG ${ficha.turnos_fusion || 3}t`;
    badge.title = `Fusión activa: ${ficha.turnos_fusion || 3} turnos restantes${ficha.ataque_emblema_usado ? ' (Técnica Engage usada)' : ''}`;
    tok.appendChild(badge);
  } else if (ficha.es_aliado && ficha.emblema_nombre) {
    const energia = ficha.energia_emblema !== undefined ? ficha.energia_emblema : 6;
    const maxEnergia = ficha.max_energia_emblema || 6;
    const gaugeBadge = document.createElement("span");
    gaugeBadge.className = "token-gauge-badge" + (energia >= maxEnergia ? " gauge-lleno" : "");
    gaugeBadge.textContent = energia >= maxEnergia ? "LISTO" : `${energia}/${maxEnergia}`;
    gaugeBadge.title = `Medidor de Emblema: ${energia}/${maxEnergia}${energia >= maxEnergia ? ' (Fusión lista)' : ''}`;
    tok.appendChild(gaugeBadge);
  }'''

content = content.replace(old_token_badge, new_token_badge)

# 2. Update desc title in crearToken
old_desc = '''  if (ficha.en_fusion || ficha.turnos_fusion > 0) desc += `\\n[MODO ENGAGE ACTIVO: Fusión con ${ficha.emblema_nombre || 'Emblema'}]`;'''
new_desc = '''  if (ficha.en_fusion || ficha.turnos_fusion > 0) desc += `\\n[MODO ENGAGE ACTIVO: ${ficha.turnos_fusion} turno(s) restante(s)${ficha.ataque_emblema_usado ? ' - Técnica Engage consumida' : ''}]`;
  else if (ficha.es_aliado && ficha.emblema_nombre) desc += `\\n[MEDIDOR DE EMBLEMA: ${ficha.energia_emblema !== undefined ? ficha.energia_emblema : 6}/${ficha.max_energia_emblema || 6}${ficha.energia_emblema >= (ficha.max_energia_emblema || 6) ? ' - FUSIÓN LISTA' : ''}]`;'''

content = content.replace(old_desc, new_desc)

# 3. In abrirModalNuevo, initialize f-nivel-vinculo
old_nuevo = '''  $("f-fusion").checked = false;
  $("label-fusion").style.opacity = esAliado ? "1" : "0.5";
  $("label-fusion").style.pointerEvents = esAliado ? "auto" : "none";'''

new_nuevo = '''  if ($("f-nivel-vinculo")) $("f-nivel-vinculo").value = "1";
  $("f-fusion").checked = false;
  $("f-fusion").disabled = !esAliado;
  $("label-fusion").style.opacity = esAliado ? "1" : "0.5";
  $("label-fusion").style.pointerEvents = esAliado ? "auto" : "none";
  $("label-fusion").title = "";'''

content = content.replace(old_nuevo, new_nuevo)

# 4. In abrirModalEdicion, lock fusion if active
old_edicion = '''  $("f-emblema").value = ficha.emblema_nombre || "";
  establecerLiderTresCasas(ficha.lider_tres_casas || "Dimitri");
  actualizarSelectorLiderTresCasas();
  $("f-fusion").checked = ficha.en_fusion || false;

  const tieneEmblema = !!ficha.emblema_nombre;
  $("label-fusion").style.opacity = tieneEmblema ? "1" : "0.5";
  $("label-fusion").style.pointerEvents = tieneEmblema ? "auto" : "none";'''

new_edicion = '''  $("f-emblema").value = ficha.emblema_nombre || "";
  if ($("f-nivel-vinculo")) $("f-nivel-vinculo").value = ficha.nivel_vinculo || 1;
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
  }'''

content = content.replace(old_edicion, new_edicion)

# 5. In guardarUnidadDesdeModal
old_guardar = '''  const str = parseInt($("f-stat-str").value, 10) || 0;'''
new_guardar = '''  const nivelVinculo = $("f-nivel-vinculo") ? (parseInt($("f-nivel-vinculo").value, 10) || 1) : 1;
  const str = parseInt($("f-stat-str").value, 10) || 0;'''

content = content.replace(old_guardar, new_guardar)

old_guardar_payload = '''  const fichaExistente = state.fichas[nombreOriginal || nombre];
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
    en_fusion: enFusion,'''

new_guardar_payload = '''  const fichaExistente = state.fichas[nombreOriginal || nombre];
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
    nivel_vinculo: nivelVinculo,'''

content = content.replace(old_guardar_payload, new_guardar_payload)

# 6. In f-fusion change listener
old_change = '''  $("f-fusion").addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    const eInfo = buscarEmblemaInfo($("f-emblema").value);
    if (!eInfo) return;'''

new_change = '''  $("f-fusion").addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    const nombreOriginal = $("f-edit-original-name") ? $("f-edit-original-name").value : "";
    const fichaExistente = state.fichas[nombreOriginal];
    if (fichaExistente && (fichaExistente.en_fusion || fichaExistente.turnos_fusion > 0) && fichaExistente.turnos_fusion > 0 && !isChecked) {
      e.target.checked = true;
      mostrarToast(`La fusión no puede retirarse manualmente. Quedan ${fichaExistente.turnos_fusion} turno(s).`, "info");
      return;
    }
    const eInfo = buscarEmblemaInfo($("f-emblema").value);
    if (!eInfo) return;'''

content = content.replace(old_change, new_change)

# Remove any stray emojis in strings
content = content.replace("¡Fusión Engage con ", "Fusión Engage con ")
content = content.replace("! activada!", " activada.")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("gemelo.js patched successfully!")
