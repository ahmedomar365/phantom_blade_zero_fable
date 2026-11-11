"""Vermilion Gate: shrine forecourt arena -> game/assets/arena.glb + arena_meta.json
Blender coords: x east, y north, z up (three.js: x, z, -y). The fight circle is r = 11 at the origin.
Run: blender -b -P tools/build_arena.py [-- preview]"""
import bpy, bmesh, math, os, sys, json, random
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import *
from mathutils import Quaternion

reset()
rng = random.Random(11)
C, S_ = math.cos, math.sin
rad = math.radians

# ------------------------------------------------------------------ materials
FLAG = mat('ar_flag', (0.92, 0.94, 1.0), tex='flag')
BAND = mat('ar_band', (0.24, 0.25, 0.28), tex='stone')
MED = mat('ar_medallion', (1.0, 1.0, 1.0), tex='medallion')
STONE = mat('ar_stone', (0.46, 0.47, 0.50), tex='stone')
STONE_D = mat('ar_stone_dark', (0.27, 0.28, 0.31), tex='stone')
PLASTER = mat('ar_plaster', (0.60, 0.56, 0.50), tex='plaster')
VERM = mat('ar_vermilion', (0.56, 0.060, 0.030), tex='lacquer')
VERM_D = mat('ar_vermilion_dark', (0.26, 0.030, 0.020), tex='lacquer')
BLACKW = mat('ar_blackwood', (0.060, 0.045, 0.040), tex='lacquer')
GREENW = mat('ar_green', (0.045, 0.200, 0.170), tex='lacquer')
BLUEW = mat('ar_blue', (0.030, 0.060, 0.160), tex='lacquer')
GOLD = mat('ar_gold', (0.90, 0.62, 0.22), rough=0.32, metal=1.0)
WOOD = mat('ar_wood', (0.50, 0.42, 0.34), tex='wood')
TILE = mat('ar_tile', (0.62, 0.68, 0.80), tex='rooftile')
TILE_D = mat('ar_tile_dark', (0.30, 0.33, 0.40), tex='rooftile')
BARK = mat('ar_bark', (1.0, 1.0, 1.0), tex='bark')
BRONZE = mat('ar_bronze', (0.44, 0.31, 0.16), tex='metal')
IRON = mat('ar_iron', (0.13, 0.13, 0.14), tex='metal')
ROPE = mat('ar_rope', (0.20, 0.15, 0.10), rough=0.9)
SKIN = mat('ar_drumskin', (0.72, 0.64, 0.50), rough=0.6)
CERAMIC = mat('ar_ceramic', (0.10, 0.16, 0.20), rough=0.22)
PAPER = mat('glow_paper', (1.0, 1.0, 1.0), tex='paper', emit=(1.0, 0.62, 0.28), emit_strength=2.6, rough=0.8)
PAPER_RED = mat('glow_paperred', (1.0, 1.0, 1.0), tex='paperred', emit=(1.0, 0.30, 0.10), emit_strength=2.4, rough=0.8)
LATTICE = mat('glow_lattice', (1.0, 1.0, 1.0), tex='lattice', emit=(1.0, 0.58, 0.24), emit_strength=1.3)
FLAME = mat('glow_flame', (1.0, 0.8, 0.5), emit=(1.0, 0.62, 0.22), emit_strength=7.0)
INTERIOR = mat('glow_interior', (0.80, 0.55, 0.34), tex='plaster', emit=(1.0, 0.42, 0.12), emit_strength=0.55)
FOLIAGE = mat('ar_foliage', (1.0, 1.0, 1.0), tex='foliage', alpha='tex', rough=0.55)
NEEDLE = mat('ar_needle', (1.0, 1.0, 1.0), tex='needle', alpha='tex', rough=0.7)
BANNER = mat('ar_banner', (1.0, 1.0, 1.0), tex='banner')
EARTH = mat('bg_ground', (0.016, 0.020, 0.018), rough=1.0)
MTN1 = mat('bg_mtn_near', (0.010, 0.016, 0.028), rough=1.0)
MTN2 = mat('bg_mtn_far', (0.022, 0.034, 0.058), rough=1.0)
MTN3 = mat('bg_mtn_haze', (0.038, 0.056, 0.092), rough=1.0)

TZ = 1.19                      # terrace height (7 risers)
PZ = TZ + 0.30                 # hall plinth
HX = 17.6                      # courtyard half width (inner wall face)
SY = -17.6                     # south wall
NY = 13.0                      # foot of the steps
TY = 16.5                      # terrace front edge
META = {'radius': 11.0, 'stone_lanterns': [], 'hall_lanterns': [], 'string_lanterns': [], 'candles': []}


def T3(p):
    """Blender point -> three.js [x, y, z]."""
    return [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]


# ================================================================== FLOOR
FUV = lambda p: (p[0] * 0.25, p[1] * 0.25)


def annulus(b, r0, r1, m, S=96, z=0.0, uvfn=None):
    pts, faces = [], []
    for i in range(S):
        a = 2 * math.pi * i / S
        pts.append((r0 * C(a), r0 * S_(a), z))
    for i in range(S):
        a = 2 * math.pi * i / S
        pts.append((r1 * C(a), r1 * S_(a), z))
    for i in range(S):
        j = (i + 1) % S
        faces.append((i, S + i, S + j, j))
    b.poly(pts, faces, m=m, recalc=False, uvs=[(uvfn or FUV)(p) for p in pts])


b = MB(uv=0.25)
R_MED, R_IN, R_BAND = 2.6, 10.55, 11.0
# medallion disc (own 0..1 UVs)
S = 96
pts = [(0, 0, 0)] + [(R_MED * C(2 * math.pi * i / S), R_MED * S_(2 * math.pi * i / S), 0) for i in range(S)]
b.poly(pts, [(0, 1 + i, 1 + (i + 1) % S) for i in range(S)], m=MED, recalc=False,
       uvs=[(0.5 + 0.5 * p[0] / R_MED, 0.5 + 0.5 * p[1] / R_MED) for p in pts])
annulus(b, R_MED, R_MED + 0.22, BAND)
annulus(b, R_MED + 0.22, 6.3, FLAG)
annulus(b, 6.3, 6.48, BAND)
annulus(b, 6.48, R_IN, FLAG)
annulus(b, R_IN, R_BAND, BAND)
# outside the ring: out to the rectangle of the court
X0, X1, Y0, Y1 = -HX - 0.3, HX + 0.3, SY - 0.3, NY + 0.2
angs = sorted(set([round(2 * math.pi * i / S, 6) for i in range(S)] +
                  [round(math.atan2(y, x) % (2 * math.pi), 6) for x in (X0, X1) for y in (Y0, Y1)]))
inner, outer = [], []
for a in angs:
    dx, dy = C(a), S_(a)
    t = min(v for v in ((X1 / dx) if dx > 1e-9 else 1e9, (X0 / dx) if dx < -1e-9 else 1e9,
                        (Y1 / dy) if dy > 1e-9 else 1e9, (Y0 / dy) if dy < -1e-9 else 1e9))
    inner.append((R_BAND * dx, R_BAND * dy, 0))
    outer.append((t * dx, t * dy, 0))
n = len(angs)
b.poly(inner + outer, [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)], m=FLAG, recalc=False, uvs=[FUV(p) for p in inner + outer])
# path beyond the south gate
_pp = [(-2.6, -46, 0), (2.6, -46, 0), (2.6, Y0, 0), (-2.6, Y0, 0)]
b.poly(_pp, [(0, 1, 2, 3)], m=FLAG, recalc=False, uvs=[FUV(p) for p in _pp])
FLOOR = b.finish('Floor')

b = MB(uv=0.1)
pts = [(0, 0, -0.06)] + [(170 * C(2 * math.pi * i / 48), 170 * S_(2 * math.pi * i / 48), -0.06) for i in range(48)]
b.poly(pts, [(0, 1 + i, 1 + (i + 1) % 48) for i in range(48)], m=EARTH, recalc=False, uvs=[(p[0] * 0.1, p[1] * 0.1) for p in pts])
GROUND = b.finish('Ground')


