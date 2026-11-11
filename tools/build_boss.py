"""Marshal Yan, Warden of the Vermilion Gate: armoured giant with a glaive -> game/assets/boss.glb + boss_meta.json
Run: blender -b -P tools/build_boss.py [-- preview look [Clip [frame]] | preview <Clip>[,<Clip>] [frames]] [-- noclips]"""
import bpy, math, os, sys, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import *
from rigkit import *
from charkit import *

reset()
sc = bpy.context.scene
sc.render.fps = 60

# ------------------------------------------------------------------ materials
LAC = mat('b_lacquer', (0.040, 0.040, 0.050), rough=0.30, tex='c_lacquer')
LACR = mat('b_lacquer_red', (0.520, 0.060, 0.035), rough=0.32, tex='c_lacquer')
GOLD = mat('b_gold', (0.95, 0.64, 0.24), rough=0.30, metal=1.0, tex='c_gold', nrm_strength=0.5)
STL = mat('b_steel', (0.60, 0.63, 0.68), rough=0.35, metal=1.0, tex='c_steel')
DRK = mat('b_darksteel', (0.150, 0.160, 0.185), rough=0.45, metal=1.0, tex='c_steel')
MIRROR = mat('b_mirror', (0.78, 0.80, 0.84), rough=0.14, metal=1.0)
CLOTH = mat('b_cloth', (0.070, 0.060, 0.062), rough=0.9, tex='c_cloth')
CAPE = mat('b_cape', (0.330, 0.030, 0.028), rough=0.92, tex='c_twill')
CAPE2 = mat('b_cape_lining', (0.110, 0.022, 0.024), rough=0.92, tex='c_twill')
LEA = mat('b_leather', (0.090, 0.055, 0.040), rough=0.6, tex='c_leather')
CORD = mat('b_cord', (0.640, 0.060, 0.035), rough=0.85, tex='c_twill')
PLUME = mat('b_plume', (0.660, 0.045, 0.030), rough=0.6, tex='c_hair')
MASK = mat('b_mask', (0.430, 0.250, 0.100), rough=0.42, metal=1.0, tex='c_gold')
MASKD = mat('b_mask_dark', (0.060, 0.035, 0.028), rough=0.5, metal=0.6, tex='c_steel')
IVORY = mat('b_ivory', (0.86, 0.80, 0.66), rough=0.4)
VOID = mat('b_void', (0.010, 0.008, 0.008), rough=0.95)
EYE = mat('b_eye', (1.0, 0.55, 0.12), rough=0.3, emit=(1.0, 0.50, 0.08), emit_strength=5.0)
WOOD = mat('b_wood', (0.085, 0.040, 0.030), rough=0.42, tex='c_wood')
BLADE = mat('b_blade', (0.74, 0.77, 0.82), rough=0.20, metal=1.0, tex='c_steel', nrm_strength=0.4)
EDGE = mat('b_blade_edge', (0.93, 0.94, 0.97), rough=0.10, metal=1.0, emit=(1.0, 0.24, 0.04), emit_strength=0.0)

EDGE['glow'] = [1.0, 0.24, 0.04]        # exported as material extras: the colour the game should light the edge with
EYE['glow'] = [1.0, 0.50, 0.08]

# ------------------------------------------------------------------ skeleton (hero x 1.27, broader)
LIMBS = {'upperarm': (0.305, 0, 1.905), 'forearm': (0.405, 0, 1.555), 'hand': (0.495, 0, 1.225),
         'thigh': (0.135, 0, 1.213), 'shin': (0.140, 0, 0.660), 'foot': (0.145, 0, 0.115)}
CENTRE = [('hips', 'root', (0, 0, 1.27)), ('spine', 'hips', (0, 0, 1.435)), ('chest', 'spine', (0, 0, 1.65)),
          ('neck', 'chest', (0, 0, 2.01)), ('head', 'neck', (0, 0, 2.12))]
RIGKW = dict(ankle_h=0.115, ball=0.20, grip=0.079)


def ell(a, rx, ry, z, oy=0.0):
    a = math.radians(a)
    return (rx * math.cos(a), oy + ry * math.sin(a), z)


def lerp(a, b_, t):
    return a + (b_ - a) * t


# tassets: six armoured panels round the hips (front gap is covered by the tabard)
TS_TOP, TS_BOT = (0.262, 0.202, 1.27), (0.375, 0.325, 0.72)
PANELS = {'tasFL': (291, 349), 'tasSL': (351, 411), 'tasBL': (53, 89), 'tasBR': (91, 127), 'tasSR': (129, 189), 'tasFR': (191, 249)}


def ts_r(z, k=1.0):
    e = (TS_TOP[2] - z) / (TS_TOP[2] - TS_BOT[2])
    return lerp(TS_TOP[0], TS_BOT[0], e) * k, lerp(TS_TOP[1], TS_BOT[1], e) * k


CHAINS = {}
for k, (a0, a1) in PANELS.items():
    am = (a0 + a1) / 2
    CHAINS[k] = Chain(k, 'hips', [ell(am, *ts_r(z), z) for z in (1.25, 0.985, 0.72)])
CHAINS['tabard'] = Chain('tabard', 'hips', [(0, -0.215, 1.23), (0, -0.270, 0.90), (0, -0.305, 0.57)])


# cape: one sheet, five spring chains across it
def cape(U, v):
    x = (U - 0.5) * (0.70 + 0.56 * v)
    edge = (2 * U - 1) ** 2
    y = 0.225 + 0.25 * v - 0.115 * edge * (1 - v) ** 2 + 0.040 * math.sin(U * 4.5 * 2 * math.pi + 0.6) * min(1.0, v * 2.2)
    rag = 0.5 + 0.5 * math.sin(U * 31.0 + 1.3) * math.sin(U * 13.0)
    z = 1.985 - 0.03 * edge - 1.60 * v - 0.16 * rag * v ** 7
    return (x, y, z)


