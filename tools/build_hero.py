"""The Wanderer: straw-hatted swordsman in layered robes -> game/assets/hero.glb + hero_meta.json
Run: blender -b -P tools/build_hero.py [-- preview look | preview <Clip>[,<Clip>] [frames]] [-- noclips]"""
import bpy, math, os, sys, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import *
from rigkit import *
from charkit import *

reset()
sc = bpy.context.scene
sc.render.fps = 60

# ------------------------------------------------------------------ materials
SKIN = mat('h_skin', (0.36, 0.25, 0.19), rough=0.6)
EYEW = mat('h_eyewhite', (0.42, 0.40, 0.38), rough=0.4)
IRIS = mat('h_iris', (0.03, 0.025, 0.02), rough=0.2)
VOID = mat('h_void', (0.012, 0.010, 0.010), rough=0.9)
HAIR = mat('h_hair', (0.030, 0.026, 0.026), rough=0.5, tex='c_hair')
MASK = mat('h_mask', (0.040, 0.046, 0.058), rough=0.9, tex='c_cloth')
TUN = mat('h_tunic', (0.115, 0.135, 0.160), rough=0.85, tex='c_cloth')
COAT = mat('h_coat', (0.050, 0.085, 0.150), rough=0.9, tex='c_twill')
COAT2 = mat('h_coat_lining', (0.150, 0.170, 0.200), rough=0.9, tex='c_cloth')
RED = mat('h_red', (0.560, 0.045, 0.030), rough=0.9, tex='c_twill')
WRAP = mat('h_wrap', (0.560, 0.500, 0.400), rough=0.9, tex='c_cloth')
LEA = mat('h_leather', (0.120, 0.070, 0.045), rough=0.6, tex='c_leather')
LEA2 = mat('h_leather2', (0.330, 0.200, 0.105), rough=0.6, tex='c_leather')
BLK = mat('h_black', (0.030, 0.028, 0.030), rough=0.6, tex='c_leather')
STL = mat('h_steel', (0.62, 0.65, 0.70), rough=0.35, metal=1.0, tex='c_steel')
DRK = mat('h_darksteel', (0.170, 0.180, 0.205), rough=0.45, metal=1.0, tex='c_steel')
GOLD = mat('h_gold', (0.95, 0.66, 0.26), rough=0.3, metal=1.0, tex='c_gold')
STRAW = mat('h_straw', (0.640, 0.500, 0.285), rough=0.8, tex='c_straw')
STRAW2 = mat('h_straw_under', (0.300, 0.225, 0.130), rough=0.85, tex='c_straw')
WOOD = mat('h_wood', (0.070, 0.035, 0.028), rough=0.4, tex='c_wood')
GOURD = mat('h_gourd', (0.520, 0.300, 0.110), rough=0.35)
BLADE = mat('h_blade', (0.80, 0.83, 0.87), rough=0.16, metal=1.0)
EDGE = mat('h_blade_edge', (0.92, 0.95, 1.0), rough=0.10, metal=1.0, emit=(0.45, 0.75, 1.0), emit_strength=0.0)

# ------------------------------------------------------------------ skeleton
LIMBS = {'upperarm': (0.215, 0, 1.50), 'forearm': (0.295, 0, 1.225), 'hand': (0.365, 0, 0.965),
         'thigh': (0.10, 0, 0.955), 'shin': (0.105, 0, 0.52), 'foot': (0.11, 0, 0.09)}
CENTRE = [('hips', 'root', (0, 0, 1.00)), ('spine', 'hips', (0, 0, 1.13)), ('chest', 'spine', (0, 0, 1.30)),
          ('neck', 'chest', (0, 0, 1.585)), ('head', 'neck', (0, 0, 1.67))]


def ell(a, rx, ry, z, oy=0.0):
    a = math.radians(a)
    return (rx * math.cos(a), oy + ry * math.sin(a), z)


SK_TOP, SK_MID, SK_BOT = (0.190, 0.146, 1.02), (0.250, 0.205, 0.70), (0.300, 0.262, 0.40)
PANELS = {'coatBL': (22, 88), 'coatBR': (92, 158), 'coatFR': (162, 256), 'coatFL': (284, 378)}
CHAINS = {}
for k, (a0, a1) in PANELS.items():
    am = (a0 + a1) / 2
    CHAINS[k] = Chain(k, 'hips', [ell(am, *SK_TOP), ell(am, *SK_MID), ell(am, *SK_BOT)])
for k, x in (('scarfA', 0.060), ('scarfB', -0.045)):
    CHAINS[k] = Chain(k, 'chest', [(x, 0.150, 1.555), (x * 1.3, 0.200, 1.30), (x * 1.5, 0.215, 1.02), (x * 1.6, 0.225, 0.74)])
CHAINS['sash'] = Chain('sash', 'hips', [(0.165, -0.105, 1.04), (0.185, -0.125, 0.80), (0.190, -0.130, 0.56)])
CHAINS['tassel'] = None
SPR = []
for ch in CHAINS.values():
    if ch:
        SPR += ch.bones()