# ================================================================== helpers
def balustrade(b, p0, p1, z0, post_every=1.9):
    """Stone posts with a panel and rails between them, along an axis-aligned run."""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = p1 - p0
    L = d.length
    n = max(1, round(L / post_every))
    ang = math.degrees(math.atan2(d.y, d.x))
    for i in range(n + 1):
        p = p0 + d * (i / n)
        b.box((0.24, 0.24, 1.08), (p.x, p.y, z0 + 0.54), m=STONE, bevel=0.02)
        b.box((0.30, 0.30, 0.06), (p.x, p.y, z0 + 1.10), m=STONE, bevel=0.015)
        b.sphere(1.0, (p.x, p.y, z0 + 1.22), scale=(0.115, 0.115, 0.14), m=STONE, segs=12)
    for i in range(n):
        a, c = p0 + d * (i / n), p0 + d * ((i + 1) / n)
        m_ = (a + c) / 2
        seg = (c - a).length - 0.24
        b.box((seg, 0.13, 0.11), (m_.x, m_.y, z0 + 0.93), rot=(0, 0, ang), m=STONE, bevel=0.015)
        b.box((seg, 0.09, 0.46), (m_.x, m_.y, z0 + 0.56), rot=(0, 0, ang), m=STONE_D, bevel=0.01)
        b.box((seg, 0.13, 0.12), (m_.x, m_.y, z0 + 0.17), rot=(0, 0, ang), m=STONE, bevel=0.015)
        b.box((seg * 0.5, 0.11, 0.26), (m_.x, m_.y, z0 + 0.56), rot=(0, 0, ang), m=STONE, bevel=0.03)


def stone_lantern(b, g, x, y, z0=0.0, s=1.0, key='stone_lanterns'):
    M = TRS((x, y, z0), (0, 0, rng.uniform(0, 90)), s)
    b.lathe([(0, 0), (0.40, 0), (0.42, 0.06), (0.36, 0.12), (0.30, 0.20), (0.20, 0.26), (0.155, 0.34)], m=STONE, segs=6, M=M)
    b.lathe([(0.155, 0.34), (0.135, 0.60), (0.130, 0.95), (0.150, 1.12), (0.30, 1.20), (0.34, 1.26), (0.34, 1.30), (0, 1.30)],
            m=STONE, segs=12, M=M)
    for sx in (1, -1):
        for sy in (1, -1):
            b.box((0.055, 0.055, 0.36), m=STONE, M=M @ TRS((0.19 * sx, 0.19 * sy, 1.48)))
    g.box((0.34, 0.34, 0.34), m=PAPER, M=M @ TRS((0, 0, 1.48)))
    b.lathe([(0.52, 1.66), (0.50, 1.70), (0.36, 1.76), (0.22, 1.86), (0.10, 1.98), (0.05, 2.02), (0.09, 2.08), (0.07, 2.16), (0, 2.22)],
            m=STONE_D, segs=6, M=M)
    b.lathe([(0.26, 1.64), (0.52, 1.66)], m=STONE_D, segs=6, M=M)
    META[key].append(T3((x, y, z0 + 1.48 * s)))


def paper_lantern(g, b, x, y, z, R=0.5, H=0.62, m=PAPER_RED, top=None, key='hall_lanterns'):
    """Hanging lantern centred at (x, y, z). top = z of the hook it hangs from."""
    n = 12
    prof = []
    for i in range(n + 1):
        t = -1 + 2 * i / n
        prof.append((max(0.16 * R / 0.5, R * (1 - abs(t) ** 2.4) ** 0.5), t * H))
    plen = sum(math.hypot(prof[i + 1][0] - prof[i][0], prof[i + 1][1] - prof[i][1]) for i in range(n))
    mean_r = sum(p[0] for p in prof) / len(prof)
    g.lathe(prof, m=m, segs=20, M=TRS((x, y, z)), uvs=(0.9 / (2 * math.pi * mean_r), 1.0 / plen))
    for sg in (1, -1):
        b.cyl(prof[0][0] * 1.08, 0.07 * R / 0.5, (x, y, z + sg * (H + 0.02)), m=BLACKW, segs=14, bevel=0.01)
        b.cyl(prof[0][0] * 1.12, 0.02, (x, y, z + sg * (H - 0.03)), m=GOLD, segs=14)
    b.cyl(0.012, 0.5 * R / 0.5, (x, y, z - H - 0.25 * R / 0.5), m=VERM, segs=5)
    b.cyl(0.05 * R / 0.5, 0.34 * R / 0.5, (x, y, z - H - 0.62 * R / 0.5), m=VERM, segs=8, r2=0.02 * R / 0.5)
    if top is not None:
        b.cyl(0.012, top - (z + H), (x, y, (top + z + H) / 2), m=ROPE, segs=5)
    if key:
        META[key].append(T3((x, y, z)))


def column(b, x, y, z0, h, r=0.34, m=VERM):
    b.lathe([(r * 1.75, 0), (r * 1.75, 0.10), (r * 1.55, 0.16), (r * 1.25, 0.30), (r * 1.12, 0.34)], m=STONE, segs=16, M=TRS((x, y, z0)))
    b.lathe([(r * 1.04, 0.34), (r, 0.6), (r, h * 0.55), (r * 0.94, h - 0.2), (r * 0.94, h)], m=m, segs=16, M=TRS((x, y, z0)),
            uvs=(0.66, 0.4))
    b.cyl(r * 1.0, 0.07, (x, y, z0 + 0.62), m=GOLD, segs=16)
    b.cyl(r * 0.99, 0.10, (x, y, z0 + h - 0.42), m=GREENW, segs=16)
    b.cyl(r * 1.0, 0.03, (x, y, z0 + h - 0.34), m=GOLD, segs=16)
    b.box((r * 2.5, r * 2.5, 0.16), (x, y, z0 + h + 0.02), m=BLACKW, bevel=0.03)


def roof_slope(b, e0, e1, t0, t1, ze, zt, lift, period=0.40, amp=0.075, nv=10, m=TILE, p=1.7):
    e0, e1, t0, t1 = (Vector(v) for v in (e0, e1, t0, t1))
    L = (e1 - e0).length
    rows = max(2, round(L / period))
    run = ((t0 + t1) / 2 - (e0 + e1) / 2).length

    def fn(u, v):
        q = e0.lerp(e1, u).lerp(t0.lerp(t1, u), v)
        c = abs(2 * u - 1)
        z = ze + (zt - ze) * (v ** p) + lift * (c ** 3.2) * ((1 - v) ** 2)
        z += amp * (0.5 + 0.5 * C(2 * math.pi * u * rows)) * (1 - 0.5 * v)
        return (q.x, q.y, z)
    b.grid(fn, rows * 4, nv, m=m, uvs=(L / 2.0, math.hypot(run, zt - ze) / 2.0))
    return rows


