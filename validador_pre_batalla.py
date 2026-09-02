from dataclasses import dataclass
from typing import List, Dict
from motor_calculo import CalculadoraEngage

@dataclass
class UnidadRoster:
    nombre: str
    clase: str
    nivel: int
    fuerza: int
    magia: int
    velocidad: int
    armas_tipos: List[str]  # ej. ['Espada', 'Arco']
    tiene_bastones: bool = False
    complexion: int = 7    # BLD — complexión (Build). Default conservador de infantería media.
    peso_arma: int = 0     # WT del arma equipada actualmente. 0 = sin arma o arma ligera.

@dataclass
class GrupoEnemigo:
    tipo_unidad: str  # ej. 'Wyvern', 'Acorazado', 'Mago'
    cantidad: int
    velocidad_media: int
    defensa_media: int
    res_media: int

class AuditorPlantilla:
    """
    Analiza la composición del equipo del jugador antes de iniciar el mapa.
    Busca carencias tácticas (falta de curanderos, daño físico/mágico, anti-aéreos).
    """

    def __init__(self, capitulo: int, roster: List[UnidadRoster], enemigos: List[GrupoEnemigo]):
        self.capitulo = capitulo
        self.roster = roster
        self.enemigos = enemigos
        self.alertas = []
        self.recomendaciones = []

    def _auditar_anti_aereos(self):
        voladores_enemigos = sum(e.cantidad for e in self.enemigos if e.tipo_unidad in ['Pegaso', 'Wyvern', 'Grifo'])
        arqueros_aliados = sum(1 for u in self.roster if 'Arco' in u.armas_tipos or u.clase in ['Tirador', 'Jinete Arquero'])
        
        if voladores_enemigos > 0:
            if arqueros_aliados == 0:
                self.alertas.append(
                    f"CRÍTICO: El mapa tiene {voladores_enemigos} unidades voladoras y NO llevas ningún arco. "
                    "Te van a destrozar el flanco. Equipa un Emblema con arco (ej. Lyn/Lucina) o cambia una clase."
                )
            elif voladores_enemigos >= 5 and arqueros_aliados < 2:
                self.recomendaciones.append(
                    f"Aviso: Alta densidad de voladores ({voladores_enemigos}). Un solo arquero podría no dar abasto."
                )

    def _auditar_ruptura_armaduras(self):
        acorazados_enemigos = sum(e.cantidad for e in self.enemigos if e.tipo_unidad in ['General', 'Jinete Pesado'])
        magos_aliados = sum(1 for u in self.roster if 'Tomo' in u.armas_tipos or u.magia >= 15)
        rompe_armaduras = sum(1 for u in self.roster if 'Martillo' in u.armas_tipos or 'Estoque' in u.armas_tipos)

        if acorazados_enemigos >= 3 and magos_aliados == 0 and rompe_armaduras == 0:
            self.alertas.append(
                f"CRÍTICO: Hay {acorazados_enemigos} Acorazados con extrema defensa física. "
                "No tienes daño mágico ni armas efectivas. Te vas a quedar atascado haciendo 0 de daño."
            )

    def _auditar_velocidad_doble_ataque(self):
        vel_enemiga_media = sum(e.velocidad_media * e.cantidad for e in self.enemigos) / max(1, sum(e.cantidad for e in self.enemigos))
        # Usamos el AS real (Attack Speed) en lugar de la velocidad cruda.
        # En Engage: AS = SPD - max(0, wt - bld). El peso del arma penaliza
        # si supera la complexión de la unidad, lo que puede provocar ataques dobles del enemigo.
        unidades_dobladas = sum(
            1 for u in self.roster
            if CalculadoraEngage.calcular_velocidad_ataque(u.velocidad, u.complexion, u.peso_arma)
            <= (vel_enemiga_media - 5)
        )

        if unidades_dobladas > len(self.roster) * 0.4:
            self.alertas.append(
                f"PELIGRO: El {round((unidades_dobladas/len(self.roster))*100)}% de tu equipo es demasiado lento. "
                f"La media enemiga es {round(vel_enemiga_media)} Vel. Vas a recibir ataques dobles masivos."
            )

    def _auditar_sostenibilidad(self):
        curanderos = sum(1 for u in self.roster if u.tiene_bastones)
        if curanderos == 0:
            self.alertas.append(
                "CRÍTICO: No llevas ninguna unidad capaz de usar Bastones (curación). "
                "En dificultad Extremo esto es un suicidio. Añade un Monje/Obispo o equipa el anillo de Micaiah."
            )

    def ejecutar_auditoria(self) -> dict:
        self._auditar_anti_aereos()
        self._auditar_ruptura_armaduras()
        self._auditar_velocidad_doble_ataque()
        self._auditar_sostenibilidad()

        estado = "OK"
        if len(self.alertas) > 0:
            estado = "NO_GO"
        elif len(self.recomendaciones) > 0:
            estado = "ADVERTENCIA"

        return {
            "estado": estado,
            "alertas_criticas": self.alertas,
            "recomendaciones": self.recomendaciones,
            "viabilidad": "El roster es viable para comenzar el capítulo." if estado == "OK" else "Se requieren ajustes antes de iniciar la batalla."
        }

if __name__ == "__main__":
    # Simulación de un usuario que se olvida de los magos y los arcos
    mi_equipo = [
        UnidadRoster("Alear", "Dragón Divino", 10, 15, 5, 14, ['Espada']),
        UnidadRoster("Vander", "Paladín", 12, 12, 2, 8, ['Hacha']),
        UnidadRoster("Louis", "General", 10, 18, 0, 5, ['Lanza']),
    ]

    # Simulación de enemigos del Capítulo (ej. lleno de voladores y acorazados)
    enemigos_cap_7 = [
        GrupoEnemigo("Wyvern", 6, 16, 12, 5),
        GrupoEnemigo("General", 4, 8, 22, 2),
    ]

    auditor = AuditorPlantilla(7, mi_equipo, enemigos_cap_7)
    reporte = auditor.ejecutar_auditoria()
    
    print(f"--- REPORTE DE BARRACÓN (CAPÍTULO 7) ---")
    print(f"ESTADO: {reporte['estado']}")
    for alerta in reporte['alertas_criticas']:
        print(f"[!] {alerta}")
    for rec in reporte['recomendaciones']:
        print(f"[*] {rec}")