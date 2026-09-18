"""
condicion_dsl.py — Intérprete de la DSL Condition/Act* de Skill.xml (FE Engage)

Skill.xml codifica las pasivas del juego con un mini-lenguaje de condiciones en
japonés (campo Condition) y una lista estructurada de efectos (ActNames /
ActOperations / ActValues). Este módulo tokeniza, parsea y evalúa esa DSL
contra un ContextoCombate, para que motor_calculo.py deje de adivinar
umbrales/valores por nombre de habilidad y use los reales del datamine.

Vocabulario: solo se registran las variables/funciones que necesitan las
habilidades relevantes para el Capítulo 7 (ver tests/test_ground_truth_cap7.py
y la tabla de migración del plan). Añadir soporte a un mapa o personaje futuro
es extender VARIABLES/FUNCTIONS/LITERALS aquí — nunca la lógica de combate.

Nota sobre 手番回数 vs 総手番回数 (sin telemetría oficial del motor original
para verificarlo con certeza): se interpretan como "número de turno de la
batalla" (手番回数, >=1 durante el combate real) y "acciones ya realizadas
este turno por la unidad" (総手番回数, 0 al iniciar su turno) respectivamente
— es la lectura que hace consistentes tanto la condición de Resonance
(手番回数 > 0, prácticamente siempre cierto en combate real) como la de
Alacrity (総手番回数 == 0, solo en la primera acción del turno).
"""

import os
import re
import json
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Catálogo de habilidades — carga independiente para evitar un import
# circular con catalogo_loader.py (que ya importa de motor_calculo.py).
# ---------------------------------------------------------------------------
_dir_actual = os.path.dirname(os.path.abspath(__file__))
_ruta_catalogo_json = os.path.join(_dir_actual, "json", "catalogo_engage.json")
_ruta_catalogo = _ruta_catalogo_json if os.path.exists(_ruta_catalogo_json) else os.path.join(_dir_actual, "catalogo_engage.json")
HABILIDADES_CATALOGO = {}
if os.path.exists(_ruta_catalogo):
    try:
        with open(_ruta_catalogo, "r", encoding="utf-8") as f:
            HABILIDADES_CATALOGO = json.load(f).get("habilidades", {})
    except Exception:
        HABILIDADES_CATALOGO = {}


def buscar_habilidad_activa(sids_candidatos, habilidades_sids=None, habs_lower=None):
    """
    Devuelve la entrada del catálogo (con su Condition/Act*) del primer Sid de
    `sids_candidatos` que la unidad posea. Comprueba, en orden:
    1. `habilidades_sids` (Sids crudos vía catalogo_loader — fuente canónica).
    2. `habs_lower` (nombres/strings crudos en minúsculas, para compatibilidad
       con datos construidos a mano en tests que no pasan por el catálogo).
    """
    habilidades_sids = habilidades_sids or []
    habs_lower = habs_lower or []
    for sid in sids_candidatos:
        info = HABILIDADES_CATALOGO.get(sid)
        if not info:
            continue
        if sid in habilidades_sids or sid.lower() in habs_lower:
            return info
        nombre_l = str(info.get("nombre", "")).lower()
        if nombre_l and any(nombre_l in h for h in habs_lower):
            return info
    return None


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"""
    (?:
        (?P<STRING>"[^"]*") |
        (?P<NUMBER>\d+(?:\.\d+)?) |
        (?P<OP2>&&|\|\||==|!=|>=|<=) |
        (?P<OP1>[()><=+\-,]) |
        (?P<IDENT>[^\s()><=+\-,"&|]+)
    )
""", re.VERBOSE)