NCAPE = 5
for i in range(NCAPE):
    U = (i + 0.5) / NCAPE
    CHAINS[f'cape{i}'] = Chain(f'cape{i}', 'chest', [cape(U, v) for v in (0.0, 1 / 3, 2 / 3, 1.0)])
CHAINS['plume'] = Chain('plume', 'head', [(0, 0.020, 2.535), (0, 0.105, 2.760), (0, 0.300, 2.865), (0, 0.520, 2.760)])

_T = Rig('tmp', CENTRE, LIMBS, **RIGKW)
HFL, HFR = _T.hand_frame(1), _T.hand_frame(-1)
Ms = HFR @ TRS((0, 0, 0), (0, 90, 0))                  # glaive frame: Z = toward the blade, -X = cutting edge, Y = flats
G_BUTT, G_BASE, G_LEN = -1.10, 0.70, 0.80             # shaft from butt to blade base, blade length
_tb = Ms @ Vector((-0.045, 0, G_BASE + 0.03))
CHAINS['tassel'] = Chain('tassel', 'hand.R', [_tb, _tb + Vector((0, 0, -0.17)), _tb + Vector((0, 0, -0.36))])
SPR = []
for ch in CHAINS.values():
    SPR += ch.bones()
R = Rig('Boss', CENTRE, LIMBS, springs=SPR, **RIGKW)
R.two_off = -0.62
J = R.J
LB = Limbs(R)
PARTS, MARK = {}, {}


def chain_t(ch, co):
    """Fraction along a chain's polyline nearest to a point."""
    best, bt = 1e9, 0.0
    for i in range(ch.n):
        a, c = ch.pts[i], ch.pts[i + 1]
        d = c - a
        t = max(0.0, min(1.0, (co - a).dot(d) / d.length_squared))
        dist = (a + d * t - co).length
        if dist < best:
            best, bt = dist, (i + t) / ch.n
    return bt


def rivets(b, pts, m, w, r=0.011):
    for p in pts:
        b.sphere(r, p, m=m, w=w, segs=6)


TORSO = [(1.10, .215, .165), (1.21, .242, .186), (1.31, .234, .178), (1.42, .228, .172), (1.54, .252, .186),
         (1.65, .292, .206, 0, -.008), (1.78, .328, .224, 0, -.018), (1.88, .322, .212, 0, -.010),
         (1.955, .272, .176), (2.005, .140, .120)]
TORSO_W = ['hips', 'hips', {'hips': .7, 'spine': .3}, 'spine', {'spine': .6, 'chest': .4},
           'chest', 'chest', 'chest', 'chest', 'chest']
cw = lambda co: {'chest': sm((co.z - 1.42) / 0.25), 'spine': 1 - sm((co.z - 1.42) / 0.25)}
WAIST = {'hips': .7, 'spine': .3}

# ================================================================== BODY
b = MB(uv=3.0, w='hips')
b.loft(TORSO, m=CLOTH, w=TORSO_W, segs=20, sq=2.5, uvs=(3, 3))
# cuirass: breast and back in black lacquer, belly lames with gold rims
b.loft(grow(TORSO[4:9], 0.022), m=LAC, w=TORSO_W[4:9], segs=26, sq=2.6, cap=(False, True), uvs=(3, 3))
for i, z in enumerate((1.33, 1.415, 1.50)):
    rx, ry = (.262, .200) if i == 0 else ((.266, .202) if i == 1 else (.276, .208))
    b.loft([(z + 0.062, rx - 0.012, ry - 0.012), (z + 0.01, rx + 0.006, ry + 0.006), (z - 0.03, rx + 0.014, ry + 0.014)], m=LAC,
           w=cw, segs=26, sq=2.5, cap=(False, False), uvs=(3, 3))
    b.loft([(z - 0.026, rx + 0.017, ry + 0.017), (z - 0.040, rx + 0.017, ry + 0.017)], m=GOLD, w=cw, segs=26, sq=2.5, cap=(False, False))
    rivets(b, [ell(a, rx + 0.016, ry + 0.016, z - 0.008) for a in (232, 252, 288, 308)], GOLD, cw, r=0.009)
# gorget
b.loft([(1.945, .215, .165), (1.985, .190, .158), (2.045, .150, .140), (2.075, .138, .132)], m=LAC, w=['chest', 'chest', 'neck', 'neck'],
       segs=20, sq=2.2, cap=(False, False), uvs=(3, 3))
torus(b, 0.138, 0.012, TRS((0, 0, 2.075), (0, 0, 0), (1, 0.95, 1)), GOLD, 'neck', segs=20, tsegs=6)
# mirror plate on the breast, gold rim, rivets, red cords to shoulders and waist
Mm = TRS((0, -0.262, 1.765), (84, 0, 0))
b.lathe([(0, 0.030), (.060, 0.026), (.105, 0.012), (.122, 0.0)], m=MIRROR, w='chest', segs=28, M=Mm)
torus(b, 0.124, 0.013, Mm, GOLD, 'chest', segs=28, tsegs=8)
torus(b, 0.060, 0.006, Mm @ TRS((0, 0, 0.027)), GOLD, 'chest', segs=20, tsegs=6)
b.sphere(0.022, m=GOLD, w='chest', segs=10, M=Mm @ TRS((0, 0, 0.032)))
rivets(b, [Mm @ Vector((0.150 * math.cos(a * math.pi / 4), 0.150 * math.sin(a * math.pi / 4), -0.004)) for a in range(8)], GOLD, 'chest')
for sx in (1, -1):
    b.tube([Mm @ Vector((0.10 * sx, 0.09, 0.0)), (0.215 * sx, -0.235, 1.90), (0.262 * sx, -0.150, 1.965)], 0.011, m=CORD, w='chest', segs=6)
    b.tube([Mm @ Vector((0.09 * sx, -0.095, 0.0)), (0.150 * sx, -0.250, 1.60), (0.165 * sx, -0.232, 1.50)], 0.010, m=CORD, w=cw, segs=6)
    b.sphere(0.022, (0.165 * sx, -0.232, 1.49), m=GOLD, w=cw, segs=8)