def eave_trim(b, e0, e1, t0, t1, ze, lift, rows, rafter=1.3, every=2):
    """Round tile ends along the eave, a fascia board, and rafter tails under it."""
    e0, e1, t0, t1 = (Vector(v) for v in (e0, e1, t0, t1))
    d = (e1 - e0).normalized()
    out = ((e0 + e1) / 2 - (t0 + t1) / 2)
    out = (out - d * out.dot(d)).normalized()
    ang = math.degrees(math.atan2(out.y, out.x))
    for i in range(rows + 1):
        u = i / rows
        q = e0.lerp(e1, u)
        z = ze + lift * abs(2 * u - 1) ** 3.2
        b.cyl(0.075, 0.05, (q.x + out.x * 0.01, q.y + out.y * 0.01, z + 0.075), rot=(90, 0, ang - 90), m=TILE_D, segs=8)
        if i % every == 0 and i < rows:
            qi = q - out * (rafter / 2)
            b.box((0.11, rafter, 0.13), (qi.x, qi.y, z - 0.16), rot=(-6, 0, ang - 90), m=GREENW)
            b.box((0.115, 0.02, 0.135), (q.x + out.x * 0.005, q.y + out.y * 0.005, z - 0.09), rot=(-6, 0, ang - 90), m=GOLD)

    def fn(u, v):
        q = e0.lerp(e1, u) - out * 0.04
        return (q.x, q.y, ze + lift * abs(2 * u - 1) ** 3.2 - 0.02 - 0.20 * v)
    b.grid(fn, max(8, rows // 2), 1, m=VERM_D, uvs=((e1 - e0).length / 1.5, 0.15))


def hip_ridge(b, ce, ct, ze, zt, lift, r=0.15, p=1.7, curl=1.0):
    ce, ct = Vector(ce), Vector(ct)
    out = (ce - ct).normalized()
    pts, rs = [], []
    for i in range(11):
        v = 1 - i / 10
        q = ce.lerp(ct, v)
        pts.append((q.x, q.y, ze + (zt - ze) * v ** p + lift * (1 - v) ** 2 + 0.11))
        rs.append(r)
    zc = pts[-1][2]
    for k, (o, up, rr) in enumerate(((0.28, 0.10, 0.9), (0.55, 0.30, 0.75), (0.74, 0.62, 0.55), (0.80, 0.98, 0.32), (0.74, 1.26, 0.10))):
        pts.append((ce.x + out.x * o * curl, ce.y + out.y * o * curl, zc + up * curl))
        rs.append(r * rr)
    b.tube(pts, rs, m=TILE_D, segs=8)
    for v in (0.25, 0.5, 0.75):                              # ridge beasts: small studs along the hip
        q = ce.lerp(ct, v)
        b.sphere(1.0, (q.x, q.y, ze + (zt - ze) * v ** p + lift * (1 - v) ** 2 + 0.11 + r), scale=(0.10, 0.10, 0.16), m=TILE_D, segs=8)


def rect_roof(b, cx, cy, hw, hd, ze, thw, thd, zt, lift, ridge=True, rafter=1.3, p=1.7, m=TILE):
    co = lambda sx, sy: (cx + sx * hw, cy + sy * hd)
    ct = lambda sx, sy: (cx + sx * thw, cy + sy * thd)
    for (a, c) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
        rows = roof_slope(b, co(*a), co(*c), ct(*a), ct(*c), ze, zt, lift, m=m, p=p)
        eave_trim(b, co(*a), co(*c), ct(*a), ct(*c), ze, lift, rows, rafter=rafter)
    for sx in (1, -1):
        for sy in (1, -1):
            hip_ridge(b, co(sx, sy), ct(sx, sy), ze, zt, lift, p=p)
    if ridge:
        b.box((thw * 2 + 0.5, 0.42, 0.50), (cx, cy, zt + 0.16), m=TILE_D, bevel=0.06)
        b.box((thw * 2 + 0.7, 0.50, 0.10), (cx, cy, zt + 0.44), m=TILE_D, bevel=0.03)
        for k in range(int(thw * 2 / 0.8) + 1):
            b.cyl(0.11, 0.44, (cx - thw + k * 0.8, cy, zt + 0.16), rot=(90, 0, 0), m=GOLD, segs=8)
        for sx in (1, -1):                                   # owl-tail finials curling inward
            x0 = cx + sx * (thw + 0.25)
            b.tube([(x0, cy, zt + 0.1), (x0 + sx * 0.18, cy, zt + 0.7), (x0 + sx * 0.10, cy, zt + 1.25),
                    (x0 - sx * 0.22, cy, zt + 1.62), (x0 - sx * 0.52, cy, zt + 1.66)], [0.30, 0.27, 0.21, 0.14, 0.05], m=TILE_D, segs=8)
            b.sphere(0.16, (x0 + sx * 0.02, cy, zt + 0.5), m=GOLD, segs=10)


def wall(b, p0, p1, z0, h, posts=4.4, thick=0.5):
    """Plastered wall with a stone footing and a tiled cap, axis-aligned between p0 and p1."""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = p1 - p0
    L = d.length
    ang = math.degrees(math.atan2(d.y, d.x))
    mid = (p0 + p1) / 2
    b.box((L, thick + 0.14, 0.62), (mid.x, mid.y, z0 + 0.31), rot=(0, 0, ang), m=STONE_D, bevel=0.03)
    b.box((L, thick, h - 0.62), (mid.x, mid.y, z0 + 0.62 + (h - 0.62) / 2), rot=(0, 0, ang), m=PLASTER)
    b.box((L, thick + 0.10, 0.14), (mid.x, mid.y, z0 + h - 0.05), rot=(0, 0, ang), m=VERM_D)
    b.extrude_profile([(-0.62, 0.0), (-0.30, 0.10), (0, 0.36), (0.30, 0.10), (0.62, 0.0), (0, 0.04)], L,
                      loc=(mid.x, mid.y, z0 + h + 0.02), rot=(0, 0, ang - 90), m=TILE)
    b.cyl(0.085, L, (mid.x, mid.y, z0 + h + 0.38), rot=(0, 90, ang), m=TILE_D, segs=8)
    n = max(1, round(L / posts))
    for i in range(n + 1):
        q = p0 + d * (i / n)
        b.box((0.36, thick + 0.20, h - 0.1), (q.x, q.y, z0 + (h - 0.1) / 2), rot=(0, 0, ang), m=VERM_D, bevel=0.02)
        b.box((0.44, thick + 0.28, 0.5), (q.x, q.y, z0 + 0.25), rot=(0, 0, ang), m=STONE, bevel=0.03)


# ================================================================== STEPS + TERRACE
b = MB(uv=0.5)
for i in range(7):
    dep = 3.5 - 0.5 * i
    b.box((16.0, dep, 0.17), (0, NY + 0.5 * i + dep / 2, 0.17 * i + 0.085), m=STONE, bevel=0.018)
for sx in (1, -1):
    x0, x1 = sx * 8.0, sx * 8.7
    prof = [(NY - 0.35, 0.0), (TY, 0.0), (TY, TZ + 0.42), (TY - 0.7, TZ + 0.42), (NY - 0.35, 0.50)]
    pts = [(x0, y, z) for y, z in prof] + [(x1, y, z) for y, z in prof]
    k = len(prof)
    b.poly(pts, [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)] + [tuple(range(k)), tuple(range(2 * k - 1, k - 1, -1))],
           m=STONE, smooth=False)
    b.box((1.0, 1.0, 0.62), (sx * 8.35, NY - 0.55, 0.31), m=STONE, bevel=0.04)          # newel block at the foot
    b.box((0.84, 0.84, 0.10), (sx * 8.35, NY - 0.55, 0.67), m=STONE_D, bevel=0.03)
# terrace body with a paved top and a coping
b.box((2 * HX + 0.6, 31.6 - TY, TZ - 0.07), (0, (TY + 31.6) / 2, (TZ - 0.07) / 2), m=STONE_D)
bt = MB(uv=0.25)
bt.box((2 * HX + 0.6, 31.6 - TY + 0.12, 0.07), (0, (TY + 31.6) / 2 - 0.06, TZ - 0.035), m=FLAG, bevel=0.015)
for sx in (1, -1):
    b.box((HX - 8.6, 0.16, 0.20), (sx * (8.7 + (HX - 8.6) / 2), TY - 0.03, TZ - 0.24), m=STONE, bevel=0.03)   # string course
    balustrade(b, (sx * 8.9, TY + 0.22), (sx * (HX - 0.3), TY + 0.22), TZ)
    for k in range(5):                                       # carved roundels on the retaining wall
        b.cyl(0.36, 0.06, (sx * (10.0 + k * 1.75), TY - 0.02, 0.56), rot=(90, 0, 0), m=STONE, segs=20, bevel=0.02)
        b.cyl(0.20, 0.08, (sx * (10.0 + k * 1.75), TY - 0.03, 0.56), rot=(90, 0, 0), m=STONE_D, segs=8, bevel=0.02)
TERRACE = b.finish('Terrace')
TERRACE_TOP = bt.finish('TerraceTop')

# ================================================================== HALL
b = MB(uv=0.5)
g = MB(uv=1.0)                # everything that glows
HY0, HWALL, HY1, HHW = 21.2, 24.6, 29.6, 12.4
COLX = (-11.4, -7.0, -2.6, 2.6, 7.0, 11.4)
CH = 5.2
CT = PZ + CH                  # column tops
# plinth with two front steps
b.box((2 * HHW + 3.2, HY1 - 20.0 + 1.6, 0.30), (0, (20.0 + HY1 + 1.6) / 2, TZ + 0.15), m=STONE, bevel=0.03)
b.box((7.0, 0.5, 0.15), (0, 19.75, TZ + 0.075), m=STONE, bevel=0.02)
for x in COLX:
    column(b, x, HY0, PZ, CH)
    column(b, x, HWALL, PZ, CH)
for x in (-HHW, HHW):
    for y in (HWALL, 27.1, HY1):
        column(b, x, y, PZ, CH)
for x in COLX:
    column(b, x, HY1, PZ, CH)
# architrave on the front columns, tie beams back to the wall
for y, m_ in ((HY0, GREENW), (HWALL, VERM_D)):
    b.box((2 * HHW + 0.9, 0.34, 0.52), (0, y, CT - 0.58), m=m_, bevel=0.03)
    b.box((2 * HHW + 0.9, 0.36, 0.06), (0, y, CT - 0.30), m=GOLD)
    b.box((2 * HHW + 0.9, 0.36, 0.05), (0, y, CT - 0.86), m=GOLD)
    b.box((2 * HHW + 0.9, 0.30, 0.30), (0, y, CT - 1.12), m=BLUEW if y == HY0 else VERM_D, bevel=0.03)
for k in range(40):                                          # painted panels on the architrave face
    x = -HHW + 0.5 + k * (2 * HHW - 1.0) / 39
    b.box((0.34, 0.02, 0.30), (x, HY0 - 0.175, CT - 0.58), m=(GOLD if k % 4 == 0 else (VERM if k % 2 else BLUEW)), bevel=0.004)
for x in COLX:
    b.box((0.30, HWALL - HY0, 0.36), (x, (HY0 + HWALL) / 2, CT - 0.50), m=VERM_D, bevel=0.03)
    # bracket set stepping out under the eave
    for k, (w_, dy, z) in enumerate(((0.56, 0.0, 0.16), (0.92, -0.30, 0.38), (1.30, -0.62, 0.60))):
        b.box((w_, 0.30, 0.17), (x, HY0 + dy, CT + z), m=(GREENW if k % 2 == 0 else VERM_D), bevel=0.02)
        b.box((0.26, 0.86 + 0.42 * k, 0.17), (x, HY0 + dy * 0.6 - 0.1, CT + z - 0.02), m=(VERM_D if k % 2 == 0 else GREENW), bevel=0.02)
        for sx in (1, -1):
            b.box((0.20, 0.34, 0.12), (x + sx * w_ * 0.42, HY0 + dy, CT + z + 0.13), m=BLACKW, bevel=0.02)
            b.box((0.205, 0.02, 0.125), (x + sx * w_ * 0.42, HY0 + dy - 0.175, CT + z + 0.13), m=GOLD)
for i in range(len(COLX) - 1):                                # lighter sets between the columns
    for f in ((0.5,) if abs(COLX[i] + COLX[i + 1]) < 0.1 else (0.33, 0.67)):
        x = COLX[i] + (COLX[i + 1] - COLX[i]) * f
        for k, (w_, dy, z) in enumerate(((0.40, 0.0, 0.16), (0.70, -0.30, 0.38))):
            b.box((w_, 0.26, 0.15), (x, HY0 + dy, CT + z), m=(BLUEW if k == 0 else GREENW), bevel=0.02)
            b.box((0.20, 0.7, 0.15), (x, HY0 + dy * 0.5, CT + z - 0.02), m=VERM_D, bevel=0.02)
b.box((2 * HHW + 3.6, 0.26, 0.24), (0, HY0 - 1.62, CT + 0.64), m=VERM_D, bevel=0.03)          # eave purlin
# front wall: side bays with lattice windows, centre bay open
BAYS = ((-HHW, -7.0), (-7.0, -2.6), (2.6, 7.0), (7.0, HHW))
for x0, x1 in BAYS:
    cx, w_ = (x0 + x1) / 2, (x1 - x0) - 0.6
    b.box((w_, 0.22, 1.15), (cx, HWALL, PZ + 0.575), m=VERM_D)
    for k in range(3):
        b.box((w_ / 3 - 0.12, 0.03, 0.80), (cx + (k - 1) * w_ / 3, HWALL - 0.12, PZ + 0.60), m=BLACKW, bevel=0.01)
    b.box((w_, 0.26, 0.14), (cx, HWALL, PZ + 1.20), m=BLACKW, bevel=0.02)
    g.poly([(cx - w_ / 2, HWALL - 0.03, PZ + 1.27), (cx + w_ / 2, HWALL - 0.03, PZ + 1.27), (cx + w_ / 2, HWALL - 0.03, PZ + 3.85),
            (cx - w_ / 2, HWALL - 0.03, PZ + 3.85)], [(0, 1, 2, 3)], m=LATTICE, uvs=[(0, 0), (w_ / 2.4, 0), (w_ / 2.4, 1.08), (0, 1.08)])
    for k in range(1, 3):
        b.box((0.10, 0.12, 2.6), (cx - w_ / 2 + k * w_ / 3, HWALL - 0.05, PZ + 2.56), m=BLACKW)
    b.box((w_, 0.26, 0.14), (cx, HWALL, PZ + 3.92), m=BLACKW, bevel=0.02)
    b.box((w_, 0.20, CH - 4.0 - 1.25), (cx, HWALL, PZ + 4.0 + (CH - 5.25) / 2), m=PLASTER)
# door bay: jambs, transom lattice, two leaves swung inward
DW, DH = 2.15, 4.3
for sx in (1, -1):
    b.box((0.45, 0.30, DH + 0.2), (sx * (DW + 0.22), HWALL, PZ + DH / 2), m=VERM, bevel=0.03)
    Md = TRS((sx * DW, HWALL + 0.05, PZ)) @ TRS((0, 0, 0), (0, 0, -sx * 68))
    b.box((DW, 0.12, DH), m=VERM, bevel=0.015, M=Md @ TRS((-sx * DW / 2, 0, DH / 2)))
    for iy in range(7):
        for ix in range(5):
            b.sphere(0.035, m=GOLD, segs=8, M=Md @ TRS((-sx * (0.25 + ix * 0.41), -0.07, 0.45 + iy * 0.56)))
    b.cyl(0.11, 0.03, m=GOLD, segs=12, M=Md @ TRS((-sx * (DW - 0.28), -0.07, 2.0), (90, 0, 0)))
b.box((2 * DW + 0.9, 0.34, 0.26), (0, HWALL, PZ + DH + 0.13), m=VERM, bevel=0.03)
g.poly([(-DW - 0.4, HWALL - 0.03, PZ + DH + 0.28), (DW + 0.4, HWALL - 0.03, PZ + DH + 0.28), (DW + 0.4, HWALL - 0.03, CT - 1.28),
        (-DW - 0.4, HWALL - 0.03, CT - 1.28)], [(0, 1, 2, 3)], m=LATTICE, uvs=[(0, 0), (2.5, 0), (2.5, 0.25), (0, 0.25)])
# name board over the door
Mb = TRS((0, HY0 - 0.34, CT - 1.35), (-12, 0, 0))
b.box((3.0, 0.10, 1.16), m=BLUEW, bevel=0.02, M=Mb)
b.box((3.16, 0.08, 1.32), m=GOLD, bevel=0.03, M=Mb @ TRS((0, 0.03, 0)))
for k in range(3):                                           # three abstract gold seals
    Mg = Mb @ TRS(((k - 1) * 0.92, -0.06, 0))
    b.box((0.62, 0.02, 0.07), m=GOLD, M=Mg @ TRS((0, 0, 0.30)))
    b.box((0.62, 0.02, 0.07), m=GOLD, M=Mg @ TRS((0, 0, -0.30)))
    b.box((0.07, 0.02, 0.60), m=GOLD, M=Mg @ TRS((-0.26 + 0.26 * k, 0, 0)))
    b.box((0.36, 0.02, 0.07), m=GOLD, M=Mg @ TRS((0.10 - 0.1 * k, 0, 0.02)))
# body: side and back walls, interior
for sx in (1, -1):
    b.box((0.24, HY1 - HWALL, CH - 0.3), (sx * HHW, (HWALL + HY1) / 2, PZ + (CH - 0.3) / 2), m=PLASTER)
b.box((2 * HHW, 0.24, CH - 0.3), (0, HY1, PZ + (CH - 0.3) / 2), m=PLASTER)
b.box((2 * HHW, HY1 - HWALL, 0.2), (0, (HWALL + HY1) / 2, CT - 0.2), m=BLACKW)                 # ceiling
bw = MB(uv=0.5)
bw.box((2 * HHW, HY1 - HWALL, 0.04), (0, (HWALL + HY1) / 2, PZ + 0.02), m=WOOD)
g.poly([(-6.5, HY1 - 0.16, PZ), (6.5, HY1 - 0.16, PZ), (6.5, HY1 - 0.16, CT - 0.3), (-6.5, HY1 - 0.16, CT - 0.3)], [(0, 1, 2, 3)],
       m=INTERIOR, uvs=[(0, 0), (3, 0), (3, 1.2), (0, 1.2)])
for sx in (1, -1):                                           # inner partitions close the lit nave
    b.box((0.2, HY1 - HWALL, CH - 0.3), (sx * 6.6, (HWALL + HY1) / 2, PZ + (CH - 0.3) / 2), m=VERM_D)
# seated guardian on a dais, altar with candles
b.box((4.4, 2.2, 0.5), (0, 28.2, PZ + 0.25), m=BLACKW, bevel=0.04)
b.box((4.6, 2.4, 0.08), (0, 28.2, PZ + 0.54), m=GOLD, bevel=0.02)
Ms = TRS((0, 28.3, PZ + 0.58))
b.lathe([(0, 0), (1.25, 0), (1.32, 0.20), (1.10, 0.42), (0.80, 0.62), (0.62, 1.0), (0.66, 1.5), (0.74, 1.9), (0.60, 2.2),
         (0.30, 2.36), (0.27, 2.50), (0.36, 2.66), (0.40, 2.90), (0.30, 3.12), (0.12, 3.24), (0.10, 3.40), (0, 3.46)],
        m=BRONZE, segs=20, M=Ms @ TRS((0, 0, 0), (0, 0, 0), (1.0, 0.72, 1.0)))
for sx in (1, -1):
    b.sphere(1.0, m=BRONZE, segs=14, M=Ms @ TRS((sx * 0.95, -0.25, 0.42), (0, 0, sx * 25), (0.62, 0.36, 0.30)))      # knees
    b.sphere(1.0, m=BRONZE, segs=12, M=Ms @ TRS((sx * 0.82, 0.0, 1.9), (0, sx * 20, 0), (0.30, 0.30, 0.52)))         # shoulders
g.lathe([(1.5, 0), (1.52, 0.02)], m=GOLD, segs=4, M=Ms)
b.lathe([(1.30, 2.0), (1.42, 2.02), (1.30, 2.04)], m=GOLD, segs=28, M=Ms @ TRS((0, 0.42, 0.9), (90, 0, 0)))          # halo ring
b.box((3.4, 0.7, 0.9), (0, 26.4, PZ + 0.45), m=BLACKW, bevel=0.03)
b.box((3.6, 0.8, 0.06), (0, 26.4, PZ + 0.93), m=VERM, bevel=0.02)
for k in range(7):
    x = -1.5 + k * 0.5
    h = 0.20 + 0.10 * ((k * 7) % 3)
    b.cyl(0.035, h, (x, 26.4, PZ + 0.96 + h / 2), m=PLASTER, segs=8)
    g.sphere(1.0, (x, 26.4, PZ + 0.96 + h + 0.05), scale=(0.028, 0.028, 0.06), m=FLAME, segs=8)
    META['candles'].append(T3((x, 26.4, PZ + 1.0 + h)))
b.lathe([(0.20, 0), (0.34, 0.10), (0.38, 0.30), (0.30, 0.42), (0.34, 0.46), (0, 0.46)], m=BRONZE, segs=14, M=TRS((0, 26.4, PZ + 0.96)))
# hanging festival lanterns in the porch bays
for x0, x1 in BAYS:
    paper_lantern(g, b, (x0 + x1) / 2, HY0 - 0.9, CT - 1.75, R=0.50, H=0.60, top=CT + 0.4)
for sx in (1, -1):
    paper_lantern(g, b, sx * 1.55, HY0 - 0.5, CT - 2.2, R=0.34, H=0.44, m=PAPER, top=CT - 1.0)
META['door'] = T3((0, HWALL, PZ + 2.2))
META['altar'] = T3((0, 26.4, PZ + 1.4))
HALL = b.finish('Hall')
HALL_FLOOR = bw.finish('HallFloor')

# ================================================================== ROOFS
b = MB(uv=0.5)
HCY = (HY0 + HY1) / 2
rect_roof(b, 0, HCY, HHW + 2.9, (HY1 - HY0) / 2 + 2.9, CT + 0.62, 10.5, 2.9, CT + 2.95, lift=1.05, ridge=False, rafter=1.7)
# upper storey band between the two roofs
UZ0, UZ1 = CT + 2.80, CT + 3.95
bu = MB(uv=0.5)
bu.box((21.0, 5.8, UZ1 - UZ0), (0, HCY, (UZ0 + UZ1) / 2), m=VERM_D)
for k in range(9):
    x = -9.6 + k * 2.4
    bu.box((0.26, 5.9, UZ1 - UZ0), (x, HCY, (UZ0 + UZ1) / 2), m=VERM, bevel=0.02)
    if k < 8:
        for sy in (1, -1):
            g.poly([(x + 0.2, HCY + sy * 2.92, UZ0 + 0.42), (x + 2.2, HCY + sy * 2.92, UZ0 + 0.42), (x + 2.2, HCY + sy * 2.92, UZ1 - 0.12),
                    (x + 0.2, HCY + sy * 2.92, UZ1 - 0.12)], [(0, 1, 2, 3)], m=LATTICE, uvs=[(0, 0), (1.0, 0), (1.0, 0.25), (0, 0.25)])
bu.box((21.4, 6.2, 0.16), (0, HCY, UZ1 - 0.02), m=GREENW, bevel=0.02)
for k in range(22):                                          # small bracket blocks under the upper eave
    x = -10.2 + k * (20.4 / 21)
    for sy in (1, -1):
        bu.box((0.34, 0.9, 0.18), (x, HCY + sy * 3.3, UZ1 + 0.16), m=(GREENW if k % 2 else BLUEW), bevel=0.02)
        bu.box((0.56, 0.3, 0.16), (x, HCY + sy * 3.5, UZ1 + 0.36), m=VERM_D, bevel=0.02)
rect_roof(b, 0, HCY, 13.0, 5.5, UZ1 + 0.45, 8.4, 0.16, UZ1 + 4.3, lift=1.25, rafter=1.5)
ROOFS = b.finish('Roofs', smooth=60)
UPPER = bu.finish('HallUpper')

# ================================================================== COURT WALLS + SOUTH GATE
b = MB(uv=0.33)
WH = 3.1
wx = HX + 0.25
for sx in (1, -1):
    wall(b, (sx * wx, SY - 0.25), (sx * wx, TY), 0, WH)
    wall(b, (sx * wx, TY), (sx * wx, 31.4), TZ, WH)
    wall(b, (sx * 2.9, SY - 0.25), (sx * wx, SY - 0.25), 0, WH)
wall(b, (-wx, 31.4), (wx, 31.4), TZ, WH)
WALLS = b.finish('Walls')

b = MB(uv=0.5)
GY = SY - 0.25
for sx in (1, -1):
    column(b, sx * 2.55, GY, 0, 5.0, r=0.30)
    column(b, sx * 4.3, GY, 0, 3.6, r=0.22)
    b.box((1.9, 0.26, 0.30), (sx * 3.4, GY, 3.45), m=GREENW, bevel=0.03)
    b.box((1.9, 0.30, 0.05), (sx * 3.4, GY, 3.62), m=GOLD)
    Md = TRS((sx * 2.2, GY - 0.1, 0)) @ TRS((0, 0, 0), (0, 0, sx * 74))
    b.box((2.15, 0.12, 3.9), m=VERM, bevel=0.015, M=Md @ TRS((-sx * 1.075, 0, 1.95)))
    for iy in range(6):
        for ix in range(4):
            b.sphere(0.035, m=GOLD, segs=8, M=Md @ TRS((-sx * (0.3 + ix * 0.5), 0.07, 0.5 + iy * 0.6)))
b.box((6.2, 0.36, 0.46), (0, GY, 4.62), m=GREENW, bevel=0.03)
b.box((6.2, 0.38, 0.06), (0, GY, 4.88), m=GOLD)
b.box((5.4, 0.30, 0.30), (0, GY, 4.15), m=VERM_D, bevel=0.03)
b.box((2.2, 0.08, 0.80), (0, GY + 0.22, 4.40), rot=(10, 0, 0), m=BLUEW, bevel=0.02)
b.box((2.34, 0.06, 0.94), (0, GY + 0.20, 4.40), rot=(10, 0, 0), m=GOLD, bevel=0.03)
for x in (-2.55, 0, 2.55):
    for k, (w_, z) in enumerate(((0.5, 5.12), (0.9, 5.32))):
        b.box((w_, 0.9 + 0.6 * k, 0.16), (x, GY, z), m=(GREENW if k == 0 else VERM_D), bevel=0.02)
rect_roof(b, 0, GY, 4.9, 2.0, 5.45, 3.5, 0.16, 6.95, lift=0.75, rafter=0.9)
gg = MB(uv=1.0)
for sx in (1, -1):
    paper_lantern(gg, b, sx * 1.35, GY + 0.75, 3.55, R=0.34, H=0.44, m=PAPER_RED, top=4.4, key='hall_lanterns')
GATE = b.finish('Gate', smooth=60)

# ================================================================== STONE LANTERNS, STRINGS, PROPS
b = MB(uv=0.5)
for a in (25, 65, 115, 155, 205, 245, 295, 335):
    stone_lantern(b, g, 13.4 * C(rad(a)), 13.4 * S_(rad(a)))
for sx in (1, -1):
    stone_lantern(b, g, sx * 8.35, NY - 0.55, 0.72, s=0.9)
META['path_lanterns'] = []
for sx, y in ((1, -27.0), (-1, -36.0)):
    stone_lantern(b, g, sx * 3.4, y, 0, key='path_lanterns')
LANTERNS = b.finish('Lanterns')


def string_run(b, g, p0, p1, sag, n, start=0):
    p0, p1 = Vector(p0), Vector(p1)
    pts = []
    for i in range(25):
        t = i / 24
        q = p0.lerp(p1, t)
        q.z -= sag * 4 * t * (1 - t)
        pts.append(q)
    b.tube(pts, 0.012, m=ROPE, segs=4, cap=False)
    for i in range(n):
        t = (i + 0.5) / n
        q = p0.lerp(p1, t)
        q.z -= sag * 4 * t * (1 - t) + 0.30
        paper_lantern(g, b, q.x, q.y, q.z, R=0.19, H=0.23, m=(PAPER_RED if (i + start) % 2 == 0 else PAPER),
                      top=q.z + 0.30, key='string_lanterns')


def pole(b, x, y, h, z0=0.0):
    b.lathe([(0.16, 0), (0.16, 0.5), (0.10, 0.56), (0.085, h * 0.5), (0.065, h)], m=BLACKW, segs=10, M=TRS((x, y, z0)))
    b.box((0.5, 0.5, 0.3), (x, y, z0 + 0.15), m=STONE, bevel=0.04)
    b.sphere(0.10, (x, y, z0 + h + 0.06), m=GOLD, segs=10)


b = MB(uv=0.5)
PH = 6.4
SW_, SE_ = (-16.2, -16.2, PH), (16.2, -16.2, PH)
WM, WN = (-16.4, -1.0, PH), (-16.2, 14.6, PH)
EM = (16.4, -1.5, PH)
for p in (SW_, SE_, WM, WN, EM):
    pole(b, p[0], p[1], PH)
string_run(b, g, SW_, WM, 1.0, 7)
string_run(b, g, WM, WN, 1.0, 7, start=1)
string_run(b, g, SE_, EM, 1.0, 7)
string_run(b, g, SW_, (-4.9, GY, 6.3), 0.9, 5, start=1)
string_run(b, g, SE_, (4.9, GY, 6.3), 0.9, 5, start=1)
# banners flanking the steps and the south gate
for (x, y, h, face) in ((-10.6, 11.9, 7.4, 1), (10.6, 11.9, 7.4, 1), (-6.6, -16.3, 6.2, -1), (6.6, -16.3, 6.2, -1)):
    pole(b, x, y, h)
    b.cyl(0.035, 1.5, (x, y, h - 0.35), rot=(0, 90, 0), m=BLACKW, segs=8)
    bw_, bh = 1.25, 4.4
    ph = rng.uniform(0, 6)

    def bfn(u, v, x=x, y=y, h=h, ph=ph, face=face):
        sway = (1 - v) * (0.16 * S_(v * 4.0 + ph) + 0.05 * S_(u * 9 + ph))
        return (x + (u - 0.5) * bw_ * face * -1, y - 0.04 * face + sway * -face, h - 0.42 - bh * (1 - v))
    b.grid(bfn, 6, 22, m=BANNER, uvs=(1.0, 1.0))
    b.cyl(0.03, 1.3, (x, y - 0.04, h - 0.42 - bh), rot=(0, 90, 0), m=BLACKW, segs=8)
# bronze censers on the terrace
for sx in (1, -1):
    Mc = TRS((sx * 5.4, 18.3, TZ))
    for k in range(3):
        a = rad(90 + k * 120)
        b.tube([(sx * 5.4 + 0.50 * C(a), 18.3 + 0.50 * S_(a), TZ), (sx * 5.4 + 0.56 * C(a), 18.3 + 0.56 * S_(a), TZ + 0.3),
                (sx * 5.4 + 0.42 * C(a), 18.3 + 0.42 * S_(a), TZ + 0.62)], [0.09, 0.07, 0.10], m=BRONZE, segs=8)
    b.lathe([(0, 0.52), (0.36, 0.54), (0.62, 0.70), (0.74, 0.95), (0.70, 1.18), (0.60, 1.26), (0.66, 1.30), (0.66, 1.36), (0.50, 1.36)],
            m=BRONZE, segs=20, M=Mc)
    b.lathe([(0.56, 1.36), (0.50, 1.52), (0.32, 1.70), (0.14, 1.80), (0.10, 1.90), (0.15, 1.98), (0, 2.04)], m=BRONZE, segs=20, M=Mc)
    for k in range(2):
        b.lathe([(0.10, 0.0), (0.12, 0.02), (0.10, 0.04)], m=BRONZE, segs=12, M=Mc @ TRS(((k * 2 - 1) * 0.78, 0, 1.12), (90, 0, 0)))
    g.cyl(0.44, 0.04, (sx * 5.4, 18.3, TZ + 1.33), m=FLAME, segs=14)
    META.setdefault('censers', []).append(T3((sx * 5.4, 18.3, TZ + 1.5)))
# great drum on a stand (west side)
Md = TRS((-15.4, 4.6, 0), (0, 0, 14))
b.lathe([(0.0, -0.55), (0.72, -0.55), (0.86, -0.30), (0.92, 0.0), (0.86, 0.30), (0.72, 0.55), (0.0, 0.55)], m=VERM, segs=24,
        M=Md @ TRS((0, 0, 1.65), (0, 90, 0)))
for sg in (1, -1):
    b.cyl(0.70, 0.03, m=SKIN, segs=24, M=Md @ TRS((sg * 0.56, 0, 1.65), (0, 90, 0)))
    for k in range(20):
        a = rad(k * 18)
        b.sphere(0.028, m=GOLD, segs=6, M=Md @ TRS((sg * 0.50, 0.745 * C(a), 1.65 + 0.745 * S_(a))))
for sy in (1, -1):
    for sx in (1, -1):
        b.box((0.12, 0.12, 1.9), m=BLACKW, bevel=0.015, M=Md @ TRS((sx * 0.36, sy * 0.86, 0.95), (sy * -7, 0, 0)))
    b.box((1.0, 0.12, 0.12), m=BLACKW, bevel=0.015, M=Md @ TRS((0, sy * 0.80, 0.42)))
    b.box((1.0, 0.14, 0.14), m=BLACKW, bevel=0.015, M=Md @ TRS((0, sy * 0.76, 0.85)))
b.box((0.16, 1.8, 0.12), m=BLACKW, bevel=0.015, M=Md @ TRS((0, 0, 0.42)))
# glazed urns
for (x, y, s) in ((-15.6, -13.6, 1.0), (-14.5, -14.9, 0.8), (15.5, -11.8, 1.1), (15.9, -9.9, 0.75), (15.2, 3.4, 0.9), (-15.9, 12.0, 0.85)):
    b.lathe([(0, 0), (0.26, 0), (0.30, 0.06), (0.46, 0.34), (0.50, 0.62), (0.40, 0.92), (0.24, 1.04), (0.22, 1.10), (0.30, 1.16),
             (0.28, 1.20), (0.20, 1.18)], m=CERAMIC, segs=18, M=TRS((x, y, 0), (0, 0, 0), s))
# weapon rack on the west wall
Mr = TRS((-16.5, -7.0, 0), (0, 0, 90))
for sx in (1, -1):
    b.box((0.10, 0.5, 1.5), m=WOOD, M=Mr @ TRS((sx * 1.5, 0, 0.75)), bevel=0.01)
    b.box((0.14, 0.7, 0.10), m=WOOD, M=Mr @ TRS((sx * 1.5, 0, 0.05)), bevel=0.01)
for z in (0.55, 1.42):
    b.box((3.1, 0.10, 0.10), m=WOOD, M=Mr @ TRS((0, 0, z)), bevel=0.01)
for k in range(6):
    x = -1.25 + k * 0.5
    L = 2.5 + 0.25 * ((k * 5) % 3)
    Mp = Mr @ TRS((x, 0.12, 0.05), (4, 0, 0))
    b.cyl(0.022, L, m=BLACKW, segs=6, M=Mp @ TRS((0, 0, L / 2)))
    if k % 2 == 0:
        b.cyl(0.05, 0.42, m=IRON, segs=4, r2=0.002, M=Mp @ TRS((0, 0, L + 0.2), (0, 0, 45)) @ TRS((0, 0, 0), (0, 0, 0), (1, 0.3, 1)))
        b.cyl(0.035, 0.10, m=VERM, segs=8, M=Mp @ TRS((0, 0, L - 0.05)))
    else:
        b.box((0.012, 0.11, 0.62), m=IRON, M=Mp @ TRS((0, 0.035, L + 0.25)), bevel=0.004)
        b.cyl(0.03, 0.06, m=GOLD, segs=8, M=Mp @ TRS((0, 0, L - 0.05)))
# training posts wrapped in rope (south-east corner)
for (x, y, h) in ((13.2, -13.6, 1.9), (14.6, -15.0, 1.7), (15.4, -13.2, 2.1)):
    b.cyl(0.13, h, (x, y, h / 2), m=WOOD, segs=10, bevel=0.02)
    b.cyl(0.155, 0.5, (x, y, h * 0.62), m=ROPE, segs=10, bevel=0.02, bsegs=1)
    b.cyl(0.155, 0.3, (x, y, h * 0.25), m=ROPE, segs=10, bevel=0.02, bsegs=1)
PROPS = b.finish('Props')
GLOW = g.finish('Glow')
GLOW2 = gg.finish('GlowGate')

# ================================================================== MAPLE
tb = MB(uv=0.6)
fb = MB(uv=1.0)
trng = random.Random(5)
CELLS = [(0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5)]
LEAF_PTS = []


def spray(fb, p, d, size):
    """Two crossed cards hanging from a twig at p, growing along d."""
    d = d.normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 0.1:
        side = Vector((1, 0, 0))
    side.normalize()
    droop = Vector((0, 0, -0.35))
    for k in range(2):
        s = Quaternion(d, rad(trng.uniform(0, 180) + 90 * k)) @ side
        axis = (d * 0.8 + droop + Vector((trng.uniform(-.3, .3), trng.uniform(-.3, .3), trng.uniform(-.2, .2)))).normalized()
        a = p - axis * size * 0.10
        cu, cv = CELLS[trng.randrange(4)]
        pts = [a - s * size * 0.5, a + s * size * 0.5, a + s * size * 0.5 + axis * size, a - s * size * 0.5 + axis * size]
        fb.poly([tuple(q) for q in pts], [(0, 1, 2, 3)], m=FOLIAGE, recalc=False,
                uvs=[(cu, cv), (cu + 0.5, cv), (cu + 0.5, cv + 0.5), (cu, cv + 0.5)])
    LEAF_PTS.append(p.copy())


def ok_leaf(p):
    return not (math.hypot(p.x, p.y) < 12.2 and p.z < 5.0) and p.z > 2.6 and abs(p.x) < 21 and p.y < 19.5


def grow(p, d, L, r, depth):
    n = 5
    pts, rs = [p.copy()], [r]
    d = d.normalized()
    for i in range(n):
        d = (d + Vector((trng.uniform(-.3, .3), trng.uniform(-.3, .3), trng.uniform(-.10, .22))) * 0.45).normalized()
        p = p + d * (L / n)
        pts.append(p.copy())
        rs.append(r * (1 - 0.42 * (i + 1) / n))
    tb.tube(pts, rs, m=BARK, segs=(10 if depth == 0 else (7 if depth < 3 else 5)), cap=(depth == 0))
    if depth >= 2:
        for i in range(1, n + 1):
            for k in range(1 if depth == 2 else 2):
                q = pts[i] + Vector((trng.uniform(-.4, .4), trng.uniform(-.4, .4), trng.uniform(-.2, .3)))
                if ok_leaf(q):
                    spray(fb, q, (d + Vector((trng.uniform(-.8, .8), trng.uniform(-.8, .8), trng.uniform(-.5, .2)))), trng.uniform(1.2, 2.0))
    if depth < 4:
        kids = 3 if depth in (0, 2) else 2
        base = trng.uniform(0, 360)
        for j in range(kids):
            ax = Quaternion(d, rad(base + j * 360 / kids + trng.uniform(-25, 25))) @ d.orthogonal().normalized()
            nd = Quaternion(ax, rad(trng.uniform(30, 58))) @ d
            nd.z = max(nd.z, -0.05 if depth < 3 else -0.35)
            grow(pts[-1], nd, L * trng.uniform(0.66, 0.84), rs[-1] * 0.82, depth + 1)


TREE_AT = Vector((13.9, 9.2, 0))
tb.lathe([(0.95, -0.1), (0.70, 0.10), (0.52, 0.34), (0.44, 0.7)], m=BARK, segs=12, M=TRS(tuple(TREE_AT)))
for k in range(5):                                           # root flares
    a = rad(k * 72 + 20)
    tb.tube([TREE_AT + Vector((0.30 * C(a), 0.30 * S_(a), 0.5)), TREE_AT + Vector((0.75 * C(a), 0.75 * S_(a), 0.14)),
             TREE_AT + Vector((1.5 * C(a), 1.5 * S_(a), -0.05))], [0.17, 0.14, 0.05], m=BARK, segs=6)
grow(TREE_AT + Vector((0, 0, 0.5)), Vector((-0.30, -0.16, 1.0)), 3.3, 0.44, 0)
# stone ring around the tree bed
tb.lathe([(1.9, 0), (1.9, 0.30), (1.62, 0.30), (1.62, 0.0)], m=STONE, segs=10, M=TRS(tuple(TREE_AT)))
tb.lathe([(0, 0.22), (1.62, 0.22)], m=EARTH, segs=10, M=TRS(tuple(TREE_AT)))
TREE = tb.finish('Tree')
FOLI = fb.finish('Foliage', smooth=180)
cx_ = sum(p.x for p in LEAF_PTS) / len(LEAF_PTS)
cy_ = sum(p.y for p in LEAF_PTS) / len(LEAF_PTS)
cz_ = sum(p.z for p in LEAF_PTS) / len(LEAF_PTS)
META['tree'] = {'trunk': T3(tuple(TREE_AT)), 'canopy': T3((cx_, cy_, cz_)),
                'radius': round(max(math.hypot(p.x - cx_, p.y - cy_) for p in LEAF_PTS), 2),
                'bottom': round(min(p.z for p in LEAF_PTS), 2), 'top': round(max(p.z for p in LEAF_PTS), 2)}
print('LEAF SPRAYS', len(LEAF_PTS), META['tree'])

# ================================================================== PINES outside the walls
pb = MB(uv=0.6)
nb = MB(uv=1.0)
prng = random.Random(21)


def pine(x, y, h, z0=0.0):
    lean = prng.uniform(-0.5, 0.5)
    pb.tube([(x, y, z0 - 0.3), (x + lean * 0.3, y, z0 + h * 0.5), (x + lean, y, z0 + h)], [0.30 * h / 12, 0.2 * h / 12, 0.04], m=BARK, segs=6)
    tiers = int(h / 1.25)
    for t in range(tiers):
        f = t / tiers
        z = z0 + h * (0.30 + 0.70 * f)
        R = (1 - f) * h * 0.34 + 0.7
        cx = x + lean * (0.30 + 0.70 * f) ** 2
        for k in range(7):
            a = rad(k * 360 / 7 + t * 37 + prng.uniform(-15, 15))
            dx, dy = C(a), S_(a)
            px, py = -dy, dx
            w_ = R * 0.62
            z1 = z - R * prng.uniform(0.30, 0.55)
            nb.poly([(cx - px * w_ * 0.3, y - py * w_ * 0.3, z + 0.1), (cx + px * w_ * 0.3, y + py * w_ * 0.3, z + 0.1),
                     (cx + dx * R + px * w_, y + dy * R + py * w_, z1), (cx + dx * R - px * w_, y + dy * R - py * w_, z1)],
                    [(0, 1, 2, 3)], m=NEEDLE, recalc=False, uvs=[(0.3, 1), (0.7, 1), (1, 0), (0, 0)])


for (x, y, h) in ((-22, -12, 13), (-24.5, -3, 16), (-21.5, 6, 12), (-25, 14, 17), (-22.5, 24, 14), (-27, 31, 18),
                  (22.5, -13, 14), (25, -5, 12), (23, 16, 15), (26.5, 26, 17), (22, 33, 13),
                  (-13, -24, 14), (-7.5, -27, 16), (8, -26, 15), (14, -23.5, 12), (-19, -21.5, 13), (20, -21, 15),
                  (-12, 37, 17), (-3, 39.5, 19), (7, 38.5, 18), (15, 36.5, 16), (-21, 37, 15), (23, 38, 15),
                  (-9, -40, 15), (9.5, -42, 17), (-32, 4, 18), (33, 8, 19), (31, -16, 17), (-31, -18, 16)):
    pine(x + prng.uniform(-1, 1), y + prng.uniform(-1, 1), h * prng.uniform(0.9, 1.15))
PINES = pb.finish('BackdropPines')
NEEDLES = nb.finish('BackdropNeedles', smooth=180)

# ================================================================== MOUNTAINS
mb = MB(uv=0.01)


def ridge(R, base, amp, seed, m, peaks=()):
    """Ring of ridgeline: layered ridged noise (sharp crests, soft saddles) plus a few broad named peaks."""
    r_ = random.Random(seed)
    octs = [(r_.uniform(0, 6.28), f, w) for f, w in ((3, 1.0), (5, 0.8), (8, 0.62), (13, 0.46), (21, 0.30), (34, 0.20), (55, 0.12), (89, 0.07))]
    S = 420
    pts = []
    for i in range(S):
        a = 2 * math.pi * i / S
        h = 0.0
        for p, f, wt in octs:
            h += wt * (1 - abs(S_(a * f * 0.5 + p))) ** 1.6                 # ridged: pointed tops
        h = base + amp * h / 3.0
        for (pa, pw, phh) in peaks:
            dd = math.atan2(S_(a - pa), C(a - pa))
            h += phh * math.exp(-abs(dd / pw) ** 1.5) * (0.8 + 0.2 * S_(a * 60 + seed))
        pts.append((R * C(a), R * S_(a), -15))
        pts.append((R * C(a), R * S_(a), h))
    mb.poly(pts, [(2 * i, 2 * ((i + 1) % S), 2 * ((i + 1) % S) + 1, 2 * i + 1) for i in range(S)], m=m, smooth=False)


# a (Blender angle): north = 90 deg. A tall massif NNE of the hall balances the moon in the NNW.
ridge(210, 10, 40, 3, MTN1, peaks=((rad(62), 0.28, 34), (rad(205), 0.35, 24)))
ridge(330, 26, 70, 5, MTN2, peaks=((rad(120), 0.30, 46), (rad(18), 0.35, 34)))
ridge(470, 44, 100, 9, MTN3, peaks=((rad(82), 0.24, 120), (rad(300), 0.35, 50)))
MTNS = mb.finish('BackdropMountains')

# ================================================================== output
obs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print('TRIS', {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in obs})
print('TOTAL', sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in obs))
md = Vector((-0.38, 0.40, -0.83)).normalized()
META['moon_dir'] = [round(v, 4) for v in md]
META['steps_z'] = -NY
META['terrace_y'] = TZ
META['bounds'] = {'x': HX, 'south_z': -SY, 'north_z': -NY}

