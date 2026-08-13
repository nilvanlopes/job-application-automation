from job_application_automation.ai_email import _normalize_email_body_structure


def test_normalizer_preserves_three_single_line_paragraphs_after_greeting():
    body = (
        "Olá,\n\n"
        "Tenho interesse na vaga.\n"
        "Atuo com PHP e MySQL em sistemas reais.\n"
        "Gostaria de conversar sobre a oportunidade."
    )

    normalized = _normalize_email_body_structure(body)

    assert normalized.split("\n\n") == [
        "Olá,",
        "Tenho interesse na vaga.",
        "Atuo com PHP e MySQL em sistemas reais.",
        "Gostaria de conversar sobre a oportunidade.",
    ]
