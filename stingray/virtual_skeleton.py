import bpy
from mathutils import Matrix, Vector, Quaternion
from typing import List, Tuple, Dict

class VirtualBone:
    """
    Represents a single bone in the in-memory 'Single Source of Truth' skeleton.
    This structure is independent of any specific Havok file format.
    """
    def __init__(self, name: str, parent_name: str, transform_dict: dict, attributes: list, index: int):
        self.name: str = name
        self.parent_name: str = parent_name
        self.attributes: list = attributes
        self.index: int = index
        self.parent_index: int = -1  # Resolved after all bones are processed

        # Convert the JSON transform dictionary to a Blender Matrix
        self.transform: Matrix = self._create_matrix_from_dict(transform_dict)

    def _create_matrix_from_dict(self, t_dict: dict) -> Matrix:
        """Creates a 4x4 Matrix from a transform dictionary."""
        if not t_dict:
            return Matrix.Identity(4)
        
        pos = Vector(t_dict.get("position", [0, 0, 0]))
        rot = Quaternion(t_dict.get("rotation_quat", [1, 0, 0, 0]))
        scale = Vector(t_dict.get("scale", [1, 1, 1]))
        
        mat_trans = Matrix.Translation(pos)
        mat_rot = rot.to_matrix().to_4x4()
        mat_scale = Matrix.Scale(scale.x, 4, (1, 0, 0)) @ \
                    Matrix.Scale(scale.y, 4, (0, 1, 0)) @ \
                    Matrix.Scale(scale.z, 4, (0, 0, 1))
                    
        return mat_trans @ mat_rot @ mat_scale

    def __repr__(self):
        return f"<VirtualBone {self.index}:'{self.name}' parent_idx:{self.parent_index}>"

# Type alias for clarity. The "Virtual Skeleton" is a list of VirtualBone objects.
VirtualSkeleton = List[VirtualBone]


class VirtualSkeletonGenerator:
    """
    Builds a complete, in-memory skeleton structure (the "Single Source of Truth")
    by merging an original skeleton with modifications defined in a Mod-Data JSON.
    """
    def __init__(self, original_bones_data: list, mod_data: dict):
        """
        Args:
            original_bones_data (list): A list of dictionaries, where each dict
                                        represents a bone from the original skeleton.
            mod_data (dict): The 'skeleton_modifications' section from the Mod-Data JSON.
        """
        self.original_bones_data = original_bones_data
        self.mod_data = mod_data

    def generate(self) -> Tuple[VirtualSkeleton, Dict[str, int]]:
        """
        Generates the virtual skeleton.

        Returns:
            A tuple containing:
            - A list of VirtualBone objects (the SoT), aliased as VirtualSkeleton.
            - A dictionary mapping bone names to their final indices.
        """
        virtual_bones: VirtualSkeleton = []
        name_to_index: Dict[str, int] = {}

        # 1. Process original bones
        for i, bone_data in enumerate(self.original_bones_data):
            vb = VirtualBone(name=bone_data.get('name'), parent_name=bone_data.get('parent_name'), transform_dict=bone_data.get('transform'), attributes=bone_data.get('attributes', []), index=i)
            virtual_bones.append(vb)
            name_to_index[vb.name] = i

        # 2. Process new bones from mod_data, enforcing "Append only at tail"
        current_index = len(virtual_bones)
        for new_bone_data in self.mod_data.get('add_bones', []):
            vb = VirtualBone(name=new_bone_data.get('name'), parent_name=new_bone_data.get('parent_bone'), transform_dict=new_bone_data.get('transform'), attributes=new_bone_data.get('attributes', []), index=current_index)
            virtual_bones.append(vb)
            name_to_index[vb.name] = current_index
            current_index += 1

        # 3. Resolve parent indices for all bones
        for bone in virtual_bones:
            bone.parent_index = name_to_index.get(bone.parent_name, -1)

        print(f"Virtual Skeleton Generated: {len(self.original_bones_data)} original + {len(self.mod_data.get('add_bones', []))} new = {len(virtual_bones)} total bones.")
        return virtual_bones, name_to_index

def generate_skeleton_from_armature(armature_obj: bpy.types.Object) -> Tuple[VirtualSkeleton, Dict[str, int]]:
    """
    Generates a VirtualSkeleton from a Blender armature object.
    This is used when the source of truth is the armature in the scene,
    not a set of JSON files.
    """
    if not armature_obj or armature_obj.type != 'ARMATURE':
        return [], {}

    # --- Save current context ---
    active_obj = bpy.context.view_layer.objects.active
    original_mode = 'OBJECT'
    if active_obj:
        original_mode = active_obj.mode
    
    # --- Set new context for operation ---
    # Ensure we are in object mode before changing active object/selection
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Deselect all, then select and activate the target armature
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')

    virtual_bones: VirtualSkeleton = []
    name_to_index: Dict[str, int] = {}
    
    edit_bones = armature_obj.data.edit_bones

    # First pass: create VirtualBone objects and build name_to_index map
    for i, bone in enumerate(edit_bones):
        if bone.parent:
            local_matrix = bone.parent.matrix.inverted() @ bone.matrix
        else:
            local_matrix = bone.matrix
        
        pos, rot, scale = local_matrix.decompose()
        transform_dict = {
            "position": list(pos),
            "rotation_quat": [rot.w, rot.x, rot.y, rot.z],
            "scale": list(scale)
        }
        
        vb = VirtualBone(name=bone.name, parent_name=bone.parent.name if bone.parent else "", transform_dict=transform_dict, attributes=[], index=i)
        virtual_bones.append(vb)
        name_to_index[vb.name] = i

    # Second pass: resolve parent indices
    for bone in virtual_bones:
        bone.parent_index = name_to_index.get(bone.parent_name, -1)

    # Restore previous state
    # Go back to object mode before changing active object
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Deselect our temporary selection
    armature_obj.select_set(False)

    if active_obj:
        bpy.context.view_layer.objects.active = active_obj
        if bpy.context.mode != original_mode:
            bpy.ops.object.mode_set(mode=original_mode)

    return virtual_bones, name_to_index