if 'preview' in sys.argv:
    kw = dict(sun=(2.2, (60, 0, 150)), world=(0.10, 0.12, 0.16), fill=0.8)
    preview(os.path.join(PREVIEW, 'arena_play.png'), (0, -13, 2.4), (0, 14, 4.5), lens=28, res=(1400, 800), **kw)
    preview(os.path.join(PREVIEW, 'arena_hall.png'), (6, 6, 2.0), (0, 22, 6), lens=30, res=(1400, 800))
    preview(os.path.join(PREVIEW, 'arena_top.png'), (0, -34, 46), (0, 4, 0), lens=30, res=(1400, 800))
    preview(os.path.join(PREVIEW, 'arena_rev.png'), (3, 15, 3.2), (-2, -14, 2.0), lens=24, res=(1400, 800))
    preview(os.path.join(PREVIEW, 'arena_east.png'), (-9, -5, 2.2), (14, 8, 4.0), lens=26, res=(1400, 800))
    drop_preview_rig()

strip_preview_tint()
_path = os.path.join(OUT, 'arena.glb')
bpy.ops.export_scene.gltf(filepath=_path, export_format='GLB', export_yup=True, export_apply=True, export_extras=True,
                          export_image_format='WEBP', export_image_quality=88, export_animations=False, export_tangents=False)
print('EXPORTED', _path, round(os.path.getsize(_path) / 1e6, 2), 'MB')
with open(os.path.join(OUT, 'arena_meta.json'), 'w') as f:
    json.dump(META, f, indent=1)
print('ARENA DONE')
