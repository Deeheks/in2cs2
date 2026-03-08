import bpy, re, os, json
from bpy.props import *
from .common import *

def has_pending_transforms(obj):
    # Ignore location
    #if obj.location.length > 0.0001:
    #    return True

    if obj.rotation_euler.to_matrix().is_identity is False:
        return True

    for s in obj.scale:
        if abs(1.0 - s) > 0.0001:
            return True
    return False

def make_dir_if_not(dir_name):
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)

def is_mesh_rigged(obj):
    isrigged = False
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE' and modifier.object is not None:
            isrigged = True
            break
    return isrigged

# https://cs2.paradoxwikis.com/Asset_Pipeline:_Buildings#Sub_Meshes
def cs2submesh_type(suffix):
    if suffix:
        submesh = suffix.lower().replace("_", "")
        if submesh == 'gls':
            return "Glass"
        elif submesh == 'win':
            return "Window (clear)"
        elif submesh == 'wim':
            return "Window (blur)"
        elif submesh == 'gra':
            return "Grass"
        elif submesh == 'wat':
            return "Water"
        else:
            return "Unknown"
    else:
        return None

def expire_validation(obj_name):
    obj = bpy.data.objects.get(obj_name)
    if obj:
        try:
            obj.yp.asset_needs_repair = -1
        except:
            print(f"Validation Property not found on {obj_name}")
    else:
        print(f"{obj_name} no longer exists")

    return None


class YValidateObject(bpy.types.Operator):
    bl_idname = "wm.y_validate_object"
    bl_label = "Validate Object"
    bl_description = "Verifies CS2 compliance before exporting"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = get_active_object()
        mat = get_active_material(obj)

        # Supported submesh types (lowercase for comparison)
        submesh_types = {"gls", "win", "wim", "gra", "wat"}

        # Strip Blender's duplicate suffix (e.g., .001) for clean parsing
        blender_suffix = ""
        dup_match = re.search(r"(\.\d{3,})$", obj.name)
        if dup_match:
            blender_suffix = dup_match.group(1)
            clean_name = obj.name[:-len(blender_suffix)]
        else:
            clean_name = obj.name

        parts = clean_name.split('_')

        lod_suffix = ""
        submesh_suffix = ""

        # Extract suffixes starting from the very end of the name.
        # We require len(parts) > 1 so we never consume the base name itself.
        while len(parts) > 1:
            last_part = parts[-1].lower()

            # Check if the last part is an LOD suffix (e.g., lod1, LOD12)
            lod_match = re.match(r"^(lod)(\d+)$", last_part)
            if lod_match:
                lod_suffix = f"_LOD{lod_match.group(2)}"
                parts.pop()
                continue

            # Check if the last part is a supported Submesh suffix
            if last_part in submesh_types:
                submesh_suffix = f"_{last_part.capitalize()}"
                parts.pop()
                continue

            # If the chunk matches neither, we've hit the base name. Break the loop.
            break

        # Reconstruct the clean base and target names
        base_name = "_".join(parts)
        target_name = base_name + lod_suffix + submesh_suffix

        # Apply the rename operation if needed
        if obj.name != target_name:
            obj.name = target_name
            self.report({'INFO'}, f"Object renamed to comply with naming convention: {obj.name} -> {target_name}")

        ypo = obj.yp
        asset_is_main = base_name == target_name
        mismatch_mesh = obj.data.name != target_name
        mismatch_material = mat.name != target_name if mat else False
        units = bpy.context.scene.unit_settings
        uv_layer = get_uv_layers(obj)
        repair_code = -1
        error_msg = ""
        if units.system != 'METRIC':
            repair_code = 1
            error_msg = "Scene unit System should be set to Metric"
        elif is_mesh_rigged(obj):
            if round(units.scale_length, 4) != 0.01:  # 0.01 scaling accounts for rigged meshes hack prior to official support
                repair_code = 2
                error_msg = "Scene unit Scale should be 0.01 for Rigged objects"
        elif round(units.scale_length, 4) != 1.0:
            repair_code = 3
            error_msg = "Scene unit Scale should be 1.0 for Static objects"
        elif mismatch_mesh:
            repair_code = 11
            error_msg = "Mesh Name mismatch"
        elif len(obj.material_slots) > 1:
            repair_code = 101
            error_msg = "Object has more than one assigned Material"
        elif submesh_suffix and mat:
            repair_code = 102
            error_msg = "Submeshes should have no Material assigned"
        elif not submesh_suffix and not mat:
            repair_code = 103
            error_msg = "Object has no Material assigned"
        # At this point, we're sure it has assigned material
        elif mismatch_material and asset_is_main and not ypo.asset_uses_shared:
            repair_code = 12
            error_msg = "Material Name mismatch"
        elif mismatch_material and lod_suffix == "_LOD1" and not ypo.asset_lod1shares0:
            repair_code = 13
            error_msg = "Material Name mismatch"
        elif mismatch_material and lod_suffix == "_LOD2" and not (ypo.asset_lod2shares0 or ypo.asset_lod2shares1):
            repair_code = 14
            error_msg = "Material Name mismatch"
        elif has_pending_transforms(obj):
            repair_code = 21
            error_msg = "Pending Transforms need to be Applied"
        elif not uv_layer or len(uv_layer) == 0:
            repair_code = 22
            error_msg = "Mesh has no UV Map"
        else:
            repair_code = 0    # Export-ready!
            if is_bl_newer_than(2, 80):
                bpy.app.timers.register(lambda: expire_validation(target_name), first_interval=5.0)

        ypo.asset_needs_repair = repair_code
        ypo.asset_error_msg = error_msg

        return {'FINISHED'}


