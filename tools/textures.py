"""Environment texture sets + night sky HDR for Vermilion Gate, generated with numpy inside Blender.
Run: blender -b -P tools/textures.py [-- only name,name]"""
import bpy, numpy as np, os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import TEX, OUT

N = 1024
ONLY = sys.argv[sys.argv.index('only') + 1].split(',') if 'only' in sys.argv else None


def want(name):
    return ONLY is None or name in ONLY


def fbm(beta=2.0, seed=0, n=N, lo=0, aniso=(1.0, 1.0)):
    """Tileable spectral noise in 0..1. beta = spectral slope (higher = smoother)."""
    r = np.random.default_rng(seed)
    f = np.fft.fft2(r.standard_normal((n, n)))
    fy = np.fft.fftfreq(n)[:, None] * aniso[1]
    fx = np.fft.fftfreq(n)[None, :] * aniso[0]
    k = np.sqrt(fx * fx + fy * fy)
    k[0, 0] = 1
    amp = 1.0 / np.power(k, beta / 2)
    amp[k < lo / n] = 0
    amp[0, 0] = 0
    x = np.real(np.fft.ifft2(f * amp))
    return (x - x.min()) / (x.max() - x.min())


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def rgb(c, shape=(N, N)):
    return np.ones((*shape, 3)) * np.array(c)[None, None, :]


def normal_map(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-dx, -dy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save(name, arr, jpg=False, data=False, hdr=False, alpha=None, assets=False):
    arr = np.asarray(arr, np.float32)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, -1)
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=alpha is not None, float_buffer=hdr)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = arr if hdr else np.clip(arr, 0, 1)
    if alpha is not None:
        px[..., 3] = np.clip(alpha, 0, 1)
        img.alpha_mode = 'STRAIGHT'
    if data:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(px.ravel())
    ext = '.hdr' if hdr else ('.jpg' if jpg else '.png')
    img.filepath_raw = os.path.join(OUT if (hdr or assets) else TEX, name + ext)
    img.file_format = 'HDR' if hdr else ('JPEG' if jpg else 'PNG')
    if alpha is not None:
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'
    try:
        img.save(quality=90)
    except TypeError:
        img.save()
    bpy.data.images.remove(img)
    print('TEX', name + ext)


def orm(rough, metal=0.0):
    return np.stack([np.ones_like(rough), np.clip(rough, 0.03, 1), np.clip(metal, 0, 1) * np.ones_like(rough)], -1)


def drips(seed):
    return fbm(2.2, seed, aniso=(1.0, 0.04))


YY, XX = np.mgrid[0:N, 0:N]

# ---------------------------------------------------------------- stone flags (tile = 4 m: 8 courses of 0.5 m, 1 m stones)
if want('flag'):
    ROWS, COLS = 8, 4
    rng = np.random.default_rng(101)
    wob = (fbm(1.6, 102) - 0.5) * 9.0                       # chipped, wandering joint lines (pixels)
    ry = (YY + wob) * ROWS / N
    row = np.floor(ry).astype(int) % ROWS
    fy = ry - np.floor(ry)
    offs = rng.uniform(0, 1, ROWS)
    rx = (XX + wob.T) * COLS / N + offs[row]
    col_i = np.floor(rx).astype(int) % COLS
    fx = rx - np.floor(rx)
    sid = row * COLS + col_i
    ex = np.minimum(fx, 1 - fx) * (N / COLS)                # distance to the stone edge in pixels
    ey = np.minimum(fy, 1 - fy) * (N / ROWS)
    edge = np.minimum(ex, ey)
    gap = 1 - ss(2.0, 6.5, edge)
    bevel = 1 - ss(3.0, 16.0, edge)
    sv = rng.uniform(0.74, 1.12, ROWS * COLS)[sid]
    hue = rng.uniform(-1, 1, ROWS * COLS)[sid]
    tx = rng.uniform(-1, 1, ROWS * COLS)[sid]
    ty = rng.uniform(-1, 1, ROWS * COLS)[sid]
    grain = fbm(0.8, 103)
    mid = fbm(2.0, 104)
    big = fbm(3.0, 105)
    pit = ss(0.80, 0.92, fbm(0.5, 106))
    crack = (1 - ss(0.0, 0.007, np.abs(fbm(2.5, 107) - 0.5))) * ss(0.55, 0.7, fbm(3.0, 108))
    moss = ss(0.52, 0.75, fbm(2.6, 109)) * ss(14.0, 3.0, edge)
    v = 0.235 * sv * lerp(0.80, 1.12, mid) * lerp(0.86, 1.08, big) * (1 + 0.16 * (grain - 0.5))
    v = v * (1 - 0.35 * pit) * (1 - 0.55 * crack) * (1 - 0.82 * gap) * (1 - 0.14 * bevel)
    col = np.stack([v * (1.0 + 0.05 * hue), v * 1.0, v * (1.04 - 0.05 * hue)], -1)
    col = lerp(col, np.array([0.035, 0.060, 0.030])[None, None] * lerp(0.6, 1.6, grain)[..., None], (moss * 0.75)[..., None])
    rough = 0.70 + 0.24 * (grain - 0.5) + 0.16 * (mid - 0.5) + 0.2 * gap + 0.2 * moss - 0.10 * big
    hgt = (fx - 0.5) * tx * 0.9 + (fy - 0.5) * ty * 0.9 + grain * 0.35 + mid * 0.5 - pit * 0.9 - crack * 1.6 - gap * 3.2 - bevel * 0.9
    save('flag_col', col, jpg=True)
    save('flag_orm', orm(rough), data=True)
    save('flag_nrm', normal_map(hgt, 4.0), data=True)

