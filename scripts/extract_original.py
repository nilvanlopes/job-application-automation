import subprocess
import shutil
from pathlib import Path

def copy_and_read():
    workspace = Path("/home/pyu/docker/job-application-automation")
    input_dir = workspace / "input"
    input_dir.mkdir(exist_ok=True)
    dest_pdf = input_dir / "curriculo_nilvan_lopes.pdf"
    
    ps_cmd = """
    $src = "C:\\Users\\pyu\\OneDrive\\Documentos\\Obsidian\\dev\\curriculo_nilvan_lopes.pdf"
    if (Test-Path $src) {
        Write-Host "FOUND_SRC"
        $bytes = [System.IO.File]::ReadAllBytes($src)
        Write-Host "BYTES_LENGTH=$($bytes.Length)"
    } else {
        Write-Error "NOT_FOUND"
    }
    """
    res = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=30)
    print("PS result:", res.stdout, res.stderr)
    
    # Try direct copy from /mnt/c
    mnt_path = Path("/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/curriculo_nilvan_lopes.pdf")
    if mnt_path.exists():
        shutil.copy2(mnt_path, dest_pdf)
        print("Copied via /mnt/c, size:", dest_pdf.stat().st_size)
    else:
        # Copy via powershell base64 or file copy
        ps_copy = f"""
        Copy-Item -Path "C:\\Users\\pyu\\OneDrive\\Documentos\\Obsidian\\dev\\curriculo_nilvan_lopes.pdf" -Destination "\\\\wsl.localhost\\Ubuntu\\home\\pyu\\docker\\job-application-automation\\input\\curriculo_nilvan_lopes.pdf" -Force
        """
        res2 = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_copy], capture_output=True, text=True, timeout=30)
        print("PS copy result:", res2.stdout, res2.stderr)

    if dest_pdf.exists():
        import pypdf
        reader = pypdf.PdfReader(str(dest_pdf))
        print(f"PDF Pages: {len(reader.pages)}")
        full_text = "\n".join(page.extract_text() for page in reader.pages)
        (input_dir / "curriculo_nilvan_lopes_extracted.txt").write_text(full_text, encoding="utf-8")
        print("Extracted text preview (first 1000 chars):")
        print(full_text[:1000])
        print("TOTAL LENGTH:", len(full_text))

if __name__ == "__main__":
    copy_and_read()
