# -*- coding: utf-8 -*-
"""
Якутский балаган (бала5ан) - упрощённая версия для Blender 2.9 - 4.x
Запуск: вкладка Scripting -> Open -> balagan.py -> Run Script (Alt+P)

В сцене только: сам балаган (наклонные брёвна, дверь, окна, крыша,
завалинка, пол), цилиндрический камелёк, простой стол и простой стул.
Цвета яркие и нереалистичные.
"""
import bpy
import math
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

ROOF_VISIBLE = True  # False -> крыша скрыта, видно стол и стул внутри
BUILD_KAMELEK = True # False -> без камелька
CLEAR_SCENE = True   # удалить стандартные куб/свет/камеру

# камелёк (цилиндрическая печь)
K_R = 0.55           # радиус цилиндра
K_BODY_H = 1.35      # высота цилиндрической части
K_WALL = 0.08        # толщина стенок
K_OPEN_W = 0.70      # ширина арки для дров
K_OPEN_H = 0.95      # высота арки от пола
K_CONE_H = 0.55      # высота конуса-перехода к трубе
K_PIPE_R = 0.17      # радиус трубы
K_FACE = 'W'         # куда смотрит арка: 'W', 'E', 'S' или 'N'

# яркие нереалистичные цвета (R, G, B от 0 до 1)
COL = {
    "log":    (1.00, 0.40, 0.70),   # розовые брёвна
    "log_d":  (0.55, 0.30, 0.95),   # фиолетовые брёвна
    "turf":   (0.50, 1.00, 0.20),   # салатовая крыша
    "earth":  (0.10, 0.60, 1.00),   # голубая завалинка
    "floor":  (1.00, 0.90, 0.20),   # жёлтый пол
    "plank":  (1.00, 0.50, 0.10),   # оранжевые дверь и рамы
    "ice":    (0.60, 1.00, 1.00),   # окна
    "clay":   (0.90, 0.10, 0.15),   # красный камелёк
    "stone":  (0.30, 0.90, 0.80),   # бирюзовая подина
    "fire":   (1.00, 0.45, 0.08),   # огонь
    "table":  (0.00, 0.90, 0.90),   # бирюзовый стол
    "chair":  (0.10, 0.80, 0.20),   # зелёный стул
}
SKY = (0.85, 0.75, 1.00)            # цвет фона
# =========================================================

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
def make_mat(name, color, rough=0.6, alpha=1.0, emit=None):
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
M["ice"] = make_mat("ice", COL["ice"], rough=0.1, alpha=0.5)
M["fire"] = make_mat("fire", COL["fire"], rough=0.5, emit=COL["fire"])


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


def box(name, size, loc, mat=None, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    return _finish(bpy.context.active_object, name, mat, rot, size)


def cyl(name, r, depth, loc, mat, rot=None, verts=14):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r,
                                        depth=depth, location=loc)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _finish(o, name, mat, rot)


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
        for i, p in enumerate(wall_positions(side)):
            base, top = wall_pts(side, p)
            mat = M["log"] if i % 2 == 0 else M["log_d"]   # розовый/фиолетовый
            for (s, e) in free_intervals(p, ops):
                if e - s < 0.03:
                    continue
                rod("log_" + side, at(base, top, s), at(base, top, e),
                    LOG_R, mat)


def panel(side, p0, p1, t0, t1, thick, mat, name):
    """Плоская панель в наклонной плоскости стены (окно)."""
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
    # окна и рамы
    for (side, p0, p1, t0, t1) in OPENINGS[1:]:
        panel(side, p0, p1, t0, t1, 0.04, M["ice"], "window")
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


# ---------------------- крыша ----------------------
def build_roof():
    objs = []
    n = int((2 * tb) / 0.2) + 1
    for k in range(n):
        y = -tb + 2 * tb * k / (n - 1)
        objs.append(rod("roof_pole", Vector((-ta - 0.25, y, H + 0.07)),
                        Vector((ta + 0.25, y, H + 0.07)), 0.07,
                        M["log_d"], verts=10))
    objs.append(box("roof", (2 * ta + 0.7, 2 * tb + 0.7, 0.22),
                    (0, 0, H + 0.25), M["turf"]))
    if BUILD_KAMELEK:
        fx, fy = a - 0.95, b - 1.0
        objs.append(rod("chimney_top", Vector((fx, fy, H)),
                        Vector((fx, fy, H + 0.95)), K_PIPE_R, M["clay"]))
        objs.append(cyl("chimney_cap", K_PIPE_R + 0.06, 0.07,
                        (fx, fy, H + 0.95), M["clay"]))
    if not ROOF_VISIBLE:
        for o in objs:
            o.hide_viewport = True
            o.hide_render = True


# ---------------------- завалинка и пол ----------------------
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
    box("floor", (WIDTH + 0.4, LENGTH + 0.4, 0.1), (0, 0, -0.03), M["floor"])


