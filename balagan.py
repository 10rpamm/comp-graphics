# -*- coding: utf-8 -*-
"""
Якутский балаган (бала5ан) для Blender 2.9 - 4.x
Запуск: вкладка Scripting -> Open -> balagan.py -> Run Script (Alt+P)

Всё строится кодом: наклонные брёвна стен, дверь, ледяные окна,
земляная крыша со снегом, камелёк с трубой, нары, стол на трёх ножках,
сундук, полка, ковёр, дрова, сэргэ (коновязь) и ёлки вокруг.
Размеры и цвета меняются в блоке ПАРАМЕТРЫ.
"""
import bpy
import math
import random
from mathutils import Vector, Euler, Quaternion

# ======================= ПАРАМЕТРЫ =======================
WIDTH = 5.0          # ширина по оси X (м)
LENGTH = 6.2         # длина по оси Y (м)
HEIGHT = 2.4         # высота стен (м)
WALL_INSET = 0.55    # насколько верх стен сдвинут внутрь (наклон стен)
LOG_R = 0.09         # радиус бревна

DOOR_X = 0.0         # положение двери по X на южной стене
DOOR_W = 0.95
DOOR_H = 1.8
DOOR_ANGLE = 75      # на сколько градусов открыта дверь (0 = закрыта)

WIN_Z0, WIN_Z1 = 1.15, 1.75   # высота окон от/до

ROOF_VISIBLE = True  # False -> крыша скрыта, видно интерьер сверху
SNOW = True          # снег на крыше и земле
CLEAR_SCENE = True   # удалить стандартные куб/свет/камеру
SEED = 7

COL = {
    "log":    (0.33, 0.20, 0.11),
    "log_d":  (0.24, 0.14, 0.08),
    "turf":   (0.22, 0.17, 0.09),
    "snow":   (0.93, 0.96, 1.00),
    "ground": (0.80, 0.86, 0.92),
    "earth":  (0.45, 0.34, 0.24),
    "floor":  (0.30, 0.19, 0.11),
    "plank":  (0.58, 0.38, 0.19),
    "clay":   (0.66, 0.48, 0.36),
    "iron":   (0.07, 0.07, 0.08),
    "ice":    (0.70, 0.88, 1.00),
    "fur1":   (0.42, 0.27, 0.16),
    "fur2":   (0.88, 0.82, 0.70),
    "red":    (0.62, 0.12, 0.10),
    "blue":   (0.15, 0.30, 0.55),
    "fire":   (1.00, 0.45, 0.08),
    "leaf":   (0.07, 0.22, 0.12),
    "rug":    (0.55, 0.15, 0.12),
}
# =========================================================

random.seed(SEED)
a = WIDTH / 2.0
b = LENGTH / 2.0
H = HEIGHT
ta = a - WALL_INSET          # полуширина верха стен
tb = b - WALL_INSET          # полудлина верха стен
TILT = math.atan2(WALL_INSET, H)


# ---------------------- подготовка сцены ----------------------
if CLEAR_SCENE:
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

coll = bpy.data.collections.new("Balagan")
bpy.context.scene.collection.children.link(coll)
bpy.context.view_layer.active_layer_collection = \
    bpy.context.view_layer.layer_collection.children[coll.name]


