"""
IIIF Image API 3.0 Endpunkte für hochauflösende Betrachtung mit OpenSeadragon / Mirador.
"""

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.services.iiif_service import iiif_service

router = APIRouter(prefix="/iiif", tags=["IIIF Image API 3.0"])


@router.get("/{identifier}/info.json")
async def get_iiif_info(identifier: str, request: Request):
    """
    Liefert die IIIF Image API 3.0 info.json Spezifikation für ein Archivbild.
    """
    base_url = str(request.base_url).rstrip("/")
    # Falls hinter Reverse-Proxy gelaufen
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"

    info = iiif_service.get_image_info(identifier, base_url=base_url)
    return JSONResponse(
        content=info,
        media_type='application/ld+json;profile="http://iiif.io/api/image/3/context.json"',
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Link": '<http://iiif.io/api/image/3/context.json>; rel="http://www.w3.org/ns/json-ld#context"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/{identifier}")
async def redirect_to_info(identifier: str):
    """Leitet den Basis-Identifier gemäß IIIF-Spezifikation auf /info.json weiter."""
    return RedirectResponse(url=f"/api/iiif/{identifier}/info.json", status_code=303)


@router.get("/{identifier}/{region}/{size}/{rotation}/{quality_and_format}")
async def get_iiif_tile(
    identifier: str,
    region: str,
    size: str,
    rotation: str,
    quality_and_format: str,
):
    """
    Liefert eine berechnete Bildkachel gemäß IIIF Image API 3.0:
    Format: {region}/{size}/{rotation}/{quality}.{format}
    Beispiel: /api/iiif/XYZ/0,0,512,512/512,/0/default.webp
    """
    if "." not in quality_and_format:
        raise HTTPException(
            status_code=400,
            detail="Letztes Pfadsegment muss im Format {quality}.{format} vorliegen (z. B. default.jpg).",
        )

    quality, fmt = quality_and_format.rsplit(".", 1)

    tile_bytes, media_type = iiif_service.render_tile(
        identifier=identifier,
        region=region,
        size=size,
        rotation=rotation,
        quality=quality,
        fmt=fmt,
    )

    return Response(
        content=tile_bytes,
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=604800, immutable",
            "Link": '<http://iiif.io/api/image/3/context.json>; rel="http://www.w3.org/ns/json-ld#context"',
        },
    )
