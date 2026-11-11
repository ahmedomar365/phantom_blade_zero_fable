"""Biped rig + pose solver + clip baker shared by the fighter and the goblin (Blender 5.x).

Characters face -Y, their left is +X. Every bone points straight up with roll 0, so all
bones share the same local axes whatever the limb direction.

Poses are authored as body FK + IK targets in character space (left, forward, up) metres:
  hips=(l,f,u) offset     hr/sp/ch/nk/hd=(pitch, yaw, roll) degrees (+pitch leans forward,
  +yaw turns left, +roll tilts right)
  look=(l,f,u)  point the head tracks (neck takes half); hx = extra head euler on top
  fL/fR=(l,f,u,yaw,pitch) sole under the ankle; heel raise pivots on the ball of the foot
  kL/kR knee direction
  gL/gR fist position   cL/cR direction the knuckles (and talons) point
  nL/nR direction the back of the hand faces   wL/wR direction of a held weapon (replaces n)
  pL/pR elbow direction
  'x:<bone>'=(pitch, yaw, roll) extra FK bones (jaw, ...)   lookw = 0..1 head tracking weight
  spin = degrees the whole body (feet, hands, weapon) is turned about the hips; targets stay in body space
  two = 0..1 left hand joins the right on a two-handed hilt
  draw = 0..1 bowstring pull, nock = 0..1 right hand follows the string's nocking point
  adv = (forward, left) metres the root has travelled since the clip began. The game moves the
        character by it; foot targets (fL/fR) are then given in clip-start space so planted feet
        stay planted while the body travels. Everything else stays in body space.
  tw = where the left hand grips along the weapon axis for this pose (overrides two_off)
"""
import bpy, math
from mathutils import Vector, Matrix, Euler, Quaternion

SIDES = (('L', 1), ('R', -1))


