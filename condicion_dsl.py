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

Semántica de las cuentas del combate (deducida de los Act* del propio
Skill.xml: Dragon Blast "手番回数 = 2", Bond Blast "= 3", Follow-Up
"手番回数 = min(手番回数, 1)", Counter (50 %) "総手番回数 == 手番回数 - 1",
3er golpe de Bond Blast "総手番回数 == 2"):
  - 手番回数       rondas de ataque que la unidad tiene en este combate (1, 2 con
                   follow-up; 0 si no puede atacar/contraatacar).
  - 総手番回数     rondas ya ejecutadas (índice de la ronda en curso, 0 antes de golpear).
  - 相手の手番回数 rondas del rival (0 = no puede contraatacar).
  - 行動回数 / 攻撃回数  golpes por ronda (Brave ×2) / golpes por ataque (Lodestar 7…).
Antes del combate (cuando se evalúan las pasivas de Timing 3) valen 1 / 0 / 1-0.
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
        (?P<OP1>[()><=+\-,*/%!]) |
        (?P<IDENT>[^\s()><=+\-,"&|*/%!]+)
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


@dataclass
class UnOp:
    op: str          # "!" (negación lógica) o "-" (cambio de signo)
    operando: object


_CMP_OPS = {("OP2", "=="), ("OP2", "!="), ("OP2", ">="), ("OP2", "<="), ("OP1", ">"), ("OP1", "<")}


class _Parser:
    """Descenso recursivo. Precedencia: || < && < comparaciones < +/- < * / % < unarios (! -)."""

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
        izq = self._mul()
        while self._peek()[0] == "OP1" and self._peek()[1] in ("+", "-"):
            _, op = self._avanzar()
            izq = BinOp(op, izq, self._mul())
        return izq

    def _mul(self):
        izq = self._unary()
        while self._peek()[0] == "OP1" and self._peek()[1] in ("*", "/", "%"):
            _, op = self._avanzar()
            izq = BinOp(op, izq, self._unary())
        return izq

    def _unary(self):
        if self._peek()[0] == "OP1" and self._peek()[1] in ("!", "-"):
            _, op = self._avanzar()
            return UnOp(op, self._unary())
        return self._primary()

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
    turno_actual: int = 1               # 手番回数: rondas de ataque de `unidad` en este combate (0 = no ataca)
    turno_total: int = 0                # 総手番回数: rondas ya ejecutadas (0 antes del primer golpe)
    rondas_rival: int = 1               # 相手の手番回数: rondas del rival (0 = no puede contraatacar)
    rol: str = ""                       # 立場: "atacante" | "defensor" | "apoyo"
    chain_attacks: int = 0              # チェインアタック回数: Chain Attacks de aliados de apoyo en este combate
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
    # Evaluación por golpe (Fase 3): daño del golpe en curso, antes de aplicar la pasiva
    dano_actual: float = 0              # ダメージ: daño que `unidad` está a punto de recibir/infligir en este golpe
    dano_rival: float = 0               # 相手のダメージ
    rol_rival: str = ""                 # 相手の立場: "atacante" | "defensor" | "apoyo" (chain attack)
    # Rellenado por スキル確率(): probabilidad (0-100) con la que la Condition en curso
    # se cumple. pasivas.recopilar lo lee tras evaluar cada habilidad y la clasifica como proc.
    proc_prob: Optional[float] = None


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


def _identificador(u) -> str:
    """識別子: identidad estable de una unidad (pid de Person.xml o, si no, su nombre)."""
    if u is None:
        return ""
    stats = getattr(u, 'stats', None)
    return str(getattr(u, 'pid', '') or getattr(stats, 'pid', '') or getattr(u, 'nombre', '') or '')


def es_personaje(u, nombre_jp: str) -> bool:
    """個人判定("リュール"): ¿`u` es ese personaje? Por pid (PID_リュール) o, para datos
    a mano sin pid, por el nombre inglés equivalente (constants.JAPANESE_FALLBACK_TERMS)."""
    if u is None:
        return False
    from constants import JAPANESE_FALLBACK_TERMS
    ident = _identificador(u)
    if ident.startswith("PID_"):
        return ident == f"PID_{nombre_jp}" or ident.startswith(f"PID_{nombre_jp}_") or ident.startswith(f"PID_{nombre_jp}男") or ident.startswith(f"PID_{nombre_jp}女")
    nombre_en = str(JAPANESE_FALLBACK_TERMS.get(nombre_jp, nombre_jp)).lower()
    nombre = str(getattr(u, 'nombre', '') or '').lower()
    return bool(nombre_en) and nombre_en in nombre


def _rival_es_personaje(ctx: ContextoCombate, nombre_jp: str) -> bool:
    # 相手 = la otra parte de la evaluación: en un aura (Timing 20) es el aliado que
    # recibiría el efecto; en combate, el enemigo.
    return es_personaje(ctx.rival, nombre_jp)


def _contar_genero_alrededor(ctx: ContextoCombate, radio: int, genero: int) -> int:
    from motor_calculo import obtener_genero_unidad
    return sum(1 for u, d in (ctx.aliados_cercanos or []) if d <= radio and u is not ctx.unidad and obtener_genero_unidad(u) == genero)


def _nivel_emblema(u) -> int:
    """神将レベル: nivel de vínculo con el Emblema equipado (0 = sin Emblema)."""
    if u is None:
        return 0
    stats = getattr(u, 'stats', None)
    emb = getattr(u, 'emblema_nombre', '') or getattr(stats, 'emblema_nombre', '') or getattr(u, 'emblema', '')
    if not emb:
        return 0
    return int(getattr(u, 'nivel_vinculo', 0) or getattr(stats, 'nivel_vinculo', 0) or 1)


def _hp(u):
    if u is None:
        return 0
    v = getattr(u, 'hp_actual', None)
    return v if v is not None else getattr(u, 'hp', 0)


def _hp_max(u):
    if u is None:
        return 0
    return getattr(u, 'hp_max', 0) or getattr(u, 'hp', 0)


def _stat(u, attr):
    return (getattr(u, attr, 0) or 0) if u is not None else 0


def _tipo_arma(arma):
    tipo = getattr(arma, 'tipo', '') if arma is not None else ''
    return 'Tomo' if tipo in ('Tomo', 'Tome') else tipo


def _atributo_ataque(arma):
    """物理属性 / 魔法属性 del arma: 'magico' si apunta a RES, 'fisico' si a DEF."""
    if arma is None:
        return 'fisico'
    return 'magico' if (getattr(arma, 'es_magica', False) or _tipo_arma(arma) == 'Tomo') else 'fisico'


def _relacion_triangulo(arma, arma_rival):
    """武器相性 desde el punto de vista de `arma`: 'ventaja' / 'desventaja' / 'neutral'."""
    from motor_calculo import TRIANGULO_ARMAS
    t1, t2 = _tipo_arma(arma), _tipo_arma(arma_rival)
    if t2 in TRIANGULO_ARMAS.get(t1, []):
        return 'ventaja'
    if t1 in TRIANGULO_ARMAS.get(t2, []):
        return 'desventaja'
    return 'neutral'


def _estilo(u):
    from motor_calculo import resolver_estilo_combate
    return resolver_estilo_combate(getattr(u, 'estilo_combate', '') if u is not None else '')


def _defensa_efectiva(u, arma_rival):
    """防御力: DEF o RES de `u` según el atributo del arma que lo golpea."""
    return _stat(u, 'resistencia') if _atributo_ataque(arma_rival) == 'magico' else _stat(u, 'defensa')


def _rival_tiene_habilidad(ctx: ContextoCombate, fragmento: str) -> bool:
    rival = ctx.rival
    if rival is None:
        return False
    frag_l = fragmento.lower()
    try:
        import pasivas
        sids = pasivas.sids_activos(rival)
    except Exception:
        sids = list(getattr(rival, 'habilidades_sids', []) or [])
    if fragmento in sids or any(fragmento in s for s in sids):
        return True
    return any(frag_l in str(h).lower() for h in (getattr(rival, 'habilidades', []) or []))


def _proc(ctx: ContextoCombate, prob) -> bool:
    """スキル確率(x): la Condition se cumple con probabilidad x %. Se registra en el
    contexto y se devuelve True para que la habilidad se evalúe como candidata;
    pasivas.recopilar la clasifica como proc con esa probabilidad."""
    try:
        p = float(prob)
    except (TypeError, ValueError):
        p = 0.0
    p = max(0.0, min(100.0, p))
    ctx.proc_prob = p if ctx.proc_prob is None else min(100.0, ctx.proc_prob * p / 100.0)
    return p > 0


VARIABLES = {
    "HP": lambda ctx: _hp(ctx.unidad),
    "MaxHP": lambda ctx: _hp_max(ctx.unidad),
    "相手のHP": lambda ctx: _hp(ctx.rival),
    "相手のMaxHP": lambda ctx: _hp_max(ctx.rival),
    "生存": lambda ctx: 1 if _hp(ctx.unidad) > 0 else 0,
    "相手の生存": lambda ctx: 1 if _hp(ctx.rival) > 0 else 0,
    # Stats propios y del rival (Unidad de motor_calculo)
    "力": lambda ctx: _stat(ctx.unidad, 'fuerza'),
    "魔力": lambda ctx: _stat(ctx.unidad, 'magia'),
    "技": lambda ctx: _stat(ctx.unidad, 'destreza'),
    "速さ": lambda ctx: _stat(ctx.unidad, 'velocidad'),
    "守備": lambda ctx: _stat(ctx.unidad, 'defensa'),
    "魔防": lambda ctx: _stat(ctx.unidad, 'resistencia'),
    "幸運": lambda ctx: _stat(ctx.unidad, 'suerte'),
    "体格": lambda ctx: _stat(ctx.unidad, 'complexion'),
    "相手の力": lambda ctx: _stat(ctx.rival, 'fuerza'),
    "相手の魔力": lambda ctx: _stat(ctx.rival, 'magia'),
    "相手の技": lambda ctx: _stat(ctx.rival, 'destreza'),
    "相手の速さ": lambda ctx: _stat(ctx.rival, 'velocidad'),
    "相手の守備": lambda ctx: _stat(ctx.rival, 'defensa'),
    "相手の魔防": lambda ctx: _stat(ctx.rival, 'resistencia'),
    "相手の幸運": lambda ctx: _stat(ctx.rival, 'suerte'),
    "防御力": lambda ctx: _defensa_efectiva(ctx.unidad, ctx.arma_rival),
    "相手の防御力": lambda ctx: _defensa_efectiva(ctx.rival, ctx.arma),
    # Armas y atributos
    "武器の種類": lambda ctx: _tipo_arma(ctx.arma),
    "相手の武器の種類": lambda ctx: _tipo_arma(ctx.arma_rival),
    "攻撃属性": lambda ctx: _atributo_ataque(ctx.arma),
    "相手の攻撃属性": lambda ctx: _atributo_ataque(ctx.arma_rival),
    "武器相性": lambda ctx: _relacion_triangulo(ctx.arma, ctx.arma_rival),
    "戦闘スタイル": lambda ctx: _estilo(ctx.unidad),
    "相手の戦闘スタイル": lambda ctx: _estilo(ctx.rival),
    "相手の立場": lambda ctx: ctx.rol_rival,
    # Golpe en curso (Fase 3)
    "ダメージ": lambda ctx: ctx.dano_actual,
    "相手のダメージ": lambda ctx: ctx.dano_rival,
    "手番回数": lambda ctx: ctx.turno_actual,
    "総手番回数": lambda ctx: ctx.turno_total,
    "相手の手番回数": lambda ctx: ctx.rondas_rival,
    "立場": lambda ctx: ctx.rol,
    "チェインアタック回数": lambda ctx: ctx.chain_attacks,
    # Identidad, género y Emblema (auras: 相手 = quien recibiría el efecto)
    "識別子": lambda ctx: _identificador(ctx.unidad),
    "相手の識別子": lambda ctx: _identificador(ctx.rival),
    "性別": lambda ctx: __import__('motor_calculo').obtener_genero_unidad(ctx.unidad),
    "相手の性別": lambda ctx: __import__('motor_calculo').obtener_genero_unidad(ctx.rival),
    "神将レベル": lambda ctx: _nivel_emblema(ctx.unidad),
    "相手の神将レベル": lambda ctx: _nivel_emblema(ctx.rival),
    "地形回避": lambda ctx: getattr(ctx.terreno_propio, 'avo', 0) if ctx.terreno_propio else 0,
    "相手の地形回避": lambda ctx: getattr(ctx.terreno_rival, 'avo', 0) if ctx.terreno_rival else 0,
    "周囲の味方数": lambda ctx: sum(1 for _, d in (ctx.aliados_cercanos or []) if d <= 1),
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
    # Tipos de arma (Arma.tipo de motor_calculo)
    "剣": "Espada",
    "槍": "Lanza",
    "斧": "Hacha",
    "弓": "Arco",
    "短剣": "Daga",
    "拳": "Artes",
    "魔道書": "Tomo",
    "杖": "Bastón",
    "特殊": "Especial",
    # Atributo de ataque
    "物理属性": "fisico",
    "魔法属性": "magico",
    # Relación del triángulo de armas
    "有利": "ventaja",
    "不利": "desventaja",
    # Rol del rival en el combate (相手の立場)
    "攻め": "atacante",
    "受け": "defensor",
    "援護": "apoyo",
    # Estilos de combate (ids canónicos de constants.ESTILOS_COMBATE_ALIASES)
    "魔法スタイル": "mistico",
    "隠密スタイル": "encubierto",
    "重装スタイル": "acorazado",
    "連携スタイル": "apoyo",
    "竜族スタイル": "dragon",
    "騎馬スタイル": "caballeria",
    "飛行スタイル": "volador",
    "気功スタイル": "qi_adept",
    "ブレイク": "break",
    "男性": 1,
    "女性": 2,
}

FUNCTIONS = {
    "min": lambda ctx, *args: min(args),
    "max": lambda ctx, *args: max(args),
    "int": lambda ctx, v: int(float(v)),
    "cond": lambda ctx, c, a, b: a if bool(c) else b,
    "スキル確率": lambda ctx, prob: _proc(ctx, prob),
    "相手のスキル所持": lambda ctx, frag: _rival_tiene_habilidad(ctx, str(frag)),
    "スキル所持": lambda ctx, frag: _tiene_habilidad(ctx, str(frag)),
    "攻撃結果": lambda ctx, resultado: str(resultado) == ctx.ultimo_resultado,
    "相手の個人判定": lambda ctx, nombre_jp: _rival_es_personaje(ctx, str(nombre_jp)),
    "周囲の隣接男女数": lambda ctx, n, g1, g2: _contar_pares_adyacentes_genero(ctx, int(n), int(g1), int(g2)),
    "周囲の性別数": lambda ctx, n, g: _contar_genero_alrededor(ctx, int(n), int(g)),
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
    if isinstance(nodo, UnOp):
        v = _eval(nodo.operando, ctx)
        return (not bool(v)) if nodo.op == "!" else -v
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
        if nodo.op == "*":
            return izq * der
        if nodo.op == "/":
            return izq / der if der else 0
        if nodo.op == "%":
            return izq % der if der else 0
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
    # ── consumidos hoy por motor_calculo ──
    "HP": "hp",
    "威力": "power",         # daño neto del golpe (Atk − Def): "×1.2" multiplica el daño, no el Atk
    "攻撃力": "atk",         # Atk (stat ofensiva + Mt): en sumas equivale a 威力 (Momentum, Spur Attack)
    "命中値": "hit",
    "回避値": "avo",
    "必殺値": "crit",
    "相手の威力": "rival_power",
    "相手の命中値": "rival_hit",
    "相手の武器特効": "rival_effectividad",
    "手番回数": "turno_extra",
    # ── acumulados por pasivas.recopilar (Fase 1); los consume el motor en Fases 2-3 ──
    "ユニット攻撃力": "unit_atk",        # stat ofensiva de la unidad (sin arma): "=" la sustituye (Qi Adept, Sandstorm)
    "武器攻撃力": "power_arma",
    "必殺回避": "ddg",
    "命中率": "hit_rate",              # tasa final (= 100 en Ataques de Emblema), no el valor Hit
    "必殺率": "crit_rate",
    "相手の命中率": "rival_hit_rate",
    "相手の必殺率": "rival_crit_rate",
    "相手の回避値": "rival_avo",
    "相手の必殺値": "rival_crit",
    "地形回避": "terreno_avo",
    "相手の地形回避": "rival_terreno_avo",
    "攻撃速度": "as",
    "ダメージ": "dano",                # daño del golpe en curso (evaluación por golpe)
    "相手のダメージ": "rival_dano",
    "攻撃回数": "golpes",              # nº de golpes por ataque (armas brave, Astra Storm…)
    "相手の手番回数": "rival_turno_extra",
    "行動回数": "acciones",
    "回復": "curacion",
    "相手の回復": "rival_curacion",
    "相手のHP": "rival_hp",
    "力": "str", "魔力": "mag", "技": "dex", "守備": "def", "魔防": "res",
    "相手の防御力": "rival_defensa_efectiva",   # Luna: -50 % de la DEF/RES que aplica a este golpe
    "相手のユニット防御力": "rival_defensa_efectiva",
    "一時変数": "tmp",
    "攻撃結果": "resultado",           # valor de texto (p.ej. ブレイク)
    "攻撃属性": "atributo",            # valor de texto (物理属性 / 魔法属性)
    "エンゲージカウント": "engage_count",
    "相手のエンゲージカウント": "rival_engage_count",
    "吹き飛ばし距離": "empuje",
    "吹き飛ばし率": "empuje_pct",
    "武器の消費": "usos_arma",
    "取得経験": "exp",
    "相手の取得経験": "rival_exp",
    "拾得アイテム": "item",
    "スキル確率補正": "proc_bonus",
    "神将スキル確率補正": "proc_bonus_emblema",
}

# Acts cuyo valor es un literal de texto (no una expresión numérica)
ACTS_TEXTO = {"resultado", "atributo", "item"}


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
        if clave in ACTS_TEXTO:
            resultado.append((clave, op, LITERALS.get(str(val), str(val))))
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
        if isinstance(valor, str):
            acumulador[clave] = valor
            continue
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