# war belt: leather over a red sash, round gold buckle, knotted cord
b.loft([(1.215, .262, .200), (1.235, .274, .212), (1.31, .268, .206), (1.36, .258, .196), (1.375, .246, .186)], m=CORD, w=WAIST,
       segs=26, sq=2.4, uvs=(3, 3))
b.loft([(1.262, .280, .217), (1.300, .278, .215)], m=LEA, w=WAIST, segs=26, sq=2.4, cap=(False, False), uvs=(4, 4))
Mb = TRS((0, -0.222, 1.281), (90, 0, 0))
b.lathe([(0, 0.022), (.035, 0.020), (.060, 0.008), (.066, 0.0)], m=GOLD, w=WAIST, segs=18, M=Mb)
b.sphere(0.020, m=LACR, w=WAIST, segs=10, M=Mb @ TRS((0, 0, 0.022)))
for z in (1.245, 1.318):
    torus(b, 0.240, 0.008, TRS((0, 0, z), (0, 0, 0), (1.165, 0.905, 1)), GOLD, WAIST, segs=26, tsegs=5)
# cloth under-skirt
sw = LB.skirt_w(1.30, 0.50, kmax=0.85, half=0.13)
b.loft([(1.27, .245, .188), (1.10, .285, .235), (0.92, .315, .270), (0.80, .330, .285)], m=CLOTH, w=sw, segs=22, sq=2.3,
       cap=(False, False), uvs=(3, 3))

# tassets: four stepped lames per panel, gold rim and two rivets on each
for k, (a0, a1) in PANELS.items():
    ch = CHAINS[k]
    wz = lambda z, ch=ch: ch.w((TS_TOP[2] - z) / (TS_TOP[2] - TS_BOT[2]))
    for j in range(4):
        zt = 1.275 - j * 0.136
        zb = zt - 0.150
        ri, ro = ts_r(zt, 0.985 + 0.012 * j), ts_r(zb, 1.035)
        rings = [(zt, ri[0], ri[1]), (zt - 0.02, ri[0] + 0.012, ri[1] + 0.012), (zb + 0.012, ro[0] + 0.010, ro[1] + 0.010), (zb, ro[0] + 0.004, ro[1] + 0.004)]
        b.loft(rings, m=LAC if j % 2 == 0 else LACR, w=[wz(r[0]) for r in rings], segs=5, sq=2.3, arc=(a0, a1), cap=(False, False), uvs=(3, 3))
        rim = [(zb + 0.022, ro[0] + 0.015, ro[1] + 0.015), (zb + 0.004, ro[0] + 0.015, ro[1] + 0.015), (zb - 0.004, ro[0] + 0.006, ro[1] + 0.006)]
        b.loft(rim, m=GOLD, w=wz(zb), segs=5, sq=2.3, arc=(a0, a1), cap=(False, False))
        for a in (a0 + (a1 - a0) * 0.22, a0 + (a1 - a0) * 0.78):
            rr = ts_r(zb + 0.065, 1.035)
            b.sphere(0.010, ell(a, rr[0] + 0.012, rr[1] + 0.012, zb + 0.065), m=GOLD, w=wz(zb + 0.065), segs=6)
# tabard between the front tassets: vermilion with gold border and a disc
tb = CHAINS['tabard']
strip(b, tb, 0.215, GOLD, (0, -1, -0.12), nu=2, nv=8, taper=0.10)
strip(b, Chain('tabard', 'hips', [p + Vector((0, -0.006, 0.012)) for p in tb.pts]), 0.180, LACR, (0, -1, -0.12), nu=3, nv=10, taper=0.10, notch=0.0)
Mt = TRS(tuple(tb.at(0.36) + Vector((0, -0.016, 0))), (80, 0, 0))
b.lathe([(0, 0.012), (.040, 0.010), (.058, 0.0)], m=GOLD, w=tb.w(0.36), segs=16, M=Mt)
b.tube([tb.at(1.0) + Vector((x, -0.004, 0.0)) for x in (-0.08, 0.08)], 0.012, m=GOLD, w=tb.w(1.0), segs=6)
for x in (-0.06, -0.02, 0.02, 0.06):
    b.tube([tb.at(1.0) + Vector((x, -0.004, 0.0)), tb.at(1.0) + Vector((x * 1.1, -0.004, -0.085))], [0.008, 0.004], m=CORD, w=tb.w(1.0), segs=5)