_T = Rig('tmp', CENTRE, LIMBS)
HFL, HFR = _T.hand_frame(1), _T.hand_frame(-1)
Ms = HFR @ TRS((0, 0, 0), (0, 90, 0))                  # sword frame: Z = blade, -X = cutting edge, Y = flats
CHAINS['tassel'] = Chain('tassel', 'hand.R', [Ms @ Vector((0, 0, -0.165)), Ms @ Vector((0.02, 0, -0.30)), Ms @ Vector((0.03, 0, -0.44))])
SPR += CHAINS['tassel'].bones()
R = Rig('Hero', CENTRE, LIMBS, springs=SPR)
R.two_off = -0.115
J = R.J
LB = Limbs(R)
PARTS, MARK = {}, {}

TORSO = [(0.88, .150, .110), (0.96, .172, .125), (1.04, .165, .118), (1.12, .158, .112), (1.21, .170, .118),
         (1.30, .190, .128, 0, -.005), (1.40, .208, .136, 0, -.012), (1.48, .205, .128, 0, -.006),
         (1.535, .175, .108), (1.575, .095, .080)]
TORSO_W = ['hips', 'hips', {'hips': .7, 'spine': .3}, 'spine', {'spine': .6, 'chest': .4},
           'chest', 'chest', 'chest', 'chest', 'chest']
cw = lambda co: {'chest': sm((co.z - 1.12) / 0.2), 'spine': 1 - sm((co.z - 1.12) / 0.2)}

# ================================================================== BODY
b = MB(uv=4.0, w='hips')
b.loft(TORSO, m=TUN, w=TORSO_W, segs=20, sq=2.5, uvs=(4, 4))
# sleeveless coat over the tunic, open in a V at the chest
b.loft(grow(TORSO[2:9], 0.013), m=COAT, w=TORSO_W[2:9], segs=24, sq=2.5, cap=(False, False), arc=(-64, 244), uvs=(4, 4))
for sx in (1, -1):                                       # crossed collar bands
    pts = [(0.020 * sx, -0.146, 1.10), (0.055 * sx, -0.150, 1.26), (0.095 * sx, -0.136, 1.42), (0.105 * sx, -0.070, 1.535),
           (0.085 * sx, 0.040, 1.572), (0.0, 0.100, 1.575)]
    b.tube(pts, [0.021, 0.022, 0.022, 0.021, 0.020, 0.020], m=COAT2, w=cw, segs=8)
b.box((.085, .012, .165), (0, -0.128, 1.335), rot=(-6, 0, 0), m=TUN, bevel=0.004, w='chest')         # tunic showing in the V
# chest strap + scabbard strap ring
b.loft([(-0.022, .232, .152), (0.022, .232, .152)], m=LEA2, w=cw, segs=24, sq=2.5, cap=(False, False),
       M=TRS((0, -0.004, 1.315), (0, -33, 0)), uvs=(4, 4))
b.cyl(0.026, 0.012, (-0.048, -0.150, 1.30), rot=(82, 0, 0), m=STL, w='chest', segs=14, bevel=0.004)
# wide sash wound twice round the waist, knot on the left hip
b.loft([(0.985, .180, .132), (1.00, .191, .142), (1.06, .189, .139), (1.12, .184, .134), (1.135, .174, .126)], m=RED,
       w={'hips': .7, 'spine': .3}, segs=24, sq=2.4, uvs=(4, 4))
for z in (1.02, 1.065, 1.105):
    torus(b, 0.165, 0.007, TRS((0, 0, z), (0, 0, 0), (1.16, 0.87, 1)), RED, {'hips': .7, 'spine': .3}, segs=24, tsegs=6)
b.sphere(1.0, (0.165, -0.098, 1.055), scale=(.046, .040, .050), m=RED, w='hips', segs=12)
strip(b, CHAINS['sash'], 0.105, RED, (0.55, -0.83, 0), nu=3, nv=10, taper=0.15, wave=0.012, notch=0.02)
# belt gear: pouch (right back), gourd (right hip) on a cord
b.box((.095, .050, .095), (-0.150, 0.110, 0.975), rot=(0, 0, 35), m=LEA2, bevel=0.016, w='hips')
b.box((.100, .054, .030), (-0.150, 0.110, 1.012), rot=(0, 0, 35), m=LEA, bevel=0.010, w='hips')
Mg = TRS((-0.215, -0.030, 0.905), (8, -10, 0))
b.lathe([(0, -0.105), (.040, -0.098), (.058, -0.070), (.056, -0.040), (.036, -0.012), (.028, 0.004), (.040, 0.030),
         (.040, 0.052), (.022, 0.074), (.014, 0.086), (.016, 0.100), (0, 0.102)], m=GOURD, w='hips', segs=16, M=Mg)
