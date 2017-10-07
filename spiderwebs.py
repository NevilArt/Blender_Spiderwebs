from mathutils import Vector, Matrix, geometry
from math import pi, inf, sin
from random import random, randint, shuffle, sample, seed
import numpy as np
import bpy
import bmesh
import time
from bpy.types import Operator
from bpy.props import IntProperty, FloatProperty, BoolProperty


bl_info = {
    "name": "Spider Webs",
    "author": "Maxime Herpin",
    "version": (1, 0),
    "blender": (2, 79, 0),
    "location": "View3D > Add > Mesh > New Object",
    "description": "Adds a new spider web object",
    "warning": "",
    "wiki_url": "",
    "category": "Add Mesh",
    }



class Add_Spider_Web(Operator):
    """Create a new web Object"""
    bl_idname = "mesh.add_spider_web"
    bl_label = "Add Spider Web Object"
    bl_options = {'REGISTER', 'UNDO'}

    gravity = FloatProperty(name="gravity_strength", default=1)
    number = IntProperty(name="number of webs", default=1, min=1)
    draw_3d = BoolProperty(name="generate web strands", default=False)
    draw_curve = BoolProperty(name="generate web strands", default=True)
    draw_2d = BoolProperty(name="create textures and planes", default=False)
    texture_size = IntProperty(name="texture size", default=1024, min=1)
    SeedProp = IntProperty(name='seed', default=0)

    def execute(self, context):
        seed(self.SeedProp)
        Webs(webs_number=self.number, gravity_strength=self.gravity, draw_3d=self.draw_3d, draw_2d=self.draw_2d, texture_size=self.texture_size, draw_curve=self.draw_curve)

        return {'FINISHED'}


class Thread:
    def __init__(self, points=[], thread_type='basic', web_parent=None):
        self.points = points
        self.points = points
        self.thread_type = thread_type
        self.web_parent = web_parent
        self.gravity_strength = web_parent.gravity_strength

    def position_on_curve(self, segment_index, t, randomness=0):
        if randomness > 0:
            random_vect = Vector((random(), random(), random())) * randomness
        else:
            random_vect = Vector((0, 0, 0))
        point_a, point_c = self.web_parent.verts[self.points[segment_index]], self.web_parent.verts[self.points[segment_index+1]]
        if self.thread_type == 'frame':
            point_b = (point_a + point_c)/2 + (point_a-point_c).length * (self.web_parent.position - (point_a + point_c)/2)*0.05
            point_b += .2 * (point_a-point_c).length * self.gravity_strength * Vector((0, 0, -1))
        elif self.thread_type == 'support':
            point_b = (point_a + point_c)/2 + (point_a-point_c).length * (self.web_parent.position - (point_a + point_c)/2)*.4
            point_b += .2 * (point_a - point_c).length * self.gravity_strength * Vector((0, 0, -1))
        elif self.thread_type == 'filling':
            point_b = (point_a+point_c)/2 + .3 * (point_a - point_c).length * self.gravity_strength * Vector((0, 0, -1))

        elif self.thread_type == 'hub':
            point_b = (point_a+point_c)/2 + .3 * (point_a - point_c).length * self.gravity_strength * Vector((0, 0, -1))

        elif self.thread_type == 'radial':
            vect = point_a - point_c
            vect.normalize()
            z = vect.z
            z = .5 + z/2
            point_b = (point_a + point_c)/2 + .3 * self.gravity_strength * z * Vector((0, 0, -1))

        point_b.z = max(point_b.z, 0)

        curve_point = (1-t)**2 * point_a + 2*(1-t)*t * (point_b + random_vect * (point_a - point_c).length) + t**2 * point_c
        return curve_point

    def to_vectors(self):
        return[self.web_parent.verts[i] for i in self.points]

    def to_edges(self):
        edges = []
        if len(self.points) > 0:
            current_point = self.points[0]
            for i in range(1, len(self.points)):
                edges.append((current_point, self.points[i]))
                current_point = self.points[i]
            edges.reverse()
        return edges


