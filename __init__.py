bl_info = {
    "name": "ImagesBridge",
    "blender": (4, 5, 0),
    "category": "Image",
    "version": (1, 0, 34),
    "author": "lesergei3d",
    "description": "Allows selecting from multiple external image editors with buttons for each editor.",
    
}

import os
import subprocess
import time

import bpy
from bpy.props import StringProperty, IntProperty, CollectionProperty, BoolProperty

# ===== helpers pour le timer =====

_last_mtimes = {}

def _start_timer():
    # (ré)enregistre le timer proprement
    try:
        bpy.app.timers.unregister(auto_reload_images)
    except Exception:
        pass
    bpy.app.timers.register(auto_reload_images, first_interval=0.5, persistent=True)

def _stop_timer():
    try:
        bpy.app.timers.unregister(auto_reload_images)
    except Exception:
        pass

def on_toggle_auto_reload(self, context):
    """Callback appelé quand la case Auto Reload est (dé)cochée."""
    if getattr(self, "auto_reload", False):
        _start_timer()
    else:
        _stop_timer()


class ExternalEditor(bpy.types.PropertyGroup):
    """Group of properties for an external editor."""
    name: StringProperty(name="Editor Name", default="New Editor")
    path: StringProperty(name="Editor Path", subtype='FILE_PATH')


