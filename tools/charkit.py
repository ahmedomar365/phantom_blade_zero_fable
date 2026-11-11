"""Shared modelling helpers for the two fighters (on top of common.MB and rigkit.Rig)."""
import math
from mathutils import Vector, Matrix
from common import TRS, between
from rigkit import sm, SIDES


def torus(b, Rr, r, M, m, w, segs=22, tsegs=10, squash=1.0):
    prof = [(Rr + r * math.cos(2 * math.pi * i / tsegs), squash * r * math.sin(2 * math.pi * i / tsegs))
            for i in range(tsegs + 1)]
    b.lathe(prof, m=m, w=w, segs=segs, M=M)


def grow(rings, d, dz0=0.0, dz1=0.0):
    out = [(r[0], r[1] + d, r[2] + d) + tuple(r[3:]) for r in rings]
    out[0] = (out[0][0] + dz0,) + out[0][1:]
    out[-1] = (out[-1][0] + dz1,) + out[-1][1:]
    return out


class Chain:
    """A chain of spring bones through `pts` (n+1 points -> n bones), simulated by the game."""

    def __init__(self, name, parent, pts):
        self.name, self.parent = name, parent
        self.pts = [Vector(p) for p in pts]
        self.n = len(pts) - 1

    def bone(self, i):
        return f'{self.name}.{i + 1}'

    def bones(self):
        return [(self.bone(i), self.parent if i == 0 else self.bone(i - 1), tuple(self.pts[i])) for i in range(self.n)]

    def names(self):
        return [self.bone(i) for i in range(self.n)]

    def markers(self, R, MARK):
        for i in range(self.n):
            MARK[self.bone(i)] = R.marker(self.bone(i), self.pts[i + 1])

    def at(self, t):
        s = max(0.0, min(1.0, t)) * self.n
        i = min(int(s), self.n - 1)
        return self.pts[i].lerp(self.pts[i + 1], s - i)

    def w(self, t, top=None):
        """Weights at fraction t along the chain. top: weights of the anchor (default: the parent)."""
        top = top or {self.parent: 1.0}
        s = max(0.0, min(1.0, t)) * self.n
        if s < 0.6:
            k = sm(s / 0.6)
            out = {g: x * (1 - k) for g, x in top.items()}
            out[self.bone(0)] = out.get(self.bone(0), 0.0) + k
            return out
        j = int(round(s))
        if 1 <= j <= self.n - 1 and abs(s - j) < 0.3:
            k = sm((s - j + 0.3) / 0.6)
            return {self.bone(j - 1): 1 - k, self.bone(j): k}
        return {self.bone(min(int(s), self.n - 1)): 1.0}


def strip(b, ch, width, m, normal, nu=3, nv=14, top=None, wave=0.0, taper=0.0, uvs=(3.0, 3.0), t0=0.0, notch=0.0):
    """Cloth ribbon along a chain. width: metres (or fn(v)); normal: the way its face points.
    wave = fold depth, taper = how much narrower the far end is, notch = ragged hem depth."""
    n = Vector(normal).normalized()

    def pt(u, v):
        t = t0 + (1 - t0) * v
        c = ch.at(t)
        d = (ch.at(min(1, t + 0.02)) - ch.at(max(0, t - 0.02))).normalized()
        side = d.cross(n).normalized()
        wd = (width(v) if callable(width) else width) * (1 - taper * v)
        p = c + side * (u - 0.5) * wd + n * (wave * math.sin(u * 6.3 + v * 3.0) * v + 0.010 * (abs(u - 0.5) * 2) ** 2)
        if notch and v > 0.999:
            p = p - d * notch * (0.5 + 0.5 * math.sin(u * 17.0 + c.x * 40))
        return tuple(p)

    b.grid(pt, nu, nv, m=m, wfn=lambda u, v: ch.w(t0 + (1 - t0) * v, top), uvs=uvs)


