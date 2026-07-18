from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

from pypdf import PdfReader


SUPPORTED_RESUME_EXTENSIONS = {".md", ".txt", ".html", ".htm", ".pdf"}


class ResumeReadError(ValueError):
    pass


def read_resume_text(
    resume_path: Path,
    *,
    pdf_reader_factory: Callable = PdfReader,
) -> str:
    path = Path(resume_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de currículo não encontrado: {path}")
    if not path.is_file():
        raise ResumeReadError(f"A fonte do currículo não é um arquivo: {path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_RESUME_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_RESUME_EXTENSIONS))
        raise ResumeReadError(f"Extensão de currículo inválida: {extension or '(sem extensão)'}. Use {allowed}.")
    if path.stat().st_size == 0:
        raise ResumeReadError(f"Arquivo de currículo vazio: {path}")

    if extension == ".pdf":
        try:
            reader = pdf_reader_factory(path)
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            raise ResumeReadError(f"Não foi possível extrair texto do PDF {path}: {exc}") from exc
        if not text:
            raise ResumeReadError(
                f"O PDF não contém texto extraível: {path}. Execute OCR ou forneça HTML, Markdown ou TXT."
            )
        return text

    content = path.read_text(encoding="utf-8-sig")
    if extension in {".html", ".htm"}:
        parser = _ResumeHTMLTextExtractor()
        parser.feed(content)
        content = parser.text()
    content = content.strip()
    if not content:
        raise ResumeReadError(f"Arquivo de currículo vazio: {path}")
    return content


class _ResumeHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "iframe", "object", "embed"}:
            self._skip_depth += 1
        elif not self._skip_depth and tag.lower() in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "iframe", "object", "embed"}:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif not self._skip_depth and tag.lower() in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(line.strip() for line in " ".join(self._parts).splitlines() if line.strip())
