import bpy
import json
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix

# --- Helper Functions ---

def get_active_armature():
    """Gets the active armature object in the scene."""
    obj = bpy.context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj
    return None

# --- Operators ---

class HD2SDK_OT_ExportOriginalSkeleton(bpy.types.Operator, ExportHelper):
    """Exports the bone structure of the active armature to a JSON file (original_bones.json)"""
    bl_idname = "hd2sdk.export_original_skeleton"
    bl_label = "Export Original Skeleton"
    bl_description = "Export the active armature's bones to original_bones.json"
    
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        armature = get_active_armature()
        if not armature:
            self.report({'ERROR'}, "No active or selected armature found.")
            return {'CANCELLED'}

        bones_data = []
        for bone in armature.data.bones:
            if bone.parent:
                local_matrix = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local_matrix = bone.matrix_local
            
            pos, rot, scale = local_matrix.decompose()

            bone_entry = {
                "name": bone.name,
                "parent_name": bone.parent.name if bone.parent else "",
                "transform": {
                    "position": list(pos),
                    "rotation_quat": [rot.w, rot.x, rot.y, rot.z],
                    "scale": list(scale)
                },
                "attributes": [] # Placeholder for future attribute editing
            }
            bones_data.append(bone_entry)

        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(bones_data, f, indent=2)
            
        self.report({'INFO'}, f"Exported {len(bones_data)} bones to {self.filepath}")
        return {'FINISHED'}

class HD2SDK_OT_AddCustomBoneMarker(bpy.types.Operator):
    """Adds an Empty object to serve as a marker for a new custom bone"""
    bl_idname = "hd2sdk.add_custom_bone_marker"
    bl_label = "Add Custom Bone Marker"
    bl_description = "Add an Empty to mark a new bone's position and properties"

    def execute(self, context):
        marker = bpy.data.objects.new("CustomBoneMarker", None)
        context.scene.collection.objects.link(marker)
        
        marker['hd2_bone_name'] = "new_bone_name"
        marker['hd2_parent_bone'] = "Spine2" # A common default
        marker['hd2_attributes_json'] = '[{"name": "HD_ragdoll_material", "value": "cloth_heavy"}]'

        marker.location = context.scene.cursor.location
        
        bpy.ops.object.select_all(action='DESELECT')
        marker.select_set(True)
        context.view_layer.objects.active = marker
        
        self.report({'INFO'}, "Added a new Custom Bone Marker. Edit its properties in the Object Properties panel.")
        return {'FINISHED'}

class HD2SDK_OT_ExportModData(bpy.types.Operator, ExportHelper):
    """Exports all Custom Bone Markers in the scene to a Mod-Data JSON file"""
    bl_idname = "hd2sdk.export_mod_data"
    bl_label = "Export Mod Data"
    bl_description = "Export all Custom Bone Markers to mod_data.json"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    target_unit_id: bpy.props.StringProperty(name="Target Unit ID", description="The ID of the game unit this mod applies to", default="5556372446766824087")

    def execute(self, context):
        markers = [obj for obj in context.scene.objects if 'hd2_bone_name' in obj]
        if not markers:
            self.report({'ERROR'}, "No Custom Bone Markers found in the scene.")
            return {'CANCELLED'}

        added_bones = []
        armature = get_active_armature()
        if not armature:
            self.report({'ERROR'}, "An active armature is required to calculate relative transforms.")
            return {'CANCELLED'}

        for marker in markers:
            parent_name = marker.get('hd2_parent_bone', "")
            
            if parent_name and parent_name in armature.data.bones:
                parent_bone = armature.data.bones[parent_name]
                parent_matrix_world = armature.matrix_world @ parent_bone.matrix_local
            else:
                self.report({'WARNING'}, f"Parent bone '{parent_name}' for marker '{marker.name}' not found. Using world space.")
                parent_matrix_world = Matrix.Identity(4)

            local_matrix = parent_matrix_world.inverted() @ marker.matrix_world
            pos, rot, scale = local_matrix.decompose()

            attributes = []
            try:
                attr_str = marker.get('hd2_attributes_json', '[]')
                attributes = json.loads(attr_str)
                if not isinstance(attributes, list): raise ValueError()
            except (json.JSONDecodeError, ValueError):
                self.report({'WARNING'}, f"Invalid JSON in attributes for marker '{marker.name}'. Using empty list.")
                attributes = []

            added_bones.append({
                "name": marker.get('hd2_bone_name', "unnamed_bone"),
                "parent_bone": parent_name,
                "transform": {
                    "position": list(pos), "rotation_quat": [rot.w, rot.x, rot.y, rot.z], "scale": list(scale)
                },
                "attributes": attributes
            })

        mod_data = {
            "schema_version": "1.0.0",
            "mod_info": {"name": "My Custom Bone Mod", "author": "Modder", "version": "1.0.0"},
            "target_unit_id": self.target_unit_id,
            "skeleton_modifications": {"add_bones": added_bones}
        }

        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(mod_data, f, indent=2)

        self.report({'INFO'}, f"Exported {len(added_bones)} custom bones to {self.filepath}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.filepath = "mod_data.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# --- UI Panel ---

class HD2SDK_PT_CustomBonePanel(bpy.types.Panel):
    """Creates a Panel in the 3D View for Custom Bone operations"""
    bl_label = "Custom Bone Tools"
    bl_idname = "HD2SDK_PT_custom_bone_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'HD2 SDK'

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Phase A: Data Generation", icon='PRESET')
        box.operator(HD2SDK_OT_ExportOriginalSkeleton.bl_idname, text="1. Export Original Skeleton", icon='ARMATURE_DATA')
        box.operator(HD2SDK_OT_AddCustomBoneMarker.bl_idname, text="2. Add Bone Marker", icon='EMPTY_DATA')
        box.operator(HD2SDK_OT_ExportModData.bl_idname, text="3. Export Mod Data", icon='FILE_JSON')

# --- Registration ---

classes = (HD2SDK_OT_ExportOriginalSkeleton, HD2SDK_OT_AddCustomBoneMarker, HD2SDK_OT_ExportModData, HD2SDK_PT_CustomBonePanel)

def register():
    for cls in classes: bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes): bpy.utils.unregister_class(cls)