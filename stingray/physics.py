from .virtual_skeleton import VirtualSkeleton
from ..utils import havoklib
from ..utils.memoryStream import MemoryStream
from ..utils.logger import PrettyPrint

class StingrayPhysics:
    def __init__(self):
        self.Raw = b""
        self.Xml = b""
        self.IsXml = False
        self.PreData = b""
        self.is_modified = False

    def Serialize(self, f: MemoryStream):
        if f.IsReading():
            try:
                import lxml.etree as etree
            except ImportError:
                PrettyPrint("Error: lxml module not found. Please ensure it's installed and restart Blender.", "error")
                return self # lxml 없이 진행할 수 없음
            self.Raw = f.read()
            havok_magic = b"\x57\xE0\xE0\x57"
            magic_idx = self.Raw.find(havok_magic)
            if magic_idx != -1:
                self.PreData = self.Raw[:magic_idx]
                havok_data = self.Raw[magic_idx:]
            else:
                havok_data = self.Raw
            try:
                PrettyPrint("  - Unpacking Havok data to XML...", "info")
                xml = havoklib.hkx_to_xml(havok_data)
                if xml:
                    PrettyPrint("  - Unpack successful.", "success")
                    self.Xml = xml
                    self.IsXml = True
                else:
                    PrettyPrint("  - Unpack failed. HavokLib returned no data.", "error")
            except Exception as e:
                PrettyPrint(f"HavokLib unpack for physics failed: {e}", "error")
        else: # Writing
            try:
                import lxml.etree as etree
            except ImportError:
                PrettyPrint("Error: lxml module not found. Please ensure it's installed and restart Blender.", "error")
                return self # lxml 없이 진행할 수 없음
            if self.is_modified and self.IsXml:
                try:
                    hkx = havoklib.xml_to_hkx(self.Xml, reconstruct=True)
                    merged_data = self.PreData + hkx
                    f.write(merged_data)
                except Exception as e:
                    print(f"HavokLib pack for physics failed: {e}")
                    f.write(self.Raw)
            else:
                f.write(self.Raw)
        return self

    def sync_with_skeleton(self, skeleton: VirtualSkeleton):
        """
        .physics 파일의 본 데이터를 가상 스켈레톤(SoT)에 맞춰 동기화합니다.
        """
        try:
            import lxml.etree as etree
        except ImportError:
            PrettyPrint("Error: lxml module not found. Please ensure it's installed and restart Blender.", "error")
            return False # lxml 없이 진행할 수 없음

        if not self.IsXml:
            PrettyPrint(f"Cannot sync physics: not valid XML.", "warn")
            return False

        PrettyPrint(f"Syncing physics with virtual skeleton...", "info")
        root = etree.fromstring(self.Xml)

        # Physics 파일 내의 모든 hkaSkeleton 객체를 찾습니다.
        skeleton_objs = root.findall(".//hkobject[@class='hkaSkeleton']")
        if not skeleton_objs:
            PrettyPrint(f"Could not find any hkaSkeleton object in physics file. Skipping.", "warn")
            return False

        was_modified = False
        new_bone_count = len(skeleton)

        for i, skeleton_obj in enumerate(skeleton_objs):
            PrettyPrint(f"  - Patching skeleton #{i+1}/{len(skeleton_objs)} in physics file...", "info")
            
            # 1. Update bones array
            bones_param = skeleton_obj.find("./hkparam[@name='m_bones']")
            bones_param.clear()
            bones_param.set('numelements', str(new_bone_count))
            for bone in skeleton:
                bone_el = etree.SubElement(bones_param, 'hkobject')
                etree.SubElement(bone_el, 'hkparam', name='m_name').text = bone.name
                etree.SubElement(bone_el, 'hkparam', name='m_lockTranslation').text = 'false'

            # 2. Update parent indices
            parent_indices_param = skeleton_obj.find("./hkparam[@name='m_parentIndices']")
            parent_indices_param.set('numelements', str(new_bone_count))
            parent_indices_param.text = ' '.join(str(b.parent_index) for b in skeleton)

            # 3. Update reference pose (This was missing)
            ref_pose_param = skeleton_obj.find("./hkparam[@name='m_referencePose']")
            if ref_pose_param is not None: # Not all skeletons in physics files have a reference pose
                ref_pose_param.clear()
                ref_pose_param.set('numelements', str(new_bone_count))
                for bone in skeleton:
                    pos, rot, scale = bone.transform.decompose()
                    tqs_text = f"({pos.x:.6f} {pos.y:.6f} {pos.z:.6f})({rot.x:.6f} {rot.y:.6f} {rot.z:.6f} {rot.w:.6f})({scale.x:.6f} {scale.y:.6f} {scale.z:.6f})"
                    etree.SubElement(ref_pose_param, 'hkval').text = tqs_text
            
            was_modified = True

        if not was_modified:
            return False

        self.Xml = etree.tostring(root, encoding='utf-8')
        self.is_modified = True
        PrettyPrint(f"Successfully patched {len(skeleton_objs)} skeleton(s) in physics file.", "success")
        return True