class EXTERNAL_EDITOR_UL_list(bpy.types.UIList):
    """UIList for displaying external editors in addon preferences."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False)
            row.prop(item, "path", text="", emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


class ImagesBridgePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    editors: CollectionProperty(type=ExternalEditor)
    active_editor_index: IntProperty(default=0)

    show_details: BoolProperty(
        name="Show Details",
        description="Expand to view detailed usage instructions",
        default=False
    )

    # --- AJOUT: propriété avec callback update ---
    auto_reload: BoolProperty(
        name="Auto Reload",
        description="Automatically reload images when file changes on disk",
        default=False,
        update=on_toggle_auto_reload,
    )

    def draw(self, context):
        layout = self.layout

        # Display editor list with UIList
        row = layout.row()
        row.template_list("EXTERNAL_EDITOR_UL_list", "", self, "editors", self, "active_editor_index")

        col = row.column(align=True)
        col.operator("external_editor.add_editor", text="", icon="ADD")
        col.operator("external_editor.remove_editor", text="", icon="REMOVE")
        col.separator()
        col.operator("external_editor.move_editor_up", text="", icon="TRIA_UP")
        col.operator("external_editor.move_editor_down", text="", icon="TRIA_DOWN")

        # Auto Reload section
        layout.separator()
        layout.label(text="OPTION FOR AUTO RELOAD IMAGE.")
        layout.prop(self, "auto_reload", text="Enable Auto Reload")
        
        # Information section
        layout.separator()
        layout.label(text="Addon Information", icon="INFO")
        layout.label(text="TO EDIT AN IMAGE EXTERNALLY, SAVE IT FIRST IN IMAGE EDITOR.")
        layout.prop(self, "show_details", text="Show Details", icon="TRIA_DOWN" if self.show_details else "TRIA_RIGHT")

        # Detailed content (displayed only if show_details is enabled)
        if self.show_details:
            box = layout.box()
            box.label(text="How to Use ImagesBridge", icon="QUESTION")

            col = box.column(align=True)
            col.label(text="1. Configure your external editors in Preferences.", icon="PREFERENCES")
            col.label(text="2. Select an image in Image Editor or Node Editor.", icon="IMAGE_DATA")
            col.label(text="3. Save the image if it has no file path yet.", icon="FILE_TICK")
            col.label(text="4. Click on an editor button to open the image externally.", icon="FILE_IMAGE")
            col.label(text="5. Edit and save the image in the external editor.", icon="BRUSH_DATA")
            col.label(text="6. Enable 'Auto Reload' in Preferences to refresh automatically.", icon="FILE_REFRESH")
            col.label(text="7. Or use 'Reload Image' manually if Auto Reload is disabled.", icon="FILE_REFRESH")
            col.label(text="8. Optionally, export UV maps via 'Export UV Layout'.", icon="UV")

class AddExternalEditorOperator(bpy.types.Operator):
    """Operator to add a new external editor."""
    bl_idname = "external_editor.add_editor"
    bl_label = "Add External Editor"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        editor = prefs.editors.add()
        editor.name = f"Editor {len(prefs.editors)}"
        editor.path = ""
        prefs.active_editor_index = len(prefs.editors) - 1
        return {'FINISHED'}


class RemoveExternalEditorOperator(bpy.types.Operator):
    """Operator to remove the selected external editor."""
    bl_idname = "external_editor.remove_editor"
    bl_label = "Remove External Editor"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        if prefs.editors and 0 <= prefs.active_editor_index < len(prefs.editors):
            prefs.editors.remove(prefs.active_editor_index)
            prefs.active_editor_index = max(0, prefs.active_editor_index - 1)
        return {'FINISHED'}


class MoveEditorUpOperator(bpy.types.Operator):
    """Operator to move the selected editor up in the list."""
    bl_idname = "external_editor.move_editor_up"
    bl_label = "Move Editor Up"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        index = prefs.active_editor_index
        if index > 0:
            prefs.editors.move(index, index - 1)
            prefs.active_editor_index -= 1
        return {'FINISHED'}


class MoveEditorDownOperator(bpy.types.Operator):
    """Operator to move the selected editor down in the list."""
    bl_idname = "external_editor.move_editor_down"
    bl_label = "Move Editor Down"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        index = prefs.active_editor_index
        if index < len(prefs.editors) - 1:
            prefs.editors.move(index, index + 1)
            prefs.active_editor_index += 1
        return {'FINISHED'}


def find_image_in_node_tree(node_tree):
    """Recursively search for an image in the node tree."""
    for node in node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            return node.image
        elif node.type == 'GROUP' and node.node_tree:
            image = find_image_in_node_tree(node.node_tree)
            if image:
                return image
    return None


class SelectImageNodeOperator(bpy.types.Operator):
    """Operator to select an image node."""
    bl_idname = "node.select_image_node"
    bl_label = "Select Image Node"
    bl_description = "Select an image node to use"

    node_name: StringProperty()

    def execute(self, context):
        node_tree = context.space_data.node_tree
        if not node_tree:
            self.report({'ERROR'}, "No node tree found.")
            return {'CANCELLED'}

        node = node_tree.nodes.get(self.node_name)
        if not node or node.type != 'TEX_IMAGE':
            self.report({'ERROR'}, "Invalid node selected.")
            return {'CANCELLED'}

        node_tree.nodes.active = node
        self.report({'INFO'}, f"Selected image node: {node.name}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        node_tree = context.space_data.node_tree

        if not node_tree:
            layout.label(text="No node tree found.", icon="ERROR")
            return

        image_nodes = [node for node in node_tree.nodes if node.type == 'TEX_IMAGE']

        if not image_nodes:
            layout.label(text="No image nodes available.", icon="ERROR")
            return

        for node in image_nodes:
            layout.operator("node.select_image_node", text=node.name).node_name = node.name

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def get_active_image(context):
    """Retrieve the active image from various Blender contexts."""
    if context.space_data:
        if context.space_data.type == 'IMAGE_EDITOR':
            return context.space_data.image

        if context.space_data.type == 'NODE_EDITOR':
            node_tree = context.space_data.node_tree
            if node_tree:
                active_node = node_tree.nodes.active
                if active_node and active_node.type == 'TEX_IMAGE' and active_node.image:
                    return active_node.image
                else:
                    bpy.ops.node.select_image_node('INVOKE_DEFAULT')
                    return None

    obj = context.active_object
    if obj and obj.type == 'MESH':
        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if mat and mat.use_nodes:
                image = find_image_in_node_tree(mat.node_tree)
                if image:
                    return image

    return None


class OpenInExternalEditorOperator(bpy.types.Operator):
    """Operator to open the active image in the selected external editor."""
    bl_idname = "image.open_in_external_editor"
    bl_label = "Open in External Editor"
    bl_description = "Open the active image in the selected external editor"

    editor_index: IntProperty()

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences

        if self.editor_index >= len(prefs.editors):
            self.report({'ERROR'}, "Editor not found.")
            return {'CANCELLED'}

        editor = prefs.editors[self.editor_index]

        if not editor.path or not os.path.isfile(editor.path):
            self.report({'ERROR'}, f"Invalid path for editor: {editor.name}")
            return {'CANCELLED'}

        image = get_active_image(context)
        if not image:
            self.report({'ERROR'}, "No active image found.")
            return {'CANCELLED'}

        if not image.filepath:
            self.report({'INFO'}, "Image has no file path. Please save it first.")
            return {'CANCELLED'}

        return self.open_editor(editor, image)

    def open_editor(self, editor, image):
        try:
            subprocess.Popen([editor.path, bpy.path.abspath(image.filepath)])
            self.report({'INFO'}, f"Opened image in {editor.name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open editor: {e}")
            return {'CANCELLED'}


class SaveImageOperator(bpy.types.Operator):
    """Operator to save the active image."""
    bl_idname = "image.save_image"
    bl_label = "Save Image"
    bl_description = "Save the active image if it has unsaved changes, or prompt for a file path if none is set"

    @classmethod
    def poll(cls, context):
        image = get_active_image(context)
        return image is not None

    def execute(self, context):
        image = get_active_image(context)

        if not image:
            self.report({'ERROR'}, "No image available to save.")
            return {'CANCELLED'}

        if not image.filepath:
            self.report({'INFO'}, "Image has no file path. Opening save dialog.")
            if context.area.type == 'IMAGE_EDITOR':
                bpy.ops.image.save_as('INVOKE_DEFAULT')
            else:
                self.report({'ERROR'}, "Please switch to the Image Editor to save an unsaved image.")
            return {'CANCELLED'}

        if image.is_dirty:
            try:
                image.save()
                self.report({'INFO'}, f"Saved image: {image.filepath}")
            except RuntimeError as e:
                self.report({'ERROR'}, f"Failed to save image: {e}")
                return {'CANCELLED'}
        else:
            self.report({'INFO'}, "No changes to save.")

        return {'FINISHED'}


class ReloadImageOperator(bpy.types.Operator):
    """Operator to reload the active image from disk."""
    bl_idname = "image.reload_image"
    bl_label = "Reload Image"
    bl_description = "Reload the active image from disk"

    @classmethod
    def poll(cls, context):
        image = get_active_image(context)
        return image is not None and image.filepath

    def execute(self, context):
        image = get_active_image(context)

        if not image:
            self.report({'ERROR'}, "No image available to reload.")
            return {'CANCELLED'}

        if not image.filepath:
            self.report({'ERROR'}, "The image does not have a valid file path.")
            return {'CANCELLED'}

        try:
            image.reload()
            self.report({'INFO'}, f"Reloaded image: {image.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to reload image: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class ExternalEditorPanelImage(bpy.types.Panel):
    """Panel in the Image Editor to display ImagesBridge options."""
    bl_label = "ImagesBridge"
    bl_idname = "IMAGE_PT_imagesbridge"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences

        image = get_active_image(context)

        if image:
            layout.label(text=f"Active Image: {image.name}", icon="IMAGE_DATA")
        else:
            layout.label(text="No active image found.", icon="ERROR")

        for i, editor in enumerate(prefs.editors):
            row = layout.row()
            row.operator("image.open_in_external_editor", text=editor.name, icon="FILE_IMAGE").editor_index = i

        layout.separator()
        layout.operator("image.save_image", text="Save Image", icon="FILE_TICK")
        layout.operator("uv.export_uv_layout_custom", text="Export UV Layout", icon="EXPORT")
        layout.operator("image.reload_image", text="Reload Image", icon="FILE_REFRESH")


class ExternalEditorPanel3DView(bpy.types.Panel):
    """Panel in the 3D View to display ImagesBridge options."""
    bl_label = "ImagesBridge"
    bl_idname = "VIEW3D_PT_imagesbridge"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences

        image = get_active_image(context)

        if image:
            layout.label(text=f"Active Image: {image.name}", icon="IMAGE_DATA")
        else:
            layout.label(text="No active image found.", icon="ERROR")

        for i, editor in enumerate(prefs.editors):
            row = layout.row()
            row.operator("image.open_in_external_editor", text=editor.name, icon="FILE_IMAGE").editor_index = i

        layout.separator()
        layout.operator("image.reload_image", text="Reload Image", icon="FILE_REFRESH")


class ExternalEditorPanelProperties(bpy.types.Panel):
    """Panel in the Properties to display ImagesBridge options."""
    bl_label = "ImagesBridge"
    bl_idname = "PROPERTIES_PT_imagesbridge"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences

        image = get_active_image(context)

        if image:
            layout.label(text=f"Active Image: {image.name}", icon="IMAGE_DATA")
        else:
            layout.label(text="No active image found.", icon="ERROR")

        for i, editor in enumerate(prefs.editors):
            row = layout.row()
            row.operator("image.open_in_external_editor", text=editor.name, icon="FILE_IMAGE").editor_index = i

        layout.separator()
        layout.operator("image.reload_image", text="Reload Image", icon="FILE_REFRESH")


class ExportUVLayoutOperator(bpy.types.Operator):
    """Exporter le layout UV de l'objet actif"""
    bl_idname = "uv.export_uv_layout_custom"
    bl_label = "Export UV layout"
    bl_description = "Export the UV layout of the active object"
    
    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj and obj.type == 'MESH' and
            obj.data and obj.data.uv_layers.active
        )

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    export_format: bpy.props.EnumProperty(
        name="Format",
        description="Format du fichier exporté",
        items=[
            ('PNG', "PNG", ""),
            ('SVG', "SVG", ""),
            ('EPS', "EPS", ""),
        ],
        default='PNG'
    )
    size: bpy.props.IntVectorProperty(
        name="Taille",
        description="Dimensions de l'image exportée",
        size=2,
        default=(1024, 1024),
        min=1
    )
    opacity: bpy.props.FloatProperty(
        name="Opacité",
        description="Opacité des lignes UV",
        default=1.0,
        min=0.0,
        max=1.0
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Aucun objet mesh actif trouvé.")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.export_layout(
            filepath=self.filepath,
            mode=self.export_format,
            size=self.size,
            opacity=self.opacity,
            check_existing=False
        )
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"Layout UV exporté vers : {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        import os
        obj = context.object
        object_name = obj.name if obj else "Untitled"

        default_ext = self.export_format.lower()
        default_path = os.path.join(
            os.path.dirname(bpy.data.filepath),
            f"{object_name}_UV.{default_ext}"
        )
        self.filepath = default_path
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# === AUTO RELOAD SYSTEM ===
def auto_reload_images():
    """Timer: recharge les images disque si leur mtime a changé."""
    # si la pref est désactivée → stop
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
    except Exception:
        return None

    if not getattr(prefs, "auto_reload", False):
        return None

    for img in bpy.data.images:
        # on ne gère que les images provenant d'un fichier disque non packé
        if not getattr(img, "filepath", ""):
            continue
        if getattr(img, "source", "FILE") != 'FILE':
            continue
        if getattr(img, "packed_file", None):
            continue

        abs_path = bpy.path.abspath(img.filepath)
        if not abs_path or not os.path.isfile(abs_path):
            continue

        try:
            mtime = os.path.getmtime(abs_path)
        except Exception:
            continue

        last = _last_mtimes.get(abs_path)
        if last is None:
            _last_mtimes[abs_path] = mtime
        elif mtime > last:
            try:
                img.reload()
                _last_mtimes[abs_path] = mtime
                print(f"[ImagesBridge] Auto-reloaded: {img.name}")
            except Exception as e:
                print(f"[ImagesBridge] Failed to reload {img.name}: {e}")

    return 2.0  # relance dans 2s


