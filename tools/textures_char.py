"""Tiling PBR texture sets for the two fighters (cloth, leather, steel, lacquer, straw, gold).
Run: blender -b -P tools/textures_char.py   -> build/tex/c_*_col.jpg / _orm.png / _nrm.png"""
import bpy, numpy as np, os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import TEX

N = 512


def fbm(beta=2.0, seed=0, n=N, aniso=(1.0, 1.0)):
    r = np.random.default_rng(seed)
    f = np.fft.fft2(r.standard_normal((n, n)))
    fy = np.fft.fftfreq(n)[:, None] * aniso[1]
    fx = np.fft.fftfreq(n)[None, :] * aniso[0]
    k = np.sqrt(fx * fx + fy * fy)
    k[0, 0] = 1
    amp = 1.0 / np.power(k, beta / 2)
    amp[0, 0] = 0
    x = np.real(np.fft.ifft2(f * amp))
    return (x - x.min()) / (x.max() - x.min())


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def normal_map(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-dx, -dy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save(name, arr, jpg=False, data=False):
    arr = np.asarray(arr, np.float32)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, -1)
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = np.clip(arr, 0, 1)
    if data:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = os.path.join(TEX, name + ('.jpg' if jpg else '.png'))
    img.file_format = 'JPEG' if jpg else 'PNG'
    try:
        img.save(quality=90)
    except TypeError:
        img.save()
    bpy.data.images.remove(img)
    print('TEX', name)


def orm(rough, metal):
    rough = rough * np.ones((N, N))
    return np.stack([np.ones_like(rough), np.clip(rough, 0.03, 1), np.clip(metal, 0, 1) * np.ones_like(rough)], -1)


def emit(name, v, rough, metal, height, nrm):
    """v: brightness map around 1.0 (the material tint supplies the hue)."""
    save(name + '_col', np.clip(v, 0, 1), jpg=True)
    save(name + '_orm', orm(rough, metal), data=True)
    save(name + '_nrm', normal_map(height, nrm), data=True)


yy, xx = np.mgrid[0:N, 0:N] / N

# ---------------------------------------------------------------- cloth: plain weave, slub threads, wear
T = 64
warp = 0.5 + 0.5 * np.cos(2 * np.pi * xx * T)
weft = 0.5 + 0.5 * np.cos(2 * np.pi * yy * T)
check = 0.5 + 0.5 * np.cos(2 * np.pi * xx * T / 2) * np.cos(2 * np.pi * yy * T / 2)
weave = warp * check + weft * (1 - check)
slub = fbm(1.4, 11, aniso=(1.0, 0.05)) * 0.5 + fbm(1.4, 12, aniso=(0.05, 1.0)) * 0.5
wear = fbm(2.6, 13)
h = weave * 0.7 + slub * 0.6 + wear * 0.5
v = 0.80 + 0.16 * (weave - 0.5) + 0.22 * (slub - 0.5) + 0.20 * (wear - 0.5)
emit('c_cloth', v, 0.86 + 0.1 * (wear - 0.5), 0.0, h, 2.2)

# heavy twill for capes and sashes: diagonal ribs
rib = 0.5 + 0.5 * np.cos(2 * np.pi * (xx + yy) * 48)
fuzz = fbm(0.8, 21)
big = fbm(3.0, 22)
h = rib * 0.8 + fuzz * 0.35 + big * 1.2
v = 0.80 + 0.14 * (rib - 0.5) + 0.12 * (fuzz - 0.5) + 0.26 * (big - 0.5)
emit('c_twill', v, 0.9 + 0.08 * (fuzz - 0.5), 0.0, h, 2.4)

# ---------------------------------------------------------------- leather: pores, creases, scuffs
pores = ss(0.55, 0.8, fbm(0.4, 31))
crease = 1 - ss(0.0, 0.035, np.abs(fbm(2.3, 32) - 0.5))
crease2 = 1 - ss(0.0, 0.02, np.abs(fbm(1.8, 33) - 0.5))
scuff = ss(0.55, 0.8, fbm(2.8, 34))
h = -pores * 0.5 - crease * 1.2 - crease2 * 0.6 + fbm(2.0, 35) * 0.8
v = 0.82 - 0.22 * crease - 0.10 * crease2 - 0.06 * pores + 0.22 * scuff
emit('c_leather', v, 0.52 + 0.22 * scuff - 0.1 * crease, 0.0, h, 2.6)

