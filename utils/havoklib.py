import os, subprocess, tempfile, shutil, sys
from .logger import PrettyPrint
import bpy # bpy 모듈을 임포트하여 애드온 설정에 접근합니다.


def get_exe_path():
    # 애드온 설정에서 HavokLib 경로를 가져옵니다.
    # 이 경로는 __init__.py의 register 함수에서 기본값으로 설정됩니다.
    havoklib_path = bpy.context.scene.Hd2ToolPanelSettings.HavokLibPath
    
    if not havoklib_path:
        PrettyPrint("HavokLib CLI 경로가 애드온 환경설정에 설정되어 있지 않습니다. 기본 대체 경로를 사용합니다.", "warn")
        # 설정이 비어있을 경우, 기존의 하드코딩된 상대 경로를 대체 경로로 사용합니다.
        here = os.path.dirname(__file__)
        havoklib_path = os.path.join(here, '..', 'HavokLib', 'HKLib.CLI.exe')
        havoklib_path = os.path.normpath(havoklib_path)
    
    if not os.path.exists(havoklib_path):
        raise FileNotFoundError(f"HavokLib CLI 실행 파일을 찾을 수 없습니다: '{havoklib_path}'. 애드온 환경설정에서 경로를 확인해주세요.")
        
    return havoklib_path


def convert(input_bytes, input_ext, reconstruct=False): # reconstruct 매개변수 추가
    tmpdir = tempfile.mkdtemp()
    try:
        input_name = 'input' + input_ext
        input_path = os.path.join(tmpdir, input_name)
        with open(input_path, 'wb') as f:
            f.write(input_bytes)
        
        exe = get_exe_path() # 설정에서 가져온 경로를 사용합니다.
        
        command = [exe, input_path]
        if reconstruct: # reconstruct 플래그가 True인 경우 명령에 추가
            command.append("--reconstruct")

        try:
            # Add a timeout to prevent the addon from freezing indefinitely.
            # 60 seconds should be more than enough for any reasonable file.
            proc = subprocess.run(command, cwd=tmpdir, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        except subprocess.TimeoutExpired:
            PrettyPrint(f"HavokLib CLI timed out after 60 seconds. The file may be too large, corrupted, or HKLib.CLI.exe has an issue.", "error")
            return None # Return None to indicate failure
        except Exception as e:
            PrettyPrint(f"Failed to start HavokLib executable: {e}", "error")
            raise
        if proc.returncode != 0:
            error_output = proc.stderr.strip() if proc.stderr else f"HavokLib CLI가 종료 코드 {proc.returncode}로 실패했습니다."
            PrettyPrint(f'HavokLib CLI 실패: {error_output}', 'error')
            return None # Return None to indicate failure
        # find output file (anything other than input)
        files = [f for f in os.listdir(tmpdir) if os.path.join(tmpdir, f) != input_path]
        out_file = None
        for fname in files:
            if fname.lower().endswith('.xml') or fname.lower().endswith('.hkx'):
                out_file = fname
                break
        if not out_file and files:
            out_file = files[0]
        if not out_file:
            raise Exception('No output file produced by HavokLib')
        out_path = os.path.join(tmpdir, out_file)
        with open(out_path, 'rb') as f:
            out_bytes = f.read()
        return out_bytes
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


def hkx_to_xml(hkx_bytes):
    return convert(hkx_bytes, '.hkx')


def xml_to_hkx(xml_bytes, reconstruct=False): # reconstruct 매개변수 추가
    return convert(xml_bytes, '.xml', reconstruct=reconstruct) # reconstruct 매개변수를 전달