torus(b, 0.031, 0.006, Mg @ TRS((0, 0, 0.004)), RED, 'hips', segs=14, tsegs=6)
b.tube([(-0.205, -0.030, 0.99), (-0.200, -0.030, 1.03)], 0.005, m=RED, w='hips', segs=5)
# coat skirts: four panels on spring chains, open at the front
for k, (a0, a1) in PANELS.items():
    ch = CHAINS[k]

    def sk(u, v, a0=a0, a1=a1):
        a = a0 + (a1 - a0) * u
        e = sm(v) * 0.35 + v * 0.65
        rx = SK_TOP[0] + (SK_BOT[0] - SK_TOP[0]) * e
        ry = SK_TOP[1] + (SK_BOT[1] - SK_TOP[1]) * e
        fold = 1 + 0.045 * v * math.sin(a * 0.19 + 1.3)
        z = SK_TOP[2] + 0.03 - (SK_TOP[2] + 0.03 - SK_BOT[2]) * v + 0.018 * v * math.sin(a * 0.11)
        return ell(a, rx * fold, ry * fold, z)

    b.grid(sk, 7, 10, m=COAT, wfn=lambda u, v, ch=ch: ch.w(v), uvs=(2.0, 2.6))
    b.grid(lambda u, v: tuple(Vector(sk(u, 0.86 + 0.14 * v)) * Vector((1.012, 1.012, 1.0))), 7, 1, m=COAT2,
           wfn=lambda u, v, ch=ch: ch.w(0.86 + 0.14 * v))                                                 # hem band

# head: face, eyes, cloth mask, hair
b.sphere(1.0, (0, -0.006, 1.765), scale=(.098, .112, .125), m=SKIN, w='head', segs=24)
b.box((.150, .030, .020), (0, -0.103, 1.802), rot=(-14, 0, 0), m=SKIN, bevel=0.009, w='head')
for sx in (1, -1):
    b.sphere(1.0, (.039 * sx, -0.095, 1.777), scale=(.027, .012, .0150), m=VOID, w='head', segs=12)
    b.sphere(1.0, (.039 * sx, -0.099, 1.776), scale=(.0165, .010, .0060), m=EYEW, w='head', segs=12)
    b.sphere(1.0, (.0395 * sx, -0.1035, 1.7755), scale=(.0096, .0078, .0092), m=IRIS, w='head', segs=10)
    b.box((.050, .020, .012), (.040 * sx, -0.1045, 1.7865), rot=(-10, -13 * sx, 0), m=SKIN, bevel=0.004, w='head')
    b.box((.058, .016, .011), (.041 * sx, -0.104, 1.7975), rot=(-18, 0, 12 * sx), m=HAIR, bevel=0.004, w='head')
    b.sphere(1.0, (.100 * sx, 0.0, 1.765), scale=(.014, .026, .034), m=SKIN, w='head', segs=10)        # ear
b.loft([(1.762, .103, .119, 0, -.006), (1.70, .102, .119, 0, -.006), (1.65, .088, .108, 0, -.006), (1.612, .062, .088, 0, -.006)],
       m=MASK, w='head', segs=14, arc=(196, 344), uvs=(12, 12))
b.box((.030, .034, .062), (0, -0.120, 1.738), rot=(-14, 0, 0), m=MASK, bevel=0.012, w='head')
b.sphere(1.0, (0, 0.014, 1.790), scale=(.106, .112, .118), m=HAIR, w='head', segs=18)
b.sphere(1.0, (0, 0.105, 1.700), scale=(.050, .046, .052), m=HAIR, w='head', segs=12)                 # knot at the nape
torus(b, 0.030, 0.008, TRS((0, 0.090, 1.722), (60, 0, 0)), RED, 'head', segs=12, tsegs=6)
# conical straw hat, tipped forward; dark underside, chin cord
Mh = TRS((0, -0.020, -0.030), (0, 0, 0)) @ Matrix.Translation((0, 0, 1.86)) @ TRS((0, 0, 0), (-14, 0, 0)) @ Matrix.Translation((0, 0, -1.86))
HATP = [(.345, 1.846), (.338, 1.856), (.300, 1.880), (.220, 1.928), (.140, 1.975), (.070, 2.014), (.028, 2.034), (0, 2.040)]
b.lathe(HATP, m=STRAW, w='head', segs=40, M=Mh, uvs=(5, 5))
b.lathe([(.343, 1.845)] + [(r * 0.985, z - 0.012) for r, z in HATP[2:6]] + [(.050, 1.975)], m=STRAW2, w='head', segs=40, M=Mh, uvs=(5, 5))
for i in range(5):                                       # concentric plait ridges
    r, z = HATP[1 + i]
    torus(b, r, 0.0045, Mh @ TRS((0, 0, z + 0.004)), STRAW2 if i == 0 else STRAW, 'head', segs=40, tsegs=5)
b.lathe([(.034, 2.030), (.036, 2.046), (.020, 2.066), (0, 2.070)], m=STRAW2, w='head', segs=12, M=Mh)
for sx in (1, -1):
    b.tube([Mh @ Vector((.106 * sx, 0.0, 1.915)), (.104 * sx, -0.02, 1.80), (.092 * sx, -0.055, 1.69), (.03 * sx, -0.085, 1.625), (0, -0.090, 1.618)],
           0.0042, m=RED, w='head', segs=5)