class Webs:
    def __init__(self, webs_number, gravity_strength, draw_3d=False, draw_curve=False, draw_2d=False, texture_size=1024):
        self.grease_points = get_grease_points()
        self.anchor_points = [i for i in self.grease_points]
        self.webs = []
        self.verts = []
        self.edges = []
        self.threads_vects = []
        self.gravity_strength = gravity_strength

        self.clock = Clock()
        self.clock.begin_clock('generating_webs')
        self.generate_webs(webs_number)
        self.clock.end_clock('generating_webs')
        if draw_curve:
            self.draw_curve()
        if draw_3d:
            self.draw_3d()
        if draw_2d:
            self.draw_2d(texture_size)

    def generate_webs(self, number):
        for i in range(number):
            web = Web(anchor_points_candidates=self.anchor_points, gravity_strength=self.gravity_strength)
            self.webs.append(web)
            new_anchors = [web.verts[i] for i in sample(range(len(web.verts)), 10)]
            self.anchor_points.extend(new_anchors)
            n = len(self.verts)
            self.verts.extend(web.verts)
            self.edges.extend(web.get_edges(n))
            self.threads_vects.extend(web.get_threads_vects())

    def draw_3d(self):
        scene = bpy.context.scene

        me = bpy.data.meshes.new("webs")
        me.from_pydata(self.verts, self.edges, [])
        obj = bpy.data.objects.new("webs", me)
        self.object = obj
        scene.objects.link(obj)
        obj.select = False

    def draw_curve(self):
        curve_data = bpy.data.curves.new('web', type='CURVE')
        curve_data.dimensions = '3D'

        # map coords to spline
        for thread in self.threads_vects:
            polyline = curve_data.splines.new('POLY')
            polyline.points.add(len(thread)-1)
            for i, coord in enumerate(thread):
                x, y, z = coord
                polyline.points[i].co = (x, y, z, 1)

            # create Object
        curveOB = bpy.data.objects.new('web', curve_data)
        curve_data.bevel_depth = 0.0005
        curve_data.bevel_resolution = 2
        curve_data.fill_mode = 'FULL'

        # attach to scene and validate context
        scene = bpy.context.scene
        scene.objects.link(curveOB)
        scene.objects.active = curveOB
        curveOB.select = True

    def draw_2d(self, res=1024):
        scene = bpy.context.scene
        self.clock.begin_clock('preparing_2d_data')
        anchors = []
        planes = []
        locations = []
        edges_vect = []
        uvs = []
        for i, web in enumerate(self.webs):
            normal = web.plane_normal
            index = len(planes)
            appending = True
            if i > 0:
                for j, n in enumerate(planes):
                    if n.angle(normal) < pi/12 and (web.center - locations[j]).length < 1.5:
                        anchors[j].extend(web.anchor_points)
                        edges_vect[j].extend(web.get_edges_vect())
                        appending = False
                        break
            if appending:
                planes.append(normal)
                anchors.append(web.anchor_points)
                edges_vect.append(web.get_edges_vect())
                uvs.append([])
                locations.append(web.center)

        self.clock.end_clock('preparing_2d_data')
        self.clock.begin_clock('painting_pixels')
        res_x = res * len(edges_vect)
        # pixels = [(0, 0, 0, 0) for i in range(res * res_x)]
        pixels = np.zeros((res*res_x))

        for i, edges in enumerate(edges_vect):
            points = [k for l in edges for k in l]
            points_2d, quat, pos, scale = points_to_uv_coords(points, planes[i])
            segments = [(points_2d[i], points_2d[i+1]) for i in range(0, len(points_2d)-1, 2)]
            curr_anchors = convex_indexing(anchors[i], planes[i])
            anchors_uv = []
            for an in curr_anchors:
                uv_coord = an.copy()
                uv_coord.rotate(quat)
                uv_coord.resize_2d()
                uv_coord -= pos
                uv_coord /= scale
                n = len(edges_vect)
                uv_coord.x /= n
                uv_coord += Vector((1/n, 0)) * i
                anchors_uv.append(uv_coord)
            uvs[i] = anchors_uv

            for segment in segments:
                p1, p2 = segment
                x0, y0 = p1
                x1, y1 = p2
                x0 = int(x0 * res) + i * res
                x1 = int(x1 * res) + i * res
                y0 = int(y0 * res)
                y1 = int(y1 * res)
                draw_line(pixels, x0, y0, x1, y1, .1, res, res_x)

        self.clock.end_clock('painting_pixels')
        self.clock.begin_clock('creating_image')
        for img in bpy.data.images:
            if "web" in img.name:
                img.user_clear()
        for img in bpy.data.images:
            if "web" in img.name:
                if not img.users:
                    bpy.data.images.remove(img)


        image = bpy.data.images.new("web_packed", width=res_x, height=res)
        # pixels = [chan for px in pixels for chan in px]
        # image.pixels = pixels.flatten
        # image.pixels = pixels.flatten('F').tolist()
        image.pixels = pixels.repeat(4)
        # image.filepath_raw = "/tmp/temp.png"
        # image.file_format = 'PNG'
        # image.save()
        self.clock.end_clock('creating_image')
        self.clock.begin_clock('creating_planes')
        objects = []
        bpy.ops.object.select_all(action='DESELECT')

        for i, verts in enumerate(anchors):
            verts = convex_indexing(verts, planes[i])
            bm = bmesh.new()
            for v in verts:
                bm.verts.new(v)
            bm.faces.new(bm.verts)

            bm.normal_update()
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()
            bm.faces.layers.tex.verify()

            face = bm.faces[-1]
            for j, loop in enumerate(face.loops):
                uv = loop[uv_layer].uv
                pos = uvs[i][j]
                uv[0] = pos.x
                uv[1] = 1 - pos.y

            me = bpy.data.meshes.new("web_plane")
            bm.to_mesh(me)

            ob = bpy.data.objects.new("web_plane", me)
            bpy.context.scene.objects.link(ob)
            bpy.context.scene.update()
            ob.select = True
            objects.append(ob)
            bpy.context.scene.objects.active = ob
        bpy.ops.object.join()
        ob = bpy.context.scene.objects.active
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.quads_convert_to_tris()
        bpy.ops.mesh.subdivide(number_cuts=2, smoothness=1)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.shade_smooth()

        self.clock.end_clock('creating_planes')


