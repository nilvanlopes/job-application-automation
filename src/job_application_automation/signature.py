from __future__ import annotations

from dataclasses import dataclass
import re
from textwrap import dedent

from .models import CandidateProfile


@dataclass(slots=True)
class SignatureProfile:
    name: str
    role: str
    phone: str
    email: str
    website: str
    linkedin: str
    github: str
    whatsapp: str

    @classmethod
    def from_candidate(cls, candidate: CandidateProfile) -> "SignatureProfile":
        return cls(
            name=candidate.name,
            role=candidate.title,
            phone=candidate.phone,
            email=candidate.email,
            website=candidate.website,
            linkedin=candidate.linkedin,
            github=candidate.github,
            whatsapp=candidate.whatsapp,
        )


def build_signature_text(profile: SignatureProfile) -> str:
    whatsapp_url = _resolve_whatsapp_url(profile)
    phone_display = _format_phone_display(profile.phone)
    return dedent(
        f"""
        --
        {profile.name}
        {profile.role}
        T: {phone_display}
        E: {profile.email}
        GitHub: {profile.github}
        LinkedIn: {profile.linkedin}
        WhatsApp: {whatsapp_url}
        """
    ).strip()


def build_signature_html(profile: SignatureProfile) -> str:
    phone_display = _format_phone_display(profile.phone)
    phone_href = _format_tel_href(profile.phone)
    whatsapp_url = _resolve_whatsapp_url(profile)
    return dedent(
        f"""
        <style>
          @media only screen and (max-width: 480px) {{
            .nl-signature-wrap {{ width:100% !important; max-width:600px !important; }}
            .nl-signature-card {{ width:100% !important; }}
            .nl-signature-pad {{ padding:14px 14px 12px 14px !important; }}
            .nl-signature-name {{ width:100% !important; max-width:229px !important; height:auto !important; }}
            .nl-signature-role {{ width:92% !important; max-width:195px !important; height:auto !important; margin-left:8px !important; }}
            .nl-signature-photo {{ width:72px !important; height:72px !important; }}
            .nl-signature-bar-lg {{ width:100% !important; max-width:150px !important; }}
            .nl-signature-bar-md {{ width:88% !important; max-width:132px !important; }}
            .nl-signature-bar-sm {{ width:76% !important; max-width:114px !important; }}
            .nl-signature-icons a {{ margin-left:8px !important; }}
          }}
        </style>
        <div class="nl-signature-wrap" style="width:100%; max-width:600px; font-family:Arial,Helvetica,sans-serif;">
          <table cellpadding="0" cellspacing="0" border="0" role="presentation" width="600"
                 background="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/background.png"
                 class="nl-signature-card"
                 style="width:100%; max-width:600px; min-height:200px; border-collapse:separate; border-spacing:0; border-radius:12px; overflow:hidden; border-bottom:6px solid #d4af37; background-color:#0d0d0d; background-image:url('https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/background.png'); background-repeat:no-repeat; background-size:cover; background-position:center center;">
            <tr>
              <td valign="top" class="nl-signature-pad" style="padding:15px 30px 18px 18px;">
                <table cellpadding="0" cellspacing="0" border="0" role="presentation" width="100%" style="width:100%; border-collapse:collapse;">
                  <tr>
                    <td valign="middle" width="58%" style="width:58%; padding-right:12px;">
                      <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/nilvan-lopes.png" width="229" height="61" alt="{profile.name}" class="nl-signature-name" style="display:block; width:229px; max-width:100%; height:auto; border:0; outline:none;">
                      <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/nilvan-role.png" width="195" height="18" alt="{profile.role}" class="nl-signature-role" style="display:block; width:195px; max-width:92%; height:auto; margin-left:13px; opacity:0.92; border:0; outline:none;">

                      <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin-top:8px;">
                        <tr>
                          <td style="padding:0 0 5px 0; font-size:12.5px; line-height:14px; color:#ffffff; opacity:0.90;">
                            <span style="color:#d4af37; font-weight:700;">T:</span>
                            <a href="{phone_href}" style="color:#ffffff; text-decoration:none;">{phone_display}</a>
                          </td>
                        </tr>
                        <tr>
                          <td style="padding:0 0 5px 0; font-size:12.5px; line-height:14px; color:#ffffff; opacity:0.90;">
                            <span style="color:#d4af37; font-weight:700;">E:</span>
                            <a href="mailto:{profile.email}" style="color:#ffffff; text-decoration:none;">{profile.email}</a>
                          </td>
                        </tr>
                        <!-- Website disabled for now.
                        <tr>
                          <td style="padding:0; font-size:12.5px; line-height:14px; color:#ffffff; opacity:0.90;">
                            <span style="color:#d4af37; font-weight:700;">W:</span>
                            <a href="{profile.website}" target="_blank" style="color:#ffffff; text-decoration:none;">{_format_website_label(profile.website)}</a>
                          </td>
                        </tr>
                        -->
                      </table>
                    </td>

                    <td valign="middle" width="42%" style="width:42%; text-align:right;">
                      <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="display:inline-table; margin-left:auto; border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
                        <tr>
                          <td align="right" style="padding-bottom:10px; line-height:0; font-size:0;">
                            <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/eu.png"
                                 width="84" height="84" alt="Foto"
                                 class="nl-signature-photo"
                                 style="display:block; width:84px; height:84px; border-radius:999px; border:3px solid #d4af37; background:#111; margin-left:auto; vertical-align:bottom;">
                          </td>
                        </tr>
                        <tr>
                          <td align="right" style="line-height:0; font-size:0;">
                            <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="display:inline-table; border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
                              <tr>
                                <td style="padding:0; line-height:0; font-size:0;">
                                  <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
                                    <tr>
                                      <td class="nl-signature-bar-lg" style="height:10px; width:180px; max-width:100%; background:#d4af37; line-height:10px; font-size:0;">&nbsp;</td>
                                    </tr>
                                  </table>
                                </td>
                              </tr>
                              <tr>
                                <td style="padding:4px 0 0 0; line-height:0; font-size:0;">
                                  <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
                                    <tr>
                                      <td class="nl-signature-bar-md" style="height:8px; width:160px; max-width:100%; background:#e6c76a; line-height:8px; font-size:0;">&nbsp;</td>
                                    </tr>
                                  </table>
                                </td>
                              </tr>
                              <tr>
                                <td style="padding:4px 0 0 0; line-height:0; font-size:0;">
                                  <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
                                    <tr>
                                      <td class="nl-signature-bar-sm" style="height:6px; width:140px; max-width:100%; background:#caa233; line-height:6px; font-size:0;">&nbsp;</td>
                                    </tr>
                                  </table>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                        <tr>
                          <td align="right" class="nl-signature-icons" style="padding-top:12px; line-height:0; font-size:0;">
                            <a href="{profile.linkedin}" target="_blank"
                               style="text-decoration:none; margin-left:10px; display:inline-block;">
                              <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/linkedin.png"
                                   width="18" height="18" alt="LinkedIn"
                                   style="display:block; border:0; outline:none;">
                            </a>
                            <a href="{profile.github}" target="_blank"
                               style="text-decoration:none; margin-left:10px; display:inline-block;">
                              <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/github.png"
                                   width="18" height="18" alt="GitHub"
                                   style="display:block; border:0; outline:none;">
                            </a>
                            <a href="{whatsapp_url}" target="_blank"
                               style="text-decoration:none; margin-left:10px; display:inline-block;">
                              <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/whatsapp.png"
                                   width="18" height="18" alt="WhatsApp"
                                   style="display:block; border:0; outline:none;">
                            </a>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
                      </table>
              </td>
            </tr>
          </table>
        </div>
        """
    ).strip()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _format_phone_display(phone: str) -> str:
    digits = _digits(phone)
    if len(digits) == 11:
        return f"+55 ({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 13 and digits.startswith("55"):
        return f"+55 ({digits[2:4]}) {digits[4:9]}-{digits[9:]}"
    return phone.strip()


def _format_tel_href(phone: str) -> str:
    digits = _digits(phone)
    if len(digits) == 11:
        digits = f"55{digits}"
    return f"tel:+{digits}" if digits else ""


def _resolve_whatsapp_url(profile: SignatureProfile) -> str:
    if profile.whatsapp.strip():
        return profile.whatsapp.strip()

    digits = _digits(profile.phone)
    if len(digits) == 11:
        digits = f"55{digits}"
    return f"https://wa.me/{digits}" if digits else ""


def _format_website_label(website: str) -> str:
    label = website.strip().removeprefix("https://").removeprefix("http://")
    return label or website.strip()