# ---------------------------------------------------------------- head: war mask, helmet, crest
HC = Vector((0, -0.010, 2.245))
b.sphere(1.0, tuple(HC), scale=(.126, .142, .158), m=MASKD, w='head', segs=20)
b.sphere(1.0, (0, -0.040, 2.215), scale=(.116, .122, .150), m=MASK, w='head', segs=22)                 # face plate
for sx in (1, -1):
    b.box((.118, .060, .042), (.058 * sx, -0.142, 2.283), rot=(-22, 0, -17 * sx), m=MASKD, bevel=0.014, w='head')   # heavy brow
    b.tube([(.012 * sx, -0.172, 2.262), (.060 * sx, -0.176, 2.296), (.118 * sx, -0.140, 2.318), (.150 * sx, -0.085, 2.352)],
           [0.016, 0.018, 0.014, 0.004], m=GOLD, w='head', segs=7)                                       # brow flame
    b.sphere(1.0, m=VOID, w='head', segs=10, M=TRS((.055 * sx, -0.136, 2.246), (0, -14 * sx, 0), (.042, .020, .017)))
    b.sphere(1.0, m=EYE, w='head', segs=10, M=TRS((.055 * sx, -0.146, 2.2455), (0, -14 * sx, 0), (.031, .012, .0085)))
    b.tube([(.024 * sx, -0.170, 2.200), (.070 * sx, -0.158, 2.180), (.108 * sx, -0.118, 2.195), (.126 * sx, -0.060, 2.235)],
           [0.013, 0.015, 0.013, 0.008], m=MASK, w='head', segs=7)                                       # cheek ridge
    b.tube([(.030 * sx, -0.168, 2.150), (.085 * sx, -0.165, 2.128), (.150 * sx, -0.130, 2.150), (.196 * sx, -0.085, 2.215)],
           [0.012, 0.014, 0.010, 0.002], m=GOLD, w='head', segs=7)                                       # whisker blade
    b.cyl(0.0125, 0.058, (.040 * sx, -0.158, 2.118), rot=(180, 0, 0), m=IVORY, w='head', segs=7, r2=0.0008)         # upper fang
    b.cyl(0.0135, 0.074, (.066 * sx, -0.150, 2.118), rot=(-8, 0, 0), m=IVORY, w='head', segs=7, r2=0.0008)          # lower tusk
    for i in range(3):
        b.cyl(0.0075, 0.024, ((.010 + .0115 * i) * sx, -0.166, 2.133), rot=(180, 0, 0), m=IVORY, w='head', segs=5, r2=0.0008)
        b.cyl(0.0070, 0.020, ((.012 + .0125 * i) * sx, -0.160, 2.092), m=IVORY, w='head', segs=5, r2=0.0008)
b.box((.044, .070, .078), (0, -0.168, 2.208), rot=(-24, 0, 0), m=MASK, bevel=0.016, w='head')            # nose
b.box((.060, .030, .022), (0, -0.176, 2.172), rot=(10, 0, 0), m=MASKD, bevel=0.008, w='head')
b.box((.118, .040, .058), (0, -0.142, 2.113), rot=(0, 0, 0), m=VOID, bevel=0.012, w='head')              # open mouth
b.box((.150, .050, .022), (0, -0.150, 2.148), rot=(8, 0, 0), m=MASK, bevel=0.009, w='head')              # upper lip
b.sphere(1.0, (0, -0.118, 2.066), scale=(.086, .070, .040), m=MASK, w='head', segs=14)                 # jaw
b.box((.050, .040, .050), (0, -0.172, 2.058), rot=(18, 0, 0), m=MASKD, bevel=0.014, w='head')            # chin spike
# helmet bowl with gold ribs, brim, peak
HB = [(.170, 2.268), (.176, 2.310), (.166, 2.380), (.136, 2.436), (.090, 2.474), (.040, 2.492), (0, 2.496)]
Mhel = TRS((0, -0.004, 0))
b.lathe(HB, m=LAC, w='head', segs=28, M=Mhel, uvs=(3, 3))
torus(b, 0.174, 0.012, Mhel @ TRS((0, 0, 2.272)), GOLD, 'head', segs=28, tsegs=6)
for i in range(8):
    a = math.radians(22.5 + i * 45)
    b.tube([(r * 1.012 * math.cos(a), -0.004 + r * 1.012 * math.sin(a), z + 0.002) for r, z in HB[:-1]], 0.0075, m=GOLD, w='head', segs=5)
b.lathe([(.042, 2.488), (.050, 2.502), (.034, 2.522), (.026, 2.540), (0, 2.544)], m=GOLD, w='head', segs=14, M=Mhel)
b.loft([(2.300, .170, .172, 0, -.004), (2.290, .200, .215, 0, -.004), (2.272, .222, .250, 0, -.004)], m=LAC, w='head', segs=10,
       arc=(222, 318), cap=(False, False), uvs=(3, 3))                                                 # peak
b.loft([(2.276, .224, .253, 0, -.004), (2.264, .224, .253, 0, -.004)], m=GOLD, w='head', segs=10, arc=(222, 318), cap=(False, False))
# flared neck guard: three lames, lowest follows the neck a little
for j in range(3):
    zt = 2.285 - j * 0.066
    r0, r1 = 0.170 + j * 0.036, 0.226 + j * 0.046
    w = 'head' if j < 2 else {'head': .7, 'neck': .3}
    b.loft([(zt, r0, r0 + 0.006, 0, -.004), (zt - 0.030, r0 + 0.020, r0 + 0.026, 0, -.004), (zt - 0.082, r1, r1 + 0.008, 0, -.004)],
           m=LAC if j != 1 else LACR, w=w, segs=18, arc=(-42, 222), cap=(False, False), uvs=(3, 3))
    b.loft([(zt - 0.070, r1 + 0.002, r1 + 0.010, 0, -.004), (zt - 0.088, r1 + 0.004, r1 + 0.012, 0, -.004)], m=GOLD, w=w, segs=18,
           arc=(-42, 222), cap=(False, False))