# ---------------------------------------------------------------- dressed stone (steps, plinths, lanterns): tintable
if want('stone'):
    grain = fbm(0.7, 111)
    mid = fbm(2.2, 112)
    big = fbm(3.2, 113)
    strata = fbm(2.0, 114, aniso=(0.12, 1.0))
    dr = drips(115)
    pit = ss(0.78, 0.9, fbm(0.4, 116))
    lich = ss(0.60, 0.80, fbm(2.8, 117)) * ss(0.3, 0.7, fbm(1.0, 118))
    v = 0.62 * lerp(0.76, 1.1, mid) * lerp(0.86, 1.06, big) * lerp(0.9, 1.05, strata) * (1 + 0.2 * (grain - 0.5))
    v = v * (1 - 0.3 * pit) * lerp(1.0, 0.66, ss(0.5, 0.9, dr))
    col = np.stack([v * 1.0, v * 1.0, v * 1.03], -1)
    col = lerp(col, rgb((0.20, 0.27, 0.16)) * lerp(0.6, 1.3, grain)[..., None], (lich * 0.6)[..., None])
    save('stone_col', col, jpg=True)
    save('stone_orm', orm(0.58 + 0.25 * (grain - 0.5) + 0.2 * lich - 0.18 * ss(0.5, 0.9, dr)), data=True)
    save('stone_nrm', normal_map(grain * 0.5 + mid * 0.7 - pit * 1.0 + strata * 0.3, 3.5), data=True)

# ---------------------------------------------------------------- aged plaster (tintable)
if want('plaster'):
    st = fbm(3.0, 121)
    mid = fbm(1.8, 122)
    dr = drips(123)
    dr2 = fbm(2.6, 124, aniso=(1.0, 0.10))
    crack = (1 - ss(0.0, 0.004, np.abs(fbm(2.4, 125) - 0.5))) * ss(0.55, 0.72, fbm(3.0, 126))
    damp = ss(0.2, 0.9, 1 - YY / N) * 0.0                    # (kept flat: walls tile vertically)
    patch = ss(0.66, 0.74, fbm(2.2, 127))                     # flaked areas showing darker undercoat
    v = 0.86 * lerp(0.74, 1.04, st) * lerp(0.9, 1.04, mid) * lerp(1.0, 0.62, ss(0.52, 0.9, dr)) * lerp(1.0, 0.84, ss(0.5, 0.8, dr2))
    v = v * (1 - 0.5 * crack) * (1 - 0.30 * patch)
    col = np.stack([v * 1.0, v * 0.985, v * 0.95], -1)
    col = lerp(col, col * np.array([0.80, 0.92, 0.80])[None, None], (ss(0.6, 0.95, dr) * 0.5)[..., None])
    save('plaster_col', col, jpg=True)
    save('plaster_orm', orm(0.74 + 0.16 * (st - 0.5) - 0.22 * ss(0.52, 0.9, dr) + 0.1 * patch), data=True)
    save('plaster_nrm', normal_map(fbm(1.0, 128) * 0.35 - crack * 1.2 - patch * 0.8 + mid * 0.3, 2.5), data=True)

