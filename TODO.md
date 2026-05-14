# HD2SDK - IK Skeleton Implementation TODO

- [x] Add `IkSkeletonID` constant (`0x57a13425279979d7`).
- [x] Implement unit load/save for `ik_skeleton`.
- [x] Implement `ik_skeleton` serialization (hkx <-> xml) using HavokLib CLI.
- [x] Verify unpack/pack workflow with `TEST_IK_SKELETON_SAVE.py`.
- [x] **Task 1: Detect IK Modifications (`detect-ik-modifications`)** - Implement logic to detect when the `ik_skeleton` XML data has been modified by the user so `Entry.IsModified` is properly set during the unit save process.
- [x] **Task 2: IK UI Editor (`add-ik-ui-editor`)** - Add a Blender UI panel to easily edit/view the `ik_skeleton` XML text or export it directly from the UI.
- [ ] **Task 3: Documentation (`update-todo-docs`)** - Update the project documentation and cleanup.

---

사용 대상 AI(블렌더 애드온 코드를 가진 다른 에이전트)에게 줄 수 있는, 실행 가능한 간단하고 명확한 사용법 문서입니다. 이 그대로 따라하면 애드온에 빌드본을 복사하고 바로 호출할 수 있습니다.

1) 전제 (입력)
- 당신에게 제공된 빌드 위치(예): 
  net7.0
- 목표: 이 빌드의 실행파일을 애드온 내부 `bin/`으로 복사하고, 애드온에서 `.hkx` → `.xml` 언팩(및 역팩) 작업을 HKLib.CLI로 수행하게 한다.

2) 파일 배치 작업 (Windows/Python)
- 동작: 빌드 폴더의 실행 파일을 애드온 `bin/` 폴더로 복사
- 예제 (애드온 루트가 `ADDON_ROOT`라 가정):

```python
import shutil, os

build_src = r"C:\Users\HP\Desktop\UTIL\HAVOK\HKLib-main\HKLib-main\HKLib.CLI\bin\Release\net7.0"
addon_root = r"C:\path\to\your\blender_addon"   # 애드온의 실제 경로
dest = os.path.join(addon_root, "bin")

# 복사 (덮어쓰기)
if os.path.exists(dest):
    shutil.rmtree(dest)
shutil.copytree(build_src, dest)
```

3) 애드온에서 호출하는 규칙 (핵심 행동)
- 실행: Call the CLI via subprocess with the absolute file path argument.
- Working directory: set `cwd=os.path.dirname(cli_path)` so the CLI detects/writes sidecar `.prepend` files reliably.
- Inputs/Outputs:
  - Call: `HKLib.CLI.exe <path/to/file.hkx>` → produces `<file>.xml` and `<file>.hkx.prepend` (when needed).
  - Later call: `HKLib.CLI.exe <path/to/file.xml>` → produces new `.hkx` and re-applies `<file>.xml.prepend` or `<file>.prepend` if present.

4) 추천 Python helpers to add to the addon (copy/paste)
- `find_cli(pref_path=None)` — get CLI path (pref → addon bin → PATH)
- `run_cli_async(cli_path, args, cwd=None, on_done=None)` — background run with callback on main thread via `bpy.app.timers.register`.

Example implementation (drop into `hklib_bridge.py` in the addon):

```python
import os, subprocess, threading, bpy

def find_cli(pref=None):
    if pref and os.path.isfile(pref): return pref
    addon_bin = os.path.join(os.path.dirname(__file__), "bin", "HKLib.CLI.exe")
    if os.path.isfile(addon_bin): return addon_bin
    for p in os.environ.get("PATH","").split(os.pathsep):
        cand = os.path.join(p, "HKLib.CLI.exe")
        if os.path.isfile(cand): return cand
    return None

def run_cli_async(cli_path, args, cwd=None, on_done=None):
    def worker():
        proc = subprocess.Popen([cli_path] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate()
        rc = proc.returncode
        if on_done:
            def cb():
                on_done(rc, out, err)
                return None
            bpy.app.timers.register(cb)
    threading.Thread(target=worker, daemon=True).start()
```