# crest: gold sun disc between two swept blades
Mc = TRS((0, -0.178, 2.372), (72, 0, 0))
b.lathe([(0, 0.014), (.042, 0.012), (.062, 0.0)], m=GOLD, w='head', segs=18, M=Mc)
b.sphere(0.020, m=LACR, w='head', segs=10, M=Mc @ TRS((0, 0, 0.014)))
for sx in (1, -1):
    pts = [(.040 * sx, -0.180, 2.360), (.120 * sx, -0.196, 2.440), (.200 * sx, -0.186, 2.560), (.236 * sx, -0.160, 2.690), (.226 * sx, -0.135, 2.790)]
    for off, rr in ((0.0, [0.020, 0.022, 0.018, 0.012, 0.002]),):
        b.tube(pts, rr, m=GOLD, w='head', segs=6)
    b.grid(lambda u, v, sx=sx: (lerp(.050, .232, v ** 0.8) * sx - sx * 0.050 * u * (1 - v), -0.186 + 0.045 * v * v, lerp(2.350, 2.780, v) - 0.035 * u * (1 - v * 0.6)),
           2, 8, m=GOLD, w='head')
# plume
pl = CHAINS['plume']
for i in range(9):
    a = i * 2 * math.pi / 8
    off = Vector((0.030 * math.cos(a), 0.012 * math.sin(a), 0.026 * math.sin(a))) if i < 8 else Vector((0, 0, 0))
    spread = 1.0 + 0.5 * (i % 3)
    pts = [pl.at(t / 10) + off * (0.4 + 2.6 * (t / 10) ** 0.7) * spread * (1 if t < 10 else 1.3) + Vector((0, 0, -0.10 * (i % 3) * (t / 10) ** 3))
           for t in range(11)]
    rs = [0.014 + 0.026 * math.sin(math.pi * min(1, t / 9)) ** 0.8 for t in range(10)] + [0.003]
    b.tube(pts, rs, m=PLUME, w=lambda co: pl.w(chain_t(pl, co), {'head': 1.0}), segs=6)

# ---------------------------------------------------------------- cape (one sheet over five chains) + mantle
def cape_w(U, v):
    c = max(0.0, min(NCAPE - 1.0, U * NCAPE - 0.5))
    i = min(int(c), NCAPE - 2)
    f = c - i
    out = {}
    for ch, k in ((CHAINS[f'cape{i}'], 1 - f), (CHAINS[f'cape{i + 1}'], f)):
        for g, x in ch.w(v, {'chest': 1.0}).items():
            out[g] = out.get(g, 0.0) + x * k
    return out


b.grid(cape, 24, 20, m=CAPE, wfn=cape_w, uvs=(3.0, 4.5))
b.grid(lambda U, v: tuple(Vector(cape(U, v)) + Vector((0, -0.006, 0))), 24, 20, m=CAPE2, wfn=cape_w, uvs=(3.0, 4.5))
b.tube([(-0.345, 0.050, 1.975), (-0.24, 0.190, 2.010), (0, 0.225, 2.020), (0.24, 0.190, 2.010), (0.345, 0.050, 1.975)],
       [0.040, 0.052, 0.056, 0.052, 0.040], m=CAPE, w='chest', segs=8)                                   # rolled mantle
for sx in (1, -1):
    b.tube([(0.345 * sx, 0.050, 1.975), (0.300 * sx, -0.120, 1.985), (0.215 * sx, -0.215, 1.945)], [0.040, 0.034, 0.026], m=CAPE, w='chest', segs=8)
    b.lathe([(0, 0.016), (.034, 0.013), (.046, 0.0)], m=GOLD, w='chest', segs=14, M=TRS((0.205 * sx, -0.232, 1.94), (80, 0, 0)))
b.tube([(0.200, -0.240, 1.925), (0.10, -0.268, 1.895), (0, -0.276, 1.885), (-0.10, -0.268, 1.895), (-0.200, -0.240, 1.925)], 0.009, m=GOLD,
       w='chest', segs=6)

