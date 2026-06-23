from __future__ import annotations

from types import SimpleNamespace

import pytest

from job_application_automation import cli
from job_application_automation.ocr import OcrError, extract_text_from_image


OPECSIS_OCR_TEXT = """VAGA DE EMPREGO: PROGRAMADOR
PHP / LARAVEL
Local: Palmas
Enviar currículo para vagas@opecsis.com.br
Empresa: OPECsis
"""


def test_extract_text_from_image_uses_embedded_python_engine(tmp_path):
    image_path = tmp_path / "vaga.png"
    image_path.write_bytes(b"fake image bytes")
    calls = []

    class Engine:
        def __call__(self, path):
            calls.append(path)
            return SimpleNamespace(txts=OPECSIS_OCR_TEXT.splitlines())

    text = extract_text_from_image(image_path, engine_factory=lambda: Engine())

    assert "PROGRAMADOR" in text
    assert "vagas@opecsis.com.br" in text
    assert calls == [str(image_path)]


def test_extract_text_from_image_supports_legacy_rapidocr_result(tmp_path):
    image_path = tmp_path / "vaga.png"
    image_path.write_bytes(b"fake image bytes")

    class Engine:
        def __call__(self, path):
            return ([([0, 0], "VAGA DE EMPREGO: PYTHON", 0.99)], 0.1)

    text = extract_text_from_image(image_path, engine_factory=lambda: Engine())

    assert "VAGA DE EMPREGO: PYTHON" in text


def test_extract_text_from_image_reports_embedded_engine_failure(tmp_path):
    image_path = tmp_path / "vaga.png"
    image_path.write_bytes(b"fake image bytes")

    class Engine:
        def __call__(self, path):
            raise RuntimeError("modelo inválido")

    with pytest.raises(OcrError, match="modelo inválido"):
        extract_text_from_image(image_path, engine_factory=lambda: Engine())


def test_extract_text_from_image_restores_job_labels(tmp_path):
    image_path = tmp_path / "vaga.png"
    image_path.write_bytes(b"fake image bytes")

    class Engine:
        def __call__(self, path):
            return SimpleNamespace(
                txts=[
                    "VAGA DE EMPREGO: PROGRAMADOR PHP / LARAVEL Local: Palmas "
                    "Modelo de trabalho: Remoto Enviar currículo para vagas@empresa.com Empresa: Empresa"
                ]
            )

    text = extract_text_from_image(image_path, engine_factory=lambda: Engine())

    assert "LARAVEL\nLocal: Palmas\nModelo de trabalho:" in text
    assert "vagas@empresa.com\nEmpresa: Empresa" in text


def test_cli_passes_embedded_ocr_text_to_workflow(monkeypatch, tmp_path):
    image_path = tmp_path / "vaga.png"
    image_path.write_bytes(b"fake image bytes")
    captured = {}

    monkeypatch.setattr(cli, "extract_text_from_image", lambda path: OPECSIS_OCR_TEXT)
    monkeypatch.setattr(
        cli,
        "run_application",
        lambda request: captured.setdefault(
            "result",
            SimpleNamespace(request=request, send_result=None, output_dir=tmp_path / "out"),
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["job-application-automation", "--job-image", str(image_path)],
    )

    assert cli.main() == 0
    assert captured["result"].request.job_text == OPECSIS_OCR_TEXT


def test_cli_apply_command_passes_review_recipient(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        cli,
        "run_application",
        lambda request: captured.setdefault(
            "result",
            SimpleNamespace(request=request, send_result=None, output_dir=tmp_path / "out"),
        ),
    )

    assert cli.main(
        [
            "apply",
            "--job-text",
            "Vaga Python",
            "--recipient-email",
            "final@example.com",
            "--review-recipient-email",
            "review@example.com",
            "--send",
        ]
    ) == 0

    request = captured["result"].request
    assert request.recipient_email == "final@example.com"
    assert request.review_recipient_email == "review@example.com"
    assert request.send is True


def test_cli_send_command_uses_existing_artifacts(monkeypatch, tmp_path):
    captured = {}

    def fake_send_existing(output_dir, *, recipient_email="", sender_email=""):
        captured["output_dir"] = output_dir
        captured["recipient_email"] = recipient_email
        captured["sender_email"] = sender_email
        return SimpleNamespace(recipient_email=recipient_email, sent_matches=1)

    monkeypatch.setattr(cli, "send_existing_application", fake_send_existing)

    assert cli.main(
        [
            "send",
            "--output-dir",
            str(tmp_path / "application"),
            "--recipient-email",
            "final@example.com",
        ]
    ) == 0

    assert captured["output_dir"] == tmp_path / "application"
    assert captured["recipient_email"] == "final@example.com"