def register():
    bpy.utils.register_class(ExternalEditor)
    bpy.utils.register_class(EXTERNAL_EDITOR_UL_list)
    bpy.utils.register_class(ImagesBridgePreferences)
    bpy.utils.register_class(AddExternalEditorOperator)
    bpy.utils.register_class(RemoveExternalEditorOperator)
    bpy.utils.register_class(MoveEditorUpOperator)
    bpy.utils.register_class(MoveEditorDownOperator)
    bpy.utils.register_class(SelectImageNodeOperator)
    bpy.utils.register_class(OpenInExternalEditorOperator)
    bpy.utils.register_class(SaveImageOperator)
    bpy.utils.register_class(ReloadImageOperator)
    bpy.utils.register_class(ExternalEditorPanelImage)
    bpy.utils.register_class(ExternalEditorPanel3DView)
    bpy.utils.register_class(ExternalEditorPanelProperties)
    bpy.utils.register_class(ExportUVLayoutOperator)

    # --- AJOUT: si la pref est déjà cochée, on démarre le timer au chargement ---
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        if getattr(prefs, "auto_reload", False):
            _start_timer()
    except Exception:
        pass


def unregister():
    # --- AJOUT: stoppe le timer proprement ---
    _stop_timer()

    bpy.utils.unregister_class(ExportUVLayoutOperator)
    bpy.utils.unregister_class(ExternalEditorPanelProperties)
    bpy.utils.unregister_class(ExternalEditorPanel3DView)
    bpy.utils.unregister_class(ExternalEditorPanelImage)
    bpy.utils.unregister_class(ReloadImageOperator)
    bpy.utils.unregister_class(SaveImageOperator)
    bpy.utils.unregister_class(OpenInExternalEditorOperator)
    bpy.utils.unregister_class(SelectImageNodeOperator)
    bpy.utils.unregister_class(MoveEditorDownOperator)
    bpy.utils.unregister_class(MoveEditorUpOperator)
    bpy.utils.unregister_class(RemoveExternalEditorOperator)
    bpy.utils.unregister_class(AddExternalEditorOperator)
    bpy.utils.unregister_class(ImagesBridgePreferences)
    bpy.utils.unregister_class(EXTERNAL_EDITOR_UL_list)
    bpy.utils.unregister_class(ExternalEditor)


if __name__ == "__main__":
    register()
