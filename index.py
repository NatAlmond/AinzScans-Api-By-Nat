"""
AinzScans API by Nat
Sumber: api.ainzscans01.com (API resmi situs) + fallback HTML /allcomic
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

app = FastAPI(
    title="AinzScans API",
    description="API komik AinzScans (v3.ainzscans01.com) — By Nat",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_BASE = "https://v3.ainzscans01.com"
API_BASE = "https://api.ainzscans01.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
    "Origin": WEB_BASE,
    "Referer": WEB_BASE + "/",
}

TIMEOUT = 20.0

AD_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:ads?|banner|casino|slot|888|iklan|promo|doubleclick|adservice)(?:[^a-z0-9]|$)",
    re.IGNORECASE,
)


def _abs(url: Optional[str]) -> str:
    if not url:
        return ""
    url = str(url).strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return urljoin(API_BASE + "/", url.lstrip("/"))


def _item_from_api(row: Dict[str, Any]) -> Dict[str, Any]:
    slug = (row.get("slug") or "").strip()
    thumb = row.get("poster_image_url") or row.get("banner_image_url") or ""
    return {
        "judul": (row.get("title") or slug or "Tanpa judul").strip(),
        "slug": slug,
        "thumbnail": _abs(thumb),
        "chapter": None,
        "status": row.get("comic_status") or row.get("series_status") or "",
        "type": row.get("comic_subtype") or row.get("type") or "",
        "url": f"{WEB_BASE}/comic/{slug}" if slug else "",
    }


async def api_get(path: str, params: Optional[dict] = None) -> Any:
    url = API_BASE + path
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        res = await client.get(url, headers=HEADERS, params=params or {})
        if res.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="Akses ditolak (403). Target memblokir server.",
            )
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail="Tidak ditemukan di API AinzScans.")
        res.raise_for_status()
        return res.json()


async def html_latest(page: int = 1) -> List[Dict[str, Any]]:
    """Fallback scrape /allcomic bila API search kosong."""
    path = "/allcomic" if page <= 1 else f"/allcomic?page={page}"
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        res = await client.get(
            WEB_BASE + path,
            headers={**HEADERS, "Accept": "text/html"},
        )
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, "html.parser")
        out: List[Dict[str, Any]] = []
        seen = set()
        for art in soup.select("article"):
            a = art.select_one("a[href*='/comic/']")
            if not a:
                continue
            href = (a.get("href") or "").strip()
            m = re.search(r"/comic/([^/?#]+)", href)
            if not m:
                continue
            slug = m.group(1)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            img = art.find("img")
            title = ""
            if img is not None:
                title = (img.get("alt") or img.get("title") or "").strip()
            if not title:
                for ax in art.select("a[href*='/comic/']"):
                    t = ax.get_text(" ", strip=True)
                    if t and not re.match(r"^(Ongoing|Completed|Hiatus|\*|\d)", t, re.I):
                        title = t
                        break
            if not title:
                title = slug.replace("-", " ").title()
            thumb = ""
            if img is not None:
                thumb = (img.get("src") or img.get("data-src") or "").strip()
            out.append(
                {
                    "judul": title[:120],
                    "slug": slug,
                    "thumbnail": _abs(thumb),
                    "chapter": None,
                    "status": "",
                    "type": "",
                    "url": f"{WEB_BASE}/comic/{slug}",
                }
            )
        return out


@app.get("/")
def root():
    return {
        "status": "online",
        "message": "AinzScans API is running",
        "version": "3.0.0",
        "author": "Nat",
        "endpoints": {
            "latest": "/api/latest?page=1",
            "search": "/api/search?q=judul",
            "detail": "/api/detail/{slug}",
            "chapter": "/api/chapter?slug=series-slug&chapter=chapter-slug",
            "chapter_by_url": "/api/chapter?url=https://v3.ainzscans01.com/comic/.../chapter/...",
        },
    }


@app.get("/api/latest")
async def latest(page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=100)):
    """Daftar komik (via API search kosong / huruf umum + fallback HTML)."""
    data: List[Dict[str, Any]] = []
    try:
        # q kosong sering mengembalikan katalog
        js = await api_get("/api/search", {"q": "", "page": page, "limit": limit})
        rows = js.get("data") if isinstance(js, dict) else []
        if isinstance(rows, list):
            data = [_item_from_api(r) for r in rows if isinstance(r, dict) and r.get("slug")]
    except Exception:
        data = []

    if not data:
        try:
            data = await html_latest(page)
        except Exception:
            data = []

    return {
        "status": True,
        "page": page,
        "total": len(data),
        "data": data,
    }


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1, description="Kata kunci pencarian"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
):
    try:
        js = await api_get("/api/search", {"q": q, "page": page, "limit": limit})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search gagal: {e}")

    rows = js.get("data") if isinstance(js, dict) else []
    data = []
    if isinstance(rows, list):
        data = [_item_from_api(r) for r in rows if isinstance(r, dict) and r.get("slug")]

    return {
        "status": True,
        "query": q,
        "page": js.get("page", page) if isinstance(js, dict) else page,
        "total": js.get("total", len(data)) if isinstance(js, dict) else len(data),
        "total_pages": js.get("total_pages") if isinstance(js, dict) else None,
        "data": data,
    }


@app.get("/api/detail/{slug}")
async def detail(slug: str):
    slug = slug.strip().strip("/")
    if slug.startswith("comic/"):
        slug = slug.split("/", 1)[-1]
    try:
        js = await api_get(f"/api/series/comic/{quote(slug, safe='')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detail gagal: {e}")

    if not isinstance(js, dict) or not js.get("slug"):
        raise HTTPException(status_code=404, detail="Komik tidak ditemukan")

    units = js.get("units") or []
    chapters = []
    for u in units:
        if not isinstance(u, dict):
            continue
        cslug = (u.get("slug") or "").strip()
        if not cslug:
            continue
        num = u.get("number") or u.get("sort_number") or ""
        title = (u.get("title") or f"Chapter {num}").strip()
        chapters.append(
            {
                "judul": title,
                "slug": cslug,
                "number": str(num),
                "url": f"{WEB_BASE}/comic/{slug}/chapter/{cslug}",
                "locked": bool(u.get("is_locked")),
                "premium": bool(u.get("is_premium")),
            }
        )

    # urutkan chapter (besar → kecil seperti reader umum)
    def _num_key(c):
        try:
            return float(c.get("number") or 0)
        except Exception:
            return 0.0

    chapters.sort(key=_num_key, reverse=True)

    genres = []
    for g in js.get("genres") or []:
        if isinstance(g, dict) and g.get("name"):
            genres.append(g["name"])
        elif isinstance(g, str):
            genres.append(g)

    return {
        "status": True,
        "data": {
            "judul": js.get("title") or slug,
            "slug": js.get("slug") or slug,
            "thumbnail": _abs(js.get("poster_image_url")),
            "sinopsis": js.get("synopsis") or "",
            "genre": genres,
            "status": js.get("comic_status") or js.get("series_status") or "",
            "type": js.get("comic_subtype") or "",
            "author": js.get("author_name") or "",
            "total_chapter": len(chapters),
            "chapters": chapters,
            "url": f"{WEB_BASE}/comic/{slug}",
        },
    }


def _parse_chapter_url(url: str) -> tuple[str, str]:
    """Ambil (series_slug, chapter_slug) dari URL web."""
    url = (url or "").strip()
    m = re.search(
        r"/comic/([^/]+)/chapter/([^/?#]+)",
        url,
        re.I,
    )
    if not m:
        raise HTTPException(
            status_code=400,
            detail="URL chapter tidak valid. Contoh: /comic/{slug}/chapter/{chapter-slug}",
        )
    return m.group(1), m.group(2)


@app.get("/api/chapter")
async def chapter(
    url: Optional[str] = Query(None, description="URL lengkap halaman chapter"),
    slug: Optional[str] = Query(None, description="Slug series"),
    chapter: Optional[str] = Query(None, description="Slug chapter, mis. chapter-11"),
):
    series_slug = (slug or "").strip()
    chapter_slug = (chapter or "").strip()

    if url and (not series_slug or not chapter_slug):
        series_slug, chapter_slug = _parse_chapter_url(url)

    if not series_slug or not chapter_slug:
        raise HTTPException(
            status_code=400,
            detail="Isi url=... atau pasangan slug=...&chapter=...",
        )

    path = f"/api/series/comic/{quote(series_slug, safe='')}/chapter/{quote(chapter_slug, safe='')}"
    try:
        js = await api_get(path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chapter gagal: {e}")

    ch = (js or {}).get("chapter") or {}
    pages = ch.get("pages") or []
    images: List[str] = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        src = (p.get("image_url") or "").strip()
        if not src:
            continue
        # jangan filter CDN chapter (yuucdn, dll); hanya blok pola iklan jelas
        low = src.lower()
        if any(x in low for x in ("banner", "casino", "slot", "doubleclick", "adservice", "/iklan/")):
            continue
        if re.search(r"(?:^|[^a-z0-9])ads?(?:[^a-z0-9]|$)", low) and "upload" not in low:
            continue
        images.append(_abs(src))

    if not images:
        raise HTTPException(status_code=404, detail="Gambar chapter kosong / terkunci")

    return {
        "status": True,
        "series": (js.get("series") or {}).get("title") or series_slug,
        "chapter": ch.get("title") or chapter_slug,
        "slug": series_slug,
        "chapter_slug": chapter_slug,
        "url": f"{WEB_BASE}/comic/{series_slug}/chapter/{chapter_slug}",
        "total_images": len(images),
        "images": images,
        "previous_chapter": js.get("previous_chapter"),
        "next_chapter": js.get("next_chapter"),
    }


# Vercel
handler = Mangum(app, lifespan="off")