# scarf: wound round the neck, two long tails down the back
b.loft([(1.525, .160, .126), (1.56, .166, .136), (1.615, .142, .126), (1.655, .116, .116, 0, -.004), (1.685, .096, .100, 0, -.004)],
       m=RED, w=['chest', 'chest', {'chest': .5, 'neck': .5}, 'neck', 'neck'], segs=20, sq=2.2, uvs=(4, 4))
torus(b, 0.118, 0.016, TRS((0, -0.004, 1.60), (8, 0, 0), (1.15, 1.02, 1)), RED, {'chest': .5, 'neck': .5}, segs=20, tsegs=8)
b.sphere(1.0, (0.010, 0.135, 1.575), scale=(.070, .040, .045), m=RED, w='chest', segs=12)
for k in ('scarfA', 'scarfB'):
    strip(b, CHAINS[k], 0.125 if k == 'scarfA' else 0.105, RED, (0, 1, 0.25), nu=3, nv=18, taper=0.25, wave=0.014, notch=0.035)

# arms: tunic sleeves, wrapped forearms with a splinted bracer, gloved fists
for s, sx in SIDES:
    M, L = LB.ARM[s]
    LB.arm(b, s, [(-0.035, .045, .050), (0.015, .074, .078), (0.10, .072, .076), (0.20, .066, .069),
                  (0.26, .064, .066), (0.30, .060, .062), (0.325, .050, .052)], TUN, segs=14, uvs=(4, 4))
    torus(b, 0.062, 0.008, M @ TRS((0, 0, 0.300)), TUN, 'forearm.' + s, segs=14, tsegs=6)                # gathered cuff
    LB.arm(b, s, [(0.315, .046, .049), (0.36, .050, .053), (0.45, .047, .049), (0.525, .040, .042), (0.545, .037, .039)],
           WRAP, segs=14, uvs=(5, 5))
    for i in range(7):                                    # bandage turns
        z = 0.335 + i * 0.030
        rr = 0.0515 - 0.0019 * i
        torus(b, rr, 0.0032, M @ TRS((0, 0, z), (9, 0, 0)), WRAP, 'forearm.' + s, segs=14, tsegs=5)
    for a in (-40, 0, 40):                                # splints on the outside of the forearm
        ar = math.radians(90 + a)
        b.box((.016, .006, .150), m=DRK, bevel=0.002, w='forearm.' + s,
              M=M @ TRS((0.054 * math.cos(ar), 0.056 * math.sin(ar), 0.435), (0, 0, a)))
    for z in (0.375, 0.495):
        b.loft([(z - 0.010, .054, .057), (z + 0.010, .053, .056)], m=LEA, w='forearm.' + s, segs=14, M=M, cap=(False, False),
               arc=(10, 170))
    b.loft([(L - 0.030, .040, .042), (L - 0.004, .042, .045), (L + 0.014, .040, .043)], m=BLK, w='hand.' + s, segs=12, M=M)
    fist(b, R.hand_frame(sx), sx, BLK, LEA, w='hand.' + s)
# left pauldron: three lacquered lames with steel rims; right shoulder: quilted cap
for i, (c, r, tilt, w) in enumerate((((.238, 0, 1.540), (.104, .116, .054), 22, {'chest': .5, 'upperarm.L': .5}),
                                     ((.286, 0, 1.478), (.090, .108, .058), 48, 'upperarm.L'),
                                     ((.312, 0, 1.402), (.074, .094, .054), 68, 'upperarm.L'))):
    b.sphere(1.0, m=DRK, w=w, segs=18, M=TRS(c, (0, tilt, 0), (r[0] * 1.06, r[1] * 1.04, r[2] * 0.62)))
    b.sphere(1.0, m=GOLD, w=w, segs=18, M=TRS(c, (0, tilt, 0), (r[0] * 1.09, r[1] * 1.07, r[2] * 0.16)))
b.sphere(0.020, (.252, 0, 1.597), m=GOLD, w={'chest': .5, 'upperarm.L': .5}, segs=10)
b.sphere(1.0, m=COAT, w={'chest': .4, 'upperarm.R': .6}, segs=18, M=TRS((-.236, 0, 1.512), (0, -30, 0), (.080, .094, .050)))
b.sphere(1.0, m=COAT2, w={'chest': .4, 'upperarm.R': .6}, segs=18, M=TRS((-.236, 0, 1.512), (0, -30, 0), (.083, .097, .016)))
# legs: loose trousers gathered under the knee, wrapped shins, cloth shoes
for s, sx in SIDES:
    LB.leg(b, s, sx, [(1.00, .100, .114, .090), (0.90, .112, .124, .100), (0.78, .110, .121, .102), (0.66, .104, .113, .104),
                      (0.55, .099, .106, .105), (0.48, .094, .099, .106), (0.44, .074, .078, .107), (0.415, .060, .064, .107)],
           TUN, segs=16, uvs=(4, 4))
    LB.leg(b, s, sx, [(0.445, .062, .066, .107), (0.42, .060, .065, .107), (0.30, .054, .060, .108), (0.17, .046, .053, .109),
                      (0.10, .044, .054, .110), (0.07, .046, .056, .110)], WRAP, segs=14, uvs=(5, 5))
    for i in range(10):
        z = 0.405 - i * 0.032
        rr = 0.0625 - 0.0020 * i
        torus(b, rr, 0.0034, TRS((.1075 * sx + 0.0002 * i * sx, 0, z), (10 * (1 if i % 2 else -1), 0, 0)), WRAP,
              LB.leg_w(s, z), segs=14, tsegs=5)
    torus(b, 0.066, 0.008, TRS((.107 * sx, 0, 0.445)), RED, 'shin.' + s, segs=14, tsegs=6)
    Mf, _ = between((.110 * sx, 0.075, 0.050), (.110 * sx, -0.23, 0.050), ref=(0, 0, 1))
    b.loft([(0.0, .034, .034, 0, -.004), (0.03, .049, .047, 0, -.003), (0.10, .052, .050), (0.17, .055, .041, 0, -.009),
            (0.235, .051, .031, 0, -.019), (0.285, .036, .022, 0, -.024), (0.315, .016, .014, 0, -.014), (0.330, .004, .006, 0, .004)],
           m=BLK, w='foot.' + s, segs=14, M=Mf, uvs=(5, 5))
    b.loft([(0.02, .050, .012, 0, -.040), (0.17, .057, .012, 0, -.040), (0.29, .038, .010, 0, -.038)], m=LEA2, w='foot.' + s,
           segs=10, M=Mf)                                                                              # sole
