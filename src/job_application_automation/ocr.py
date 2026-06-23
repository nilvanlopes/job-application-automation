from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable


class OcrError(RuntimeError):
    pass


def extract_text_from_image(
    image_path: Path | str,
    *,
    engine_factory: Callable[[], Any] | None = None,
) -> str:
    """Extract text using the OCR engine installed with this Python project."""

    path = Path(image_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {path}")
    if not path.is_file():
        raise ValueError(f"O caminho da imagem não é um arquivo: {path}")

    try:
        factory = engine_factory or _rapidocr_factory
        result = factory()(str(path))
    except Exception as exc:
        raise OcrError(f"Falha no OCR integrado: {exc}") from exc

    texts = getattr(result, "txts", None)
    if texts is None and isinstance(result, tuple):
        texts = _legacy_result_texts(result[0])
    if not texts:
        raise OcrError("O OCR integrado não encontrou texto na imagem.")
    return _clean_ocr_text("\n".join(str(text) for text in texts if str(text).strip()))


def _rapidocr_factory():
    from rapidocr import RapidOCR

    return RapidOCR()


def _legacy_result_texts(result: Any) -> list[str]:
    if not result:
        return []
    texts: list[str] = []
    for line in result:
        if isinstance(line, (list, tuple)) and len(line) >= 2:
            texts.append(str(line[1]))
    return texts


def _clean_ocr_text(text: str) -> str:
    cleaned = "\n".join(
        line.rstrip()
        for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ).strip()
    cleaned = _restore_job_label_line_breaks(cleaned)
    if not cleaned:
        raise OcrError("O OCR integrado não retornou texto utilizável.")
    return cleaned + "\n"


def _restore_job_label_line_breaks(text: str) -> str:
    labels = [
        "Local:",
        "Modelo de trabalho:",
        "DESCRIÇÃO DA VAGA:",
        "Descrição da vaga:",
        "REQUISITOS",
        "DIFERENCIAIS",
        "BENEFÍCIOS",
        "Enviar currículo para",
        "ou entre em contato",
        "Empresa:",
    ]
    normalized = text
    for label in labels:
        normalized = re.sub(rf"\s+({re.escape(label)})", r"\n\1", normalized)
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()
