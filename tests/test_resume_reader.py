from types import SimpleNamespace

import pytest

from job_application_automation.resume_reader import ResumeReadError, read_resume_text


@pytest.mark.parametrize("extension", ["md", "txt"])
def test_reads_utf8_text_formats(tmp_path, extension):
    resume = tmp_path / f"resume.{extension}"
    resume.write_text("Ana\nReact", encoding="utf-8")
    assert read_resume_text(resume) == "Ana\nReact"


def test_sanitizes_html_to_visible_text(tmp_path):
    resume = tmp_path / "resume.html"
    resume.write_text(
        '<html><style>.x{}</style><script>secret()</script><body><h1>Ana</h1><p>React</p></body></html>',
        encoding="utf-8",
    )
    text = read_resume_text(resume)
    assert "Ana" in text
    assert "React" in text
    assert "secret" not in text


def test_extracts_pdf_text_and_requires_ocr_for_scanned_pdf(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake")
    factory = lambda path: SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda: "Ana"), SimpleNamespace(extract_text=lambda: "React")]
    )
    assert read_resume_text(resume, pdf_reader_factory=factory) == "Ana\nReact"

    scanned = lambda path: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")])
    with pytest.raises(ResumeReadError, match="OCR"):
        read_resume_text(resume, pdf_reader_factory=scanned)


def test_rejects_empty_and_invalid_resume(tmp_path):
    empty = tmp_path / "resume.txt"
    empty.write_text("   ", encoding="utf-8")
    with pytest.raises(ResumeReadError, match="vazio"):
        read_resume_text(empty)
    invalid = tmp_path / "resume.docx"
    invalid.write_bytes(b"doc")
    with pytest.raises(ResumeReadError, match="Extensão"):
        read_resume_text(invalid)
