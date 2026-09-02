from enum import Enum
from pydantic import BaseModel, Field

# =============================================================================
# Definición de Intenciones (Intents)
# =============================================================================

class TipoConsulta(str, Enum):
    CALCULO_COMBATE = "calculo_combate"     # "Puedo sobrevivir si Alear ataca al jefe?"
    RNG_CRONOGEMA = "rng_cronogema"         # "He fallado con un 90%, ¿rebobino?"
    GUIA_ESTRATEGICA = "guia_estrategica"   # "¿Qué refuerzos salen en el turno 5?"
    INFO_SISTEMA = "info_sistema"           # "¿A qué nivel aprende Canter esta clase?"
    DESCONOCIDO = "desconocido"             # Charla genérica

class RespuestaClasificacion(BaseModel):
    """Estructura estricta que le pediremos al LLM que nos devuelva."""
    intencion: TipoConsulta = Field(description="La categoría de la pregunta del usuario.")
    entidades_detectadas: dict = Field(description="Nombres de personajes, capítulos o armas mencionados.", default_factory=dict)
    justificacion: str = Field(description="Breve motivo por el que se eligió esta intención.")

# =============================================================================
# Motor de Enrutamiento
# =============================================================================

class EnrutadorTactico:
    def __init__(self, llm_client=None):
        """
        Inicializa el enrutador. 
        En producción, llm_client sería tu instancia de OpenAI/Gemini/Anthropic.
        """
        self.llm = llm_client

    def analizar_intencion(self, mensaje_usuario: str) -> RespuestaClasificacion:
        """
        Envía el mensaje al LLM pidiendo que responda ÚNICAMENTE con un JSON
        que cumpla la estructura de RespuestaClasificacion.
        """
        prompt_sistema = """
        Eres el enrutador de un asistente táctico de Fire Emblem Engage.
        Tu trabajo NO es responder a la pregunta del jugador, sino clasificar 
        qué herramienta del sistema debe usarse para responderle.
        
        Reglas de clasificación:
        - Si implica daño, supervivencia, matar o atacar -> CALCULO_COMBATE
        - Si habla de fallar, críticos sorpresa, mala suerte o Cronogema -> RNG_CRONOGEMA
        - Si pregunta por la historia, refuerzos, qué hacer en el mapa -> GUIA_ESTRATEGICA
        - Si pregunta por estadísticas estáticas de clases o habilidades -> INFO_SISTEMA
        """
        
        # ── SIMULACIÓN DE RESPUESTA DEL LLM PARA DESARROLLO ──
        # En producción, aquí harías: return self.llm.chat(prompt_sistema, mensaje_usuario)
        
        mensaje_lower = mensaje_usuario.lower()
        if "fall" in mensaje_lower or "cronogema" in mensaje_lower or "suerte" in mensaje_lower:
            return RespuestaClasificacion(
                intencion=TipoConsulta.RNG_CRONOGEMA,
                entidades_detectadas={},
                justificacion="El usuario menciona eventos probabilísticos pasados."
            )
        elif "ataca" in mensaje_lower or "mata" in mensaje_lower or "sobrevive" in mensaje_lower:
            return RespuestaClasificacion(
                intencion=TipoConsulta.CALCULO_COMBATE,
                entidades_detectadas={"atacante": "detectar_por_nlp"},
                justificacion="El usuario quiere predecir el resultado de una acción."
            )
        else:
            return RespuestaClasificacion(
                intencion=TipoConsulta.GUIA_ESTRATEGICA,
                entidades_detectadas={},
                justificacion="Consulta general sobre el flujo del juego o mapa."
            )

    def procesar_consulta(self, mensaje_usuario: str, estado_tablero: dict):
        """
        El orquestador principal. Clasifica y luego ejecuta la herramienta adecuada.
        """
        print(f"\n[Usuario]: {mensaje_usuario}")
        
        # 1. Entender qué quiere el usuario
        clasificacion = self.analizar_intencion(mensaje_usuario)
        print(f"[Enrutador]: Intención detectada -> {clasificacion.intencion.value}")
        
        # 2. Derivar a la herramienta correspondiente
        if clasificacion.intencion == TipoConsulta.CALCULO_COMBATE:
            return self._ejecutar_herramienta_calculo(estado_tablero, clasificacion.entidades_detectadas)
            
        elif clasificacion.intencion == TipoConsulta.RNG_CRONOGEMA:
            return self._ejecutar_asesor_rng()
            
        elif clasificacion.intencion == TipoConsulta.GUIA_ESTRATEGICA:
            return self._ejecutar_busqueda_rag(mensaje_usuario)
            
        else:
            return "Comandante, no he entendido su orden. Especifique el objetivo."

    # ── Implementación de Herramientas (Conectores) ──

    def _ejecutar_herramienta_calculo(self, estado_tablero, entidades):
        # Aquí llamaríamos a CalculadoraEngage.evaluar_riesgo()
        return "[SYSTEM] Invocando Motor de Cálculo Determinista..."

    def _ejecutar_asesor_rng(self):
        # Usamos la lógica de "Quemar RNs" que definimos antes
        return "[SYSTEM] Invocando Protocolo de Manipulación de RNG..."
        
    def _ejecutar_busqueda_rag(self, query):
        # Aquí buscaríamos en la Base de Datos Vectorial (Qdrant/Chroma)
        return "[SYSTEM] Buscando guías del mapa en Base de Datos Vectorial..."

# =============================================================================
# Prueba de Ejecución
# =============================================================================
if __name__ == "__main__":
    router = EnrutadorTactico()
    estado_dummy = {"capitulo": 6}
    
    router.procesar_consulta("Si ataco con Alear, ¿sobrevive al contraataque?", estado_dummy)
    router.procesar_consulta("He fallado el 80% y he usado la cronogema, qué hago?", estado_dummy)
    router.procesar_consulta("¿Por dónde salen los refuerzos en este nivel?", estado_dummy)