def fist(b, HF, sx, m, m_back=None, w=None, r=0.0115):
    """Closed fist around a grip that runs along the hand frame's x axis. Thumb side = -sx."""
    xt = -sx
    m_back = m_back or m
    b.box((0.090, 0.034, 0.086), m=m_back, bevel=0.013, w=w, segs=3, M=HF @ TRS((0, 0.022, -0.014)))      # back of hand
    b.box((0.084, 0.046, 0.052), m=m, bevel=0.016, w=w, segs=3, M=HF @ TRS((0, -0.008, -0.034)))         # heel of the palm
    for i, x in enumerate((0.033, 0.011, -0.011, -0.033)):
        k = 1.0 - 0.07 * i
        pts = [(x * xt, 0.030, 0.020), (x * xt, 0.024 * k, 0.046 * k), (x * xt, -0.006, 0.056 * k),
               (x * xt, -0.034 * k, 0.040 * k), (x * xt, -0.040 * k, 0.012), (x * xt, -0.026, -0.006)]
        b.tube([HF @ Vector(p) for p in pts], [r, r, r * 0.96, r * 0.92, r * 0.86, r * 0.75], m=m, w=w, segs=7)
        b.sphere(r * 1.12, m=m_back, w=w, segs=8, M=HF @ TRS((x * xt, 0.030, 0.026)))                    # knuckle
    pts = [(0.036 * xt, -0.004, -0.040), (0.052 * xt, -0.016, -0.008), (0.050 * xt, -0.034, 0.022), (0.030 * xt, -0.046, 0.040)]
    b.tube([HF @ Vector(p) for p in pts], [r * 1.25, r * 1.2, r * 1.05, r * 0.85], m=m, w=w, segs=7)       # thumb


class Limbs:
    """Arm and leg loft helpers bound to a rig's joints (left-side joint table, mirrored)."""

    def __init__(self, R):
        self.R = R
        J = R.J
        self.ARM = {s: between(J('upperarm', sx), J('hand', sx), ref=(0, -1, 0)) for s, sx in SIDES}
        self.ELBOW = (J('forearm', 1) - J('upperarm', 1)).length
        self.zh = J('thigh', 1).z
        self.zk = J('shin', 1).z
        self.za = J('foot', 1).z
        self.sc = (self.zh - self.za) / 0.865

    def arm_w(self, s, z):
        if z < 0.0:
            return {'upperarm.' + s: 1.0}
        k = sm((z - (self.ELBOW - 0.06 * self.sc)) / (0.12 * self.sc))
        return {'upperarm.' + s: 1 - k, 'forearm.' + s: k}

    def arm(self, b, s, rings, m, **kw):
        M, L = self.ARM[s]
        b.loft(rings, m=m, w=[self.arm_w(s, r[0]) for r in rings], M=M, **kw)

    def leg_w(self, s, z):
        sc = self.sc
        if z > self.zh - 0.015 * sc:
            return {'hips': 1.0}
        if z > self.zh - 0.095 * sc:
            k = sm((self.zh - 0.015 * sc - z) / (0.08 * sc))
            return {'hips': 1 - k, 'thigh.' + s: k}
        if z > self.zk - 0.06 * sc:
            k = sm((self.zk + 0.06 * sc - z) / (0.12 * sc))
            return {'thigh.' + s: 1 - k, 'shin.' + s: k}
        if z > self.za - 0.03 * sc:
            k = sm((self.za + 0.04 * sc - z) / (0.07 * sc))
            return {'shin.' + s: 1 - k, 'foot.' + s: k}
        return {'foot.' + s: 1.0}

    def leg(self, b, s, sx, rings, m, **kw):
        rr = [(r[0], r[1], r[2], r[3] * sx, r[4] if len(r) > 4 else 0.0) + tuple(r[5:]) for r in rings]
        b.loft(rr, m=m, w=[self.leg_w(s, r[0]) for r in rings], **kw)

    def skirt_w(self, top, span, kmax=0.9, half=0.10):
        def f(co):
            k = kmax * sm((top - co.z) / span)
            l = max(0.0, min(1.0, 0.5 + co.x / half))
            return {'hips': 1 - k, 'thigh.L': k * l, 'thigh.R': k * (1 - l)}
        return f