# scabbard on the left hip, canted back
Msc, Lsc = between((0.205, -0.170, 1.055), (0.150, 0.640, 0.800), ref=(0, 0, 1))
b.loft([(0.0, .024, .013), (0.05, .025, .014), (Lsc - 0.08, .021, .012), (Lsc, .012, .008)], m=WOOD, w='hips', segs=10, M=Msc, uvs=(6, 6))
for z in (0.02, 0.20, Lsc - 0.05):
    b.loft([(z - 0.018, .027, .016), (z + 0.018, .027, .016)], m=GOLD if z < 0.1 else DRK, w='hips', segs=10, M=Msc)
b.tube([(0.200, -0.135, 1.06), (0.190, -0.10, 1.09), (0.165, -0.06, 1.10)], 0.006, m=RED, w='hips', segs=5)
PARTS['body'] = b.finish('body')

# ================================================================== SWORD (right hand; left joins for two-handed cuts)
b = MB(uv=6.0, w='hand.R')
BL, B0, n = 0.98, 0.118, 26
pts, fb, fe = [], [], []
for i in range(n + 1):
    t = i / n
    z = B0 + BL * t
    cx = 0.070 * t * t                                    # sabre curve, back toward the spine (+X)
    wd = 0.0250 * (1 - 0.10 * t) if t < 0.88 else 0.0250 * 0.912 * (1 - ((t - 0.88) / 0.12) ** 1.5)
    wd = max(wd, 0.0006)
    th = 0.0052 * (1 - 0.35 * t)
    #          spine L            spine R           bevel R                 edge             bevel L
    pts += [(cx + wd, -th, z), (cx + wd, th, z), (cx - wd * 0.25, th, z), (cx - wd * 1.15, 0, z), (cx - wd * 0.25, -th, z)]
    if i:
        a, c = (i - 1) * 5, i * 5
        fb += [(a, a + 1, c + 1, c), (a + 1, a + 2, c + 2, c + 1), (a + 4, a, c, c + 4)]
        fe += [(a + 2, a + 3, c + 3, c + 2), (a + 3, a + 4, c + 4, c + 3)]
fb.append((4, 3, 2, 1, 0))
b.poly(pts, fb, m=BLADE, M=Ms, smooth=False)
b.poly(pts, fe, m=EDGE, M=Ms, smooth=False)


def sabre_hilt(b, M):
    b.box((0.022, 0.0100, 0.030), m=GOLD, M=M @ TRS((0, 0, B0 + 0.012)), bevel=0.003)                     # collar
    b.lathe([(0, -0.006), (.040, -0.006), (.046, -0.002), (.046, 0.003), (.040, 0.007), (0, 0.007)], m=DRK, segs=20,
            M=M @ TRS((0, 0, B0 - 0.006), (0, 0, 0), (1, 0.82, 1)))                                          # guard
    torus(b, 0.044, 0.004, M @ TRS((0, 0, B0 - 0.005), (0, 0, 0), (1, 0.82, 1)), GOLD, None, segs=20, tsegs=6)
    b.loft([(-0.150, .0135, .0105), (-0.10, .0145, .0115), (0.0, .0150, .0118), (0.105, .0140, .0110)], m=BLK, segs=10, M=M, uvs=(8, 8))
    for k in range(11):
        torus(b, 0.0150, 0.0026, M @ TRS((0, 0, -0.135 + k * 0.023), (22 * (1 if k % 2 else -1), 0, 0), (1, 0.8, 1)), RED, None,
              segs=10, tsegs=5)
    b.lathe([(.0135, -0.150), (.0185, -0.156), (.0185, -0.170), (.010, -0.180), (0, -0.182)], m=GOLD, segs=12, M=M)
    torus(b, 0.014, 0.0035, M @ TRS((0, 0, -0.192), (90, 0, 0)), GOLD, None, segs=12, tsegs=6)


