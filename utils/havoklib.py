import os, subprocess, tempfile, shutil
from .logger import PrettyPrint


def get_exe_path():
    here = os.path.dirname(__file__)
    exe = os.path.join(here, '..', 'HavokLib', 'HKLib.CLI.exe')
    exe = os.path.normpath(exe)
    return exe


def convert(input_bytes, input_ext):
    tmpdir = tempfile.mkdtemp()
    try:
        input_name = 'input' + input_ext
        input_path = os.path.join(tmpdir, input_name)
        with open(input_path, 'wb') as f:
            f.write(input_bytes)
        exe = get_exe_path()
        try:
            proc = subprocess.run([exe, input_path], cwd=tmpdir, capture_output=True)
        except Exception as e:
            PrettyPrint(f"Failed to start HavokLib executable: {e}", "error")
            raise
        if proc.returncode != 0:
            PrettyPrint(f'HavokLib CLI failed: {proc.stderr.decode(errors="ignore")}', 'error')
            raise Exception('HavokLib failed')
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


def xml_to_hkx(xml_bytes):
    return convert(xml_bytes, '.xml')
