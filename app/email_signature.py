"""
HTML-signatur for utgående kladder.

Microsoft Graph PATCH med full body erstatter innholdet; Outlooks
«signatur ved oppretting» brukes ikke når vi setter body via API.
Derfor legges firmasignaturen inn eksplisitt her (tilsvarende signaturbildet).
"""

from __future__ import annotations

import html


# Firmasignatur (tekst). Logo kan legges inn som hosted URL i HTML ved behov.
DEFAULT_SIGNATURE_INNER_HTML = """
<div style="margin-top:1.5em; color:#1a2744; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:1.55;">
  <p style="margin:0 0 0.35em 0;">Med vennlig hilsen</p>
  <p style="margin:0 0 0.25em 0;"><strong>Arctic Motor</strong></p>
  <p style="margin:0 0 0.15em 0; padding-left:0.35em;">Nordstrandveien 63&nbsp;|&nbsp;8012 Bodø</p>
  <p style="margin:0 0 0.15em 0; padding-left:0.35em;">Postadresse Postboks 29&nbsp;|&nbsp;8088 Bodø</p>
  <p style="margin:0 0 0.15em 0; padding-left:0.35em;">Tlf:&nbsp;&nbsp;&nbsp;&nbsp;+47 417 80 062</p>
  <p style="margin:0;">
    <a href="mailto:Salg@arcticmotor.no" style="color:#1a56db;">Salg@arcticmotor.no</a>
  </p>
</div>
""".strip()


def plain_reply_to_outlook_html(body_plain: str, signature_inner_html: str | None = None) -> str:
    """
    Gjør modellens ren-tekst svar om til HTML og legg signatur under.

    Escaper HTML i brødtekst (unngår injeksjon hvis modellen returnerer '<').
    """
    sig = (signature_inner_html or DEFAULT_SIGNATURE_INNER_HTML).strip()
    safe = html.escape(body_plain.strip(), quote=False)
    safe_html = safe.replace("\n", "<br/>\n")
    return f'<div style="color:#1a2744; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:1.55;">{safe_html}</div>\n{sig}'