sabre_hilt(b, Ms)
PARTS['sword'] = b.finish('sword', smooth=30)
MARK['blade.tip'] = R.marker('hand.R', Ms @ Vector((0.070, 0, B0 + BL)))
MARK['blade.base'] = R.marker('hand.R', Ms @ Vector((0, 0, B0 + 0.04)))
MARK['blade.mid'] = R.marker('hand.R', Ms @ Vector((0.018, 0, B0 + BL * 0.55)))
b = MB(uv=6.0)
ch = CHAINS['tassel']
b.tube([ch.at(t / 8) for t in range(9)], [0.0035] * 5 + [0.010, 0.013, 0.012, 0.004], m=RED, w=None, segs=6)
ob = b.finish('tassel', smooth=50)
PARTS['tassel'] = ob
# tube weights follow the chain
vg = {n_: ob.vertex_groups.new(name=n_) for n_ in ch.names() + ['hand.R']}
a0, a1 = ch.pts[0], ch.pts[-1]
for v in ob.data.vertices:
    t = max(0.0, min(1.0, (v.co - a0).dot(a1 - a0) / (a1 - a0).length_squared))
    for g, x in ch.w(t).items():
        vg[g].add([v.index], x, 'REPLACE')


# ================================================================== SHEATHED SABRE HILT (shown while the greatsword is out)
b = MB(uv=6.0, w='hips')
sabre_hilt(b, Msc @ TRS((0, 0, -(B0 - 0.004))))
PARTS['sword_hip'] = b.finish('sword_hip', smooth=30)

# ================================================================== GREATSWORD (horse-cutter): right hand, long two-handed hilt
GB0, GBL = 0.150, 1.45


def great_cx(t):
    return 0.050 * t ** 2.2


def greatsword(b, M):
    n = 30
    pts, fb, fe = [], [], []
    for i in range(n + 1):
        t = i / n
        z = GB0 + GBL * t
        cx = great_cx(t)
        wd = 0.034 * (1 + 0.10 * t) if t < 0.80 else 0.034 * 1.08 * (1 - ((t - 0.80) / 0.20) ** 1.8)
        wd = max(wd, 0.0008)
        th = 0.0085 * (1 - 0.40 * t)
        pts += [(cx + wd, -th, z), (cx + wd, th, z), (cx - wd * 0.35, th, z), (cx - wd * 1.10, 0, z), (cx - wd * 0.35, -th, z)]
        if i:
            a, c = (i - 1) * 5, i * 5
            fb += [(a, a + 1, c + 1, c), (a + 1, a + 2, c + 2, c + 1), (a + 4, a, c, c + 4)]
            fe += [(a + 2, a + 3, c + 3, c + 2), (a + 3, a + 4, c + 4, c + 3)]
    fb.append((4, 3, 2, 1, 0))
    b.poly(pts, fb, m=DRK, M=M, smooth=False)
    b.poly(pts, fe, m=EDGE, M=M, smooth=False)
    b.box((0.012, 0.0185, 0.78), m=BLADE, M=M @ TRS((0.014, 0, GB0 + 0.44)), bevel=0.002)                 # polished fuller
    for t in (0.26, 0.40, 0.54):                                                                         # rings on the spine
        torus(b, 0.017, 0.0032, M @ TRS((great_cx(t) + 0.034 * (1 + 0.1 * t) + 0.010, 0, GB0 + GBL * t), (90, 0, 0)), GOLD, None, segs=12, tsegs=5)
    b.box((0.056, 0.0220, 0.052), m=GOLD, M=M @ TRS((0, 0, GB0 + 0.020)), bevel=0.005)                    # collar
    b.lathe([(0, -0.009), (.056, -0.009), (.064, -0.003), (.064, 0.004), (.056, 0.010), (0, 0.010)], m=DRK, segs=22,
            M=M @ TRS((0, 0, GB0 - 0.012), (0, 0, 0), (1, 0.66, 1)))                                         # guard
    torus(b, 0.061, 0.005, M @ TRS((0, 0, GB0 - 0.011), (0, 0, 0), (1, 0.66, 1)), GOLD, None, segs=22, tsegs=6)
    b.loft([(-0.420, .0150, .0125), (-0.30, .0165, .0135), (-0.10, .0172, .0140), (GB0 - 0.02, .0165, .0135)], m=BLK, segs=10, M=M, uvs=(8, 8))
    for k in range(18):
        torus(b, 0.0172, 0.0028, M @ TRS((0, 0, -0.395 + k * 0.030), (20 * (1 if k % 2 else -1), 0, 0), (1, 0.82, 1)), RED, None,
              segs=10, tsegs=5)
    b.lathe([(.0150, -0.420), (.0215, -0.428), (.0215, -0.446), (.012, -0.458), (0, -0.460)], m=GOLD, segs=12, M=M)
    torus(b, 0.027, 0.0055, M @ TRS((0, 0, -0.484), (90, 0, 0)), GOLD, None, segs=16, tsegs=6)             # ring pommel


