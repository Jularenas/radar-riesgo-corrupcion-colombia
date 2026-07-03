"""
Monitor Ciudadano — Radiografía 2016-2022 database downloader.

Tries to download the database from:
  https://www.monitorciudadano.co/bases-radiografia-2016-2022/

If the site blocks automation, writes a DESCARGA_MANUAL.md with exact
instructions, then continues gracefully.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

MC_URL = "https://www.monitorciudadano.co/bases-radiografia-2016-2022/"
TARGET_DIR_NAME = "monitor_ciudadano"

MANUAL_INSTRUCTIONS = """\
# Descarga Manual — Monitor Ciudadano Radiografía 2016–2022

La descarga automatizada de los archivos fue bloqueada por el sitio web.

## Pasos para descargar manualmente

1. Abre en tu navegador: https://www.monitorciudadano.co/bases-radiografia-2016-2022/
2. Descarga todos los archivos disponibles (.xlsx, .csv, .zip, .pdf).
3. Copia los archivos descargados a esta carpeta:
   `pipeline/data/raw/monitor_ciudadano/`

## Archivos esperados

Los archivos suelen tener nombres como:
- `Radiografia_hechos_corrupcion_2016_2022.xlsx`
- `base_radiografia_2016_2022.xlsx`
- `base_datos_monitor_ciudadano.xlsx`

## Fuente

Transparencia por Colombia – Monitor Ciudadano
- Sitio: https://www.monitorciudadano.co/
- Página de descarga: https://www.monitorciudadano.co/bases-radiografia-2016-2022/

## Nota

Una vez descargados los archivos, el pipeline los procesará automáticamente
en la etapa M2 (staging / normalización).
"""


def download(raw_dir: Path) -> None:
    """
    Attempt to download Monitor Ciudadano database.
    Falls back to DESCARGA_MANUAL.md if blocked.
    """
    out_dir = raw_dir / TARGET_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Fetching Monitor Ciudadano page: %s", MC_URL)

    try:
        with httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; corruption-risk-pipeline/1.0; "
                    "research project)"
                )
            },
        ) as client:
            resp = client.get(MC_URL)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPStatusError as e:
        log.warning(
            "Monitor Ciudadano page returned %d, writing manual instructions",
            e.response.status_code,
        )
        _write_manual_fallback(out_dir)
        return
    except Exception as e:
        log.warning("Could not reach Monitor Ciudadano (%s), writing manual instructions", e)
        _write_manual_fallback(out_dir)
        return

    # Find download links (.xlsx, .csv, .zip)
    links = _extract_download_links(html, MC_URL)
    if not links:
        log.warning("No download links found on Monitor Ciudadano page")
        _write_manual_fallback(out_dir)
        return

    log.info("Found %d download link(s) on Monitor Ciudadano page", len(links))
    downloaded: list[str] = []

    for url in links:
        fname = _url_to_filename(url)
        out_path = out_dir / fname
        if out_path.exists():
            log.info("Already downloaded: %s", fname)
            downloaded.append(fname)
            continue

        log.info("Downloading: %s → %s", url, fname)
        try:
            with httpx.Client(
                timeout=120,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; corruption-risk-pipeline/1.0; "
                        "research project)"
                    )
                },
            ) as client:
                r = client.get(url)
                r.raise_for_status()
                out_path.write_bytes(r.content)
                downloaded.append(fname)
                log.info("  Saved %d bytes → %s", len(r.content), out_path)
        except Exception as e:
            log.warning("Failed to download %s: %s", url, e)

    if downloaded:
        log.info(
            "Monitor Ciudadano: downloaded %d file(s): %s",
            len(downloaded),
            ", ".join(downloaded),
        )
    else:
        log.warning("No files could be downloaded from Monitor Ciudadano")
        _write_manual_fallback(out_dir)


def _extract_download_links(html: str, base_url: str) -> list[str]:
    """Extract links to .xlsx, .csv, .zip, .ods files from HTML."""
    pattern = re.compile(r'href=["\']([^"\']+\.(?:xlsx|csv|zip|ods|xls))["\']', re.IGNORECASE)
    found: list[str] = []
    for match in pattern.finditer(html):
        href = match.group(1)
        # Resolve relative URLs
        full = urllib.parse.urljoin(base_url, href)
        if full not in found:
            found.append(full)
    return found


def _url_to_filename(url: str) -> str:
    """Derive a safe local filename from a URL."""
    parsed = urllib.parse.urlparse(url)
    name = parsed.path.split("/")[-1]
    # URL-decode
    name = urllib.parse.unquote(name)
    # Sanitize
    name = re.sub(r"[^\w.\-]", "_", name)
    return name or "monitor_ciudadano_file"


def _write_manual_fallback(out_dir: Path) -> None:
    """Write the manual download instructions file."""
    manual_path = out_dir / "DESCARGA_MANUAL.md"
    manual_path.write_text(MANUAL_INSTRUCTIONS, encoding="utf-8")
    log.info(
        "Manual download instructions written to: %s",
        manual_path,
    )
    log.info(
        "Please download the Monitor Ciudadano database manually from:\n"
        "  %s",
        MC_URL,
    )