# ---------------------------------------------------------------- arms
for s, sx in SIDES:
    M, L = LB.ARM[s]
    LB.arm(b, s, [(-0.045, .066, .072), (0.02, .108, .114), (0.13, .106, .112), (0.25, .098, .102), (0.33, .092, .096),
                  (0.385, .086, .089), (0.41, .072, .075)], CLOTH, segs=14, uvs=(3, 3))
    for i, z in enumerate((0.17, 0.25, 0.33)):                                                           # upper-arm lames under the pauldron
        rr = 0.113 - 0.007 * i
        b.loft([(z - 0.055, rr - 0.006, rr), (z + 0.03, rr + 0.004, rr + 0.010), (z + 0.045, rr - 0.002, rr + 0.004)], m=LAC,
               w='upperarm.' + s, segs=12, M=M, arc=(-200, 20) if sx > 0 else (160, 380), cap=(False, False), uvs=(3, 3))
        b.loft([(z + 0.034, rr + 0.007, rr + 0.013), (z + 0.048, rr + 0.001, rr + 0.007)], m=GOLD, w='upperarm.' + s, segs=12, M=M,
               arc=(-200, 20) if sx > 0 else (160, 380), cap=(False, False))
    b.sphere(1.0, m=LAC, w={'upperarm.' + s: .5, 'forearm.' + s: .5}, segs=14, M=M @ TRS((0, -0.040, LB.ELBOW + 0.01), (0, 0, 0), (.066, .070, .086)))
    b.sphere(0.022, m=GOLD, w={'upperarm.' + s: .5, 'forearm.' + s: .5}, segs=8, M=M @ TRS((0, -0.104, LB.ELBOW + 0.01)))
    LB.arm(b, s, [(0.395, .070, .074), (0.44, .086, .090), (0.56, .080, .083), (0.655, .066, .069), (0.69, .060, .062)], LAC, segs=16, uvs=(3, 3))
    for z, r in ((0.44, .0885), (0.55, .0835), (0.655, .0690)):
        torus(b, r, 0.0085, M @ TRS((0, 0, z), (0, 0, 0), (1, 1.04, 1)), GOLD, 'forearm.' + s, segs=16, tsegs=6)
    for a in (-35, 0, 35):                                # raised splints along the outside
        ar = math.radians(a + (0 if sx > 0 else 180))
        b.box((.014, .022, .185), m=LACR, bevel=0.004, w='forearm.' + s,
              M=M @ TRS((0.087 * math.cos(ar), 0.090 * math.sin(ar), 0.545), (0, 0, math.degrees(ar)), (1, 1, 1)))
    b.loft([(L - 0.060, .064, .067), (L - 0.012, .080, .084), (L + 0.012, .076, .080)], m=LAC, w='hand.' + s, segs=14, M=M, uvs=(3, 3))
    torus(b, 0.079, 0.007, M @ TRS((0, 0, L + 0.008), (0, 0, 0), (1, 1.05, 1)), GOLD, 'hand.' + s, segs=14, tsegs=5)
    HF = R.hand_frame(sx) @ Matrix.Scale(1.30, 4)
    fist(b, HF, sx, LEA, LAC, w='hand.' + s)
    b.box((0.094, 0.016, 0.070), m=GOLD, bevel=0.005, w='hand.' + s, M=HF @ TRS((0, 0.041, -0.012)))      # knuckle plate
    # pauldron: four overlapping lames, gold rims, rivets, a boss on top
    for i, (c, r, tilt, w) in enumerate((((.300, 0, 1.985), (.170, .205, .082), 16, {'chest': .6, 'upperarm.' + s: .4}),
                                         ((.375, 0, 1.925), (.158, .196, .086), 38, {'chest': .3, 'upperarm.' + s: .7}),
                                         ((.428, 0, 1.840), (.136, .176, .082), 58, 'upperarm.' + s),
                                         ((.452, 0, 1.745), (.112, .152, .076), 72, 'upperarm.' + s))):
        Mp = TRS((c[0] * sx, c[1], c[2]), (0, tilt * sx, 0), r)
        b.sphere(1.0, m=LAC if i % 2 == 0 else LACR, w=w, segs=18, M=Mp)
        b.sphere(1.0, m=GOLD, w=w, segs=18, M=TRS((c[0] * sx, c[1], c[2]), (0, tilt * sx, 0), (r[0] * 1.035, r[1] * 1.035, r[2] * 0.22)))
        rivets(b, [Mp @ Vector((0.55 * math.cos(a), 0.55 * math.sin(a), 0.80)) for a in (0.9, 2.25, 4.0, 5.4)], GOLD, w, r=0.011)
    b.sphere(0.040, (.300 * sx, 0, 2.070), m=GOLD, w={'chest': .6, 'upperarm.' + s: .4}, segs=10)
    b.cyl(0.020, 0.090, (.300 * sx, 0, 2.125), m=GOLD, w={'chest': .6, 'upperarm.' + s: .4}, segs=8, r2=0.002)

# ---------------------------------------------------------------- legs
for s, sx in SIDES:
    LB.leg(b, s, sx, [(1.27, .140, .160, .118), (1.14, .160, .176, .132), (0.99, .156, .170, .135), (0.84, .144, .156, .137),
                      (0.72, .132, .142, .139), (0.64, .116, .124, .140)], CLOTH, segs=16, uvs=(3, 3))
    LB.leg(b, s, sx, [(0.67, .108, .116, .140), (0.60, .104, .112, .140), (0.42, .094, .102, .142), (0.24, .078, .088, .144),
                      (0.14, .074, .088, .145), (0.09, .078, .092, .145)], LEA, segs=14, uvs=(3, 3))
    # greave: front plate with a centre ridge, straps behind
    gr = [(0.640, .114, .124, .140 * sx), (0.60, .112, .122, .140 * sx), (0.42, .102, .112, .142 * sx), (0.24, .086, .098, .144 * sx), (0.155, .086, .100, .145 * sx)]
    b.loft(gr, m=LAC, w=[LB.leg_w(s, r[0]) for r in gr], segs=10, arc=(196, 344), cap=(False, False), uvs=(3, 3))
    b.tube([(.141 * sx, -0.128, 0.63), (.143 * sx, -0.116, 0.42), (.145 * sx, -0.104, 0.17)], 0.011, m=GOLD, w='shin.' + s, segs=5)
    for z in (0.60, 0.40, 0.20):
        rr = lerp(.116, .092, (0.60 - z) / 0.4)
        torus(b, rr, 0.008, TRS((.142 * sx, 0, z), (0, 0, 0), (1, 1.08, 1)), GOLD if z != 0.40 else LEA, 'shin.' + s, segs=14, tsegs=5)
    # knee: cop with gold rim and a side fan
    kw = {'thigh.' + s: .5, 'shin.' + s: .5}
    b.sphere(1.0, (.140 * sx, -0.090, 0.672), scale=(.094, .070, .112), m=LAC, w=kw, segs=14)
    b.sphere(1.0, (.140 * sx, -0.090, 0.672), scale=(.098, .050, .030), m=GOLD, w=kw, segs=14)
    b.sphere(0.022, (.140 * sx, -0.160, 0.672), m=GOLD, w=kw, segs=8)
    b.sphere(1.0, (.238 * sx, -0.020, 0.672), scale=(.022, .080, .090), m=LACR, w=kw, segs=10)
    # armoured boot: leather with lacquer lames over the instep, upturned toe
    Mf, _ = between((.145 * sx, 0.100, 0.066), (.145 * sx, -0.300, 0.066), ref=(0, 0, 1))
    b.loft([(0.0, .046, .046, 0, -.005), (0.04, .066, .064, 0, -.004), (0.13, .070, .068), (0.22, .074, .056, 0, -.012),
            (0.30, .069, .042, 0, -.025), (0.365, .050, .031, 0, -.031), (0.405, .026, .022, 0, -.014), (0.428, .006, .008, 0, .016)],
           m=LEA, w='foot.' + s, segs=14, M=Mf, uvs=(3, 3))
    b.loft([(0.02, .068, .014, 0, -.052), (0.22, .078, .014, 0, -.052), (0.38, .050, .012, 0, -.050)], m=DRK, w='foot.' + s, segs=10, M=Mf)
    for i, z in enumerate((0.15, 0.215, 0.28, 0.345)):
        rx = (.078, .080, .074, .058)[i]
        ry = (.074, .064, .050, .038)[i]
        oy = (-.002, -.010, -.022, -.030)[i]
        b.loft([(z - 0.04, rx, ry, 0, oy), (z + 0.035, rx + 0.004, ry + 0.004, 0, oy - 0.006)], m=LAC if i % 2 == 0 else LACR, w='foot.' + s,
               segs=8, M=Mf, arc=(8, 172), cap=(False, False), uvs=(3, 3))
        b.loft([(z + 0.028, rx + 0.007, ry + 0.007, 0, oy - 0.006), (z + 0.040, rx + 0.005, ry + 0.005, 0, oy - 0.007)], m=GOLD, w='foot.' + s,
               segs=8, M=Mf, arc=(8, 172), cap=(False, False))