# ---------------------- материалы ----------------------
def make_mat(name, color, rough=0.85, alpha=1.0, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
        if emit:
            for key in ("Emission Color", "Emission"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = (*emit, 1.0)
                    break
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 6.0
    m.diffuse_color = (*color, alpha)
    if alpha < 1.0:
        try:
            m.blend_method = 'BLEND'
        except Exception:
            pass
    return m


M = {k: make_mat(k, v) for k, v in COL.items()}
M["ice"] = make_mat("ice", COL["ice"], rough=0.1, alpha=0.45)
M["fire"] = make_mat("fire", COL["fire"], rough=0.5, emit=COL["fire"])
M["iron"] = make_mat("iron", COL["iron"], rough=0.5)


# ---------------------- примитивы ----------------------
def _finish(o, name, mat, rot=None, scale=None):
    o.name = name
    if rot is not None:
        o.rotation_euler = rot
    if scale is not None:
        o.scale = scale
    if mat:
        o.data.materials.append(mat)
    return o


def box(name, size, loc, mat, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    return _finish(bpy.context.active_object, name, mat, rot, size)


def cyl(name, r, depth, loc, mat, rot=None, verts=14, scale=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r,
                                        depth=depth, location=loc)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _finish(o, name, mat, rot, scale)


def cone(name, r1, r2, depth, loc, mat, verts=16, rot=None):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2,
                                    depth=depth, location=loc)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _finish(o, name, mat, rot)


def rod(name, p0, p1, r, mat, verts=12):
    """Цилиндр между двумя точками."""
    d = p1 - p0
    if d.length < 1e-4:
        return None
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return cyl(name, r, d.length, (p0 + p1) / 2, mat, rot, verts)


def sphere(name, r, loc, mat, scale=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc,
                                         segments=16, ring_count=8)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _finish(o, name, mat, None, scale)


# ---------------------- геометрия стен ----------------------
def wall_pts(side, p):
    """Нижняя и верхняя точка бревна на стене side в позиции p."""
    if side == 'S':
        return Vector((p, -b, 0)), Vector((p * ta / a, -tb, H))
    if side == 'N':
        return Vector((p, b, 0)), Vector((p * ta / a, tb, H))
    if side == 'E':
        return Vector((a, p, 0)), Vector((ta, p * tb / b, H))
    return Vector((-a, p, 0)), Vector((-ta, p * tb / b, H))


def wall_positions(side):
    span = (a - LOG_R) if side in 'SN' else (b - 2 * LOG_R)
    n = int(math.ceil(2 * span / (2 * LOG_R * 0.92))) + 1
    return [-span + 2 * span * k / (n - 1) for k in range(n)]


def at(base, top, t):
    return base + (top - base) * t


# проёмы: (стена, p0, p1, t0, t1), t - доля высоты стены
OPENINGS = [
    ('S', DOOR_X - DOOR_W / 2, DOOR_X + DOOR_W / 2, 0.0, DOOR_H / H),
    ('E', -0.6, 0.0, WIN_Z0 / H, WIN_Z1 / H),
    ('W', -0.6, 0.0, WIN_Z0 / H, WIN_Z1 / H),
    ('N', -1.3, -0.7, WIN_Z0 / H, WIN_Z1 / H),
]


def free_intervals(p, ops):
    iv = [(0.0, 1.0)]
    for (_, p0, p1, t0, t1) in ops:
        if p0 - LOG_R * 0.5 <= p <= p1 + LOG_R * 0.5:
            new = []
            for (s, e) in iv:
                if t1 <= s or t0 >= e:
                    new.append((s, e))
                else:
                    if s < t0:
                        new.append((s, t0))
                    if e > t1:
                        new.append((t1, e))
            iv = new
    return iv


def build_walls():
    for side in 'SNEW':
        ops = [o for o in OPENINGS if o[0] == side]
        for p in wall_positions(side):
            base, top = wall_pts(side, p)
            r = LOG_R * random.uniform(0.93, 1.07)
            mat = M["log"] if random.random() > 0.3 else M["log_d"]
            for (s, e) in free_intervals(p, ops):
                if e - s < 0.03:
                    continue
                rod("log_" + side, at(base, top, s), at(base, top, e), r, mat)


def panel(side, p0, p1, t0, t1, thick, mat, name):
    """Плоская панель, лежащая в наклонной плоскости стены (окно)."""
    pc = (p0 + p1) / 2
    base, top = wall_pts(side, pc)
    center = at(base, top, (t0 + t1) / 2)
    h = (t1 - t0) * (top - base).length
    w = (p1 - p0) * 0.98
    if side in 'SN':
        alpha = -math.copysign(TILT, (top - base).y)
        return box(name, (w, thick, h), center, mat, Euler((alpha, 0, 0)))
    beta = math.copysign(TILT, (top - base).x)
    return box(name, (thick, w, h), center, mat, Euler((0, beta, 0)))


def build_openings():
    # ледяные окна (мууstаах) и рамы
    for (side, p0, p1, t0, t1) in OPENINGS[1:]:
        panel(side, p0, p1, t0, t1, 0.04, M["ice"], "ice_window")
        for (q0, q1, tt0, tt1) in [
            (p0, p1, t0 - 0.02, t0), (p0, p1, t1, t1 + 0.02),
            (p0 - 0.04, p0, t0, t1), (p1, p1 + 0.04, t0, t1),
        ]:
            panel(side, q0, q1, tt0, tt1, 0.08, M["plank"], "window_frame")

    # дверная коробка
    for sgn in (-1, 1):
        px = DOOR_X + sgn * DOOR_W / 2
        base, top = wall_pts('S', px)
        rod("door_post", base, at(base, top, DOOR_H / H), 0.06, M["plank"])
    t = DOOR_H / H
    yl = -(b - WALL_INSET * t)
    z = DOOR_H + 0.03
    rod("door_lintel", Vector((DOOR_X - DOOR_W / 2 - 0.12, yl, z)),
        Vector((DOOR_X + DOOR_W / 2 + 0.12, yl, z)), 0.075, M["plank"])
    box("threshold", (DOOR_W + 0.1, 0.35, 0.08),
        (DOOR_X, -b - 0.05, 0.04), M["plank"])

    # дверь (приоткрыта)
    base, top = wall_pts('S', DOOR_X - DOOR_W / 2)
    hinge = at(base, top, DOOR_H / H / 2)
    leaf_h = (DOOR_H / H) * (top - base).length
    bpy.ops.mesh.primitive_cube_add(size=1, location=hinge)
    leaf = bpy.context.active_object
    for v in leaf.data.vertices:
        v.co.x += 0.5            # точка вращения на кромке петли
    leaf.name = "door"
    leaf.scale = (DOOR_W, 0.07, leaf_h)
    qt = Euler((-TILT, 0, 0)).to_quaternion()
    qz = Quaternion((0, 0, 1), math.radians(DOOR_ANGLE))
    leaf.rotation_euler = (qt @ qz).to_euler()
    leaf.data.materials.append(M["plank"])
    # ручка
    sphere("door_handle", 0.03, hinge + Vector((0, 0, 0)), M["iron"])
    bpy.context.active_object.location = (
        hinge.x + DOOR_W * math.cos(math.radians(DOOR_ANGLE)) * 0.85,
        hinge.y + DOOR_W * math.sin(math.radians(DOOR_ANGLE)) * 0.85 + 0.05,
        hinge.z)


# ---------------------- крыша ----------------------
roof_objs = []


def build_roof():
    n = int((2 * tb) / 0.2) + 1
    for k in range(n):
        y = -tb + 2 * tb * k / (n - 1)
        o = rod("roof_pole", Vector((-ta - 0.25, y, H + 0.07)),
                Vector((ta + 0.25, y, H + 0.07)), 0.07, M["log_d"], verts=10)
        roof_objs.append(o)
    roof_objs.append(box("roof_turf", (2 * ta + 0.7, 2 * tb + 0.7, 0.22),
                         (0, 0, H + 0.25), M["turf"]))
    if SNOW:
        roof_objs.append(box("roof_snow", (2 * ta + 0.6, 2 * tb + 0.6, 0.12),
                             (0, 0, H + 0.42), M["snow"]))
    # дымовая труба над крышей
    fx, fy = a - 0.95, b - 1.0
    roof_objs.append(rod("chimney_top", Vector((fx, fy, H)),
                         Vector((fx, fy, H + 0.95)), 0.17, M["clay"]))
    roof_objs.append(cyl("chimney_cap", 0.23, 0.07, (fx, fy, H + 0.95),
                         M["clay"]))
    if not ROOF_VISIBLE:
        for o in roof_objs:
            o.hide_viewport = True
            o.hide_render = True


# ---------------------- земляная завалинка ----------------------
def build_base():
    x_door_l = DOOR_X - DOOR_W / 2 - 0.3
    x_door_r = DOOR_X + DOOR_W / 2 + 0.3
    full = a + 0.45
    box("berm_N", (2 * full, 0.5, 0.4), (0, b + 0.1, 0.2), M["earth"])
    box("berm_E", (0.5, 2 * b + 0.5, 0.4), (a + 0.1, 0, 0.2), M["earth"])
    box("berm_W", (0.5, 2 * b + 0.5, 0.4), (-a - 0.1, 0, 0.2), M["earth"])
    wl = x_door_l + full
    box("berm_SL", (wl, 0.5, 0.4), (-full + wl / 2, -b - 0.1, 0.2), M["earth"])
    wr = full - x_door_r
    box("berm_SR", (wr, 0.5, 0.4), (x_door_r + wr / 2, -b - 0.1, 0.2),
        M["earth"])
    # пол
    box("floor", (WIDTH + 0.4, LENGTH + 0.4, 0.1), (0, 0, -0.03), M["floor"])


# ---------------------- мебель ----------------------
def inset_at(z):
    return WALL_INSET * z / H


def build_furniture():
    # --- нары (орон) вдоль боковых стен ---
    bx = a - 0.75
    for sgn, name in ((-1, "west"), (1, "east")):
        box("bed_" + name, (0.9, 2.2, 0.42), (sgn * bx, -0.6, 0.21), M["plank"])
        box("bed_edge_" + name, (0.06, 2.2, 0.1),
            (sgn * (bx - 0.45), -0.6, 0.45), M["log_d"])
    box("fur_west", (0.85, 1.2, 0.07), (-bx, -1.0, 0.455), M["fur1"])
    box("pillow_west", (0.55, 0.3, 0.12), (-bx, 0.15, 0.48), M["red"])
    box("fur_east", (0.85, 1.2, 0.07), (bx, -1.0, 0.455), M["fur2"])
    box("pillow_east", (0.55, 0.3, 0.12), (bx, 0.15, 0.48), M["blue"])

    # --- ковёр ---
    cyl("rug", 1.0, 1.0, (0, 0.8, 0.012), M["rug"], verts=32,
        scale=(1.15, 0.85, 0.02))

    # --- якутский стол на трёх ножках ---
    tc = Vector((0, 0.8, 0))
    cyl("table_top", 0.5, 0.06, (tc.x, tc.y, 0.78), M["plank"], verts=24)
    for ang in (90, 210, 330):
        d = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))
        rod("table_leg", tc + d * 0.28 + Vector((0, 0, 0.76)),
            tc + d * 0.42, 0.04, M["log"])
    # посуда на столе
    cyl("bowl", 0.11, 0.06, (0.12, 0.85, 0.84), M["iron"], verts=16)
    cyl("cup", 0.05, 0.1, (-0.2, 0.7, 0.86), M["clay"], verts=12)

    # --- чурки-табуреты ---
    cyl("stool1", 0.2, 0.42, (0.95, 0.7, 0.21), M["log"], verts=14)
    cyl("stool2", 0.2, 0.42, (-0.9, 1.0, 0.21), M["log"], verts=14)

    # --- камелёк (глиняный очаг с трубой) ---
    fx, fy = a - 0.95, b - 1.0
    box("hearth", (1.1, 1.1, 0.7), (fx, fy, 0.35), M["clay"])
    cone("fireplace_hood", 0.65, 0.2, 1.2, (fx, fy, 1.3), M["clay"],
         verts=4, rot=(0, 0, math.radians(45)))
    rod("fireplace_pipe", Vector((fx, fy, 1.9)),
        Vector((fx, fy, H + 0.1)), 0.17, M["clay"])
    box("firebox", (0.05, 0.5, 0.33), (fx - 0.56, fy, 0.4), M["iron"])
    box("fire", (0.04, 0.4, 0.2), (fx - 0.575, fy, 0.34), M["fire"])
    bpy.ops.object.light_add(type='POINT', location=(fx - 0.9, fy, 0.5))
    lamp = bpy.context.active_object
    lamp.name = "fire_light"
    lamp.data.color = COL["fire"]
    lamp.data.energy = 150

    # --- поперечная балка ---
    zb = 1.95
    xb = a - inset_at(zb) - LOG_R
    rod("tie_beam", Vector((-xb, 0.2, zb)), Vector((xb, 0.2, zb)),
        0.08, M["log_d"])

    # --- полка на северной стене с утварью ---
    zs = 1.45
    ys = b - inset_at(zs) - LOG_R - 0.16
    box("shelf", (1.2, 0.26, 0.05), (0.4, ys, zs), M["plank"])
    for i, (jx, c) in enumerate(((0.0, "clay"), (0.3, "iron"), (0.6, "red"))):
        cyl("jar%d" % i, 0.07, 0.18, (jx, ys, zs + 0.115), M[c], verts=12)
    box("bucket_ladle", (0.1, 0.1, 0.1), (0.85, ys, zs + 0.075), M["log"])

    # --- сундук ---
    cx, cy = -(a - 1.1), b - 0.7
    box("chest", (0.9, 0.5, 0.5), (cx, cy, 0.25), M["log"])
    box("chest_lid", (0.94, 0.54, 0.08), (cx, cy, 0.54), M["plank"])
    box("chest_strap1", (0.06, 0.56, 0.54), (cx - 0.25, cy, 0.27), M["iron"])
    box("chest_strap2", (0.06, 0.56, 0.54), (cx + 0.25, cy, 0.27), M["iron"])

    # --- светильник-плошка на стене у двери ---
    zl = 1.6
    box("lamp_shelf", (0.3, 0.15, 0.04),
        (-(DOOR_W / 2 + 0.9), -b + inset_at(zl) + LOG_R + 0.1, zl), M["plank"])


