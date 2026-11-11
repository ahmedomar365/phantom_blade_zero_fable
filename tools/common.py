"""Shared Blender helpers for the Sand Falcons asset pipeline (Blender 5.x, run headless)."""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, Euler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, 'build', 'tex')
OUT = os.path.join(ROOT, 'game', 'assets')
PREVIEW = os.path.join(ROOT, 'build', 'preview')
for _d in (TEX, OUT, PREVIEW):
    os.makedirs(_d, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _img(path, data=False):
    img = bpy.data.images.load(path, check_existing=True)
    if data:
        img.colorspace_settings.name = 'Non-Color'
    return img


def mat(name, color=(1, 1, 1), rough=0.5, metal=0.0, tex=None, emit=None,
        emit_strength=1.0, nrm_strength=1.0, alpha=None, two_sided=True, slot=None, orm=True):
    """Principled material. `tex` names a texture set in build/tex (<tex>_col.jpg,
    optional <tex>_orm.png / <tex>_nrm.png). `color` tints the texture: it is exported
    as the custom property `tint` and multiplied in by the game. `slot` is a recolour
    channel name the game may override per character (cloth1, cloth2, metal, trim...)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m['tint'] = list(color)
    if slot:
        m['slot'] = slot
    m.use_backface_culling = False      # everything is exported double-sided (winding-proof)
    if tex:
        col = os.path.join(TEX, tex + '_col.jpg')
        if not os.path.exists(col):
            col = os.path.join(TEX, tex + '_col.png')
        nrm = os.path.join(TEX, tex + '_nrm.png')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = _img(col)
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        nt.links.new(t.outputs['Color'], mix.inputs[6])
        mix.inputs[7].default_value = (*color, 1)
        # the multiply node is only for Blender previews: glTF export reads the texture
        m['has_tex'] = 1
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
        if alpha == 'tex':
            nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
        use_orm = orm
        orm = os.path.join(TEX, tex + '_orm.png')
        if use_orm and os.path.exists(orm):
            t2 = nt.nodes.new('ShaderNodeTexImage')
            t2.image = _img(orm, True)
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(t2.outputs['Color'], sep.inputs[0])
            nt.links.new(sep.outputs[1], b.inputs['Roughness'])
            nt.links.new(sep.outputs[2], b.inputs['Metallic'])
        if os.path.exists(nrm):
            t3 = nt.nodes.new('ShaderNodeTexImage')
            t3.image = _img(nrm, True)
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value = nrm_strength
            nt.links.new(t3.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if emit is not None:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    if alpha is not None and alpha != 'tex':
        b.inputs['Alpha'].default_value = alpha
        m.surface_render_method = 'BLENDED'
    return m


def strip_preview_tint():
    """Before glTF export: wire textures straight into Base Color (the exporter does not
    understand the multiply node); the tint travels as a custom property instead."""
    for m in bpy.data.materials:
        if not m.get('has_tex') or not m.use_nodes:
            continue
        nt = m.node_tree
        b = nt.nodes['Principled BSDF']
        mix = next((n for n in nt.nodes if n.type == 'MIX'), None)
        if not mix:
            continue
        src = mix.inputs[6].links[0].from_socket
        nt.links.new(src, b.inputs['Base Color'])
        nt.nodes.remove(mix)


def TRS(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """rot in degrees (XYZ euler)."""
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    r = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
    s = Matrix.Diagonal((*scale, 1))
    return Matrix.Translation(loc) @ r @ s


def between(p0, p1, ref=None):
    """Matrix placing a Z-aligned primitive that starts at p0 and runs to p1 (origin at p0).
    Returns (matrix, length)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    z = d.normalized()
    r = Vector(ref) if ref is not None else (Vector((0, -1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0)))
    y = (r - z * r.dot(z)).normalized()
    x = y.cross(z)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = p0
    return M, d.length


def _sup(c, e):
    return math.copysign(abs(c) ** e, c)


class MB:
    """Mesh builder. Accumulates primitives into one mesh with per-part material, UVs and
    skin weights. `w` on any primitive is a bone name, a {bone: weight} dict, a callable
    (co -> weights) evaluated on the final vertex position, or (lofts) one entry per ring."""

    def __init__(self, uv=1.0, w=None):
        self.bm = bmesh.new()
        self.uvl = self.bm.loops.layers.uv.new('UVMap')
        self.mats = []
        self.vw = []
        self.base = Matrix.Identity(4)
        self.uv = uv
        self.default_w = w

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _merge(self, t, M, m, w, per_vert=None, smooth=True):
        """Copy temp bmesh `t` into the mesh. per_vert: list of weights aligned with t.verts."""
        M = self.base @ (M if M is not None else Matrix.Identity(4))
        flip = M.determinant() < 0
        mi = self._mi(m)
        tuv = t.loops.layers.uv.get('UVMap')
        t.verts.index_update()
        if w is None:
            w = self.default_w
        new = []
        for i, v in enumerate(t.verts):
            nv = self.bm.verts.new(M @ v.co)
            new.append(nv)
            ww = per_vert[i] if per_vert is not None else w
            if callable(ww):
                ww = ww(nv.co)
            if isinstance(ww, str):
                ww = {ww: 1.0}
            self.vw.append(ww)
        N3 = M.to_3x3()
        for f in t.faces:
            vs = [new[v.index] for v in f.verts]
            if flip:
                vs.reverse()
            try:
                nf = self.bm.faces.new(vs)
            except ValueError:
                continue
            nf.material_index = mi
            nf.smooth = smooth
            loops = list(f.loops)
            if flip:
                loops.reverse()
            if tuv is not None:
                for l, src in zip(nf.loops, loops):
                    l[self.uvl].uv = src[tuv].uv
            else:
                n = (N3 @ f.normal)
                ax = max(range(3), key=lambda k: abs(n[k]))
                for l in nf.loops:
                    c = l.vert.co
                    if ax == 0:
                        l[self.uvl].uv = (c.y * self.uv, c.z * self.uv)
                    elif ax == 1:
                        l[self.uvl].uv = (c.x * self.uv, c.z * self.uv)
                    else:
                        l[self.uvl].uv = (c.x * self.uv, c.y * self.uv)
        t.free()

    # ------------------------------------------------------------ primitives
    def box(self, size, loc=(0, 0, 0), rot=(0, 0, 0), m=None, bevel=0.0, w=None, segs=2, M=None):
        t = bmesh.new()
        bmesh.ops.create_cube(t, size=1.0)
        bmesh.ops.scale(t, vec=size, verts=t.verts)
        if bevel > 0:
            bmesh.ops.bevel(t, geom=t.edges[:], offset=bevel, segments=segs, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        self._merge(t, M if M is not None else TRS(loc, rot), m, w)

    def cyl(self, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), m=None, bevel=0.0, w=None,
            segs=20, r2=None, M=None, bsegs=2):
        """Cylinder along local Z, centered."""
        t = bmesh.new()
        bmesh.ops.create_cone(t, cap_ends=True, cap_tris=False, segments=segs,
                              radius1=r, radius2=r if r2 is None else r2, depth=depth)
        if bevel > 0:
            caps = [e for e in t.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6]
            bmesh.ops.bevel(t, geom=caps, offset=bevel, segments=bsegs, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        self._merge(t, M if M is not None else TRS(loc, rot), m, w)

    def sphere(self, r, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), m=None, w=None, segs=20, M=None):
        t = bmesh.new()
        bmesh.ops.create_uvsphere(t, u_segments=segs, v_segments=max(8, segs // 2), radius=r)
        self._merge(t, M if M is not None else TRS(loc, rot, scale), m, w)

    def poly(self, pts, faces, m=None, w=None, M=None, recalc=True, uvs=None, smooth=True):
        """Raw geometry. uvs: optional list of (u, v) per point."""
        t = bmesh.new()
        vs = [t.verts.new(p) for p in pts]
        for f in faces:
            try:
                t.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        if recalc:
            bmesh.ops.recalc_face_normals(t, faces=t.faces)
        if uvs is not None:
            t.verts.index_update()
            l = t.loops.layers.uv.new('UVMap')
            for f in t.faces:
                for lp in f.loops:
                    lp[l].uv = uvs[lp.vert.index]
        self._merge(t, M, m, w, smooth=smooth)

    def extrude_profile(self, prof, length, loc=(0, 0, 0), rot=(0, 0, 0), m=None, w=None, cap=True, M=None):
        """Closed 2D profile (x,z) extruded along local Y, centered."""
        n = len(prof)
        pts = [(x, -length / 2, z) for x, z in prof] + [(x, length / 2, z) for x, z in prof]
        faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        if cap:
            faces.append(tuple(range(n)))
            faces.append(tuple(range(2 * n - 1, n - 1, -1)))
        self.poly(pts, faces, m, w, M if M is not None else TRS(loc, rot), smooth=False)

    def loft(self, rings, m=None, w=None, segs=16, cap=(True, True), M=None, uvs=(1.0, 1.0),
             sq=2.0, arc=None, twist=0.0):
        """Tube along local Z. rings: (z, rx, ry[, ox, oy[, sq]]). Elliptic (or superelliptic,
        sq > 2 is boxier) cross-sections. arc=(a0, a1) degrees makes an open strip (0 = +X,
        90 = +Y, i.e. the BACK of a character facing -Y; front is 270). w may list one entry
        per ring. UVs: u around (metres * uvs[0]), v along (metres * uvs[1])."""
        t = bmesh.new()
        uvl = t.loops.layers.uv.new('UVMap')
        closed = arc is None
        a0, a1 = (0.0, 360.0) if closed else arc
        n = segs if closed else segs + 1
        rows, vlen, pw = [], [0.0], []
        ringw = w if isinstance(w, (list, tuple)) else None
        for ri, r in enumerate(rings):
            z, rx, ry = r[0], r[1], r[2]
            ox = r[3] if len(r) > 3 else 0.0
            oy = r[4] if len(r) > 4 else 0.0
            e = 2.0 / (r[5] if len(r) > 5 else sq)
            row = []
            for i in range(n):
                a = math.radians(a0 + (a1 - a0) * i / segs + twist * ri)
                row.append(t.verts.new((ox + rx * _sup(math.cos(a), e), oy + ry * _sup(math.sin(a), e), z)))
                if ringw is not None:
                    pw.append(ringw[ri])
            rows.append(row)
            if ri:
                p = rings[ri - 1]
                vlen.append(vlen[-1] + math.hypot(z - p[0], (rx + ry) / 2 - (p[1] + p[2]) / 2))
        mean_r = sum((r[1] + r[2]) / 2 for r in rings) / len(rings)
        circ = 2 * math.pi * mean_r * (a1 - a0) / 360.0
        ucount = max(1, round(circ * uvs[0])) if closed else circ * uvs[0]
        for ri in range(len(rows) - 1):
            for i in range(segs):
                j = (i + 1) % n if closed else i + 1
                f = t.faces.new((rows[ri][i], rows[ri][j], rows[ri + 1][j], rows[ri + 1][i]))
                us = (i / segs * ucount, (i + 1) / segs * ucount)
                vs = (vlen[ri] * uvs[1], vlen[ri + 1] * uvs[1])
                for lp, uv in zip(f.loops, ((us[0], vs[0]), (us[1], vs[0]), (us[1], vs[1]), (us[0], vs[1]))):
                    lp[uvl].uv = uv
        if closed:
            for end, row in ((0, rows[0]), (1, rows[-1])):
                if cap[end] and rings[-end][1] > 1e-5:
                    f = t.faces.new(row[::-1] if end == 0 else row)
                    for lp in f.loops:
                        lp[uvl].uv = (lp.vert.co.x * uvs[0], lp.vert.co.y * uvs[0])
        self._merge(t, M, m, None if ringw is not None else w, per_vert=pw if ringw is not None else None)

    def lathe(self, prof, m=None, w=None, segs=24, M=None, uvs=(1.0, 1.0), arc=None):
        """Revolve profile [(r, z), ...] around local Z."""
        rings = [(z, r, r) for r, z in prof]
        # v length must follow the profile, so compute it here and reuse loft for topology
        t = bmesh.new()
        uvl = t.loops.layers.uv.new('UVMap')
        closed = arc is None
        a0, a1 = (0.0, 360.0) if closed else arc
        n = segs if closed else segs + 1
        rows, vlen = [], [0.0]
        for ri, (r, z) in enumerate(prof):
            if r < 1e-6:
                rows.append([t.verts.new((0, 0, z))] * n)
            else:
                rows.append([t.verts.new((r * math.cos(math.radians(a0 + (a1 - a0) * i / segs)),
                                          r * math.sin(math.radians(a0 + (a1 - a0) * i / segs)), z)) for i in range(n)])
            if ri:
                vlen.append(vlen[-1] + math.hypot(r - prof[ri - 1][0], z - prof[ri - 1][1]))
        mean_r = max(1e-3, sum(r for r, _ in prof) / len(prof))
        ucount = max(1, round(2 * math.pi * mean_r * uvs[0])) * (a1 - a0) / 360.0
        for ri in range(len(rows) - 1):
            for i in range(segs):
                j = (i + 1) % n if closed else i + 1
                q = [rows[ri][i], rows[ri][j], rows[ri + 1][j], rows[ri + 1][i]]
                uv = [(i / segs * ucount, vlen[ri] * uvs[1]), ((i + 1) / segs * ucount, vlen[ri] * uvs[1]),
                      ((i + 1) / segs * ucount, vlen[ri + 1] * uvs[1]), (i / segs * ucount, vlen[ri + 1] * uvs[1])]
                vs, us = [], []
                for v, u in zip(q, uv):
                    if v not in vs:
                        vs.append(v)
                        us.append(u)
                if len(vs) < 3:
                    continue
                try:
                    f = t.faces.new(vs)
                except ValueError:
                    continue
                for lp, u in zip(f.loops, us):
                    lp[uvl].uv = u
        self._merge(t, M, m, w)

    def grid(self, fn, nu, nv, m=None, w=None, M=None, uvs=(1.0, 1.0), wfn=None):
        """Sheet: fn(u, v) -> (x, y, z) for u, v in 0..1. wfn(u, v) -> weights."""
        t = bmesh.new()
        uvl = t.loops.layers.uv.new('UVMap')
        vs, pw = [], []
        for j in range(nv + 1):
            for i in range(nu + 1):
                vs.append(t.verts.new(fn(i / nu, j / nv)))
                if wfn:
                    pw.append(wfn(i / nu, j / nv))
        for j in range(nv):
            for i in range(nu):
                a = j * (nu + 1) + i
                f = t.faces.new((vs[a], vs[a + 1], vs[a + nu + 2], vs[a + nu + 1]))
                uv = ((i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv))
                for lp, u in zip(f.loops, uv):
                    lp[uvl].uv = (u[0] * uvs[0], u[1] * uvs[1])
        self._merge(t, M, m, w, per_vert=pw if wfn else None)

    def tube(self, pts, r, m=None, w=None, segs=8, cap=True):
        """Round tube through a list of points (r: number or per-point list)."""
        pts = [Vector(p) for p in pts]
        rs = r if isinstance(r, (list, tuple)) else [r] * len(pts)
        t = bmesh.new()
        rows = []
        ref = Vector((0, 0, 1))
        for i, p in enumerate(pts):
            d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            if abs(d.dot(ref)) > 0.95:
                ref = Vector((1, 0, 0))
            x = d.cross(ref).normalized()
            y = d.cross(x).normalized()
            rows.append([t.verts.new(p + (x * math.cos(2 * math.pi * k / segs) + y * math.sin(2 * math.pi * k / segs)) * rs[i])
                         for k in range(segs)])
        for i in range(len(rows) - 1):
            for k in range(segs):
                t.faces.new((rows[i][k], rows[i][(k + 1) % segs], rows[i + 1][(k + 1) % segs], rows[i + 1][k]))
        if cap:
            t.faces.new(rows[0][::-1])
            t.faces.new(rows[-1])
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        self._merge(t, None, m, w)

    # ------------------------------------------------------------ output
    def finish(self, name, smooth=40.0, weld=False, collection=None):
        bm = self.bm
        if weld:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            self.vw = None
        bm.normal_update()
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        for m in self.mats:
            me.materials.append(m)
        me.set_sharp_from_angle(angle=math.radians(smooth))
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if self.vw and any(w for w in self.vw):
            groups = {}
            for i, w in enumerate(self.vw):
                if not w:
                    continue
                tot = sum(w.values())
                for g, x in w.items():
                    if x > 0:
                        groups.setdefault(g, []).append((i, x / tot))
            for g, lst in groups.items():
                vg = ob.vertex_groups.new(name=g)
                for i, x in lst:
                    vg.add([i], x, 'REPLACE')
        bm.free()
        return ob


def empty(name, loc=(0, 0, 0), parent=None, rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    bpy.context.scene.collection.objects.link(e)
    if parent:
        e.parent = parent
    return e


def export_glb(path, anim=False, selected=False):
    strip_preview_tint()
    kw = dict(filepath=path, export_format='GLB', export_yup=True, export_apply=not anim,
              export_extras=True, export_image_format='AUTO', export_jpeg_quality=88,
              export_animations=anim, export_tangents=False, use_selection=selected)
    if anim:
        kw.update(export_animation_mode='NLA_TRACKS', export_skins=True, export_def_bones=False,
                  export_optimize_animation_size=False, export_force_sampling=True,
                  export_anim_slide_to_zero=True)
    bpy.ops.export_scene.gltf(**kw)
    print('EXPORTED', path, round(os.path.getsize(path) / 1e6, 2), 'MB')


def preview(path, cam_loc, target, lens=50, res=(1100, 800), sun=(3.0, (55, 0, 35)), world=(0.30, 0.33, 0.40),
            fill=1.2):
    """Quick EEVEE render so the art can be checked without opening Blender."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get('_pcam')
    if not cam:
        cam = bpy.data.objects.new('_pcam', bpy.data.cameras.new('_pcam'))
        sc.collection.objects.link(cam)
        sd = bpy.data.lights.new('_psun', 'SUN')
        so = bpy.data.objects.new('_psun', sd)
        sc.collection.objects.link(so)
        sd.energy = sun[0]
        sd.color = (1.0, 0.86, 0.68)
        so.rotation_euler = [math.radians(a) for a in sun[1]]
        sd2 = bpy.data.lights.new('_pfill', 'SUN')
        so2 = bpy.data.objects.new('_pfill', sd2)
        sc.collection.objects.link(so2)
        sd2.energy = fill
        sd2.color = (0.7, 0.8, 1.0)
        so2.rotation_euler = [math.radians(a) for a in (60, 0, 200)]
        w = bpy.data.worlds.new('_pw')
        w.use_nodes = True
        w.node_tree.nodes['Background'].inputs[0].default_value = (*world, 1)
        sc.world = w
    cam.data.lens = lens
    cam.data.clip_end = 2000
    cam.location = cam_loc
    d = Vector(target) - Vector(cam_loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'AgX'
    except Exception:
        pass
    bpy.ops.render.render(write_still=True)
    print('PREVIEW', path)


def drop_preview_rig():
    for o in [o for o in bpy.data.objects if o.name.startswith('_p')]:
        bpy.data.objects.remove(o)


def sheet(paths, out, cols):
    """Stitch rendered previews into one contact sheet."""
    import numpy as np
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(a)
        imgs.append(a.reshape(h, w, 4))
        bpy.data.images.remove(im)
    while len(imgs) % cols:
        imgs.append(np.zeros_like(imgs[0]))
    rows = [np.concatenate(imgs[i:i + cols], 1) for i in range(0, len(imgs), cols)]
    full = np.concatenate(rows[::-1], 0)
    h, w = full.shape[:2]
    img = bpy.data.images.new('_sheet', w, h, alpha=True)
    img.pixels.foreach_set(full.ravel())
    img.filepath_raw = out
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    print('SHEET', out)
