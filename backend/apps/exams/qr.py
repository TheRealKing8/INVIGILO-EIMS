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


def qr_png_response(obj, *, payload_attr: str = "id") -> HttpResponse:
    """Render a PNG QR encoding ``str(getattr(obj, payload_attr))``.

    The default ``payload_attr="id"`` works for any
    :class:`apps.core.models.UUIDModel` (the row's UUID). For other
    payloads, pass a different attribute.
    """
    payload = str(getattr(obj, payload_attr))
    img = qrcode.make(payload, **_QR_VERSION_KW)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    response = HttpResponse(buf.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="qr-{payload}.png"'
    # Don't let an intermediary cache a personal QR.
    response["Cache-Control"] = "private, no-store"
    return response


__all__ = ["qr_png_response"]
