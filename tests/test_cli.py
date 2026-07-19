import pytest

from job_application_automation.cli import build_parser


def test_apply_accepts_optimizer_provider_and_removes_template_flag():
    parser = build_parser()
    args = parser.parse_args([
        "apply",
        "--job-text", "Vaga Python",
        "--resume-file", "resume.pdf",
        "--provider", "gemini",
        "--optimizer-provider", "ollama",
    ])
    assert args.provider == "gemini"
    assert args.optimizer_provider == "ollama"
    assert str(args.resume_file) == "resume.pdf"

    with pytest.raises(SystemExit):
        parser.parse_args([
            "apply",
            "--job-text", "Vaga Python",
            "--optimizer-template", "base.html",
        ])
