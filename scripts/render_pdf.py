import subprocess
import shutil
from pathlib import Path

def main():
    root = Path("/home/pyu/docker/job-application-automation/output/cesfa-tecnico-de-tecnologia-da-informacao")
    html_file = root / "Curriculo_Otimizado.html"
    pdf_file = root / "Curriculo_Nilvan_Lopes_Tecnico_de_Tecnologia_da_Informacao.pdf"
    
    # Target paths in Windows
    win_temp_html = Path("/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo_Otimizado_CESFA.html")
    win_temp_pdf = Path("/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo_Nilvan_Lopes_Tecnico_de_Tecnologia_da_Informacao.pdf")
    
    if win_temp_pdf.exists():
        win_temp_pdf.unlink()
    if pdf_file.exists():
        pdf_file.unlink()
        
    shutil.copy2(html_file, win_temp_html)
    
    win_html_path = "C:\\Users\\pyu\\OneDrive\\Documentos\\Obsidian\\dev\\Curriculo_Otimizado_CESFA.html"
    win_pdf_path = "C:\\Users\\pyu\\OneDrive\\Documentos\\Obsidian\\dev\\Curriculo_Nilvan_Lopes_Tecnico_de_Tecnologia_da_Informacao.pdf"
    
    # --headless=new --no-pdf-header-footer guarantees zero header/footer print markings
    ps_script = f"""
$browsers = @(
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
)

$browserPath = $null
foreach ($b in $browsers) {{
    if (Test-Path $b) {{
        $browserPath = $b
        break
    }}
}}

if (-not $browserPath) {{
    $cmd = Get-Command msedge.exe -ErrorAction SilentlyContinue
    if ($cmd) {{ $browserPath = $cmd.Source }}
}}

if (-not $browserPath) {{
    Write-Error "No supported browser found."
    exit 1
}}

Write-Host "Using browser: $browserPath"
& $browserPath --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --run-all-compositor-stages-before-draw --print-to-pdf="{win_pdf_path}" "{win_html_path}"
Start-Sleep -Seconds 3
if (Test-Path "{win_pdf_path}") {{
    Write-Host "PDF_SUCCESS"
}} else {{
    Write-Error "PDF generation failed."
    exit 1
}}
"""
    res = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=60)
    print("PS exit code:", res.returncode)
    
    if win_temp_pdf.exists():
        shutil.copy2(win_temp_pdf, pdf_file)
        print("Successfully generated clean PDF without headers/footers! File size:", pdf_file.stat().st_size)
    else:
        raise RuntimeError("PDF generation failed: win_temp_pdf does not exist.")

if __name__ == "__main__":
    main()