Operators (examples to register into existing addon UI):

```python
class HKLIB_OT_unpack(bpy.types.Operator):
    bl_idname = "hklib.unpack"
    bl_label = "HKLib: Unpack .hkx -> .xml"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        cli = find_cli(context.preferences.addons[__package__].preferences.hkcli_path if __package__ in context.preferences.addons else None)
        if not cli:
            self.report({'ERROR'}, "HKLib.CLI not found")
            return {'CANCELLED'}
        inp = self.filepath
        def done(rc, out, err):
            if rc==0: self.report({'INFO'}, "Unpack finished")
            else:
                self.report({'ERROR'}, f"HKLib CLI failed: {rc}")
                print(err)
        run_cli_async(cli, [inp], cwd=os.path.dirname(cli), on_done=done)
        return {'FINISHED'}
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self); return {'RUNNING_MODAL'}
```

동일한 방식으로 `HKLIB_OT_pack` 를 추가해 `.xml` 입력을 넘기면 됩니다.

5) `.prepend` 사이드카 규칙 (AI가 반드시 준수해야 할 점)
- 언팩: 원본 .hkx에서 leading extra bytes가 있으면 CLI가 `<file>.hkx.prepend` 로 저장합니다.
- 편집: 유저/애드온은 생성된 `<file>.xml`을 편집/저장합니다.
- 팩: CLI에 XML을 넘길 때 동일한 디렉터리에 `<file>.xml.prepend` 또는 `<file>.prepend`가 있으면 CLI가 이를 자동으로 재적용해 원본 레이아웃을 복원합니다.
- 구현 팁: 항상 절대 경로 전달, `cwd`는 `os.path.dirname(cli_path)`로 두면 사이드카 감지/쓰기 위치가 일관됩니다.

6) 간단한 테스트 절차 (AI가 자동 실행 가능)
- 1) 복사: build → addon `bin/` (위 스크립트)
- 2) Blender에서 애드온 활성화(또는 사전 등록 스크립트로 operator 등록)
- 3) Unpack 테스트:
```python
# inside Blender Python
bpy.ops.hklib.unpack('INVOKE_DEFAULT')  # 선택창에서 avatar_helldiver.ik_skeleton.hkx 고르기
```
- 4) 확인: 생성된 `avatar_helldiver.ik_skeleton.xml` 및 `.prepend` 존재 확인
- 5) Pack 테스트: 편집 없이 바로 pack 수행 → compare with original (optional)
- 6) (옵션) 바이트 비교: repo에 있는 compare_hkxs.ps1 사용:
```powershell
# run in repo root
powershell -ExecutionPolicy Bypass -File compare_hkxs.ps1
```
이 스크립트는 `.hkx.bak`(원본)과 새로 생성된 `.hkx`를 비교하고 SHA256을 보여줍니다.

7) 에러/로깅 방침 (AI가 출력/보고하도록)
- 캡처 stdout/stderr, 리턴코드 != 0 이면 사용자에게 알림(`self.report({'ERROR'},...)`) 및 전체 stderr를 콘솔에 `print()`로 남김.
- 파일 잠금/권한 문제: 실패 시 사용자에게 파일 경로와 권한 문제를 안내하도록 메시지 작성.

8) 배포/라이센스 지침 (간단)
- 애드온에 `HKLib.CLI.exe`를 포함할 경우, 원저작권/라이선스 파일(LICENSE)을 함께 포함하고 README에 라이선스 표기.
- 실행파일을 포함하지 않고 사용자에게 빌드 폴더를 주는 워크플로라면, AI에게 복사 명령(2)만 실행하도록 지시.

9) 권장 옵션 (성능/규모)
- 여러 파일을 빠르게 처리해야 하면 장기 실행 백그라운드 서버(HTTP/gRPC)를 만들어 애드온에서 요청만 보내는 방법 권장(그러나 더 많은 초기 작업 필요).
- 단순 사용, 쉬운 배포: single-file self-contained exe 포함.