def _tokenizar(cond: str):
    tokens = []
    pos = 0
    n = len(cond)
    while pos < n:
        if cond[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(cond, pos)
        if not m:
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "STRING":
            val = val[1:-1]
        tokens.append((kind, val))
    return tokens


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------
@dataclass
class NumLit:
    valor: float


@dataclass
class StrLit:
    valor: str


@dataclass
class Ident:
    nombre: str


@dataclass
class Llamada:
    nombre: str
    args: list


@dataclass
class BinOp:
    op: str
    izq: object
    der: object


_CMP_OPS = {("OP2", "=="), ("OP2", "!="), ("OP2", ">="), ("OP2", "<="), ("OP1", ">"), ("OP1", "<")}


class _Parser:
    """Descenso recursivo. Precedencia: || < && < comparaciones < +/-."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def _avanzar(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def parse(self):
        return self._or()

    def _or(self):
        izq = self._and()
        while self._peek() == ("OP2", "||"):
            self._avanzar()
            izq = BinOp("||", izq, self._and())
        return izq

    def _and(self):
        izq = self._cmp()
        while self._peek() == ("OP2", "&&"):
            self._avanzar()
            izq = BinOp("&&", izq, self._cmp())
        return izq

    def _cmp(self):
        izq = self._add()
        if self._peek() in _CMP_OPS:
            _, op = self._avanzar()
            return BinOp(op, izq, self._add())
        return izq

    def _add(self):
        izq = self._primary()
        while self._peek()[0] == "OP1" and self._peek()[1] in ("+", "-"):
            _, op = self._avanzar()
            izq = BinOp(op, izq, self._primary())
        return izq

    def _primary(self):
        kind, val = self._avanzar()
        if kind == "NUMBER":
            return NumLit(float(val))
        if kind == "STRING":
            return StrLit(val)
        if kind == "OP1" and val == "(":
            nodo = self._or()
            self._avanzar()  # consume ')'
            return nodo
        if kind == "IDENT":
            if self._peek() == ("OP1", "("):
                self._avanzar()
                args = []
                if self._peek() != ("OP1", ")"):
                    args.append(self._or())
                    while self._peek() == ("OP1", ","):
                        self._avanzar()
                        args.append(self._or())
                self._avanzar()  # consume ')'
                return Llamada(val, args)
            return Ident(val)
        raise ValueError(f"Token inesperado en Condition: {kind!r} {val!r}")


def _parsear(cond: str):
    cond = (cond or "").strip()
    if not cond:
        return None
    tokens = _tokenizar(cond)
    if not tokens:
        return None
    return _Parser(tokens).parse()


# ---------------------------------------------------------------------------
# Contexto de combate
# ---------------------------------------------------------------------------
@dataclass
class ContextoCombate:
    unidad: object                      # atacante o defensor, según el lado evaluado
    rival: object
    es_iniciador: bool = True
    turno_actual: int = 1               # 手番回数: nº de turno de la batalla (>=1 en combate real)
    turno_total: int = 0                # 総手番回数: nº de acciones ya realizadas este turno por `unidad`
    terreno_propio: object = None
    terreno_rival: object = None
    arma: object = None
    arma_rival: object = None
    aliados_cercanos: list = field(default_factory=list)   # [(unidad, distancia), ...]
    mult_efectividad_rival: int = 1     # 相手の武器特効: multiplicador ya calculado por calcular_efectividad()
    habilidades_sids: list = field(default_factory=list)
    habs_lower: list = field(default_factory=list)
    ultimo_resultado: str = ""          # p.ej. "break" si este golpe acaba de romper al rival
    distancia_movida: int = 0           # 移動距離: casillas recorridas antes de atacar (Momentum)


def _tiene_habilidad(ctx: ContextoCombate, fragmento: str) -> bool:
    frag_l = fragmento.lower()
    if fragmento in ctx.habilidades_sids:
        return True
    return any(frag_l in h for h in ctx.habs_lower)


def _velocidad_ataque(unidad, arma):
    if not unidad or not arma:
        return 0
    from motor_calculo import CalculadoraEngage
    return CalculadoraEngage.calcular_velocidad_ataque(unidad.velocidad, unidad.complexion, arma.wt)


def _contar_pares_adyacentes_genero(ctx: ContextoCombate, radio: int, g1: int, g2: int) -> int:
    from motor_calculo import obtener_genero_unidad, distancia_entre_unidades
    cercanos = [u for u, d in (ctx.aliados_cercanos or []) if d <= radio and u is not ctx.unidad]
    grupo1 = [u for u in cercanos if obtener_genero_unidad(u) == g1]
    grupo2 = [u for u in cercanos if obtener_genero_unidad(u) == g2]
    pares = 0
    for a in grupo1:
        for b in grupo2:
            if a is b:
                continue
            if distancia_entre_unidades(a, b) == 1:
                pares += 1
    return pares


def _rival_es_personaje(ctx: ContextoCombate, nombre_jp: str) -> bool:
    from constants import JAPANESE_FALLBACK_TERMS
    nombre_en = JAPANESE_FALLBACK_TERMS.get(nombre_jp, nombre_jp).lower()
    cercanos = [u for u, d in (ctx.aliados_cercanos or []) if d <= 1]
    return any(nombre_en in str(getattr(u, 'nombre', '')).lower() for u in cercanos)


VARIABLES = {
    "HP": lambda ctx: (getattr(ctx.unidad, 'hp_actual', None)
                        if getattr(ctx.unidad, 'hp_actual', None) is not None
                        else getattr(ctx.unidad, 'hp', 0)),
    "手番回数": lambda ctx: ctx.turno_actual,
    "総手番回数": lambda ctx: ctx.turno_total,
    "相手の手番回数": lambda ctx: ctx.turno_total,
    "地形回避": lambda ctx: getattr(ctx.terreno_propio, 'avo', 0) if ctx.terreno_propio else 0,
    "周囲の味方数": lambda ctx: sum(1 for _, d in (ctx.aliados_cercanos or []) if d <= 1),
    "武器の種類": lambda ctx: 'Tomo' if getattr(ctx.arma, 'tipo', '') in ('Tomo', 'Tome') else getattr(ctx.arma, 'tipo', ''),
    "攻撃速度": lambda ctx: _velocidad_ataque(ctx.unidad, ctx.arma),
    "相手の攻撃速度": lambda ctx: _velocidad_ataque(ctx.rival, ctx.arma_rival),
    "相手の武器特効": lambda ctx: ctx.mult_efectividad_rival,
    # 移動距離: casillas movidas este turno antes del combate. Se lee del contexto o,
    # si no se fijó, del propio objeto de stats (motor_analisis/app la anotan ahí).
    "移動距離": lambda ctx: int(ctx.distancia_movida or getattr(ctx.unidad, 'distancia_movida', 0) or 0),
    # 総行動回数: acciones ya realizadas este turno por la unidad (0 al iniciar combate)
    "総行動回数": lambda ctx: ctx.turno_total,
}

LITERALS = {
    "魔道書": "Tomo",
    "ブレイク": "break",
    "男性": 1,
    "女性": 2,
}

FUNCTIONS = {
    "min": lambda ctx, *args: min(args),
    "max": lambda ctx, *args: max(args),
    "スキル所持": lambda ctx, frag: _tiene_habilidad(ctx, str(frag)),
    "攻撃結果": lambda ctx, resultado: str(resultado) == ctx.ultimo_resultado,
    "相手の個人判定": lambda ctx, nombre_jp: _rival_es_personaje(ctx, str(nombre_jp)),
    "周囲の隣接男女数": lambda ctx, n, g1, g2: _contar_pares_adyacentes_genero(ctx, int(n), int(g1), int(g2)),
}


# ---------------------------------------------------------------------------
# Evaluador
# ---------------------------------------------------------------------------
def _eval(nodo, ctx: ContextoCombate):
    if isinstance(nodo, NumLit):
        return nodo.valor
    if isinstance(nodo, StrLit):
        return nodo.valor
    if isinstance(nodo, Ident):
        if nodo.nombre in VARIABLES:
            return VARIABLES[nodo.nombre](ctx)
        if nodo.nombre in LITERALS:
            return LITERALS[nodo.nombre]
        return nodo.nombre  # identificador sin registrar: se trata como literal propio (enum sin traducir)
    if isinstance(nodo, Llamada):
        args = [_eval(a, ctx) for a in nodo.args]
        fn = FUNCTIONS.get(nodo.nombre)
        if fn is None:
            return False
        return fn(ctx, *args)
    if isinstance(nodo, BinOp):
        if nodo.op == "&&":
            return bool(_eval(nodo.izq, ctx)) and bool(_eval(nodo.der, ctx))
        if nodo.op == "||":
            return bool(_eval(nodo.izq, ctx)) or bool(_eval(nodo.der, ctx))
        izq = _eval(nodo.izq, ctx)
        der = _eval(nodo.der, ctx)
        if nodo.op == "+":
            return izq + der
        if nodo.op == "-":
            return izq - der
        if nodo.op == "==":
            return izq == der
        if nodo.op == "!=":
            return izq != der
        if nodo.op == ">":
            return izq > der
        if nodo.op == ">=":
            return izq >= der
        if nodo.op == "<":
            return izq < der
        if nodo.op == "<=":
            return izq <= der
    raise ValueError(f"Nodo no soportado: {nodo!r}")


def evaluar_condicion(cond: str, ctx: ContextoCombate) -> bool:
    """Evalúa el campo Condition de una habilidad contra un ContextoCombate.
    Sin Condition (string vacío) se considera incondicional (True). Cualquier
    fallo de parseo/evaluación se trata como no cumplida (False), nunca lanza."""
    try:
        nodo = _parsear(cond)
    except Exception:
        return False
    if nodo is None:
        return True
    try:
        return bool(_eval(nodo, ctx))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Aplicador de Act* (ActNames / ActOperations / ActValues)
# ---------------------------------------------------------------------------
# Nombre JP del stat -> clave del acumulador que consume motor_calculo.py.
# Ampliar aquí para soportar un Act* nuevo, nunca en motor_calculo.py.
ACT_STAT_MAP = {
    "HP": "hp",
    "威力": "power",
    "攻撃力": "power",       # Atk: a efectos del daño se suma igual que la potencia (Momentum)
    "命中値": "hit",
    "回避値": "avo",
    "必殺値": "crit",
    "相手の威力": "rival_power",
    "相手の命中値": "rival_hit",
    "相手の武器特効": "rival_effectividad",
    "手番回数": "turno_extra",
}


def leer_acts(info_habilidad: dict, ctx: ContextoCombate = None):
    """[(clave_acumulador, operacion, valor_float), ...] a partir de los
    act_names/act_operations/act_values de una entrada del catálogo.
    Un act_value no numérico (p.ej. "min( 移動距離, 10 )" de Momentum) es una
    expresión de la DSL: se evalúa con `ctx`; sin contexto se ignora."""
    nombres = info_habilidad.get("act_names", [])
    ops = info_habilidad.get("act_operations", [])
    vals = info_habilidad.get("act_values", [])
    resultado = []
    for nombre_jp, op, val in zip(nombres, ops, vals):
        clave = ACT_STAT_MAP.get(nombre_jp)
        if not clave:
            continue
        try:
            valor = float(val)
        except (TypeError, ValueError):
            if ctx is None:
                continue
            try:
                valor = float(_eval(_parsear(str(val)), ctx))
            except Exception:
                continue
        resultado.append((clave, op, valor))
    return resultado


def aplicar_acts(info_habilidad: dict, acumulador: dict, ctx: ContextoCombate = None) -> dict:
    """Aplica los Act* de una habilidad sobre `acumulador` (dict mutable) y lo
    devuelve para encadenar. '=' sobreescribe, '+'/'-' suman/restan, '*'
    multiplica el valor ya presente (p.ej. "威力;*;1.2" en los bonos de estilo
    de los Ataques de Emblema). `ctx` permite act_values con expresiones."""
    for clave, op, valor in leer_acts(info_habilidad, ctx):
        actual = acumulador.get(clave, 0)
        if op == "+":
            acumulador[clave] = actual + valor
        elif op == "-":
            acumulador[clave] = actual - valor
        elif op == "*":
            acumulador[clave] = actual * valor
        elif op == "=":
            acumulador[clave] = valor
    return acumulador
