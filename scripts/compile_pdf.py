from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _to_windows_path(path: Path) -> str:
    resolved = path.resolve()
    text = str(resolved)
    if text.startswith("/mnt/") and len(text) > 6:
        drive = text[5]
        rest = text[7:].replace("/", "\\")
        return f"{drive.upper()}:\\{rest}"
    return "\\\\wsl.localhost\\Ubuntu" + text.replace("/", "\\")


def compile_resume_pdf(
    output_dir: Path | str,
    pdf_name: str = "",
    html_name: str = "Curriculo_Otimizado.html",
) -> Path:
    out_dir = Path(output_dir).resolve()
    if not out_dir.exists():
        raise FileNotFoundError(f"Diretório de saída não encontrado: {out_dir}")

    html_file = out_dir / html_name
    if not html_file.exists():
        raise FileNotFoundError(f"Arquivo HTML do currículo não encontrado: {html_file}")

    if not pdf_name:
        # Tenta localizar o nome do PDF no manifesto ou no cargo estruturado
        manifest_path = out_dir / "application_manifest.json"
        if manifest_path.exists():
            import json

            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                pdf_name = manifest.get("resume_pdf", "")
            except Exception:
                pass

        if not pdf_name:
            # Fallback buscando pelo título no job_structured.json
            job_path = out_dir / "job_structured.json"
            if job_path.exists():
                import json

                try:
                    job = json.loads(job_path.read_text(encoding="utf-8"))
                    clean_title = (
                        job.get("title", "Desenvolvedor")
                        .replace(" ", "_")
                        .replace("/", "_")
                    )
                    pdf_name = f"Curriculo_Nilvan_Lopes_{clean_title}.pdf"
                except Exception:
                    pass

        if not pdf_name:
            pdf_name = "Curriculo_Nilvan_Lopes.pdf"

    pdf_file = out_dir / pdf_name
    win_html = _to_windows_path(html_file)
    win_pdf = _to_windows_path(pdf_file)

    browsers = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]

    for browser in browsers:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={win_pdf}",
            win_html,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if pdf_file.exists() and pdf_file.stat().st_size > 0:
                print(f"[PDF_SUCCESS] PDF gerado via {Path(browser).name}: {pdf_file} ({pdf_file.stat().st_size} bytes)")
                return pdf_file
        except Exception:
            continue

    # Fallback via powershell.exe
    ps_cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        f"""
        $browsers = @(
            'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
            'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
        )
        $browser = $null
        foreach ($b in $browsers) {{ if (Test-Path $b) {{ $browser = $b; break }} }}
        if (-not $browser) {{ $browser = (Get-Command msedge.exe -ErrorAction SilentlyContinue).Source }}
        
        & $browser --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --run-all-compositor-stages-before-draw --print-to-pdf='{win_pdf}' '{win_html}'
        Start-Sleep -Seconds 2
        """,
    ]
    try:
        subprocess.run(ps_cmd, capture_output=True, text=True, timeout=35)
        if pdf_file.exists() and pdf_file.stat().st_size > 0:
            print(f"[PDF_SUCCESS] PDF gerado via PowerShell/Edge: {pdf_file} ({pdf_file.stat().st_size} bytes)")
            return pdf_file
    except Exception as exc:
        raise RuntimeError(f"Falha na compilação do PDF: {exc}") from exc

    if not pdf_file.exists() or pdf_file.stat().st_size == 0:
        raise RuntimeError(f"Arquivo PDF não foi gerado em {pdf_file}")

    return pdf_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Compila o currículo HTML em PDF vetorial A4 via Edge/Chrome Headless.")
    parser.add_argument("--output-dir", "-o", required=True, type=Path, help="Diretório da candidatura (ex: output/<empresa>-<cargo>)")
    parser.add_argument("--pdf-name", "-p", default="", help="Nome do PDF final (opcional)")
    args = parser.parse_args()

    try:
        compile_resume_pdf(args.output_dir, pdf_name=args.pdf_name)
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