PARTS['body'] = b.finish('body')

# ================================================================== GLAIVE (right hand leads, left hand on the shaft)
b = MB(uv=4.0, w='hand.R')
b.cyl(0.0235, G_BASE - G_BUTT, m=WOOD, segs=10, M=Ms @ TRS((0, 0, (G_BASE + G_BUTT) / 2)))
for z in (-1.06, -0.86, -0.42, 0.22, 0.52, 0.66):
    b.loft([(z - 0.022, .0262, .0262), (z - 0.014, .0290, .0290), (z + 0.014, .0290, .0290), (z + 0.022, .0262, .0262)], m=GOLD, segs=10, M=Ms)
for z0 in (-0.74, -0.09):                                # cord grips where the hands sit
    for k in range(12):
        torus(b, 0.0245, 0.0042, Ms @ TRS((0, 0, z0 + k * 0.016), (14 * (1 if k % 2 else -1), 0, 0)), CORD, None, segs=10, tsegs=5)
b.cyl(0.030, 0.050, m=DRK, segs=10, M=Ms @ TRS((0, 0, G_BUTT - 0.020)), bevel=0.006)
b.cyl(0.026, 0.170, m=STL, segs=8, r2=0.002, M=Ms @ TRS((0, 0, G_BUTT - 0.125), (180, 0, 0)))
# socket and cloud guard
b.lathe([(.026, G_BASE - 0.05), (.036, G_BASE - 0.03), (.034, G_BASE + 0.03), (.046, G_BASE + 0.055), (.030, G_BASE + 0.075)], m=GOLD, segs=12, M=Ms)
b.lathe([(0, -0.012), (.070, -0.012), (.082, -0.004), (.082, 0.004), (.070, 0.012), (0, 0.012)], m=DRK, segs=16,
        M=Ms @ TRS((0, 0, G_BASE + 0.050), (0, 0, 0), (1.25, 0.42, 1)))
torus(b, 0.078, 0.007, Ms @ TRS((0, 0, G_BASE + 0.050), (0, 0, 0), (1.25, 0.42, 1)), GOLD, None, segs=16, tsegs=5)
# blade: broad belly on the edge side, tip swept back, hook on the spine
n, B0 = 30, G_BASE + 0.060
pts, fb, fe = [], [], []


def blade_at(t):
    cx = 0.150 * t ** 2.3
    W = (0.046 + 0.046 * sm(t / 0.62)) if t < 0.66 else 0.092 * (1 - ((t - 0.66) / 0.34) ** 1.7)
    W = max(W, 0.0008)
    return cx, W


for i in range(n + 1):
    t = i / n
    z = B0 + G_LEN * t
    cx, W = blade_at(t)
    th = 0.0085 * (1 - 0.45 * t)
    xs, xm, xe = cx + W * 0.55, cx - W * 0.25, cx - W * 1.25
    pts += [(xs, -th, z), (xs, th, z), (xm, th * 0.85, z), (xe, 0, z), (xm, -th * 0.85, z)]
    if i:
        a, c = (i - 1) * 5, i * 5
        fb += [(a, a + 1, c + 1, c), (a + 1, a + 2, c + 2, c + 1), (a + 4, a, c, c + 4)]
        fe += [(a + 2, a + 3, c + 3, c + 2), (a + 3, a + 4, c + 4, c + 3)]
fb.append((4, 3, 2, 1, 0))
b.poly(pts, fb, m=BLADE, M=Ms, smooth=False)
b.poly(pts, fe, m=EDGE, M=Ms, smooth=False)
hz = B0 + G_LEN * 0.30                                   # back hook
cx, W = blade_at(0.30)
hk = [(cx + W * 0.5, -0.006, hz - 0.070), (cx + W * 0.5, 0.006, hz - 0.070), (cx + W * 0.5, -0.006, hz + 0.060), (cx + W * 0.5, 0.006, hz + 0.060),
      (cx + W * 0.5 + 0.130, 0, hz + 0.125)]
b.poly(hk, [(0, 1, 4), (1, 3, 4), (3, 2, 4), (2, 0, 4), (0, 2, 3, 1)], m=BLADE, M=Ms, smooth=False)
for i in range(3):                                       # gold cloud inlay near the base, ring holes along the spine
    t = 0.06 + 0.10 * i
    cx, W = blade_at(t)
    for sy in (1, -1):
        b.sphere(1.0, m=GOLD, segs=8, M=Ms @ TRS((cx + W * 0.10, sy * 0.0075, B0 + G_LEN * t), (0, 0, 0), (0.022 - 0.004 * i, 0.003, 0.030)))
