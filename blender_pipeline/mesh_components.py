import bpy, bmesh
from mathutils import Vector
def comps(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
    seen = set(); out = []
    for f in bm.faces:
        if f.index in seen: continue
        stack = [f]; grp = []; seen.add(f.index)
        while stack:
            g = stack.pop(); grp.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); stack.append(h)
        vs = {v.co.copy().freeze() for i in grp for v in bm.faces[i].verts}
        mn = Vector([min(v[k] for v in vs) for k in range(3)]); mx = Vector([max(v[k] for v in vs) for k in range(3)])
        mats = {bm.faces[i].material_index for i in grp}
        out.append((grp, mn, mx, mats))
    bm.free(); return out
if __name__ == '__main__':
    for n in ('Chest_Body_Metal', 'Chest_Lid_Metal'):
        o = bpy.data.objects[n]; C = comps(o); print(n, len(C), 'world', tuple(o.matrix_world.translation))
        from collections import Counter
        sizes = Counter()
        for grp, mn, mx, m in C:
            d = mx - mn; c = (mn + mx) / 2
            if max(d) < 0.04: sizes['small'] += 1; continue
            print('  n=%4d dim=(%.3f %.3f %.3f) c=(%.3f %.3f %.3f) mats=%s' % (len(grp), *d, *c, m))
        print(' ', sizes)
