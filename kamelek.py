# -*- coding: utf-8 -*-
"""
Камелёк (печь) цилиндрической формы для Blender 2.9 - 4.x
Полый глиняный цилиндр, снизу большая арка для дров прямо от пола,
сверху конус-переход и дымовая труба. Внутри дрова, огонь и свет.

Запуск отдельно: Scripting -> Open -> kamelek.py -> Run Script.
Для балагана: в balagan.py удали старый код камелька (hearth, fireplace_hood,
fireplace_pipe, firebox, fire, fire_light) и вставь сюда функцию
build_kamelek(...) - она использует те же имена материалов.
"""
import bpy
import math
from mathutils import Vector

# ======================= ПАРАМЕТРЫ =======================
CX, CY = 1.55, 2.10      # центр печи на полу (как в балагане: правый дальний угол)
R = 0.55                 # внешний радиус цилиндра
BODY_H = 1.35            # высота цилиндрической части
WALL = 0.08              # толщина глиняных стенок
OPEN_W = 0.70            # ширина арки для дров
OPEN_H = 0.95            # высота арки от пола (большое отверстие)
CONE_H = 0.55            # высота конуса-перехода к трубе
PIPE_R = 0.17            # радиус трубы
PIPE_TOP = 2.9           # на какой высоте заканчивается труба
FACE = 'W'               # куда смотрит арка: 'W', 'E', 'S' или 'N'
# =========================================================

DIRS = {'W': (-1, 0), 'E': (1, 0), 'S': (0, -1), 'N': (0, 1)}


# ---------------------- материалы ----------------------
def make_mat(name, color, rough=0.9, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        if emit:
            for key in ("Emission Color", "Emission"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = (*emit, 1.0)
                    break
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 8.0
    m.diffuse_color = (*color, 1.0)
    return m


MAT = {
    "clay": make_mat("kam_clay", (0.66, 0.48, 0.36)),
    "stone": make_mat("kam_stone", (0.35, 0.33, 0.31)),
    "log": make_mat("kam_log", (0.30, 0.18, 0.10)),
    "fire": make_mat("kam_fire", (1.0, 0.45, 0.08), 0.5, emit=(1.0, 0.45, 0.08)),
}


# ---------------------- помощники ----------------------
def _set(o, name, mat, rot=None, scale=None):
    o.name = name
    if rot is not None:
        o.rotation_euler = rot
    if scale is not None:
        o.scale = scale
    if mat:
        o.data.materials.append(mat)
    return o


def cyl(name, r, depth, loc, mat, rot=None, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r,
                                        depth=depth, location=loc)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _set(o, name, mat, rot)


def cone(name, r1, r2, depth, loc, mat, verts=48):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2,
                                    depth=depth, location=loc)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _set(o, name, mat)


def box(name, size, loc, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    return _set(bpy.context.active_object, name, mat, None, size)


def rod(name, p0, p1, r, mat, verts=10):
    d = p1 - p0
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return cyl(name, r, d.length, (p0 + p1) / 2, mat, rot, verts)


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


# ---------------------- сама печь ----------------------
def build_kamelek(cx=CX, cy=CY, r=R, body_h=BODY_H, wall=WALL,
                  open_w=OPEN_W, open_h=OPEN_H, cone_h=CONE_H,
                  pipe_r=PIPE_R, pipe_top=PIPE_TOP, face=FACE):
    dx, dy = DIRS[face]
    dirv = Vector((dx, dy, 0))
    perp = Vector((-dy, dx, 0))
    c = Vector((cx, cy, 0))
    along_x = (dx != 0)

    # 1) полый цилиндр: внешний минус внутренний (потолок 0.12 м остаётся)
    body = cyl("kamelek_body", r, body_h, (cx, cy, body_h / 2), MAT["clay"])
    inner = cyl("kamelek_inner", r - wall, body_h - 0.12 + 0.05,
                (cx, cy, (body_h - 0.12 - 0.05) / 2), None)
    bool_cut(body, inner)

    # 2) арка для дров: прямоугольник + полукруг сверху, от самого пола
    L = r + 0.15
    mid = c + dirv * (L / 2 - 0.05)
    rect_h = open_h - open_w / 2
    if along_x:
        rect = box("cut_rect", (L, open_w, rect_h + 0.1),
                   (mid.x, mid.y, rect_h / 2 - 0.05))
        arch = cyl("cut_arch", open_w / 2, L,
                   (mid.x, mid.y, rect_h), None,
                   rot=(0, math.radians(90), 0), verts=32)
    else:
        rect = box("cut_rect", (open_w, L, rect_h + 0.1),
                   (mid.x, mid.y, rect_h / 2 - 0.05))
        arch = cyl("cut_arch", open_w / 2, L,
                   (mid.x, mid.y, rect_h), None,
                   rot=(math.radians(90), 0, 0), verts=32)
    bool_cut(body, rect)
    bool_cut(body, arch)

    # 3) конус-переход и дымовая труба
    cone("kamelek_cone", r, pipe_r, cone_h,
         (cx, cy, body_h + cone_h / 2), MAT["clay"])
    z0 = body_h + cone_h
    rod("kamelek_pipe", Vector((cx, cy, z0)), Vector((cx, cy, pipe_top)),
        pipe_r, MAT["clay"], verts=32)

    # 4) каменная подина внутри и площадка перед аркой
    cyl("kamelek_floor", r - wall + 0.01, 0.05, (cx, cy, 0.025), MAT["stone"])
    front = c + dirv * (r + 0.2)
    if along_x:
        box("kamelek_apron", (0.5, open_w + 0.4, 0.04),
            (front.x, front.y, 0.02), MAT["stone"])
    else:
        box("kamelek_apron", (open_w + 0.4, 0.5, 0.04),
            (front.x, front.y, 0.02), MAT["stone"])

    # 5) дрова шалашиком и огонь
    centre_fire = c + dirv * 0.12
    for k in (-1, 0, 1):
        base = centre_fire + dirv * 0.18 + perp * (0.17 * k)
        top = centre_fire + dirv * 0.0
        rod("kamelek_firewood", Vector((base.x, base.y, 0.07)),
            Vector((top.x, top.y, 0.5)), 0.04, MAT["log"])
    cone("kamelek_fire", 0.15, 0.0, 0.4,
         (centre_fire.x, centre_fire.y, 0.25), MAT["fire"], verts=12)

    # 6) тёплый свет от огня
    lp = c + dirv * (r + 0.35)
    bpy.ops.object.light_add(type='POINT', location=(lp.x, lp.y, 0.45))
    lamp = bpy.context.active_object
    lamp.name = "kamelek_light"
    lamp.data.color = (1.0, 0.5, 0.15)
    lamp.data.energy = 160


build_kamelek()
print("Камелёк готов!")
