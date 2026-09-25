# Créditos y fuentes

Esta herramienta no sería posible sin el trabajo de otras personas. Lo que sigue es de
dónde sale cada dato que usa el motor.

## Datos del juego

**[laqieer](https://github.com/laqieer)** — [`laqieer/FE17-DOC`](https://github.com/laqieer/FE17-DOC)
*Documentation for FE17: Fire Emblem Engage*

Todo el comportamiento de combate de la herramienta se lee de ahí. El extractor es lo que
convierte esto en una herramienta con datos reales en vez de una hoja de cálculo con
números a ojo: `compilar_catalogo.py` compila `json/catalogo_engage.json` a partir de sus
ficheros — `Skill.xml` (las Condition/Act* de cada pasiva, que son el motor entero de
`pasivas.py`), `Item.xml` (armas), `Job.xml` (clases), `Person.xml` (personajes),
`God.xml` (Emblemas y vínculos), `Dispos/` (el despliegue enemigo de cada capítulo) y los
`.csv` de textos para los nombres y las descripciones.

El repositorio **no** se distribuye con este proyecto: está en `.gitignore` y hay que
descargarlo aparte.

## Guías y referencias

Las dos cubren terreno parecido, pero con enfoques distintos y se han usado para cosas
distintas.

**[Serenes Forest — Fire Emblem Engage](https://serenesforest.net/engage/)** — la más
enciclopédica de las dos. De aquí salen:

- Las **pasivas de los Emblemas de DLC**, que no están en el datamine:
  Edelgard/Dimitri/Claude, Tiki, Hector, Veronica, Soren, Camilla y Chrom/Robin, recogidos
  en `json/dlc_emblems_canon.json` y `pasivas_overlay.py`.
- Las **correcciones de pasivas del juego base**, cuando lo que hacía el motor no cuadraba
  con lo descrito.
- Las tablas de crecimientos y estadísticas base contra las que está verificada la fórmula
  de reclutamiento (`join_stats`), y las categorías de Apoyo.

**[Fire Emblem WoD — Engage](https://www.fireemblemwod.com/fe17.htm)** — más una guía
personal de cómo avanzar en Maddening (no consta quién la escribe) que una referencia. De
aquí sale sobre todo:

- Los **refuerzos y sus disparadores** por capítulo, que alimentan
  `CALENDARIO_REFUERZOS` y `REFUERZOS_POR_EVENTO` en `cargador_dispos.py`. Es la fuente de
  partida capítulo a capítulo según se van montando los mapas.

Sobre esto último conviene una advertencia, porque ya ha pasado: **cuando la guía y el
juego no coinciden, manda el juego**. Los arqueros del Cap. 10 estaban anotados como
"turno 6" y en realidad salen cuando Hortensia actúa; llegado el turno 6 sin tocarla, no
aparecen. Las guías tienden a describir *cuándo suele pasar* algo, no qué lo dispara. Cada
corrección así queda anotada en `notas/notas_cargador_dispos.md` con la observación que la
respalda.

## Sobre el material original

*Fire Emblem Engage* es propiedad de **Nintendo** e **Intelligent Systems**. Los datos que
usa esta herramienta derivan de los assets del juego: acreditar a quien hizo el trabajo de
extracción no cambia de quién es la obra. Este proyecto es una utilidad personal, sin ánimo
de lucro y sin relación con Nintendo ni con Intelligent Systems.
