import bpy
from bpy.props import *
from .common import *


def is_scene_unit_metric(scene):
    units = scene.unit_settings
    is_metric = units.system == 'METRIC'
    if is_metric:
        return True
    else:
        print(f"Unit mismatch: System={units.system}, Scale={units.scale_length}, Length={units.length_unit}")
        return False

def is_scene_unit_one_meter(scene):
    units = scene.unit_settings
    is_scale_one = round(units.scale_length, 4) == 1.0
    if is_scale_one:
        return True
    else:
        print(f"Unit mismatch: System={units.system}, Scale={units.scale_length}, Length={units.length_unit}")
        return False


def has_pending_transforms(obj):
    """Returns True if transforms are not applied (Location 0, Rotation 0, Scale 1)."""
    # Precision threshold for floating point math
    if obj.location.length > 0.0001:
        return True

        # Check Rotation (should be Euler 0,0,0 or Identity Quaternion)
    if obj.rotation_euler.to_matrix().is_identity is False:
        return True

        # Check Scale (should be 1,1,1)
        # We check if the scale deviates from 1.0 significantly
    for s in obj.scale:
        if abs(1.0 - s) > 0.0001:
            return True

    return False


class YMatchNames(bpy.types.Operator):
    bl_idname = "wm.y_match_names"
    bl_label = "Fix mesh and material names"
    bl_description = "For CS2 editor, names of the material and mesh data must match the object name and the file name."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.object

# https://cs2.paradoxwikis.com/Asset_Pipeline:_Buildings#Sub_Meshes
        objname = obj.name \
            .replace('.', '-') \
            .replace("_", "-") \
            .replace("-LOD0", "") \
            .replace("-Gls", "_Gls") \
            .replace("-Win", "_Win") \
            .replace("-Wim", "_Wim") \
            .replace("-Gra", "_Gra") \
            .replace("-Wat", "_Wat") \
            .replace("-LOD", "_LOD")

        # Rename Mesh Data to Object Name
        if obj.data:
            obj.data.name = objname
            obj.name = objname

        # Rename Materials to Object Name
        # Note: If you have multiple materials, Blender will auto-suffix them (e.g., Name.001)
        for slot in obj.material_slots:
            if slot.material:
                slot.material.name = objname

        self.report({'INFO'}, f"Prepared: {objname}")
        return {'FINISHED'}

class YPrepareExportMesh(bpy.types.Operator):
    bl_idname = "wm.y_prepare_export_mesh"
    bl_label = "Prepare for FBX export"
    bl_description = "Select destination folder."
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        obj = context.object
        uv_layer = get_uv_layers(obj)

        if not uv_layer or len(uv_layer) == 0:
            self.report({'ERROR'}, "Mesh has no UV map.")
            return {'CANCELLED'}

        # Force select
        bpy.context.view_layer.objects.active = obj
        obj.hide_select = obj.hide_viewport = obj.hide_render = False
        obj.hide_set(False)
        obj.select_set(True)

        if has_pending_transforms(obj):
            self.report({'INFO'}, "Active object has pending visual transforms. Applying rotation and scale transforms.")
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

        bpy.ops.wm.y_export_mesh()
        return {'FINISHED'}

class YExportMesh(bpy.types.Operator):
    bl_idname = "wm.y_export_mesh"
    bl_label = "Export FBX"
    bl_description = "Exports a CS2-compliant mesh as FBX file."
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: StringProperty(
        subtype='FILE_PATH',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    previous_export_filepath: StringProperty(
        subtype='FILE_PATH',
        options={'HIDDEN'}
    )

    def invoke(self, context, event):
        obj = context.object

        #current_obj_name = context.object.name.replace('.', '-')
        suggested_name = obj.name + '.fbx'

        if bpy.data.is_saved:
            if self.previous_export_filepath:
                self.filepath = os.path.join(os.path.dirname(self.previous_export_filepath), suggested_name)
            else:
                self.filepath = os.path.join(os.path.dirname(bpy.data.filepath), suggested_name)
        else:
            if self.previous_export_filepath:
                self.filepath = os.path.join(os.path.dirname(self.previous_export_filepath), suggested_name)
            else:
                self.filepath = os.path.join(os.path.expanduser("~"), suggested_name)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            bpy.ops.export_scene.fbx(
                filepath=self.filepath,
                use_selection=True,
                use_visible=False,
                use_active_collection=False,
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_NONE',
                use_space_transform=True,
                bake_space_transform=True,
                object_types={'MESH'},
                use_mesh_modifiers=True,
                use_mesh_modifiers_render=False,
                mesh_smooth_type='OFF',
                colors_type='SRGB',
                prioritize_active_color=False,
                use_subsurf=False,
                use_mesh_edges=False,
                use_tspace=False,
                use_triangles=True,
                use_custom_props=False,
                add_leaf_bones=False,
                bake_anim=False,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
                use_batch_own_dir=False,
                use_metadata=False,
                axis_forward='-Z',
                axis_up='Y'
            )

        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

        self.previous_export_filepath = self.filepath  # Saves the filepath to the prop, ready to be recalled next time

        self.report({'INFO'}, f"{os.path.basename(self.filepath)} saved")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(YMatchNames)
    bpy.utils.register_class(YPrepareExportMesh)
    bpy.utils.register_class(YExportMesh)

def unregister():
    bpy.utils.unregister_class(YMatchNames)
    bpy.utils.unregister_class(YPrepareExportMesh)
    bpy.utils.unregister_class(YExportMesh)
