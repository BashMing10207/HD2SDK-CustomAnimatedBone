from ..utils.logger import PrettyPrint
from ..utils.memoryStream import MemoryStream
from ..utils.havoklib import hkx_to_xml, xml_to_hkx

class StingrayIkSkeleton:
    def __init__(self):
        # raw bytes as stored in TocData (hkx) and optional xml form
        self.Raw = b""
        self.Xml = b""
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
                xml = hkx_to_xml(havok_data)
                if xml:
                    self.Xml = xml
                    self.IsXml = True
            except Exception as e:
                PrettyPrint(f"HavokLib unpack failed: {e}", "warn")
        else:
            # Writing: if an XML representation exists, pack it back to hkx via HavokLib
            if self.IsXml and self.Xml:
                try:
                    hkx = xml_to_hkx(self.Xml)
                    # 보존했던 Stingray 메타데이터를 순수 hkx 앞부분에 다시 병합하여 저장
                    merged_data = self.PreData + hkx
                    self.Raw = merged_data
                    f.Data = bytearray(merged_data)
                    f.Location = len(merged_data)
                except Exception as e:
                    PrettyPrint(f"HavokLib pack failed: {e}", "error")
                    # fallback to raw
                    if isinstance(self.Raw, str):
                        self.Raw = self.Raw.encode()
                    f.Data = bytearray(self.Raw)
                    f.Location = len(self.Raw)
            else:
                if isinstance(self.Raw, str):
                    self.Raw = self.Raw.encode()
                f.Data = bytearray(self.Raw)
                f.Location = len(self.Raw)
        return self