# ---------------------------------------------------------------- lacquered timber (tintable: vermilion, black, green)
if want('lacquer'):
    gr = fbm(1.8, 131, aniso=(0.03, 1.0))
    gr2 = fbm(1.0, 132, aniso=(0.012, 1.0))
    blot = fbm(2.8, 133)
    wear = ss(0.60, 0.80, fbm(2.2, 134)) * ss(0.4, 0.7, fbm(1.0, 135))
    chk = (1 - ss(0.0, 0.006, np.abs(fbm(2.2, 136, aniso=(0.06, 1.0)) - 0.5))) * ss(0.5, 0.7, fbm(2.6, 137))
    v = 0.92 * lerp(0.80, 1.0, gr) * lerp(0.9, 1.0, gr2) * lerp(0.78, 1.05, blot)
    v = v * (1 - 0.45 * wear) * (1 - 0.6 * chk)
    col = np.stack([v, v * (1 - 0.10 * wear), v * (1 - 0.14 * wear)], -1)
    save('lacquer_col', col, jpg=True)
    save('lacquer_orm', orm(0.30 + 0.16 * (blot - 0.5) + 0.42 * wear + 0.1 * (gr - 0.5)), data=True)
    save('lacquer_nrm', normal_map(gr * 0.45 + gr2 * 0.2 - chk * 1.5 - wear * 0.5, 2.2), data=True)

# ---------------------------------------------------------------- dark timber planks (tile = 2 m, 8 planks)
if want('wood'):
    PL = 8
    yy = YY * PL / N
    plank = np.floor(yy).astype(int)
    fy = yy - np.floor(yy)
    gap = 1 - ss(0.0, 0.035, fy) * ss(0.0, 0.035, 1 - fy)
    gr = fbm(1.8, 141, aniso=(0.03, 1.0))
    gr2 = fbm(1.0, 142, aniso=(0.01, 1.0))
    pr = np.random.default_rng(143).uniform(0.72, 1.1, PL)[plank]
    stud = np.zeros((N, N))
    v = pr * lerp(0.66, 1.05, gr) * lerp(0.85, 1.0, gr2) * (1 - 0.8 * gap)
    col = np.stack([0.80 * v, 0.66 * v, 0.50 * v], -1)
    save('wood_col', col, jpg=True)
    save('wood_orm', orm(0.56 + 0.2 * (gr - 0.5)), data=True)
    save('wood_nrm', normal_map(gr * 0.6 - gap * 2.5, 3.0), data=True)

# ---------------------------------------------------------------- glazed roof tile courses (u along the eave, v up the slope; tile = 2 m)
if want('rooftile'):
    CO = 8
    yy = YY * CO / N
    crs = np.floor(yy).astype(int)
    fy = yy - np.floor(yy)
    # each course overlaps the one below: bright lip at the lower edge, shadow under the lip above
    lip = ss(0.0, 0.10, fy) * (1 - ss(0.10, 0.22, fy))
    under = 1 - ss(0.0, 0.05, fy)
    CL = 6
    xx = XX * CL / N + (crs % 2) * 0.0
    tid = crs * CL + np.floor(xx).astype(int) % CL
    rng = np.random.default_rng(151)
    tv = rng.uniform(0.70, 1.15, CO * CL)[tid]
    grain = fbm(1.0, 152)
    blot = fbm(2.6, 153)
    moss = ss(0.58, 0.78, fbm(2.4, 154)) * ss(0.35, 0.65, fbm(1.2, 155))
    v = 0.30 * tv * lerp(0.8, 1.1, blot) * (1 + 0.2 * (grain - 0.5)) * (1 - 0.7 * under) * (1 + 0.25 * lip)
    col = np.stack([v * 0.86, v * 0.97, v * 1.10], -1)
    col = lerp(col, rgb((0.05, 0.085, 0.04)) * lerp(0.7, 1.4, grain)[..., None], (moss * 0.7)[..., None])
    hgt = (1 - fy) * 1.0 - under * 1.2 + grain * 0.12 + moss * 0.2
    save('rooftile_col', col, jpg=True)
    save('rooftile_orm', orm(0.40 + 0.2 * (blot - 0.5) + 0.45 * moss + 0.1 * grain), data=True)
    save('rooftile_nrm', normal_map(hgt, 3.0), data=True)