tsl = CHAINS['tassel']
b.tube([tsl.at(t / 8) for t in range(9)], [0.006, 0.006, 0.007, 0.018, 0.026, 0.028, 0.026, 0.020, 0.004], m=PLUME, segs=7,
       w=lambda co: tsl.w(chain_t(tsl, co)))
torus(b, 0.014, 0.006, TRS(tuple(tsl.at(0.36))), GOLD, tsl.w(0.36), segs=8, tsegs=5)
PARTS['glaive'] = b.finish('glaive', smooth=30)
cxt, _ = blade_at(1.0)
MARK['blade.tip'] = R.marker('hand.R', Ms @ Vector((cxt, 0, B0 + G_LEN)))
MARK['blade.base'] = R.marker('hand.R', Ms @ Vector((0, 0, B0 + 0.02)))
MARK['blade.mid'] = R.marker('hand.R', Ms @ Vector((blade_at(0.55)[0], 0, B0 + G_LEN * 0.55)))
MARK['butt'] = R.marker('hand.R', Ms @ Vector((0, 0, G_BUTT - 0.21)))

for k, ch in CHAINS.items():
    ch.markers(R, MARK)
MARK['chest'] = R.marker('chest', (0, -0.08, 1.74))
MARK['head'] = R.marker('head', (0, 0, 2.25))
MARK['eyeL'] = R.marker('head', (0.055, -0.150, 2.2455))
MARK['eyeR'] = R.marker('head', (-0.055, -0.150, 2.2455))
MARK['footL'] = R.marker('foot.L', (0.145, -0.08, 0.0))
MARK['footR'] = R.marker('foot.R', (-0.145, -0.08, 0.0))
MARK['handL'] = R.marker('hand.L', HFL.translation)

rig = R.build(PARTS)
print('TRIS', {k: sum(len(p.vertices) - 2 for p in o.data.polygons) for k, o in PARTS.items()})

CLIPS, HITS, EVENTS, LOOPS = {}, {}, {}, []
if 'noclips' not in sys.argv:
    exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'boss_clips.py')).read())
if not CLIPS:
    _P = dict(fL=(0.145, 0, 0), fR=(-0.145, 0, 0), gL=(0.45, 0.05, 1.15), gR=(-0.45, 0.10, 1.20), wR=(0.0, 0.5, 0.86))
    CLIPS['Idle'] = [(1, _P), (30, _P)]
ONLY = [a[5:] for a in sys.argv if a.startswith('only=')]
if ONLY:
    keep = set(ONLY[0].split(','))
    CLIPS = {k: v for k, v in CLIPS.items() if k in keep}

for o in PARTS.values():
    o.hide_viewport = True
META = R.bake(CLIPS, HITS, loops=LOOPS)
for k, ev in EVENTS.items():
    if k in META:
        META[k]['events'] = {n_: (f - 1) / 60 for n_, f in ev.items()}
for o in PARTS.values():
    o.hide_viewport = False

# reach report: blade tip distance in front of the root at each hit frame
if 'reach' in sys.argv:
    tipo = Vector(MARK['blade.tip']['off'])
    for cname in CLIPS:
        for f in HITS.get(cname, []):
            R.set_clip(cname, f)
            pb = R.PB['hand.R']
            h = Vector(next(b_[2] for b_ in R.BONES if b_[0] == 'hand.R'))
            rest = h + Vector((tipo.x, -tipo.z, tipo.y))
            p = pb.matrix @ R.REST['hand.R'].inverted() @ rest
            print(f'REACH {cname} f{f}: tip l={p.x:.2f} fwd={-p.y:.2f} up={p.z:.2f}')

if 'preview' in sys.argv:
    args = [a for a in sys.argv[sys.argv.index('preview') + 1:] if not a.startswith('only=') and a != 'reach']
    which = args[0] if args else 'look'
    if which == 'look':
        cname = args[1] if len(args) > 1 else list(CLIPS)[0]
        R.set_clip(cname, int(args[2]) if len(args) > 2 else 1)
        preview(os.path.join(PREVIEW, 'boss_front.png'), (-2.3, -5.0, 1.9), (0, 0, 1.40), lens=50, res=(760, 900))
        preview(os.path.join(PREVIEW, 'boss_back.png'), (2.2, 5.0, 2.2), (0, 0, 1.40), lens=50, res=(760, 900))
        preview(os.path.join(PREVIEW, 'boss_close.png'), (-0.75, -1.9, 2.20), (0.0, 0, 2.12), lens=50, res=(760, 900))
        preview(os.path.join(PREVIEW, 'boss_side.png'), (-5.6, 0.0, 1.6), (0, -0.3, 1.40), lens=50, res=(760, 900))
    else:
        side = 'side' in args
        args = [a for a in args if a != 'side']
        for cname in which.split(','):
            n = R.clip_len[cname]
            frames = [int(a) for a in args[1].split(',')] if len(args) > 1 else sorted(set(int(1 + (n - 1) * k / 15) for k in range(16)))
            cam = (-8.5, -1.2, 2.0) if side else (-5.6, -6.2, 2.6)
            R.sheet(cname, frames, PREVIEW, cam, (0, -1.0, 1.35), cols=4, preview=preview, sheet=sheet, res=(420, 400), lens=62)
            os.replace(os.path.join(PREVIEW, f'Boss_{cname}.png'), os.path.join(PREVIEW, f'boss_{cname}{"_side" if side else ""}.png'))
    drop_preview_rig()

if not ONLY:
    R.unmute_all()
    export_glb(os.path.join(OUT, 'boss.glb'), anim=True)
    with open(os.path.join(OUT, 'boss_meta.json'), 'w') as f:
        json.dump({'clips': META, 'markers': MARK, 'springs': [ch.names() for ch in CHAINS.values()]}, f, indent=1)