class YRepairObject(bpy.types.Operator):
    bl_idname = "wm.y_repair_object"
    bl_label = "Repair Object"
    bl_description = "Enforces CS2 compliance before exporting"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        obj_name = obj.name
        mat = get_active_material(obj)
        ypo = obj.yp

        error_code = ypo.asset_needs_repair
        fixed = False
        if error_code == 11:  # mesh name mismatch
            obj.data.name = obj_name
            self.report({'INFO'}, f"Mesh renamed to match object's name: {obj_name}")
            fixed = True
        elif error_code in (12, 13, 14) and mat:
            rename_mat = False
            if error_code == 12 and not ypo.asset_uses_shared:
                rename_mat = True
            elif error_code == 13 and not ypo.asset_lod1shares0:
                rename_mat = True
            elif error_code == 14 and not (ypo.asset_lod2shares0 or ypo.asset_lod2shares1):
                rename_mat = True
            if rename_mat:
                mat.name = obj_name
                self.report({'INFO'}, f"Material renamed to match object's name: {obj_name}")
                fixed = True
        elif error_code == 21 and has_pending_transforms(obj):
            set_object_hide(obj, False)
            set_object_select(obj, True)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            fixed = True

        else:
            ypo.asset_error_msg = ypo.asset_error_msg + "Requires manual repair."

        if fixed:
            bpy.ops.wm.y_validate_object()
        else:
            ypo.asset_needs_repair = -1

        return {'FINISHED'}

class YPrepareExportMesh(bpy.types.Operator):
    bl_idname = "wm.y_prepare_export_mesh"
    bl_label = "Export FBX as ..."
    bl_description = "Select destination folder."
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        bpy.ops.wm.y_export_mesh('INVOKE_DEFAULT')
        return {'FINISHED'}


class YExportMesh(bpy.types.Operator):
    bl_idname = "wm.y_export_mesh"
    bl_label = "Export FBX"
    bl_description = "Exports a CS2-compliant mesh."
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
        set_object_hide(obj, False)
        set_object_select(obj, True)

        main_mesh = obj.name.split('_')[0]
        file_name = obj.name + '.fbx'

        if bpy.data.is_saved:
            if self.previous_export_filepath:
                self.filepath = os.path.join(os.path.dirname(self.previous_export_filepath), file_name)
            else:
                suggested_dir = os.path.join(os.path.dirname(bpy.data.filepath), main_mesh)
                make_dir_if_not(suggested_dir)
                self.filepath = os.path.join(suggested_dir, file_name)
        else:
            if self.previous_export_filepath:
                self.filepath = os.path.join(os.path.dirname(self.previous_export_filepath), file_name)
            else:
                suggested_dir = os.path.join(os.path.expanduser("~"), main_mesh)
                self.filepath = os.path.join(suggested_dir, file_name)

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


