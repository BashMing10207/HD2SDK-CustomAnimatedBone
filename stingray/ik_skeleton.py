from ..utils.logger import PrettyPrint
from ..utils.memoryStream import MemoryStream
from ..utils.havoklib import hkx_to_xml, xml_to_hkx
from .virtual_skeleton import VirtualSkeleton

class StingrayIkSkeleton:
    def __init__(self):
        # raw bytes as stored in TocData (hkx) and optional xml form
        self.Raw = b""
        self.Xml = b""
        self.is_modified = False
        self.IsXml = False
        self.PreData = b""

    def Serialize(self, f: MemoryStream):
        # Reading: capture raw bytes and attempt to unpack to xml using HavokLib
        if f.IsReading():
            self.Raw = f.read()
            
            # Havok 매직 넘버를 찾아 앞쪽의 Stingray 엔진 메타데이터를 분리 및 보존
            havok_magic = b"\x57\xE0\xE0\x57"
            magic_idx = self.Raw.find(havok_magic)
            if magic_idx != -1:
                self.PreData = self.Raw[:magic_idx]
                havok_data = self.Raw[magic_idx:]
            else:
                havok_data = self.Raw
                
            try:
                PrettyPrint("  - Unpacking Havok data to XML...", "info")
                xml = hkx_to_xml(havok_data)
                if xml:
                    PrettyPrint("  - Unpack successful.", "success")
                    self.Xml = xml
                    self.IsXml = True
                else:
                    PrettyPrint("  - Unpack failed. HavokLib returned no data.", "error")
            except Exception as e:
                PrettyPrint(f"HavokLib unpack for ik_skeleton failed: {e}", "warn")
        else: # Writing
            try:
                import lxml.etree as etree
            except ImportError:
                PrettyPrint("Error: lxml module not found. Please ensure it's installed and restart Blender.", "error")
                return self # lxml 없이 진행할 수 없음
            # Writing: if an XML representation exists, pack it back to hkx via HavokLib
            if self.is_modified and self.IsXml and self.Xml:
                try:
                    # PHASE 3: Trigger Tagfile Reconstruction.
                    # The 'reconstruct=True' flag is critical. It instructs HavokLib
                    # to perform a full, multi-pass serialization, recalculating all
                    # offsets and rebuilding the PTCH section from scratch.
                    hkx = xml_to_hkx(self.Xml, reconstruct=True)
                    # 보존했던 Stingray 메타데이터를 순수 hkx 앞부분에 다시 병합하여 저장
                    f.write(self.PreData + hkx)
                except Exception as e:
                    PrettyPrint(f"HavokLib pack failed: {e}", "error")
                    # fallback to raw
                    f.write(self.Raw)
            else:
                f.write(self.Raw)
        return self

    def sync_with_skeleton(self, skeleton: VirtualSkeleton):
        try:
            import lxml.etree as etree
        except ImportError:
            PrettyPrint("Error: lxml module not found. Please ensure it's installed and restart Blender.", "error")
            return False # lxml 없이 진행할 수 없음
        """Patches the hkaSkeleton within the .ik_skeleton file."""
        if not self.IsXml:
            PrettyPrint(f"Cannot sync ik_skeleton: not valid XML.", "warn")
            return False

        PrettyPrint(f"Syncing ik_skeleton with virtual skeleton...", "info")
        root = etree.fromstring(self.Xml)

        # Find the hkaSkeleton object
        skeleton_obj = root.find(".//hkobject[@class='hkaSkeleton']")
        if skeleton_obj is None:
            PrettyPrint(f"Could not find hkaSkeleton object in ik_skeleton. Skipping.", "warn")
            return False

        # --- Rebuild skeleton data from VirtualSkeleton (SoT) ---
        new_bone_count = len(skeleton)

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

        # 3. Update reference pose
        ref_pose_param = skeleton_obj.find("./hkparam[@name='m_referencePose']")
        ref_pose_param.clear()
        ref_pose_param.set('numelements', str(new_bone_count))
        for bone in skeleton:
            pos, rot, scale = bone.transform.decompose()
            tqs_text = f"({pos.x:.6f} {pos.y:.6f} {pos.z:.6f})({rot.x:.6f} {rot.y:.6f} {rot.z:.6f} {rot.w:.6f})({scale.x:.6f} {scale.y:.6f} {scale.z:.6f})"
            etree.SubElement(ref_pose_param, 'hkval').text = tqs_text

        self.Xml = etree.tostring(root, encoding='utf-8')
        self.is_modified = True
        PrettyPrint(f"Successfully patched ik_skeleton.", "success")
        return True
