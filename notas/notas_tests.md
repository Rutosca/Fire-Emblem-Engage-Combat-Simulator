# Tests — organización y convenciones

```
python -m pytest tests -q
```

## Ficheros (por dominio)

| fichero | qué fija |
|---|---|
| `test_ground_truth_cap7.py` | **Verdad de juego**: números observados en partida (vídeo del Cap. 7 y observaciones propias: Céline 22, Chloé 20/15, Citrinne veneno 7→10, Warp Ragnarök 18…). Si un cambio rompe esto, el motor se ha alejado del juego. |
| `test_golden_combates.py` + `golden/` | **Comportamiento actual**: todos los combates de escenarios reales. Si cambia, hay que justificar cada diferencia (ver `notas_pasivas.md`). |
| `test_combate_mecanicas.py` | Reglas del motor sin número observado: piedras resurrectoras, contraataque por rango, kill con crítico, chain attacks en la API. |
| `test_ruptura.py` | Secuencia de Ruptura a través de `/api/combate/ejecutar` (recibe → no contraataca → recupera). |
| `test_pasivas_sids.py` | Recolección de SIDs activos (`pasivas.sids_activos`). |
| `test_movimiento_posicion.py` | BFS, bloqueos, casilla óptima, líneas de peligro. |
| `test_analisis_tactico.py` | Recomendaciones de `analizar_situacion_tactica` / `/api/analizar`. |
| `test_fusion_emblema.py`, `test_lodestar_and_fusion.py`, `test_emblem_attacks_bond.py` | Fusión, vínculo, armas y ataques de Emblema. |
| `test_chain_guard_objetos.py` | Guardia en Cadena y uso de objetos. |
| `test_catalogo_loader.py`, `test_5slot_inventory.py`, `test_fase1_auditoria.py` | Resolución por catálogo: inventario, grabados, nivel interno, género, jefes. |
| `test_partida_snapshot.py` | Importar/exportar partida como fotografía exacta. |

`helpers.py`: `norm`, `ruta_fixture`, `cargar_roster`, `cargar_dispos`, `unidad_roster`,
`unidad_dispos_en` y la clase base `CasoCapitulo7` (Lance Fighter (10,6), Céline y Chloé
reales). `fixtures/`: partidas exportadas versionadas (`partida_cap7_turno10.json`,
`partida_hortensia_cap7.json`). Nada en `tests/` debe leer de `scratch/` (está en
`.gitignore`).

## Convenciones

- Un fichero por dominio, nombres de test por comportamiento (`test_fusion_no_se_retira_y_decrementa_por_turno`), no por número de arreglo.
- `resolver_unidad_con_catalogo` lee `app.tablero` para heredar estado de una unidad con el mismo nombre (Fusión, veneno, ha_actuado…). Todo test que use la app global hace `tablero.limpiar()` en `setUp`. La suite pasa en orden inverso; mantenerlo así.
- Sin scripts de exploración con `print` en `tests/`: pytest los importa y ejecutan al recoger. Para explorar, `scratch/`.
- Números nuevos observados en el juego → `test_ground_truth_cap7.py` (o `test_ground_truth_capN.py`), con la fuente en el docstring.
- Un capítulo nuevo con mapa Tiled y dispos crea solo su escenario golden: `python tests/golden/generar_golden.py capN_inicial` cuando el mapa esté terminado.
