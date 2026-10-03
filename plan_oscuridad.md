Antes de comenzar con el análisis y plan, saber que una antorcha, según la guía, "Burn to illuminate a 7-space radius (shrinks one space per turn)." Importante lo de que se encoge cada turno que pasa. Las antorchas 
La herramienta debe tener privilegios de conocimiento, pero no de ejecución.

Es decir, el simulador puede conocer el estado completo del juego gracias al datamine, pero no debe conceder al jugador acciones que el juego no le permitiría realizar con la información o posición actual.
Eso cambia bastante cómo implementaría la oscuridad.
El enemigo oculto sigue existiendo, pero no es un objetivo válido
Internamente puedes saber:
Enemy 17
posición real: (14, 9)
HP: 38
movimiento: 6
Pero para el sistema de acciones:
visible = false
targetable = false
Por tanto:
Ataque de unidad A → Enemy 17
       ↓
      ❌
aunque el motor sepa perfectamente que está ahí.
Eso es importante porque evita una de las trampas más peligrosas de un simulador de este tipo: confundir conocimiento omnisciente del motor con conocimiento/acciones disponibles para el jugador.
La Cronogema se convierte en una herramienta de planificación
Aquí creo que tu idea de guía debería ser algo más explícita.
Supongamos:
Estado actual

Alear ──────► zona oscura
                Enemy X
                Enemy Y
El jugador avanza con Alear y descubre:
Enemy X = (12,8)
Enemy Y = (14,9)
La herramienta registra ambos.
Entonces haces Cronogema.
Ahora vuelves al estado anterior:
Enemy X → conocido
Enemy Y → conocido

pero:
X.visible = false
Y.visible = false
X.targetable = false
Y.targetable = false
Y ahí el analizador puede decir:
Para eliminar a X e Y necesitas primero revelar su posición con una unidad que pueda entrar en su rango de visión.

Y la solución podría ser:
1. Mueve Alear a (11,8)
        ↓
2. X queda visible
        ↓
3. Ataca X con Panette
        ↓
4. Mueve Chloé para revelar Y
        ↓
5. Ataca Y con Kagetsu
Eso ya no es una simple predicción.
Es planificación sobre acciones legales.
Esto encaja muchísimo mejor con tu filosofía
Yo dividiría el sistema conceptualmente en tres capas:
                    ┌─────────────────┐
                    │  ESTADO REAL    │
                    │                 │
                    │ Todo lo que     │
                    │ realmente ocurre│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   VISIBILIDAD   │
                    │                 │
                    │ ¿Qué conoce el  │
                    │ jugador?        │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ ACCIONES VÁLIDAS │
                    │                 │
                    │ ¿Qué puede hacer│
                    │ realmente?      │
                    └─────────────────┘
Y encima de eso:
                 ANALIZADOR
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     combate      movimiento    riesgo
El analizador tiene acceso al estado real porque necesita saber qué ocurriría si haces una jugada.
Pero las acciones disponibles deben pasar por las mismas restricciones que el juego.
Y ahí aparece algo muy interesante
Tu herramienta puede tener una ventaja que el jugador no tiene:
Conocimiento retrospectivo
El motor sabe:
"Sé que hay dos enemigos detrás de esa esquina."

Pero no puede hacer:
"Entonces ataco al enemigo."

Tiene que hacer:
"¿Qué movimiento legal permite descubrirlo?"

Y después:
"Una vez descubierto, ¿qué ataques legales puedo realizar?"

Eso hace que el sistema sea simultáneamente omnisciente y honesto.
Una combinación bastante más rara de lo que debería ser en software de simulación, porque aparentemente hasta los simuladores tienen que aprender a no hacer trampas.
Incluso aprovecharía esto para las recomendaciones
En vez de mostrar simplemente:
⚠️ Enemigo oculto cerca.

Podrías distinguir:
Información
Enemigos conocidos pero ocultos: X, Y

Riesgo
Su posición actual no está confirmada. Pueden desplazarse hasta 6 casillas desde su última posición conocida.

Acción recomendada
Para atacar a X, primero necesitas revelar su posición.

Secuencia legal
Visor:
Alear → posición X

Revelar:
X → visible

Atacante:
Panette → X

Resultado:
X eliminado
Y si existen varias posibilidades:
Visor A → revela X → Panette mata X
Visor B → revela X → Kagetsu mata X
puedes compararlas según riesgo, movimiento restante, posiciones finales, etc.
Ahí el sistema empieza a hacer exactamente lo que tú describes:
guiar al jugador hacia la victoria más segura con lo que sabe

No jugar por él.
Y eso también resuelve el problema de los refuerzos
Los refuerzos conocidos por el datamine pueden existir en el estado real:
reinforcement #23
spawn = turn 10
position = (20,4)
Pero hasta que aparezcan:
discovered = false
visible = false
El jugador no debería poder reaccionar a ellos como si los hubiera visto.
Puedes incluso tener internamente:
REAL WORLD
──────────
Enemy 23 exists
Enemy 24 exists
Enemy 25 exists

PLAYER KNOWLEDGE
────────────────
Enemy 23 ❓
Enemy 24 ❓
Enemy 25 ❓
Cuando aparece el refuerzo:
Enemy 23
       ↓
spawn
       ↓
visibility check
       ↓
visible / hidden
y entonces entra en el mismo sistema.
Así que yo no intentaría que la herramienta "prediga movimientos enemigos"
Al menos no como comportamiento principal.
Haría:
1. Estado real:
el datamine permite conocerlo.
2. Estado conocido:
solo contiene lo que el jugador ha descubierto.
3. Estado visible:
determina qué enemigos son realmente seleccionables.
4. Predicción:
solo genera zonas potenciales de amenaza, nunca posiciones afirmadas como ciertas.
5. Planificador:
busca secuencias de acciones que respeten las restricciones reales, incluyendo revelar → atacar.
Y esa arquitectura tiene una propiedad muy buena: si mañana descubres que tu modelo de IA enemiga no reproduce perfectamente alguna situación rara de Engage, el simulador no se rompe conceptualmente. Simplemente tendrá menos capacidad para predecir el futuro. El estado observado y las acciones legales siguen siendo fiables.
Para un Digital Twin de un juego táctico determinista, me parece una distinción fundamental. El objetivo no debería ser que el simulador adivine qué hará la CPU. Debería ser que cuando te diga "puedes hacer esto", puedas hacerlo realmente en Engage.