# ---------------------------------------------------------------- bark
if want('bark'):
    rid = fbm(1.9, 161, aniso=(1.0, 0.07))
    rid2 = fbm(1.2, 162, aniso=(1.0, 0.2))
    fine = fbm(0.8, 163)
    plate = np.abs(rid - 0.5) * 2
    v = 0.20 * lerp(0.45, 1.2, plate) * lerp(0.8, 1.1, rid2) * (1 + 0.25 * (fine - 0.5))
    col = np.stack([v * 1.05, v * 0.93, v * 0.84], -1)
    lich = ss(0.66, 0.8, fbm(2.6, 164))
    col = lerp(col, rgb((0.16, 0.20, 0.15)), (lich * 0.5)[..., None])
    save('bark_col', col, jpg=True)
    save('bark_orm', orm(0.82 + 0.1 * (fine - 0.5)), data=True)
    save('bark_nrm', normal_map(plate * 1.2 + rid2 * 0.5 + fine * 0.3, 4.0), data=True)

# ---------------------------------------------------------------- bronze / iron (tintable metal)
if want('metal'):
    blot = fbm(2.6, 171)
    fine = fbm(0.9, 172)
    pat = ss(0.55, 0.78, fbm(2.2, 173)) * ss(0.3, 0.7, fbm(1.2, 174))
    v = 0.80 * lerp(0.72, 1.0, blot) * (1 + 0.18 * (fine - 0.5))
    col = rgb((1, 1, 1)) * v[..., None]
    col = lerp(col, rgb((0.34, 0.62, 0.52)) * lerp(0.7, 1.2, fine)[..., None], (pat * 0.65)[..., None])
    save('metal_col', col, jpg=True)
    save('metal_orm', orm(0.40 + 0.2 * (blot - 0.5) + 0.35 * pat, 1.0 - 0.7 * pat), data=True)
    save('metal_nrm', normal_map(fine * 0.5 + pat * fbm(0.8, 175) * 1.2, 2.0), data=True)

# ---------------------------------------------------------------- lantern paper (used as colour and emission map)
if want('paper'):
    u = XX / N
    v_ = YY / N
    ribs = 1 - ss(0.0, 0.035, np.abs(((u * 12) % 1) - 0.5) * 2 - 0.0) * 1.0
    ribs = ss(0.90, 1.0, np.abs(((u * 12) % 1) - 0.5) * 2)                    # thin dark bamboo ribs
    hoop = ss(0.88, 1.0, np.abs(((v_ * 6) % 1) - 0.5) * 2)
    fibre = fbm(1.4, 181, aniso=(0.2, 1.0))
    blot = fbm(2.8, 182)
    core = np.exp(-((v_ - 0.42) / 0.30) ** 2)                                # hotter around the flame height
    lum = lerp(0.42, 1.0, core) * lerp(0.82, 1.0, fibre) * lerp(0.85, 1.0, blot) * (1 - 0.6 * ribs) * (1 - 0.45 * hoop)
    col = np.stack([lum * 1.0, lum * lerp(0.50, 0.74, core), lum * lerp(0.16, 0.36, core)], -1)
    save('paper_col', col, jpg=True)
    save('paper_orm', orm(0.75 + 0.1 * (fibre - 0.5)), data=True)
    # red festival lantern variant
    col = np.stack([lum * 1.0, lum * lerp(0.10, 0.30, core), lum * lerp(0.03, 0.10, core)], -1)
    gold = ss(0.80, 0.86, np.abs(v_ - 0.5) * 2) * (1 - ss(0.93, 0.97, np.abs(v_ - 0.5) * 2))
    col = lerp(col, rgb((1.0, 0.72, 0.25)) * 0.8, gold[..., None])
    save('paperred_col', col, jpg=True)
    save('paperred_orm', orm(0.75 + 0.1 * (fibre - 0.5)), data=True)