def sm(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def V(p):
    return Vector((p[0], -p[1], p[2]))


def frame(d, ref):
    a1 = d.normalized()
    a2 = ref - a1 * ref.dot(a1)
    if a2.length < 1e-5:
        a2 = a1.orthogonal()
    a2.normalize()
    return Matrix((a1, a2, a1.cross(a2))).transposed()


def qe(e):
    return Euler([math.radians(a) for a in e], 'XYZ').to_quaternion()


def two_bone(S, T, a, b_, pole):
    d = T - S
    c = min(max(d.length, 0.04), (a + b_) * 0.997)
    dn = d.normalized()
    cosA = max(-1.0, min(1.0, (a * a + c * c - b_ * b_) / (2 * a * c)))
    sinA = math.sqrt(max(0.0, 1 - cosA * cosA))
    pp = pole - dn * pole.dot(dn)
    if pp.length < 1e-5:
        pp = dn.orthogonal()
    pp.normalize()
    E = S + dn * (a * cosA) + pp * (a * sinA)
    return E, S + dn * c, pp, d.length / (a + b_)


class Curve:
    """Monotone cubic (PCHIP) through (frame, tuple) keys, per component; flat at both ends."""

    def __init__(self, keys):
        self.xs = [k[0] for k in keys]
        self.n = len(keys[0][1])
        self.ys = [[k[1][i] for k in keys] for i in range(self.n)]
        self.ms = [self._tangents(y) for y in self.ys]

    def _tangents(self, y):
        x, n = self.xs, len(self.xs)
        if n < 2:
            return [0.0] * n
        h = [x[i + 1] - x[i] for i in range(n - 1)]
        d = [(y[i + 1] - y[i]) / h[i] for i in range(n - 1)]
        m = [0.0] * n
        for i in range(1, n - 1):
            if d[i - 1] * d[i] > 0:
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        return m

    def at(self, f):
        x = self.xs
        if f <= x[0]:
            return tuple(y[0] for y in self.ys)
        if f >= x[-1]:
            return tuple(y[-1] for y in self.ys)
        i = max(k for k in range(len(x) - 1) if x[k] <= f)
        h = x[i + 1] - x[i]
        t = (f - x[i]) / h
        t2, t3 = t * t, t * t * t
        out = []
        for y, m in zip(self.ys, self.ms):
            out.append((2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h * m[i]
                       + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h * m[i + 1])
        return tuple(out)


class Rig:
    def __init__(self, name, centre, limbs, extra=(), springs=(), ankle_h=0.09, ball=0.16, grip=0.062,
                 elbow_pole=(0.6, -0.8, -0.5), look_max=70.0, wrist_max=48.0):
        """centre: [(bone, parent, head)], limbs: {'upperarm': (x, y, z), ...} for the left side,
        extra: more (bone, parent, head) FK bones, springs: bones left to the game's springs."""
        self.name = name
        self.JS = limbs
        self.BONES = [('root', None, (0, 0, 0))] + list(centre) + list(extra) + list(springs)
        self.springs = [b[0] for b in springs]
        self.extra = [b[0] for b in extra]
        for s, sx in SIDES:
            P = lambda k: (limbs[k][0] * sx, limbs[k][1], limbs[k][2])
            self.BONES += [
                ('upperarm.' + s, 'chest', P('upperarm')), ('forearm.' + s, 'upperarm.' + s, P('forearm')),
                ('hand.' + s, 'forearm.' + s, P('hand')),
                ('thigh.' + s, 'hips', P('thigh')), ('shin.' + s, 'thigh.' + s, P('shin')),
                ('foot.' + s, 'shin.' + s, P('foot')),
            ]
        self.ankle_h, self.ball, self.grip = ankle_h, ball, grip
        self.elbow_pole = elbow_pole
        self.look_max = math.radians(look_max)
        self.wrist_max = math.radians(wrist_max)
        self.warn = []
        self.ob = None
        self.bow = None                 # dict(brace, length, off=(s, n), flex) when the left hand holds a bow
        self.two_off = -0.15            # where the left hand grips, along the right hand's weapon axis
        self.loc_bones = ['hips']

    def J(self, k, sx):
        return Vector((self.JS[k][0] * sx, self.JS[k][1], self.JS[k][2]))

    def head_of(self, bone):
        return Vector(next(b[2] for b in self.BONES if b[0] == bone))

    def hand_frame(self, sx):
        """Rest frame of a hand: fist centre, knuckle direction d, back-of-hand normal n,
        spread axis s. Returned as a matrix with columns (s, n, d) at the fist centre."""
        d = (self.J('hand', sx) - self.J('forearm', sx)).normalized()
        lat = Vector((sx, 0, 0))
        n = (lat - d * lat.dot(d)).normalized()
        s = n.cross(d)
        M = Matrix((s, n, d)).transposed().to_4x4()
        M.translation = self.J('hand', sx) + d * self.grip
        return M

    # ---------------------------------------------------------------- armature
    def build(self, parts):
        sc = bpy.context.scene
        ad = bpy.data.armatures.new(self.name)
        rig = bpy.data.objects.new(self.name, ad)
        sc.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        for name, parent, head in self.BONES:
            eb = ad.edit_bones.new(name)
            eb.head = head
            eb.tail = (head[0], head[1], head[2] + 0.06)
            eb.roll = 0
        for name, parent, head in self.BONES:
            if parent:
                ad.edit_bones[name].parent = ad.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in parts.values():
            ob.parent = rig
            ob.modifiers.new('Armature', 'ARMATURE').object = rig
        self.ob = rig
        self.PB = rig.pose.bones
        for pb in self.PB:
            pb.rotation_mode = 'QUATERNION'
        self.REST = {b.name: b.matrix_local.copy() for b in ad.bones}
        self.ANIMB = [n for n, _, _ in self.BONES if n != 'root' and n not in self.springs]
        return rig

    def marker(self, bone, pos):
        """Offset of a rest-space point from a bone head, in the glTF joint's local axes."""
        h = self.head_of(bone)
        p = Vector(pos)
        return {'bone': bone, 'off': [round(p.x - h.x, 5), round(p.z - h.z, 5), round(-(p.y - h.y), 5)]}

    # ---------------------------------------------------------------- solver
    def upd(self):
        bpy.context.view_layer.update()

    def set_world_rot(self, name, D):
        pb = self.PB[name]
        self.upd()
        M = D.to_4x4() @ self.REST[name]
        M.translation = pb.head
        pb.matrix = M
        self.upd()

    def world_rot(self, name):
        return self.PB[name].matrix.to_3x3() @ self.REST[name].to_3x3().inverted()

    def apply_rest(self):
        for pb in self.PB:
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
        self.upd()

    def solve_arm(self, s, sx, A, tag):
        """A holds armature-space vectors. g = fist position. Bare hand: c = knuckle direction,
        n = back-of-hand normal. Holding a weapon: w = weapon direction is kept exact and c
        (optional) is only a preference for how the wrist turns around it. The wrist never
        bends past wrist_max."""
        J = self.J
        S0, E0, W0 = J('upperarm', sx), J('forearm', sx), J('hand', sx)
        a, b_ = (E0 - S0).length, (W0 - E0).length
        d0u, d0f = (E0 - S0).normalized(), (W0 - E0).normalized()
        lat0 = Vector((sx, 0, 0))
        n0 = (lat0 - d0f * lat0.dot(d0f)).normalized()
        w = A['w' + s].normalized() if ('w' + s) in A else None
        perp = (lambda v: (v - w * v.dot(w)).normalized()) if w is not None else (lambda v: v.normalized())
        want = perp(A['c' + s]) if ('c' + s) in A else None
        ep = self.elbow_pole
        pole = A['p' + s] if ('p' + s) in A else self.Rs @ Vector((sx * ep[0], -ep[1], ep[2]))
        self.upd()
        S = self.PB['upperarm.' + s].head.copy()
        fist = A['g' + s]
        c = want if want is not None else perp(fist - S)
        for _ in range(5):
            E, Wc, pp, reach = two_bone(S, fist - c * self.grip, a, b_, pole)
            du, df = (E - S).normalized(), (Wc - E).normalized()
            near = perp(df) if (w is None or abs(df.dot(w)) < 0.995) else c      # most relaxed wrist
            if want is None:
                c = near
                continue
            bend = df.angle(want)
            if bend <= self.wrist_max:
                c = want
                break
            c = want
            for k in range(1, 11):               # ease toward the relaxed direction until it fits
                c = perp(want.lerp(near, k / 10))
                if df.angle(c) <= self.wrist_max:
                    break
        if w is not None:
            n = c.cross(w) * (-sx)
        elif ('n' + s) in A:
            n = A['n' + s]
        else:
            n = self.Rs @ Vector((sx * 0.5, 0, 1))
        Dh = frame(c, n) @ frame(d0f, n0).transposed()
        if reach > 1.0:
            self.warn.append((tag, f'arm {s} overreach x', reach))
        if want is not None and math.degrees(df.angle(want)) > 75:
            self.warn.append((tag, f'wrist {s} wanted bend deg', math.degrees(df.angle(want))))
        self.set_world_rot('upperarm.' + s, frame(du, du.cross(pp) * sx) @ frame(d0u, lat0).transposed())
        self.set_world_rot('forearm.' + s, frame(df, Dh @ lat0) @ frame(d0f, lat0).transposed())
        self.set_world_rot('hand.' + s, Dh)

    def solve_leg(self, s, sx, foot, knee, tag):
        J = self.J
        H0, K0, A0 = J('thigh', sx), J('shin', sx), J('foot', sx)
        a, b_ = (K0 - H0).length, (A0 - K0).length
        d0t, d0s = (K0 - H0).normalized(), (A0 - K0).normalized()
        yaw = math.radians(foot[3] if len(foot) > 3 else 0.0) + self.spin
        pitch = math.radians(foot[4] if len(foot) > 4 else 0.0)
        Rz = Matrix.Rotation(yaw, 3, 'Z')
        Dfoot = Rz @ Matrix.Rotation(pitch, 3, 'X')
        A = self.at(foot) + Rz @ Vector((0, -self.ball, 0)) + Dfoot @ Vector((0, self.ball, self.ankle_h))
        self.upd()
        H = self.PB['thigh.' + s].head.copy()
        pole = self.Rs @ V(knee) if knee is not None else Rz @ Vector((sx * 0.20, -1, 0))
        K, A2, pp, reach = two_bone(H, A, a, b_, pole)
        if reach > 1.0:
            self.warn.append((tag, f'leg {s} overreach x', reach))
        fwd0 = Vector((0, -1, 0))
        self.set_world_rot('thigh.' + s, frame(K - H, pp) @ frame(d0t, fwd0).transposed())
        self.set_world_rot('shin.' + s, frame(A2 - K, pp) @ frame(d0s, fwd0).transposed())
        self.set_world_rot('foot.' + s, Dfoot)

    def at(self, v):
        """Character-space point -> armature space, turned by the spin about the hips."""
        return self.piv + self.Rs @ (V(v) - self.piv)

    def solve(self, p, tag=''):
        """Pose spec -> {bone: quaternion, 'loc': {bone: (x, y, z)}} (pure FK, ready to key)."""
        PB = self.PB
        self.apply_rest()
        hl = V(p.get('hips', (0, 0, 0)))
        self.spin = math.radians(p.get('spin', (0.0,))[0])        # whole body turns about the hips
        self.Rs = Matrix.Rotation(self.spin, 3, 'Z')
        self.piv = Vector((hl.x, hl.y, 0))
        adv = p.get('adv', (0.0, 0.0))
        advf, advl = adv[0], (adv[1] if len(adv) > 1 else 0.0)
        two_off = p.get('tw', (self.two_off,))[0]
        PB['hips'].location = (hl.x, hl.z, -hl.y)
        PB['hips'].rotation_quaternion = Quaternion((0, 1, 0), self.spin) @ qe(p.get('hr', (0, 0, 0)))
        for k, n in (('sp', 'spine'), ('ch', 'chest'), ('nk', 'neck'), ('hd', 'head')):
            PB[n].rotation_quaternion = qe(p.get(k, (0, 0, 0)))
        for k, e in p.items():
            if k.startswith('x:'):
                PB[k[2:]].rotation_quaternion = qe(e)
        self.upd()
        lw = p.get('lookw', (1.0,))[0] if 'look' in p else 0.0
        if lw > 1e-4:
            d = (V(p['look']) - PB['head'].head).normalized()
            up = Vector((0, 0, 1))
            ql = (frame(d, up) @ frame(Vector((0, -1, 0)), up).transposed()).to_quaternion()
            qc = self.world_rot('chest').to_quaternion()
            qn, qh = self.world_rot('neck').to_quaternion(), self.world_rot('head').to_quaternion()
            ang = qc.rotation_difference(ql).angle
            k = min(1.0, self.look_max / max(ang, 1e-6))
            self.set_world_rot('neck', qn.slerp(qc.slerp(ql, 0.5 * k), lw).to_matrix())
            self.set_world_rot('head', qh.slerp(qc.slerp(ql, k), lw).to_matrix())
        if 'hx' in p:
            PB['head'].rotation_quaternion = PB['head'].rotation_quaternion @ qe(p['hx'])
        self.upd()
        for s, sx in SIDES:
            foot = list(p['f' + s])
            foot[0] -= advl
            foot[1] -= advf
            self.solve_leg(s, sx, foot, p.get('k' + s), tag)
        two = p.get('two', (0.0,))[0]
        nock = p.get('nock', (0.0,))[0]
        draw = p.get('draw', (0.0,))[0]
        if self.bow:
            self.pose_bow(draw)
        A = {}
        for s in 'LR':
            if ('g' + s) in p:
                A['g' + s] = self.at(p['g' + s])
            for k in 'cnwp':
                if (k + s) in p:
                    A[k + s] = self.Rs @ V(p[k + s])
        for s in (('R', 'L') if two > 0 else ('L', 'R')):
            if s == 'L' and two > 0:            # left hand takes the hilt below the right hand
                fist, axis = self.fist_axis('R')
                T = fist + axis * two_off
                A['gL'] = A['gL'].lerp(T, two)
                if two > 0.5:
                    c = T - PB['upperarm.L'].head
                    A['cL'] = c - axis * c.dot(axis)
                    A['wL'] = axis
            if s == 'R' and nock > 0:           # right hand rides the bowstring
                A['gR'] = A['gR'].lerp(self.nock_point(draw), nock)
            self.solve_arm(s, 1 if s == 'L' else -1, A, tag)
        self.upd()
        out = {n: PB[n].rotation_quaternion.copy() for n in self.ANIMB}
        out['loc'] = {n: tuple(PB[n].location) for n in self.loc_bones}
        return out

    def fist_axis(self, s):
        """Posed fist centre and held-weapon axis of a hand (armature space)."""
        sx = 1 if s == 'L' else -1
        HF = self.hand_frame(sx)
        D = self.world_rot('hand.' + s)
        fist = self.PB['hand.' + s].head + D @ (HF.translation - self.J('hand', sx))
        return fist, (D @ HF.col[0].to_3d()) * (-sx)

    def nock_point(self, draw):
        b = self.bow
        HF = self.hand_frame(1)
        D = self.world_rot('hand.L')
        fist = self.PB['hand.L'].head + D @ (HF.translation - self.J('hand', 1))
        return fist + D @ (HF.to_3x3() @ Vector((b['off'][0], b['off'][1] + b.get('grip_n', 0.0), -b['brace'] - draw * b['length'])))

    def pose_bow(self, draw):
        """String bone slides back along the arrow axis; the two limb bones flex with it."""
        b = self.bow
        R3 = self.hand_frame(1).to_3x3()
        v = R3 @ Vector((0, 0, -draw * b['length']))
        self.PB['string'].location = (v.x, v.z, -v.y)
        n = R3.col[1]
        ax = Vector((n.x, n.z, -n.y))
        th = math.radians(b['flex']) * draw
        self.PB['limb.A'].rotation_quaternion = Quaternion(ax, th)
        self.PB['limb.B'].rotation_quaternion = Quaternion(ax, -th)

    # ---------------------------------------------------------------- clips
    def bake(self, clips, hits=None, loops=(), fps=60, step=1):
        """clips: {name: [(frame, {channel: value}), ...]}. Every channel is its own curve:
        a key may set any subset of channels, each is interpolated (monotone cubic) through
        the keys that mention it, and the IK is solved on every frame, so planted feet stay
        planted and hands travel on smooth arcs. One action + muted NLA track per clip."""
        rig, PB = self.ob, self.PB
        hits = hits or {}
        rig.animation_data_create()
        bpy.context.view_layer.objects.active = rig
        meta = {}
        for cname, keys in clips.items():
            chans = {}
            for f, d in keys:
                for k, v in d.items():
                    v = tuple(v) if isinstance(v, (tuple, list)) else (v,)
                    if k[0] == 'f' and len(k) == 2:
                        v = v + (0.0,) * (5 - len(v))
                    chans.setdefault(k, []).append((f, v))
            curves = {k: Curve(v) for k, v in chans.items()}
            n = keys[-1][0]
            self.apply_rest()
            act = bpy.data.actions.new(cname)
            rig.animation_data.action = act
            prev = {}
            frames = sorted(set(list(range(1, n + 1, step)) + [n]))
            w0 = len(self.warn)
            advs = []
            for f in frames:
                spec = {k: c.at(f) for k, c in curves.items()}
                a = spec.get('adv', (0.0, 0.0))
                advs.append([round(a[0], 4), round(a[1] if len(a) > 1 else 0.0, 4)])
                p = self.solve(spec, f'{cname}@{f}')
                for b in self.ANIMB:
                    q = p[b].copy()
                    if b in prev and q.dot(prev[b]) < 0:
                        q.negate()
                    prev[b] = q
                    PB[b].rotation_quaternion = q
                    PB[b].keyframe_insert('rotation_quaternion', frame=f)
                for b in self.loc_bones:
                    PB[b].location = p['loc'][b]
                    PB[b].keyframe_insert('location', frame=f)
            rig.animation_data.action = None
            tr = rig.animation_data.nla_tracks.new()
            tr.name = cname
            st = tr.strips.new(cname, 1, act)
            st.name = cname
            tr.mute = True
            meta[cname] = {'dur': (n - 1) / fps, 'loop': cname in loops,
                           'hits': [(f - 1) / fps for f in hits.get(cname, [])]}
            if 'adv' in curves:
                meta[cname]['adv'] = advs
            # report each kind of pose problem once per clip, with its worst frame
            seen = {}
            for tag, kind, val in self.warn[w0:]:
                seen.setdefault(kind, []).append((val, tag.split('@')[1]))
            for kind, lst in seen.items():
                worst = max(lst)
                print(f'POSE WARNING {cname}: {kind} {worst[0]:.2f} at f{worst[1]} (frames {lst[0][1]}-{lst[-1][1]})')
        self.apply_rest()
        self.clip_len = {k: v[-1][0] for k, v in clips.items()}
        return meta

    def set_clip(self, cname, f):
        for t in self.ob.animation_data.nla_tracks:
            t.mute = t.name != cname
        bpy.context.scene.frame_set(f)

    def unmute_all(self):
        for t in self.ob.animation_data.nla_tracks:
            t.mute = False
        bpy.context.scene.frame_set(1)
        self.apply_rest()

    def sheet(self, cname, frames, out_dir, cam, target, lens=50, res=(420, 460), cols=4, preview=None, sheet=None):
        import os
        paths = []
        for f in frames:
            self.set_clip(cname, f)
            paths.append(os.path.join(out_dir, f'_{self.name}_{cname}_{f:03d}.png'))
            preview(paths[-1], cam, target, lens=lens, res=res)
        sheet(paths, os.path.join(out_dir, f'{self.name}_{cname}.png'), cols)
        for pth in paths:
            os.remove(pth)