b = MB(uv=6.0, w='hand.R')
greatsword(b, Ms)
PARTS['great'] = b.finish('great', smooth=30)
MARK['great.tip'] = R.marker('hand.R', Ms @ Vector((great_cx(1.0), 0, GB0 + GBL)))
MARK['great.base'] = R.marker('hand.R', Ms @ Vector((0, 0, GB0 + 0.05)))
MARK['great.mid'] = R.marker('hand.R', Ms @ Vector((great_cx(0.55), 0, GB0 + GBL * 0.55)))

# the same blade slung across the back while the sabre is in hand: hilt over the right shoulder, tip by the left knee
_gp0 = Vector((-0.300, 0.252, 1.560))
Mgb, _ = between(_gp0, _gp0 + Vector((0.574, 0.0, -0.819)), ref=(0, 1, 0))
b = MB(uv=6.0, w='chest')
greatsword(b, Mgb)
for sz in (0.34, 0.92):                                  # carrying loops
    b.box((0.100, 0.040, 0.050), m=LEA2, bevel=0.010, M=Mgb @ TRS((0.006, -0.004, sz)))
    b.box((0.104, 0.044, 0.014), m=DRK, bevel=0.004, M=Mgb @ TRS((0.006, -0.004, sz)))
b.tube([Mgb @ Vector((0, -0.02, 0.34)), (-0.16, 0.150, 1.48), (-0.20, 0.060, 1.56)], 0.008, m=LEA2, segs=6)
b.tube([Mgb @ Vector((0, -0.02, 0.92)), (0.12, 0.150, 1.06), (0.17, 0.060, 1.10)], 0.008, m=LEA2, segs=6)
PARTS['great_back'] = b.finish('great_back', smooth=30)

# ================================================================== SUMMONED HAMMER (right hand, Z = shaft, -X = striking face)
SPIRIT = mat('h_spirit', (0.50, 0.72, 1.0), rough=0.3, metal=0.5, emit=(0.35, 0.65, 1.0), emit_strength=1.0)
HZ = 0.80
b = MB(uv=4.0, w='hand.R')
b.cyl(0.021, 1.30, m=SPIRIT, segs=10, M=Ms @ TRS((0, 0, 0.10)))
for z, r, d in ((-0.55, 0.032, 0.05), (-0.20, 0.027, 0.03), (0.22, 0.027, 0.03), (HZ - 0.135, 0.040, 0.05)):
    b.cyl(r, d, m=SPIRIT, segs=10, bevel=0.006, M=Ms @ TRS((0, 0, z)))
b.box((0.300, 0.200, 0.200), m=SPIRIT, bevel=0.036, segs=1, M=Ms @ TRS((-0.010, 0, HZ)))
b.box((0.050, 0.230, 0.230), m=SPIRIT, bevel=0.018, segs=1, M=Ms @ TRS((-0.170, 0, HZ)))                 # striking face
b.box((0.060, 0.224, 0.224), m=SPIRIT, bevel=0.012, segs=1, M=Ms @ TRS((0.050, 0, HZ)))                  # band
b.cyl(0.062, 0.190, m=SPIRIT, segs=6, r2=0.004, M=Ms @ TRS((0.235, 0, HZ), (0, 90, 0)))                 # back spike
b.cyl(0.030, 0.110, m=SPIRIT, segs=6, r2=0.003, M=Ms @ TRS((0, 0, HZ + 0.150)))                         # top spike
PARTS['hammer'] = b.finish('hammer', smooth=28)
MARK['hammer.head'] = R.marker('hand.R', Ms @ Vector((-0.190, 0, HZ)))

# ================================================================== THROWING BLADE (loose; the game clones it). Point at the origin, facing -Y.
b = MB(uv=4.0)
_dp = [(0, 0, 0), (0.020, 0.135, 0), (0, 0.135, 0.0055), (-0.020, 0.135, 0), (0, 0.135, -0.0055),
       (0.011, 0.215, 0), (0, 0.215, 0.0045), (-0.011, 0.215, 0), (0, 0.215, -0.0045)]
_df = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)] + [(1 + k, 5 + k, 5 + (k + 1) % 4, 1 + (k + 1) % 4) for k in range(4)] + [(5, 6, 7, 8)]
b.poly(_dp, _df, m=SPIRIT, smooth=False)
b.cyl(0.0075, 0.090, m=SPIRIT, segs=6, M=TRS((0, 0.258, 0), (90, 0, 0)))
torus(b, 0.013, 0.0035, TRS((0, 0.316, 0), (0, 90, 0)), SPIRIT, None, segs=10, tsegs=5)
DAGGER = b.finish('dagger', smooth=30)
LOOSE = [DAGGER]

for k, ch in CHAINS.items():
    ch.markers(R, MARK)
MARK['chest'] = R.marker('chest', (0, -0.05, 1.36))
MARK['head'] = R.marker('head', (0, 0, 1.78))
MARK['handL'] = R.marker('hand.L', HFL.translation)
MARK['gourd'] = R.marker('hips', (-0.215, -0.030, 0.90))
MARK['throw'] = R.marker('hand.L', HFL.translation)
MARK['footR'] = R.marker('foot.R', (-0.110, -0.235, 0.045))