# ---------------------------------------------------------------- lattice window (paper behind a timber grid; colour + emission)
if want('lattice'):
    u = (XX / N * 8) % 1
    v_ = (YY / N * 8) % 1
    bar = np.maximum(ss(0.80, 0.86, np.abs(u - 0.5) * 2), ss(0.80, 0.86, np.abs(v_ - 0.5) * 2))
    # diamond inset in every other cell
    cu, cv = np.floor(XX / N * 8), np.floor(YY / N * 8)
    dia = ss(0.50, 0.56, np.abs(u - 0.5) + np.abs(v_ - 0.5)) * (1 - ss(0.62, 0.68, np.abs(u - 0.5) + np.abs(v_ - 0.5)))
    bar = np.maximum(bar, dia * (((cu + cv) % 2) == 0))
    fibre = fbm(1.6, 191)
    glow = lerp(0.55, 1.0, fbm(3.2, 192)) * lerp(0.85, 1.0, fibre)
    col = np.stack([glow * 1.0, glow * 0.62, glow * 0.26], -1) * (1 - bar[..., None]) + rgb((0.03, 0.012, 0.008)) * bar[..., None]
    save('lattice_col', col, jpg=True)
    save('lattice_orm', orm(lerp(0.8, 0.45, bar)), data=True)
    save('lattice_nrm', normal_map(bar * 1.0, 3.0), data=True)

# ---------------------------------------------------------------- carved medallion for the centre of the court (not tiling)
if want('medallion'):
    cx = (XX - N / 2 + 0.5) / (N / 2)
    cy = (YY - N / 2 + 0.5) / (N / 2)
    r = np.sqrt(cx * cx + cy * cy)
    th = np.arctan2(cy, cx)
    groove = np.zeros((N, N))
    for rr, wdt in ((0.955, 0.012), (0.90, 0.008), (0.66, 0.010), (0.62, 0.006), (0.30, 0.010), (0.12, 0.008)):
        groove = np.maximum(groove, 1 - ss(wdt * 0.5, wdt, np.abs(r - rr)))
    # sixteen lotus petals between the rings
    pa = np.abs(((th / (2 * np.pi) * 16) % 1) - 0.5) * 2                     # 0 at a petal axis, 1 between petals
    pr = (r - 0.66) / 0.24
    petal_edge = np.abs(pa - np.sqrt(np.clip(1 - pr, 0, 1)) * 0.92)
    petal = (1 - ss(0.02, 0.06, petal_edge)) * (pr > 0) * (pr < 1)
    groove = np.maximum(groove, petal)
    # eight-fold key fret between r = 0.30 and 0.62: radial spokes and a broken ring
    sp = np.abs(((th / (2 * np.pi) * 8 + 0.5) % 1) - 0.5) * 2
    spoke = (1 - ss(0.03, 0.06, sp * r * 3.0)) * (r > 0.30) * (r < 0.62)
    arcm = (1 - ss(0.004, 0.009, np.abs(r - 0.46))) * (np.abs(((th / (2 * np.pi) * 8) % 1) - 0.5) < 0.34)
    groove = np.maximum(groove, np.maximum(spoke, arcm))
    # inner whorl: three commas
    sw = np.sin(3 * th + r * 34.0)
    whorl = (1 - ss(0.0, 0.14, np.abs(sw))) * (r < 0.115)
    groove = np.maximum(groove, whorl)
    grain = fbm(0.8, 201)
    mid = fbm(2.2, 202)
    moss = ss(0.5, 0.8, fbm(2.4, 203)) * groove
    v = 0.30 * lerp(0.82, 1.1, mid) * (1 + 0.16 * (grain - 0.5)) * (1 - 0.72 * groove)
    col = np.stack([v * 1.03, v, v * 0.99], -1)
    col = lerp(col, rgb((0.04, 0.07, 0.035)), (moss * 0.6)[..., None])
    save('medallion_col', col, jpg=True)
    save('medallion_orm', orm(0.66 + 0.22 * (grain - 0.5) + 0.25 * groove), data=True)
    save('medallion_nrm', normal_map(grain * 0.3 + mid * 0.4 - groove * 3.0, 4.0), data=True)


