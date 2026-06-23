from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .ocr import extract_text_from_image
from .workflow import ApplicationRequest, run_application, send_existing_application


def _load_local_env() -> None:
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            _load_env_file(candidate)


def _load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-application-automation",
        description="Gera uma candidatura para revisão e envia artefatos aprovados pelo Outlook Classic.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Gera a candidatura e opcionalmente envia para revisão.",
    )
    _add_apply_arguments(apply_parser)

    send_parser = subparsers.add_parser(
        "send",
        help="Envia artefatos já gerados sem reprocessar a candidatura.",
    )
    send_parser.add_argument("--output-dir", type=Path, required=True)
    send_parser.add_argument(
        "--recipient-email",
        default="",
        help="Destinatário final. Se omitido, usa o e-mail salvo nos artefatos.",
    )
    send_parser.add_argument(
        "--sender-email",
        default=os.getenv("OUTLOOK_COM_SENDER_EMAIL", "nilvanlopes@outlook.com"),
    )
    return parser


def _add_apply_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--job-text", help="Texto da vaga.")
    source.add_argument("--job-file", type=Path, help="Arquivo de texto com a vaga.")
    source.add_argument("--job-image", type=Path, help="Imagem da vaga processada pelo OCR local.")
    parser.add_argument(
        "--recipient-email",
        default="",
        help="Destinatário final da vaga. Não recebe o e-mail de revisão.",
    )
    parser.add_argument(
        "--review-recipient-email",
        default="",
        help="Destinatário do e-mail de revisão. Padrão: JOB_APPLICATION_REVIEW_EMAIL ou pyuloko7@gmail.com.",
    )
    parser.add_argument(
        "--resume-file",
        type=Path,
        help="Currículo base alternativo. Sem esta opção, usa o currículo do Obsidian configurado.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Diretório exato da execução. Por padrão cria output/<empresa>-<cargo>.",
    )
    parser.add_argument("--send", action="store_true", help="Envia para revisão pelo Outlook Classic COM.")
    parser.add_argument(
        "--sender-email",
        default=os.getenv("OUTLOOK_COM_SENDER_EMAIL", "nilvanlopes@outlook.com"),
    )
    parser.add_argument("--optimizer-output-name", default="")
    parser.add_argument(
        "--optimizer-template",
        type=Path,
        help="Template HTML canônico usado pelo curriculum-optimizer.",
    )


def main(argv: list[str] | None = None) -> int:
    _load_local_env()
    parser = build_parser()
    args = parser.parse_args(_normalize_argv(sys.argv[1:] if argv is None else argv))
    try:
        if args.command == "send":
            result = send_existing_application(
                args.output_dir,
                recipient_email=args.recipient_email,
                sender_email=args.sender_email,
            )
            print(
                f"Artefatos enviados para {result.recipient_email}; "
                f"sent={result.sent_matches}; arquivos={args.output_dir.resolve()}"
            )
            return 0

        job_text = _resolve_job_text(args)
        result = run_application(
            ApplicationRequest(
                job_text=job_text,
                recipient_email=args.recipient_email,
                review_recipient_email=args.review_recipient_email,
                resume_file=args.resume_file,
                output_dir=args.output_dir,
                send=args.send,
                sender_email=args.sender_email,
                optimizer_output_name=args.optimizer_output_name,
                optimizer_template=args.optimizer_template,
            )
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if result.send_result:
        print(
            f"Candidatura enviada para revisão em {result.recipient_email}; "
            f"sent={result.send_result.sent_matches}; arquivos={result.output_dir.resolve()}"
        )
    else:
        print(f"Candidatura gerada em {result.output_dir.resolve()}")
    return 0


def _resolve_job_text(args: argparse.Namespace) -> str:
    if args.job_file:
        return args.job_file.read_text(encoding="utf-8")
    if args.job_image:
        return extract_text_from_image(args.job_image)
    return args.job_text


def _normalize_argv(argv: list[str]) -> list[str]:
    if argv and argv[0] in {"apply", "send"}:
        return argv
    return ["apply", *argv]


if __name__ == "__main__":
    raise SystemExit(main())