# ---------------------------------------------------------------- steel: brushed, nicks, darkened pits
brush = fbm(1.2, 41, aniso=(0.03, 1.0))
pit = ss(0.62, 0.85, fbm(2.2, 42))
nick = ss(0.86, 0.93, fbm(0.3, 43))
h = brush * 0.5 - pit * 0.9 - nick * 0.8
v = 0.88 + 0.14 * (brush - 0.5) - 0.34 * pit - 0.2 * nick
emit('c_steel', v, 0.30 + 0.20 * (brush - 0.5) + 0.32 * pit, 1.0 - 0.5 * pit, h, 1.6)

# ---------------------------------------------------------------- lacquer: glossy, fine crazing, chipped patches
craze = 1 - ss(0.0, 0.012, np.abs(fbm(1.9, 51) - 0.5))
chip = ss(0.70, 0.78, fbm(2.4, 52)) * ss(0.4, 0.6, fbm(0.6, 53))
dust = fbm(2.8, 54)
h = -craze * 0.5 - chip * 1.4 + dust * 0.4
v = 0.90 + 0.10 * (dust - 0.5) - 0.20 * craze - 0.45 * chip
emit('c_lacquer', v, 0.22 + 0.16 * (dust - 0.3) + 0.5 * chip + 0.15 * craze, 0.25 * chip, h, 1.8)

# ---------------------------------------------------------------- hammered gold / brass
cells = fbm(1.0, 61)
dimple = ss(0.35, 0.65, fbm(0.9, 62))
tarn = ss(0.5, 0.8, fbm(2.6, 63))
h = dimple * 1.0 + cells * 0.3
v = 0.92 + 0.10 * (dimple - 0.5) - 0.38 * tarn
emit('c_gold', v, 0.26 + 0.30 * tarn + 0.1 * (cells - 0.5), 1.0, h, 1.8)

# ---------------------------------------------------------------- woven straw (hat): strong diagonal plait
p1 = 0.5 + 0.5 * np.cos(2 * np.pi * (xx * 20 + yy * 20))
p2 = 0.5 + 0.5 * np.cos(2 * np.pi * (xx * 20 - yy * 20))
sel = (np.floor(xx * 20 + yy * 20) + np.floor(xx * 20 - yy * 20)) % 2
plait = np.where(sel > 0.5, p1, p2)
fib = fbm(1.2, 71, aniso=(1.0, 0.08))
stain = fbm(3.0, 72)
h = plait * 1.2 + fib * 0.4
v = 0.84 + 0.2 * (plait - 0.5) + 0.14 * (fib - 0.5) + 0.26 * (stain - 0.5)
emit('c_straw', v, 0.8, 0.0, h, 3.0)

# ---------------------------------------------------------------- hair / plume / tassel: long strands
strand = fbm(1.0, 81, aniso=(1.0, 0.012))
clump = fbm(2.2, 82, aniso=(1.0, 0.05))
h = strand * 1.0 + clump * 0.8
v = 0.80 + 0.30 * (strand - 0.5) + 0.20 * (clump - 0.5)
emit('c_hair', v, 0.55 + 0.2 * (strand - 0.5), 0.0, h, 3.0)

# ---------------------------------------------------------------- wood (shaft, scabbard): dark grain
grain = fbm(1.6, 91, aniso=(1.0, 0.03))
ring = 0.5 + 0.5 * np.sin(2 * np.pi * (xx * 6 + grain * 2.5))
h = grain * 0.7 + ring * 0.3
v = 0.82 + 0.22 * (grain - 0.5) + 0.12 * (ring - 0.5)
emit('c_wood', v, 0.42 + 0.2 * (grain - 0.5), 0.0, h, 1.4)
