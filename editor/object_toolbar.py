# -*- coding: utf-8 -*-
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Contains the objects toolbar

.. module:: toolbarpage
    :synopsis: Contains the objects toolbar

.. moduleauthor:: Karsten Bock <KarstenBock@gmx.net>
"""

from io import StringIO
import os

from lxml import etree
import yaml
import PyCEGUI
from PyCEGUIOpenGLRenderer import PyCEGUIOpenGLRenderer

from .toolbarpage import ToolbarPage


def parse_file(filename):
    """Parse an fife object definiton file

        Args:

            filename: The path to the object file.

        Returns: A list of object definitions in the file
    """
    root_path = os.path.dirname(filename)
    objects = []
    try:
        tree = etree.parse(filename)
        objects.append(parse_object(tree.getroot(), root_path))
    except etree.XMLSyntaxError as e:
        doc = file(filename, "r")
        line_no = e.position[0] - 2
        lines = doc.readlines()
        first_doc = StringIO(u"".join(lines[:line_no]))
        tree = etree.parse(first_doc)
        root = tree.getroot()
        pi = root.getprevious()
        file_type = pi.text.split("=")[1].replace('"', '').lower()
        if not file_type == "atlas":
            raise RuntimeError("Unexpected file format '%s'" % (filename))
        atlas_def = parse_atlas(root, root_path)
        second_doc = lines[line_no + 1:]
        second_doc.insert(0, "<objects>\n")
        second_doc.append("</objects>\n")
        second_doc = StringIO(u"".join(second_doc))
        tree = etree.parse(second_doc)
        object_defs = tree.getroot().findall("object")
        for obj in object_defs:
            objects.append(parse_object(obj, root_path, atlas_def))
    return objects


def parse_atlas(element, root_path):
    """Parse an atlas definition

        Args:

            element: The etree element that contains the definition

            root_path: The path of the object file the element is in

        Returns: A dictionary with images and their positions in an atlas
    """
    atlas_def = {}
    atlas_def["atlas"] = element
    atlas_def["images"] = {}
    images = element.findall("image")
    for image in images:
        attribs = image.attrib
        image_name = attribs["source"]
        atlas_def["images"][image_name] = image
    return atlas_def


def parse_object(obj, root_path, atlas_def=None):
    """Parse an object definition

        Args:

            obj: The etree element containing the definition

            root_path: The path of the object file the element is in

            atlas_def: A dictionary with images and their positions in an atlas
    """
    obj_def = {}
    obj_def["object"] = dict(obj.attrib)
    if atlas_def:
        image_sources = atlas_def["images"]
    else:
        image_sources = {}
    if int(obj.attrib["static"]) == 0:
        obj_def["actions"] = parse_actions(obj.findall("action"), root_path)
    elif int(obj.attrib["static"]) == 1:
        images = obj.findall("image")
        dir_defs = obj_def["directions"] = {}
        for image in images:
            attrib = dict(image.attrib)
            source = attrib["source"]
            image_def = attrib
            if source in image_sources:
                image_def.update(image_sources[source].attrib)
                image_def["type"] = "atlas"
                image_def["source"] = atlas_def["atlas"].attrib["name"]
            else:
                image_def["type"] = "image"
            source = os.path.join(root_path, image_def["source"])
            image_def["source"] = os.path.abspath(source)
            direction = int(image_def["direction"])
            dir_defs[direction] = image_def
    else:
        raise RuntimeError("Don't know how to handle '%s'" % (obj[0].tag))
    return obj_def


def parse_actions(actions, root_path):
    """Parse action definitions

        Args:

            actions: A list of etree elements containg action definitons

            root_path: The path of the object file the elements are in
    """
    action_dict = {}
    for action in actions:
        animations = parse_animations(action.findall("animation"), root_path)
        action_dict[action.attrib["id"]] = animations
    return action_dict


def parse_animations(animations, root_path):
    """Parse animation definitions

        Args:

            animations: A list of etree elements containg animation definitons

            root_path: The path of the object file the elements are in
    """
    ani_dict = {}
    if "atlas" in animations[0].attrib:
        ani_dict["type"] = "single"
        animation = animations[0]
        ani_dict.update(parse_animation_atlas(animation, root_path))
    else:
        ani_dict["type"] = "multi"
        ani_dict["directions"] = {}
        for animation in animations:
            ani_def = parse_animation(animation, root_path)
            direction = int(ani_def["direction"])
            ani_dict["directions"][direction] = ani_def
    return ani_dict


def parse_animation(animation, root_path):
    """Parse an animation definition

        Args:

            animation: An etree element containing the definiton

            root_path: The path of the object file the element is in
    """
    ani_dict = {}
    if "source" in animation.attrib:
        animation_file = animation.attrib["source"]
        ani_file = os.path.join(root_path, animation_file)
        ani_path = os.path.dirname(ani_file)
        ani_doc = etree.parse(ani_file)
        root = ani_doc.getroot()
        ani_dict["delay"] = root.attrib["delay"]
        ani_dict.update(parse_animation(root, ani_path))
    else:
        frames = []
        for frame in animation.findall("frame"):
            source = os.path.join(root_path, frame.attrib["source"])
            source = os.path.abspath(source)
            frames.append(source)
        ani_dict["direction"] = animation.attrib["id"].split(":")[2]
        ani_dict["frames"] = frames
        ani_dict["x_offset"] = animation.attrib["x_offset"]
        ani_dict["y_offset"] = animation.attrib["y_offset"]
    return ani_dict


def parse_animation_atlas(animation, root_path):
    """Parse an animation definition that uses an atlas

        Args:

            animation: An etree element containing the definiton

            root_path: The path of the object file the element is in
    """
    ani_dict = {}
    ani_dict["atlas"] = {}
    image = os.path.join(root_path, animation.attrib["atlas"])
    ani_dict["atlas"]["image"] = os.path.abspath(image)
    ani_dict["atlas"]["width"] = animation.attrib["width"]
    ani_dict["atlas"]["height"] = animation.attrib["height"]
    ani_dict["directions"] = {}
    for direction in animation.findall("direction"):
        action_dir = int(direction.attrib["dir"])
        dir_data = ani_dict["directions"][action_dir] = {}
        dir_data["delay"] = direction.attrib["delay"]
        dir_data["frames"] = direction.attrib["frames"]
    return ani_dict


class ObjectToolbar(ToolbarPage):
    """A toolbar for displaying and placing static objects on a map"""

    def __init__(self, editor):
        ToolbarPage.__init__(self, editor, "Objects")
        self.objects = {}

    def update_items(self):
        """Update the items of the toolbar page"""
        self.objects = {}
        model = self.editor.engine.getModel()
        namespaces = model.getNamespaces()
        for namespace in namespaces:
            objects = model.getObjects(namespace)
            for fife_object in objects:
                project_dir = self.editor.project_source
                object_filename = fife_object.getFilename()
                filename = os.path.join(project_dir, object_filename)
                objects = parse_file(filename)
                cegui_system = PyCEGUI.System.getSingleton()
                renderer = cegui_system.getRenderer()
                for obj in objects:
                    obj_def = obj["object"]
                    id = obj_def["id"]
                    self.objects[id] = {}
                    self.objects[id]["static"] = obj_def["static"]
                    if int(obj_def["static"]) == 0:
                        actions = obj["actions"]
                        self.objects[id]["actions"] = {}
                        actions_dict = self.objects[id]["actions"]
                        for action, action_def in actions.iteritems():
                            img_type = action_def["type"]
                            if img_type == "single":
                                atlas_def = action_def["atlas"]
                                name = ".".join([id, action, "atlas"])
                                fname = atlas_def["image"]
                                if renderer.isTextureDefined(name):
                                    tex = renderer.getTexture(name)
                                else:
                                    tex = renderer.createTexture(name,
                                                                 fname,
                                                                 "FIFE")
                                tex_size = tex.getSize()
                                tex_width = tex_size.d_width
                                tex_heigh = tex_size.d_height
                                frame_width = int(atlas_def["width"])
                                frame_height = int(atlas_def["height"])
                                frames_p_line = tex_width / frame_width
                                frame_count = 0
                            dirs = action_def["directions"]
                            actions_dict[action] = {}
                            action_dict = actions_dict[action]
                            dirs_iter = iter(sorted(dirs.iteritems()))
                            for direction, dir_def in dirs_iter:
                                action_dict[direction] = {}
                                dir_dict = action_dict[direction]
                                dir_dict["delay"] = dir_def["delay"]
                                if img_type == "multi":
                                    dir_dict["type"] = "multi"
                                    frame_id = 0
                                    frames = dir_def["frames"]
                                    for frame in frames:
                                        name = ".".join([id,
                                                         action,
                                                         str(direction),
                                                         str(frame_id)])
                                        if not renderer.isTextureDefined(name):
                                            tex = renderer.createTexture(name,
                                                                         frame,
                                                                         "FIFE")
                                        frame_id = frame_id + 1
                                    dir_dict["frames"] = frame_id
                                elif img_type == "single":
                                    dir_dict["type"] = "single"
                                    dir_def["frames"] = []
                                    frames = dir_def["frames"]
                                    line = frame_count / frames_p_line
                                    col =  frame_count % frames_p_line
                                    pos = PyCEGUI.Vector2f(col * frame_width,
                                                           line * frame_height)
                                    size = PyCEGUI.Sizef(frame_width,
                                                         frame_height)
                                    frames.append(PyCEGUI.Rectf(pos, size))
                                    frame_count = frame_count + 1
                    elif int(obj_def["static"]) == 1:
                        self.objects[id]["directions"] = {}
                        dir_def = self.objects[id]["directions"]
                        dir_iter = iter(sorted(obj["directions"].iteritems()))
                        for direction, dir_def in dir_iter:
                            source = dir_def["source"]
                            if dir_def["type"] == "atlas":
                                tex_name = id
                                if not renderer.isTextureDefined(tex_name):
                                    renderer.createTexture(tex_name,
                                                           source,
                                                           "FIFE")
                                pos = PyCEGUI.Vector2f(float(dir_def["xpos"]),
                                                       float(dir_def["ypos"]))
                                size = PyCEGUI.Sizef(float(dir_def["width"]),
                                                     float(dir_def["height"]))
                                dir_def["rect"] = PyCEGUI.Rectf(pos, size)
                            elif dir_def["type"] == "image":
                                tex_name = ".".join([id, str(direction)])
                                if not renderer.isTextureDefined(tex_name):
                                    renderer.createTexture(tex_name,
                                                           source,
                                                           "FIFE")
        # TODO: Create the CEGUI images
        ToolbarPage.update_items(self)