# ---------------------- камелёк ----------------------
def bool_cut(target, cutter):
    """Вычесть cutter из target и удалить cutter."""
    mod = target.modifiers.new("cut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    try:
        mod.solver = 'EXACT'
    except Exception:
        pass
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def build_kamelek():
    """Цилиндрическая печь с аркой для дров от самого пола."""
    dirs = {'W': (-1, 0), 'E': (1, 0), 'S': (0, -1), 'N': (0, 1)}
    dx, dy = dirs[K_FACE]
    dirv = Vector((dx, dy, 0))
    perp = Vector((-dy, dx, 0))
    cx, cy = a - 0.95, b - 1.0
    c = Vector((cx, cy, 0))
    along_x = (dx != 0)
    r = K_R

    # полый цилиндр
    body = cyl("kamelek", r, K_BODY_H, (cx, cy, K_BODY_H / 2),
               M["clay"], verts=48)
    inner = cyl("kamelek_inner", r - K_WALL, K_BODY_H - 0.07,
                (cx, cy, (K_BODY_H - 0.17) / 2), None, verts=48)
    bool_cut(body, inner)

    # арка для дров: прямоугольник + полукруг сверху, от самого пола
    L = r + 0.15
    mid = c + dirv * (L / 2 - 0.05)
    rect_h = K_OPEN_H - K_OPEN_W / 2
    if along_x:
        rect = box("cut_rect", (L, K_OPEN_W, rect_h + 0.1),
                   (mid.x, mid.y, rect_h / 2 - 0.05))
        arch = cyl("cut_arch", K_OPEN_W / 2, L, (mid.x, mid.y, rect_h),
                   None, rot=(0, math.radians(90), 0), verts=32)
    else:
        rect = box("cut_rect", (K_OPEN_W, L, rect_h + 0.1),
                   (mid.x, mid.y, rect_h / 2 - 0.05))
        arch = cyl("cut_arch", K_OPEN_W / 2, L, (mid.x, mid.y, rect_h),
                   None, rot=(math.radians(90), 0, 0), verts=32)
    bool_cut(body, rect)
    bool_cut(body, arch)

    # конус-переход и труба (стыкуется с трубой на крыше)
    cone("kamelek_cone", r, K_PIPE_R, K_CONE_H,
         (cx, cy, K_BODY_H + K_CONE_H / 2), M["clay"], verts=48)
    rod("kamelek_pipe", Vector((cx, cy, K_BODY_H + K_CONE_H)),
        Vector((cx, cy, H + 0.1)), K_PIPE_R, M["clay"], verts=32)

    # подина внутри
    cyl("kamelek_floor", r - K_WALL + 0.01, 0.05, (cx, cy, 0.025),
        M["stone"], verts=48)

    # дрова шалашиком и огонь
    cf = c + dirv * 0.12
    for k in (-1, 0, 1):
        base = cf + dirv * 0.18 + perp * (0.17 * k)
        rod("firewood", Vector((base.x, base.y, 0.07)),
            Vector((cf.x, cf.y, 0.5)), 0.04, M["log_d"], verts=10)
    cone("fire", 0.15, 0.0, 0.4, (cf.x, cf.y, 0.25), M["fire"], verts=12)

    # тёплый свет от огня
    lp = c + dirv * (r + 0.35)
    bpy.ops.object.light_add(type='POINT', location=(lp.x, lp.y, 0.45))
    lamp = bpy.context.active_object
    lamp.name = "fire_light"
    lamp.data.color = COL["fire"]
    lamp.data.energy = 160


# ---------------------- мебель: простой стол и стул ----------------------
def build_furniture():
    # стол: столешница + 4 ножки-коробки
    tx, ty = 0.0, 0.8
    box("table_top", (1.0, 0.7, 0.06), (tx, ty, 0.75), M["table"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("table_leg", (0.07, 0.07, 0.72),
                (tx + sx * 0.43, ty + sy * 0.28, 0.36), M["table"])

    # стул: сиденье + 4 ножки + спинка
    cx, cy = 0.0, 1.5
    box("chair_seat", (0.45, 0.45, 0.05), (cx, cy, 0.45), M["chair"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("chair_leg", (0.05, 0.05, 0.43),
                (cx + sx * 0.19, cy + sy * 0.19, 0.215), M["chair"])
    box("chair_back", (0.45, 0.05, 0.45), (cx, cy + 0.2, 0.7), M["chair"])


# ---------------------- свет, камера, фон ----------------------
def build_scene_setup():
    bpy.ops.object.light_add(type='SUN', location=(8, -8, 12))
    sun = bpy.context.active_object
    sun.name = "sun"
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sun.data.energy = 3.5

    bpy.ops.object.camera_add(location=(8.0, -9.0, 5.0))
    cam = bpy.context.active_object
    cam.name = "camera"
    d = Vector((0, 0, 1.3)) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (*SKY, 1.0)
        bg.inputs[1].default_value = 1.0


# ---------------------- сборка ----------------------
build_base()
build_walls()
build_openings()
build_roof()
if BUILD_KAMELEK:
    build_kamelek()
build_furniture()
build_scene_setup()
print("Балаган готов!")