class Web:

    def __init__(self, gravity_strength, draw=False, draw_2d=False, curve=False, anchor_points_candidates=[]):
        self.verts = []
        self.threads = []
        self.frame_threads = []
        self.support_threads = []
        self.position = Vector((0, 0, 0))
        self.randomness = .2
        self.object = None
        self.anchor_points, self.plane_normal = find_anchor_points(anchor_points_candidates, min_angle=pi / 16)
        self.center, self.normal = center_normal(self.anchor_points)
        self.position = self.center
        self.center_index = 0
        self.hub_indexes = []
        self.uv_coords = []
        self.gravity_strength = gravity_strength

        self.add_frame_threads(self.anchor_points)
        self.add_support_threads(.3, 1)
        self.add_radial_threads(pi/10, self.randomness)
        self.add_filling_threads()
        if draw_2d:
            self.draw_2d(1024)
            self.draw_plane()

        if draw:
            self.draw_3d()
            self.setup_cloth_sim()
            if curve:
                self.convert_to_curve()
        # self.smooth_hub()

    def add_frame_threads(self, anchor_points):
        n = len(self.verts)
        for i in range(0, len(anchor_points)):
            self.verts.append(anchor_points[i])
            self.threads.append(Thread([n+i, (n+i+1) % len(anchor_points)], thread_type='frame', web_parent=self))
            self.frame_threads.append(i)

    def resolution(self, resolution=5, threads=[], adaptative=False, randomness=0):
        default_res = resolution
        for thread in threads:
            if adaptative:
                length = (self.verts[thread.points[0]] - self.verts[thread.points[-1]]).length
                resolution = int(length * default_res)
            new_thread_points = []
            for i in range(len(thread.points)-1):
                new_points_indexes = [thread.points[i]]
                for j in range(1, resolution):
                    new_point = thread.position_on_curve(i, max(0, j + random()/2 - .25)/resolution, randomness/resolution)
                    n = len(self.verts)
                    self.verts.append(new_point)
                    new_points_indexes.append(n)
                new_points_indexes.append(thread.points[i+1])
                new_thread_points.extend(new_points_indexes)
            thread.points = new_thread_points

    def add_support_threads(self, reach_coef=.3, min_distance=.5):
        from_threads = self.threads
        new_indexes = [0]
        i = 0
        thread_max_index = len(from_threads)
        while i < thread_max_index:
            thread_a, thread_b = (from_threads[i], from_threads[(i+1) % thread_max_index])
            distance = (self.anchor_points[(i+1)%len(self.anchor_points)] - self.anchor_points[i]).length
            if distance < min_distance and i < thread_max_index - 1:
                thread_b = from_threads[(i+2) % thread_max_index]
                i += 1
                new_indexes.append(i)
            new_point_a = thread_a.position_on_curve(-2, 1 - reach_coef)
            new_point_b = thread_b.position_on_curve(0, reach_coef)
            n = len(self.verts)
            self.verts.append(new_point_a)
            self.verts.append(new_point_b)
            thread_a.points.insert(-1, n)
            thread_b.points.insert(1, n+1)
            threads_length = len(self.threads)
            new_indexes.append(threads_length)
            new_indexes.append(i+1)
            self.threads.append(Thread([n, n+1], 'support', self))
            i += 1

        self.threads = [self.threads[i] for i in new_indexes]

    def add_radial_threads(self, thread_angle, randomness=.2):
        curr_vect = Vector((0, 0, 1))
        new_threads = []
        center_index = len(self.verts)
        self.center_index = center_index
        center_coords = self.center + Vector((0, 0, -1)) * .6 * self.gravity_strength
        center_coords.z = max(center_coords.z, 0)
        self.center = center_coords
        self.verts.append(center_coords)
        for thread in self.threads:
            draw_radial = True
            if thread.thread_type == 'support':
                points = thread.to_vectors()
                before_points = [thread.points[0]]
                after_points = [thread.points[-1]]
                position_index = 0

            elif thread.thread_type == 'frame':
                if len(thread.points) == 4:
                    points = thread.to_vectors()
                    points = [points[1], points[2]]
                    before_points = thread.points[:2]
                    after_points = thread.points[2:]
                    position_index = 1
                else:
                    draw_radial = False

            if draw_radial:
                thread_length = (points[1] - points[0]).length
                thread_dist = ((points[0] + points[1])/2 - self.position).length
                angle_a = curr_vect.angle(points[0] - self.position)
                angle_b = curr_vect.angle(points[1] - self.position)
                if max(angle_a, angle_b) > thread_angle:
                    if angle_a > angle_b:
                        angle_a, angle_b = angle_b, angle_a
                        thread.points.reverse()
                        points.reverse()
                    coef_points = []
                    increment = thread_angle * thread_dist / thread_length
                    coef = increment/2
                    while coef < 1:
                        coef_points.append(coef)
                        coef += ((1 - randomness) * 1 + randomness * (.5 - random())) * increment

                    new_points = [i for i in before_points]

                    for coef in coef_points:
                        new_point = thread.position_on_curve(position_index, coef)
                        n = len(self.verts)
                        self.verts.append(new_point)
                        new_points.append(n)
                        new_threads.append(Thread([center_index, n], 'radial', self))
                        curr_vect = new_point - self.center
                    new_points.extend(after_points)
                    thread.points = new_points
        self.threads.extend(new_threads)

    def add_filling_threads(self, probability=.95, distance=1):
        self.resolution(30, [i for i in self.threads if i.thread_type == 'radial'], adaptative=True, randomness=.5)
        cond = False
        radial_beginning_index = -1
        center_indexes = []
        center_limits = []
        while not cond:
            radial_beginning_index += 1
            cond = self.threads[radial_beginning_index].thread_type == 'radial'

        n = len(self.threads)

        for i in range(radial_beginning_index, n-1):
            for k in range(2):
                center_indexes.append(self.threads[i].points[0])
                self.threads[i].points.pop(0)
            if len(self.threads[i].points) > 0:
                center_limits.append(self.threads[i].points[0])
            else:
                pass
            next_thread = i + 1
            if next_thread == n - 1:
                next_thread = radial_beginning_index
            links = dict([(i, False) for i in self.threads[next_thread].points])
            for j, point_index in enumerate(self.threads[i].points):
                used_proba = probability
                if (self.verts[point_index] - self.center).length > distance:
                    used_proba /= 10
                if random() < used_proba:
                    point = self.verts[point_index]
                    dist = inf
                    neighbour = point_index
                    for new_point_index in self.threads[next_thread].points:
                        new_point = self.verts[new_point_index]
                        new_dist = (point - new_point).length
                        if new_dist < dist and not links[new_point_index]:
                            dist = new_dist
                            neighbour = new_point_index
                    thread_type = 'filling' if j >0 else 'hub'
                    self.threads.append(Thread([point_index, neighbour], thread_type, self))
                    links[neighbour] = True

        center_indexes = list(set(center_indexes))
        for point_index in center_indexes:
            random_indexes = sample(range(len(center_limits)), 2)
            # point_a, point_b = [self.verts[center_limits[i]] for i in random_indexes]
            index_a = randint(0, len(center_limits) - 1)
            point_a = self.verts[center_limits[index_a]]
            point_b = self.verts[center_limits[(index_a + len(center_limits) // 2) % len(center_limits)]]
            factor = random()
            self.verts[point_index] = factor * point_a + (1-factor) * point_b
        hub_indexes = [i for i in center_indexes]
        center_indexes.extend(center_limits)
        links = {i:[] for i in center_indexes}

        for l in range(5):
            for point_index in hub_indexes:
                point = self.verts[point_index]
                dist = inf
                neighbour = 0
                for new_point_index in center_indexes:
                    if new_point_index != point_index and len(links[new_point_index]) < l+3:
                        new_point = self.verts[new_point_index]
                        new_dist = (point - new_point).length
                        if new_dist < dist and point_index not in links[new_point_index] and new_point_index not in links[point_index] and not(new_point_index in center_limits and point_index in center_limits):
                            dist = new_dist
                            neighbour = new_point_index
                self.threads.append(Thread([point_index, neighbour], 'hub', self))
                links[point_index].append(neighbour)
                links[neighbour].append(point_index)

        self.hub_indexes = center_indexes
        self.resolution(5, [i for i in self.threads if i.thread_type == 'filling'], adaptative=False)
        self.resolution(5, [i for i in self.threads if i.thread_type == 'hub'], adaptative=False)

    def get_edges(self, shift=0):
        edges = []
        for thread in self.threads:
            if not (thread.thread_type == 'frame' and len(thread.points) == 2):
                edges.extend(thread.to_edges())
        if shift > 0:
            edges = [(i[0] + shift, i[1] + shift) for i in edges]
        return edges

    def get_threads_vects(self):
        threads_vects = [[]for thread in self.threads] # if not (thread.thread_type == 'frame' and len(thread.points) == 2)]
        for i, thread in enumerate(self.threads):
            if not (thread.thread_type == 'frame' and len(thread.points) == 2):
                threads_vects[i] = [self.verts[j] for j in thread.points]
        return threads_vects

    def get_edges_vect(self):
        edges = self.get_edges(0)
        edges_vect = [(self.verts[i[0]], self.verts[i[1]]) for i in edges]
        return edges_vect

    def draw_3d(self, break_proba=0):
        scene = bpy.context.scene
        if len(bpy.context.selected_objects)>0:
            bpy.ops.object.delete(use_global=False)

        edges = []
        for thread in self.threads:
            edges.extend(thread.to_edges())
        new_edges = []
        for i in edges:
            if random() < (1 - break_proba):
                new_edges.append(i)
        edges = new_edges

        # self.verts = self.anchor_points

        me = bpy.data.meshes.new("web")
        me.from_pydata(self.verts, edges, [])
        obj = bpy.data.objects.new("web", me)
        self.object = obj
        scene.objects.link(obj)
        obj.select = True

    def draw_plane(self):
        scene = bpy.context.scene
        if len(bpy.context.selected_objects)>0:
            bpy.ops.object.delete(use_global=False)

        verts = self.anchor_points

        bm = bmesh.new()
        for v in verts:
            bm.verts.new(v)
        bm.faces.new(bm.verts)

        bm.normal_update()
        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        face = bm.faces[-1]
        for i, loop in enumerate(face.loops):
            uv = loop[uv_layer].uv
            pos = self.uv_coords[i]
            uv[0] = pos.x
            uv[1] = 1 - pos.y

        me = bpy.data.meshes.new("web_plane")
        bm.to_mesh(me)

        ob = bpy.data.objects.new("web_plane", me)
        ob.active_material = bpy.data.materials.get("alpha_web")
        bpy.context.scene.objects.link(ob)
        bpy.context.scene.update()

    def draw_2d(self, res=1024):
        normal = self.plane_normal
        up = Vector((0,0,1))
        quat = normal.rotation_difference(up)
        points_2d = []
        boundaries = [0,0,0,0]
        for point in self.verts:
            new_point = point.copy()
            new_point.rotate(quat)
            # point.rotate(quat)
            new_point.resize_2d()
            points_2d.append(new_point)
            x,y = new_point

            if x < boundaries[0]:
                boundaries[0] = x

            if y < boundaries[1]:
                boundaries[1] = y

            if x > boundaries[2]:
                boundaries[2] = x

            if y > boundaries[3]:
                boundaries[3] = y
        scale = max(boundaries[2] - boundaries[0], boundaries[3] - boundaries[1])
        # scale *= res/(res+1)
        pos = Vector((boundaries[0], boundaries[1]))
        uv_pos = []
        self.uv_coords = uv_pos
        for i , point in enumerate(points_2d):
            point -= pos
            point /= scale
            if i < len(self.anchor_points):
                uv_pos.append(point)


        pixels = [(0,0,0,0) for i in range(res**2)]
        segments = []

        for thread in self.threads:
            for i in range(len(thread.points)-1):
                segments.append((points_2d[thread.points[i]], points_2d[thread.points[i+1]]))

        for segment in segments:
            p1, p2 = segment
            x0, y0 = p1
            x1, y1 = p2
            x0 = int(x0 * res)
            x1 = int(x1 * res)
            y0 = int(y0 * res)
            y1 = int(y1 * res)
            draw_line(pixels, x0, y0, x1, y1, (1, 1, 1, 1), res)

        if bpy.data.images.get('web1') is None or [i for i in bpy.data.images['web1'].size] != [res, res]:
            image = bpy.data.images.new("web1", width=res, height=res)
        else:
            image = bpy.data.images.get('web1')
        pixels = [chan for px in pixels for chan in px]
        image.pixels = pixels
        image.filepath_raw = "/tmp/temp.png"
        image.file_format = 'PNG'
        image.save()

    def smooth_hub(self):
        vg = self.object.vertex_groups.new("hub")
        vg.add([i for i in self.hub_indexes], 1, "ADD")
        smooth = self.object.modifiers.new("smooth", type="SMOOTH")
        smooth.vertex_group = 'hub'
        smooth.iterations = 2

    def setup_cloth_sim(self):
        vg = self.object.vertex_groups.new("cloth_pinning")
        vg.add([i for i in range(len(self.anchor_points))], 1, "ADD")
        cloth_sim = self.object.modifiers.new("cloth", type="CLOTH")
        cloth_sim.settings.use_pin_cloth = True
        cloth_sim.settings.vertex_group_mass = "cloth_pinning"

    def convert_to_curve(self):
        obj = self.object
        obj.select = True
        bpy.context.scene.objects.active = obj
        bpy.ops.object.convert(target='CURVE')
        obj.data.fill_mode = 'FULL'
        obj.data.bevel_resolution = 2
        obj.data.bevel_depth = .0005
        bpy.context.object.data.fill_mode = 'FULL'
        bpy.ops.object.shade_smooth()
        obj.select = False
        # obj.active_material = bpy.data.materials['wire']


class Clock:
    def __init__(self):
        self.clocks = {}

    def begin_clock(self, name):
        self.clocks[name] = time.time()

    def end_clock(self, name):
        dt = time.time() - self.clocks.pop(name)
        print(name, dt)


def draw_point(pixels, x, y, color, alpha, res, res_x):
    y = res - y
    coord = min(y * res_x + x, res *res_x - 1)
    # pixels[0, coord] = min(pixels[0, coord] + color * alpha, 1.0)
    pixels[coord] += (1 - pixels[coord])/2 * alpha
    # for i in range(4):
    #     pixels[i, coord] = min(pixels[i, coord] + color * alpha, 1.0)   #tuple([min(color[i]*alpha + pixels[coord][i], 1) for i in range(4)])


def draw_line(pixels, x0, y0, x1, y1, color, res, res_x=None):
    "Bresenham's line algorithm, with antialiasing"
    if res_x == None:
        res_x = res
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    if dx > dy:
        err = dx / 2.0
        grad = 1 if dx ==0 else dy/dx
        y1 = y
        y2 = y + 1
        while x != x1:
            error1 = y1 - y
            error2 = y2 - (y+1)
            side1 = sign(error1)
            side2 = sign(error2)
            error1, error2 = abs(error1), abs(error2)
            draw_point(pixels, x, y + side1, color, error1, res, res_x)

            # draw_point(pixels, x, y + 1 + side2, color, error2, res, res_x)
            # draw_point(pixels, x, y + 1, color, 1 - error2, res, res_x)

            draw_point(pixels, x, y, color, 1 - error1, res, res_x)

            y1 += grad * sy
            y2 += grad * sy
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        grad = 1 if dy == 0 else dx / dy
        x1 = x
        x2 = x + 1
        while y != y1:
            error1 = x1 - x
            error2 = x2 - (x+1)
            side1, side2 = sign(error1), sign(error2)
            error1, error2 = abs(error1), abs(error2)
            draw_point(pixels, x + side1, y, color, error1, res, res_x)
            # draw_point(pixels, x + 1 + side2, y, color, error2, res, res_x)
            draw_point(pixels, x, y, color, 1 - error1, res, res_x)
            # draw_point(pixels, x + 1, y, color, 1 - error2, res, res_x)
            x1 += grad * sx
            x2 += grad * sx
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
        draw_point(pixels, x, y, color, 1, res, res_x)


def sign(x):
    return 1 if x>0 else -1 if x<0 else 0


def web_hull(points, center):
    new_points = [points[0]]
    points_left = [i for i in points if i != new_points[0]]
    vect_a = new_points[0] - center
    vect_b = points[1] - center
    curr_neighbour = points[1]
    min_angle = vect_a.angle(vect_b)
    while len(new_points) < len(points):
        for i in range(len(points_left)):
            vect_b = points_left[i]
            angle = vect_a.angle(vect_b)
            if angle < min_angle:
                min_angle = angle
                curr_neighbour = points_left[i]
        new_points.append(curr_neighbour)
        points_left = [i for i in points_left if i != curr_neighbour]
        vect_a = curr_neighbour - center
        min_angle = 10
    return new_points


def simple_polygon(vertices=5, randomness=.1):
    vector = Vector((1, 0, 0))
    new_points = []
    M = Matrix.Rotation(-2 * pi / vertices, 4, 'Y')
    N = Matrix.Rotation(pi / 4, 4, 'X')
    for i in range(vertices):
        M = Matrix.Rotation(-2 * pi / vertices, 4, 'Y')
        new_points.append(((1-randomness) + randomness * (.5 - random())) * vector)
        vector = M * vector
    return [N * i for i in new_points]


def center_normal(points):
    center = Vector((0, 0, 0))
    for i in points:
        center += i
    center /= len(points)
    normals = []
    curr_vect = points[0] - center
    for point in points[1:]:
        new_vect = point - center
        normals.append(new_vect.cross(curr_vect))
        curr_vect = new_vect
    normal = Vector((0, 0, 0))
    normal = (points[0] - center).cross(points[len(points)//4] - center)
    # for i in normals:
    #     normal += i
    normal.normalize()
    return center, normal


def get_grease_points():
    points = []
    gp = bpy.context.scene.grease_pencil
    if gp is not None and gp.layers.active is not None and gp.layers.active.active_frame is not None and len(gp.layers.active.active_frame.strokes) > 0:
        for stroke in gp.layers.active.active_frame.strokes:
            points.extend([i.co.copy() for i in stroke.points.values()])
    return points


def find_anchor_points(points, min_angle=2 * pi / 8):
    points, plane_normal = setup_anchors(points)

    center = Vector((0, 0, 0))
    for i in points:
        center += i
    center /= max(1, len(points))



    # for i in range(1, len(points)):
    #     dist = (points[i-1] - points[i]).length
    #     curr_index = i
    #     for j in range(i+1, len(points)):
    #         new_dist = (points[i-1] - points[j]).length
    #         if new_dist < dist:
    #             dist = new_dist
    #             curr_index = j
    #     points[i], points[curr_index] = points[curr_index], points[i]
    anchor_points = [points[0]]
    for point in points:
        angle = (center - anchor_points[-1]).angle(center - point)
        if angle >= min_angle:
            anchor_points.append(point)
    return anchor_points, plane_normal


def get_plane_from_points(points):
    locs = [i for i in points]

    com = Vector((0, 0, 0))
    for loc in locs:
        com += loc
    com /= len(locs)
    x, y, z = com

    mat = Matrix([[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    for loc in locs:
        mat[0][0] += (loc[0] - x) ** 2
        mat[0][1] += (loc[0] - x) * (loc[1] - y)
        mat[0][2] += (loc[0] - x) * (loc[2] - z)
        mat[1][0] += (loc[1] - y) * (loc[0] - x)
        mat[1][1] += (loc[1] - y) ** 2
        mat[1][2] += (loc[1] - y) * (loc[2] - z)
        mat[2][0] += (loc[2] - z) * (loc[0] - x)
        mat[2][1] += (loc[2] - z) * (loc[1] - y)
        mat[2][2] += (loc[2] - z) ** 2

    mat.invert()
    itermax = 500
    iter = 0
    vec = Vector((1, 1, 1))
    vec2 = (vec * mat) / (vec * mat).length
    while vec != vec2 and iter < itermax:
        iter += 1
        vec = vec2
        vec2 = (vec * mat) / (vec * mat).length
    normal = vec2

    return com, normal


def setup_anchors(points):
    n = len(points)
    random_indices = sample([i for i in range(len(points))], 20)
    random_selection = [points[i] for i in random_indices]
    plane_co, plane_normal = get_plane_from_points(random_selection)
    new_points = []
    shuffle(points)
    for point in points:
        if abs(geometry.distance_point_to_plane(point, plane_co, plane_normal)) < .6:
            new_points.append(point)

    new_points = convex_indexing(new_points, plane_normal)
    return new_points, plane_normal


def convex_indexing(points, direction):
    new_points = [i.copy() for i in points]
    up = Vector((0,0,1))
    quat = direction.rotation_difference(up)
    for point in new_points:
        point.rotate(quat)
        point.resize_2d()
    convex_indices = geometry.convex_hull_2d(new_points)
    return [points[i] for i in convex_indices]


def points_to_uv_coords(points, normal):
    up = Vector((0, 0, 1))
    quat = normal.rotation_difference(up)
    points_2d = []
    boundaries = [0, 0, 0, 0]
    for point in points:
        new_point = point.copy()
        new_point.rotate(quat)
        new_point.resize_2d()
        points_2d.append(new_point)
        x, y = new_point

        if x < boundaries[0]:
            boundaries[0] = x

        if y < boundaries[1]:
            boundaries[1] = y

        if x > boundaries[2]:
            boundaries[2] = x

        if y > boundaries[3]:
            boundaries[3] = y
    scale = max(boundaries[2] - boundaries[0], boundaries[3] - boundaries[1])
    pos = Vector((boundaries[0], boundaries[1]))
    for i, point in enumerate(points_2d):
        point -= pos
        point /= scale

    return points_2d, quat, pos, scale



def register():
    bpy.utils.register_class(Add_Spider_Web)

def unregister():
    bpy.utils.unregister_class(Add_Spider_Web)

if __name__ == "__main__":
    register()