# ---------------------------------------------------------------- maple leaves
def leaf_mask(n, rot=0.0):
    """Five-lobed leaf in an n x n window: returns (alpha, vein) arrays."""
    y, x = np.mgrid[0:n, 0:n]
    px = (x - n / 2 + 0.5) / (n / 2)
    py = (y - n * 0.42 + 0.5) / (n / 2)
    c, s = np.cos(rot), np.sin(rot)
    qx, qy = px * c + py * s, -px * s + py * c
    r = np.sqrt(qx * qx + qy * qy)
    th = np.arctan2(qy, qx)
    shape = np.zeros((n, n))
    vein = np.zeros((n, n))
    for ang, L in ((90, 0.96), (38, 0.84), (142, 0.84), (-16, 0.56), (196, 0.56)):
        d = np.angle(np.exp(1j * (th - np.radians(ang))))
        lobe = L * np.clip(np.cos(d * 1.45), 0, 1) ** 2.6 * (np.abs(d) < 1.08)
        lobe = lobe * (1 - 0.10 * np.abs(np.sin(d * 16)))                    # serrated edge
        shape = np.maximum(shape, lobe)
        vein = np.maximum(vein, (1 - ss(0.0, 0.035, np.abs(d))) * (r < L * 0.9))
    a = ss(-0.03, 0.03, shape - r)
    stem = (np.abs(qx) < 0.022) * (qy < 0) * (qy > -0.62)
    return np.maximum(a, stem.astype(float)), vein * a