# ---------------------- улица ----------------------
def build_outside():
    # земля
    bpy.ops.mesh.primitive_plane_add(size=45, location=(0, 0, -0.02))
    g = bpy.context.active_object
    g.name = "ground"
    g.data.materials.append(M["ground"] if SNOW else M["earth"])

    # сугробы
    if SNOW:
        for _ in range(10):
            ang = random.uniform(0, 2 * math.pi)
            rad = random.uniform(4.2, 8)
            s = random.uniform(0.8, 1.6)
            sphere("snowdrift", 1.0,
                   (math.cos(ang) * rad, math.sin(ang) * rad, 0),
                   M["snow"], (s, s * random.uniform(0.6, 1.0), 0.22))

    # дрова
    x0, y0 = a + 1.0, -1.2
    for row in range(4):
        n = 6 - row
        for k in range(n):
            x = x0 + (k - (n - 1) / 2) * 0.15
            cyl("firewood", 0.07, 0.9, (x, y0, 0.07 + row * 0.125), M["log"],
                rot=(math.radians(90), 0, 0), verts=8)

    # сэргэ (резной столб-коновязь)
    sx, sy = -3.9, -3.6
    cyl("serge_pole", 0.12, 3.2, (sx, sy, 1.6), M["log"], verts=12)
    for z in (2.2, 2.55, 2.9):
        cyl("serge_ring", 0.19, 0.06, (sx, sy, z), M["plank"], verts=12)
    cyl("serge_top", 0.22, 0.12, (sx, sy, 3.25), M["plank"], verts=12)

    # лиственницы / ели вокруг
    for _ in range(9):
        ang = random.uniform(0, 2 * math.pi)
        rad = random.uniform(9, 14)
        x, y = math.cos(ang) * rad, math.sin(ang) * rad
        hh = random.uniform(3.5, 5.5)
        cyl("trunk", 0.16, 1.6, (x, y, 0.8), M["log_d"], verts=8)
        cone("tree", 1.3, 0.0, hh, (x, y, 1.4 + hh / 2), M["leaf"], verts=10)
        if SNOW:
            cone("tree_snow", 0.7, 0.0, hh * 0.55,
                 (x, y, 1.4 + hh * 0.72), M["snow"], verts=10)


# ---------------------- свет, камера, небо ----------------------
def build_scene_setup():
    bpy.ops.object.light_add(type='SUN', location=(8, -8, 12))
    sun = bpy.context.active_object
    sun.name = "sun"
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sun.data.energy = 3.5

    bpy.ops.object.camera_add(location=(9.5, -10.5, 5.2))
    cam = bpy.context.active_object
    cam.name = "camera"
    target = Vector((0, 0, 1.4))
    d = target - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.55, 0.70, 0.90, 1.0)
        bg.inputs[1].default_value = 1.0


# ---------------------- сборка ----------------------
build_base()
build_walls()
build_openings()
build_roof()
build_furniture()
build_outside()
build_scene_setup()
print("Балаган готов!")
