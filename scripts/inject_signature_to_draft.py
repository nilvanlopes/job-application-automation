import subprocess
from pathlib import Path
from job_application_automation.outlook_com_mailer import _to_windows_path

ps_script_path = Path("scripts/fix_outlook_draft_signature.ps1").resolve()
windows_ps_path = _to_windows_path(ps_script_path)

cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", windows_ps_path]
try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
except Exception as e:
    print("RESULT:", e)