rig = R.build(PARTS)
print('TRIS', {k: sum(len(p.vertices) - 2 for p in o.data.polygons) for k, o in PARTS.items()})

CLIPS, HITS, EVENTS, LOOPS = {}, {}, {}, []
if 'noclips' not in sys.argv:
    exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hero_clips.py')).read())
if not CLIPS:
    _P = dict(fL=(0.11, 0, 0), fR=(-0.11, 0, 0), gL=(0.36, 0.05, 0.92), gR=(-0.36, 0.05, 0.92), wR=(0.1, 0.9, 0.4))
    CLIPS['Idle'] = [(1, _P), (30, _P)]

ONLY = next((a[5:].split(',') for a in sys.argv if a.startswith('only=')), None)
if ONLY:
    CLIPS = {k: v for k, v in CLIPS.items() if k in ONLY}
    EVENTS = {k: v for k, v in EVENTS.items() if k in ONLY}
for o in PARTS.values():
    o.hide_viewport = True
META = R.bake(CLIPS, HITS, loops=LOOPS)
for k, ev in EVENTS.items():
    META[k]['events'] = {n_: (f - 1) / 60 for n_, f in ev.items()}
for o in PARTS.values():
    o.hide_viewport = False



def weapon_of(c):
    return 'hammer' if c == 'SA_Hammer' else 'great' if (c[:2] == 'G_' or (c[0] == 'G' and c[1:].isdigit())) else 'sword'


def show(c):
    wpn = weapon_of(c)
    vis = {'body': True, 'sword': wpn == 'sword', 'tassel': wpn == 'sword', 'great': wpn == 'great', 'hammer': wpn == 'hammer',
           'great_back': wpn != 'great', 'sword_hip': wpn == 'great'}
    for k, o in PARTS.items():
        o.hide_render = not vis.get(k, True)
    for o in LOOSE:
        o.hide_render = True


if 'reach' in sys.argv:                                  # where the weapon is at each hit frame, and how low it ever goes
    for cname in CLIPS:
        if cname not in HITS:
            continue
        mk = 'footR' if cname == 'Kick' else {'sword': 'blade.tip', 'great': 'great.tip', 'hammer': 'hammer.head'}[weapon_of(cname)]
        m = MARK[mk]
        off = Vector((m['off'][0], -m['off'][2], m['off'][1]))

        def tip():
            pb = R.PB[m['bone']]
            return pb.matrix @ (R.REST[m['bone']].inverted() @ (R.head_of(m['bone']) + off))
        out = []
        for f in HITS[cname]:
            R.set_clip(cname, f)
            bpy.context.view_layer.update()
            q = tip()
            out.append(f'f{f}: fwd {-q.y:.2f} left {q.x:.2f} up {q.z:.2f}')
        lo = 9.0
        for f in range(1, R.clip_len[cname] + 1):
            R.set_clip(cname, f)
            bpy.context.view_layer.update()
            lo = min(lo, tip().z)
        print('REACH', cname, mk, ' | '.join(out), f'| lowest {lo:.2f}')

if 'preview' in sys.argv:
    args = sys.argv[sys.argv.index('preview') + 1:]
    which = args[0] if args else 'look'
    if which == 'look':
        cname = args[1] if len(args) > 1 else list(CLIPS)[0]
        show(cname)
        R.set_clip(cname, int(args[2]) if len(args) > 2 else 1)
        preview(os.path.join(PREVIEW, 'hero_front.png'), (-1.7, -3.7, 1.5), (0, 0, 1.05), lens=50, res=(700, 880))
        preview(os.path.join(PREVIEW, 'hero_back.png'), (1.6, 3.7, 1.7), (0, 0, 1.05), lens=50, res=(700, 880))
        preview(os.path.join(PREVIEW, 'hero_close.png'), (-0.7, -1.5, 1.75), (0.05, 0, 1.55), lens=50, res=(700, 880))
        preview(os.path.join(PREVIEW, 'hero_side.png'), (-4.0, 0.0, 1.3), (0, 0, 1.05), lens=50, res=(700, 880))
    else:
        for cname in which.split(','):
            show(cname)
            n = R.clip_len[cname]
            frames = [int(a) for a in args[1].split(',')] if len(args) > 1 and args[1][0].isdigit() else sorted(set(int(1 + (n - 1) * k / 11) for k in range(12)))
            side = 'side' in args
            R.sheet(cname, frames, PREVIEW, (-6.2, -0.4, 1.5) if side else (-4.6, -3.9, 1.7), (0, -0.5, 1.25), cols=6 if len(frames) > 12 else 4,
                    preview=preview, sheet=sheet, res=(380, 460))
    drop_preview_rig()

for o in list(PARTS.values()) + LOOSE:
    o.hide_render = False
R.unmute_all()
if ONLY:
    print('only= given: nothing exported')
    sys.exit(0)
export_glb(os.path.join(OUT, 'hero.glb'), anim=True)
with open(os.path.join(OUT, 'hero_meta.json'), 'w') as f:
    json.dump({'clips': META, 'markers': MARK,
               'springs': [ch.names() for ch in CHAINS.values()]}, f, indent=1)