class YSettingsJson(bpy.types.Operator):
    bl_idname = "wm.y_settings_json"
    bl_label = "Generate settings.json"
    bl_description = "Generate settings.json based on found textures"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        obj = context.object
        ypo = obj.yp
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        yp = group_tree.yp

        lod1obj = bpy.data.objects.get(f'{obj.name}_LOD1')
        lod2obj = bpy.data.objects.get(f'{obj.name}_LOD2')

        if lod1obj:
            ypo.asset_lod1shares0 = lod1obj.yp.asset_lod1shares0
        if lod2obj:
            ypo.asset_lod2shares0 = lod2obj.yp.asset_lod2shares0
            ypo.asset_lod2shares1 = lod2obj.yp.asset_lod2shares1

        curr = obj.name
        shared_assets = {}
        found_map_types = []

        if len(yp.bake_targets) > 0:
            for bt in yp.bake_targets:
                image_node = nodes.get(bt.image_node)

                # Safely get the image
                image = image_node.image if image_node and hasattr(image_node, 'image') and image_node.image else None

                if image and image.name:
                    base_image_name = image.name.rsplit('.', 1)[0]

                    if base_image_name.startswith(f"{curr}_"):
                        map_type = base_image_name.replace(f"{curr}_", "", 1)
                    else:
                        map_type = base_image_name.split('_')[-1]

                    if map_type not in found_map_types:
                        found_map_types.append(map_type)
                        # Debugging print statement
                        print(f"Found Image: '{image.name}' -> Extracted Map Type: '{map_type}'")
                    else:
                        print(f"Skipping Duplicate Map Type: '{map_type}' from '{image.name}'")

        print(f"Final extracted map types for JSON: {found_map_types}\n")

        if not found_map_types:
            self.report({'ERROR'}, "No valid textures found. JSON would be empty.")
            return {'CANCELLED'}

        # Generate JSON using only the found map types
        if ypo.asset_uses_shared_from:
            target = ypo.shared_from_name
            for m in found_map_types:
                shared_assets[f"{curr}_{m}.png"] = f"../{target}/{target}_{m}.png"
                shared_assets[f"{curr}_LOD1_{m}.png"] = f"../{target}/{target}_{m}.png"
                shared_assets[f"{curr}_LOD2_{m}.png"] = f"../{target}/{target}_LOD2_{m}.png"

        else:
            for m in found_map_types:
                if ypo.asset_lod1shares0:
                    shared_assets[f"{curr}_LOD1_{m}.png"] = f"{curr}_{m}.png"

                if ypo.asset_lod2shares0:
                    shared_assets[f"{curr}_LOD2_{m}.png"] = f"{curr}_{m}.png"
                elif ypo.asset_lod2shares1:
                    shared_assets[f"{curr}_LOD2_{m}.png"] = f"{curr}_LOD1_{m}.png"

        # Write Output to Text Editor
        data = {"sharedAssets": shared_assets}
        json_string = json.dumps(data, indent=2)
        text_name = "Settings.json"

        # Create or fetch the text block
        if text_name in bpy.data.texts:
            text_block = bpy.data.texts[text_name]
            text_block.clear()  # Wipe previous generation
        else:
            text_block = bpy.data.texts.new(name=text_name)

        text_block.write(json_string)

        text_area_found = False

        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = text_block
                area.spaces.active.top = 0
                text_area_found = True
                break

        if not text_area_found:
            areas_before = list(context.screen.areas)

            # 4a. Split the current area to create a small footprint (35% width)
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.35)

            # 4b. Identify the newly created temporary area
            temp_area = None
            for area in context.screen.areas:
                if area not in areas_before:
                    temp_area = area
                    break

            if temp_area:
                # Setup context override targeting the temp area
                override = context.copy()
                override['area'] = temp_area
                for region in temp_area.regions:
                    if region.type == 'WINDOW':
                        override['region'] = region
                        break

                windows_before = list(context.window_manager.windows)

                # 4c. Duplicate the temp area into a new window (Version agnostic)
                if hasattr(context, "temp_override"):  # Blender 3.2+
                    with context.temp_override(**override):
                        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
                else:  # Blender 2.79 - 3.1
                    bpy.ops.screen.area_dupli(override, 'INVOKE_DEFAULT')

                # 4d. Close the temporary area in the main window to clean up
                if hasattr(context, "temp_override"):
                    with context.temp_override(**override):
                        bpy.ops.screen.area_close()
                else:
                    bpy.ops.screen.area_close(override)

                # 4e. Find the newly spawned OS window and configure it
                windows_after = list(context.window_manager.windows)
                new_windows = [w for w in windows_after if w not in windows_before]

                if new_windows:
                    new_window = new_windows[0]
                    new_area = new_window.screen.areas[0]

                    new_area.type = 'TEXT_EDITOR'
                    new_area.spaces.active.text = text_block
                    new_area.spaces.active.top = 0  # Scroll to line 1

        return {'FINISHED'}

def register():
    bpy.utils.register_class(YValidateObject)
    bpy.utils.register_class(YRepairObject)
    bpy.utils.register_class(YPrepareExportMesh)
    bpy.utils.register_class(YExportMesh)
    bpy.utils.register_class(YSettingsJson)

def unregister():
    bpy.utils.unregister_class(YValidateObject)
    bpy.utils.unregister_class(YRepairObject)
    bpy.utils.unregister_class(YPrepareExportMesh)
    bpy.utils.unregister_class(YExportMesh)
    bpy.utils.unregister_class(YSettingsJson)
