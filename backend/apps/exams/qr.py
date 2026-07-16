"""QR code helpers.

Phase 15 uses the ``qrcode`` lib's PIL backend (Pillow is already a
project dep, used by reportlab). The output is a PNG returned via
Django's :class:`HttpResponse`.

We hand-roll the response rather than reaching for ``FileResponse``
because the payload is small (a few KB at most) and we want to set
the ``Content-Disposition`` ourselves.
"""
from __future__ import annotations

import io

import qrcode
from django.http import HttpResponse

# 320x320 px, ECC M (15%), 2-module quiet zone. ECC M tolerates ~15%
# surface damage before the code becomes unreadable — the right
# trade-off for printed cards that get handled, folded, and worn.
_QR_VERSION_KW = {"error_correction": qrcode.constants.ERROR_CORRECT_M, "box_size": 10, "border": 2}


def qr_png_response(payload: str) -> HttpResponse:
    """Render a PNG QR encoding ``payload``.

    ``payload`` is the raw string the door scanner reads back. For
    Phase 19 this is a signed token from
    :func:`apps.exams.qr_tokens.issue_student_qr_token` rather than
    a raw row id — see that module for the wire format.
    """
    img = qrcode.make(payload, **_QR_VERSION_KW)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    response = HttpResponse(buf.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="qr.png"'
    # Don't let an intermediary cache a personal QR. The token
    # expires on a 60s rotation; cached PNGs would be stale.
    response["Cache-Control"] = "private, no-store"
    return response


__all__ = ["qr_png_response"]