if want('leaf'):
    # single leaves, 2 x 2 atlas (for falling / floating leaves) -> game/assets/leaf.png
    C = 256
    col = np.zeros((2 * C, 2 * C, 3))
    alp = np.zeros((2 * C, 2 * C))
    tones = [(0.62, 0.035, 0.02), (0.80, 0.11, 0.02), (0.90, 0.26, 0.03), (0.46, 0.02, 0.03)]
    for i, tone in enumerate(tones):
        a, vn = leaf_mask(C)
        blot = fbm(2.4, 210 + i, n=C)
        c3 = np.array(tone)[None, None] * lerp(0.7, 1.15, blot)[..., None]
        c3 = lerp(c3, c3 * 0.45 + np.array([0.10, 0.04, 0.0])[None, None], (vn * 0.8)[..., None])
        oy, ox = (i // 2) * C, (i % 2) * C
        col[oy:oy + C, ox:ox + C] = c3
        alp[oy:oy + C, ox:ox + C] = a
    save('leaf', col, alpha=alp, assets=True)

    # foliage sprays for the canopy, 2 x 2 atlas -> build/tex/foliage_col.png
    C = 512
    col = np.zeros((2 * C, 2 * C, 3))
    alp = np.zeros((2 * C, 2 * C))
    rng = np.random.default_rng(220)
    for cell in range(4):
        oy, ox = (cell // 2) * C, (cell % 2) * C
        # a twig runs from the bottom centre and forks; leaves hang along it
        pts = []
        for br in range(5):
            ang = np.radians(rng.uniform(40, 140))
            ln = rng.uniform(0.45, 0.85) * C
            x0, y0 = C * 0.5 + rng.uniform(-0.06, 0.06) * C, C * 0.06
            for t in np.linspace(0.15, 1.0, 9):
                bend = (t * t) * rng.uniform(-0.15, 0.15) * C
                pts.append((x0 + np.cos(ang) * ln * t + bend, y0 + np.sin(ang) * ln * t))
            tt = np.linspace(0, 1, 200)
            xs = np.clip((x0 + np.cos(ang) * ln * tt).astype(int), 0, C - 1)
            ys = np.clip((y0 + np.sin(ang) * ln * tt).astype(int), 0, C - 1)
            for dx in (-1, 0, 1):
                col[oy + ys, np.clip(ox + xs + dx, ox, ox + C - 1)] = (0.10, 0.05, 0.035)
                alp[oy + ys, np.clip(ox + xs + dx, ox, ox + C - 1)] = 1
        rng.shuffle(pts)
        for (px, py) in pts:
            n = int(rng.uniform(86, 140))
            a, vn = leaf_mask(n, rot=rng.uniform(-1.3, 1.3) + np.pi)
            tone = np.array(tones[int(rng.integers(0, 4))]) * rng.uniform(0.6, 1.25)
            shade = rng.uniform(0.55, 1.0)
            x0 = int(np.clip(px - n / 2 + rng.uniform(-14, 14), 2, C - n - 2))
            y0 = int(np.clip(py - n / 2 + rng.uniform(-14, 14), 2, C - n - 2))
            c3 = tone[None, None] * shade * (1 - 0.5 * vn)[..., None]
            reg = (slice(oy + y0, oy + y0 + n), slice(ox + x0, ox + x0 + n))
            col[reg] = lerp(col[reg], c3, a[..., None])
            alp[reg] = np.maximum(alp[reg], a)
    save('foliage_col', col, alpha=alp)
    r_ = np.ones((2 * C, 2 * C)) * 0.55
    save('foliage_orm', orm(r_), data=True)

    # pine / bamboo needles, one tiling strip with alpha -> build/tex/needle_col.png
    C = 512
    col = np.zeros((C, C, 3))
    alp = np.zeros((C, C))
    rng = np.random.default_rng(230)
    for k in range(900):
        x0, y0 = rng.uniform(0, C), rng.uniform(0.25 * C, C)
        ang = np.radians(rng.uniform(-80, 80) - 90)
        ln = rng.uniform(40, 120)
        tt = np.linspace(0, 1, 90)
        xs = (x0 + np.cos(ang) * ln * tt).astype(int) % C
        ys = np.clip((y0 + np.sin(ang) * ln * tt).astype(int), 0, C - 1)
        g = rng.uniform(0.5, 1.2)
        for dx in (0, 1):
            col[ys, (xs + dx) % C] = (0.035 * g, 0.075 * g, 0.045 * g)
            alp[ys, (xs + dx) % C] = 1
    save('needle_col', col, alpha=alp)
    save('needle_orm', orm(np.ones((C, C)) * 0.7), data=True)

# ---------------------------------------------------------------- banner: red cloth, gold gate emblem (512 x 1024, not tiling)
if want('banner'):
    W, H = 512, 1024
    y, x = np.mgrid[0:H, 0:W]
    u = (x + 0.5) / W
    v_ = (y + 0.5) / H
    weave = 0.5 + 0.25 * np.sin(x * 2.2) * np.sin(y * 2.2)
    fold = fbm(2.6, 241, n=1024, aniso=(1.0, 0.15))[:, :W]
    stain = fbm(2.8, 242, n=1024)[:, :W]
    base = np.array([0.50, 0.035, 0.03])[None, None] * (lerp(0.55, 1.05, fold) * lerp(0.7, 1.05, stain) * lerp(0.9, 1.05, weave))[..., None]
    g = np.zeros((H, W))
    cx_, cy_ = u - 0.5, (v_ - 0.62) * 2.0
    rr = np.sqrt(cx_ ** 2 + cy_ ** 2)
    g = np.maximum(g, (np.abs(rr - 0.34) < 0.022))                           # ring
    # gate glyph: two posts, two lintels with upturned ends
    g = np.maximum(g, (np.abs(np.abs(cx_) - 0.13) < 0.022) * (cy_ > -0.24) * (cy_ < 0.20))
    g = np.maximum(g, (np.abs(cy_ - 0.20 - 0.35 * cx_ ** 2 * 4) < 0.026) * (np.abs(cx_) < 0.25))
    g = np.maximum(g, (np.abs(cy_ - 0.08) < 0.018) * (np.abs(cx_) < 0.17))
    # border and a column of tick marks below the emblem
    g = np.maximum(g, ((np.abs(u - 0.5) > 0.44) * (np.abs(u - 0.5) < 0.465)) | ((np.abs(v_ - 0.5) > 0.47) * (np.abs(v_ - 0.5) < 0.482)))
    for k in range(5):
        g = np.maximum(g, (np.abs(v_ - (0.10 + k * 0.045)) < 0.010) * (np.abs(u - 0.5) < 0.10 - 0.012 * k))
    gold = np.array([0.85, 0.60, 0.20])[None, None] * (lerp(0.6, 1.0, stain) * lerp(0.8, 1.0, weave))[..., None]
    col = lerp(base, gold, g.astype(float)[..., None])
    tatter = ss(0.03, 0.0, v_ - 0.05 * fbm(1.5, 243, n=1024)[:, :W])        # ragged lower hem
    save('banner_col', col, jpg=True)
    save('banner_orm', orm(0.85 - 0.25 * g), data=True)
    save('banner_nrm', normal_map(np.pad(fold * 1.2 + weave * 0.1, ((0, 0), (0, 0))), 2.5), data=True)

# ---------------------------------------------------------------- runtime textures (game/assets)
if want('water'):
    h = fbm(2.4, 61, lo=3) + 0.5 * fbm(1.6, 62, lo=12)
    save('waternormals', normal_map(h, 6.0), jpg=True, data=True, assets=True)
    # R: puddle depth mask, G: mist density, B: fine grain
    nz = np.stack([fbm(3.0, 63, lo=2), fbm(2.6, 64, lo=1), fbm(1.2, 65)], -1)
    save('noise', nz, data=True, assets=True)

# ---------------------------------------------------------------- night sky HDR (equirect, linear radiance)
if want('sky'):
    W, H = 2048, 1024
    u = (np.arange(W)[None, :] + 0.5) / W
    vv = (np.arange(H)[:, None] + 0.5) / H
    phi = (u - 0.5) * 2 * np.pi
    th = (vv - 0.5) * np.pi
    dx = np.cos(th) * np.cos(phi)
    dy = np.sin(th) * np.ones_like(phi)
    dz = np.cos(th) * np.sin(phi)
    el = np.clip(dy, 0, 1)
    zen = np.array([0.006, 0.011, 0.030])
    hor = np.array([0.030, 0.042, 0.075])
    t = np.power(1 - el, 4.0)[..., None]
    sky = zen[None, None] * (1 - t) + hor[None, None] * t
    md = np.array([-0.38, 0.40, -0.83])
    md /= np.linalg.norm(md)
    cosm = dx * md[0] + dy * md[1] + dz * md[2]
    ang = np.arccos(np.clip(cosm, -1, 1))
    R_MOON = 0.040
    disc = ss(R_MOON, R_MOON * 0.93, ang)
    # faint maria on the disc
    mare = fbm(2.6, 75, n=2048)[::2, :]
    halo = np.exp(-ang * 7.0) * 0.55 + np.exp(-ang * 1.9) * 0.10
    mcol = np.array([0.80, 0.88, 1.0])
    # two cloud decks
    cn = fbm(2.7, 71, n=2048, lo=2)[::2, :] * 0.7 + fbm(1.7, 72, n=2048, lo=6)[::2, :] * 0.3
    cl = ss(0.50, 0.74, cn) * ss(0.02, 0.30, el)
    thin = ss(0.40, 0.9, fbm(2.2, 76, n=2048, lo=3)[::2, :]) * 0.35 * ss(0.0, 0.25, el)
    # clouds are lit from behind by the moon: bright rims where they are thin
    rim = ss(0.50, 0.58, cn) * (1 - ss(0.58, 0.74, cn))
    cloud_col = (np.array([0.016, 0.020, 0.032])[None, None]
                 + (halo * 2.2 + np.exp(-ang * 1.2) * 0.10)[..., None] * mcol[None, None]
                 + (rim * np.exp(-ang * 2.0) * 0.9)[..., None] * mcol[None, None])
    stars = (np.random.default_rng(73).random((H, W)) > 0.9988) * np.random.default_rng(74).uniform(0.2, 2.2, (H, W)) ** 2
    stars = stars * ss(0.04, 0.4, el) * (1 - cl) * (1 - thin)
    sky += stars[..., None] * np.array([0.9, 0.95, 1.0])[None, None]
    sky += (halo * (1 - 0.5 * cl))[..., None] * mcol[None, None]
    sky += (thin * (0.02 + np.exp(-ang * 2.5) * 0.5))[..., None] * mcol[None, None]
    sky = sky * (1 - cl[..., None]) + cloud_col * cl[..., None]
    sky += (disc * 26.0 * (1 - 0.25 * ss(0.45, 0.6, mare)) * (1 - 0.7 * cl))[..., None] * mcol[None, None]
    below = (dy < 0)[..., None]
    ground = np.array([0.006, 0.007, 0.010])[None, None] + (np.exp(dy * 10.0) * (dy < 0))[..., None] * hor[None, None] * 0.7
    sky = np.where(below, ground, sky)
    save('sky_night', sky, hdr=True)
    print('MOON_DIR', md.tolist())

print('TEXTURES DONE')
