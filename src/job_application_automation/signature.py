from __future__ import annotations

from dataclasses import dataclass
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
    return dedent(
        f"""
        --
        {profile.name}
        {profile.role}
        T: {profile.phone}
        E: {profile.email}
        W: {profile.website}
        GitHub: {profile.github}
        LinkedIn: {profile.linkedin}
        WhatsApp: {profile.whatsapp}
        """
    ).strip()


def build_signature_html(profile: SignatureProfile) -> str:
    return dedent(
        f"""
        <div style="width:600px;max-width:600px;font-family:Arial,Helvetica,sans-serif;color:#ffffff;background:#111;border-radius:12px;overflow:hidden;">
          <div style="padding:14px 18px;background:linear-gradient(135deg,#111 0%,#1b1b1b 100%);border-bottom:4px solid #d4af37;">
            <table cellpadding="0" cellspacing="0" border="0" role="presentation" width="100%" style="width:100%;border-collapse:collapse;">
              <tr>
                <td valign="middle" style="padding-right:12px;">
                  <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/nilvan-lopes.png" width="229" height="61" alt="{profile.name}" style="display:block;border:0;">
                  <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/nilvan-role.png" width="195" height="18" alt="{profile.role}" style="display:block;margin-left:13px;margin-top:4px;opacity:0.92;border:0;">

                  <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin-top:10px;">
                    <tr><td style="padding:0 0 4px 0;font-size:12.5px;"> <span style="color:#d4af37;font-weight:700;">T:</span> <a href="tel:{profile.phone}" style="color:#ffffff;text-decoration:none;">{profile.phone}</a></td></tr>
                    <tr><td style="padding:0 0 4px 0;font-size:12.5px;"> <span style="color:#d4af37;font-weight:700;">E:</span> <a href="mailto:{profile.email}" style="color:#ffffff;text-decoration:none;">{profile.email}</a></td></tr>
                    <tr><td style="padding:0;font-size:12.5px;"> <span style="color:#d4af37;font-weight:700;">W:</span> <a href="{profile.website}" target="_blank" style="color:#ffffff;text-decoration:none;">{profile.website.replace('https://', '').replace('http://', '')}</a></td></tr>
                  </table>
                </td>
                <td valign="middle" align="right" style="text-align:right;">
                  <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/eu.png" width="84" height="84" alt="Foto de {profile.name}" style="display:block;border-radius:999px;border:3px solid #d4af37;background:#111;margin-left:auto;margin-bottom:10px;">
                  <div style="display:inline-block;height:10px;width:180px;background:#d4af37;"></div><br>
                  <div style="display:inline-block;height:8px;width:160px;background:#e6c76a;margin-top:4px;"></div><br>
                  <div style="display:inline-block;height:6px;width:140px;background:#caa233;margin-top:4px;"></div>
                  <div style="padding-top:12px;line-height:0;font-size:0;">
                    <a href="{profile.linkedin}" target="_blank" style="text-decoration:none;margin-left:10px;display:inline-block;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/linkedin.png" width="18" height="18" alt="LinkedIn" style="display:block;border:0;outline:none;"></a>
                    <a href="{profile.github}" target="_blank" style="text-decoration:none;margin-left:10px;display:inline-block;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/github.png" width="18" height="18" alt="GitHub" style="display:block;border:0;outline:none;"></a>
                    <a href="{profile.whatsapp}" target="_blank" style="text-decoration:none;margin-left:10px;display:inline-block;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/whatsapp.png" width="18" height="18" alt="WhatsApp" style="display:block;border:0;outline:none;"></a>
                  </div>
                </td>
              </tr>
            </table>
          </div>
        </div>
        """
    ).strip()
