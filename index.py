import asyncio
import re
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

app = FastAPI(
    title="AinzScans API",
    description="API untuk mengambil data komik dari v3.ainzscans01.com",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://v3.ainzscans01.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# Timeout di bawah 10 detik (batas Vercel tier gratis)
TIMEOUT = 8.0

# Pola filter iklan
AD_PATTERN = re.compile(
    r"(?<![a-z0-9])(ads?|banner|casino|slot|888|iklan|promo)(?![a-z0-9])",
    re.IGNORECASE,
)


async def get_soup(url: str) -> BeautifulSoup:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        res = await client.get(url, headers=HEADERS)
        res.raise_for_status()
        return BeautifulSoup(res.text, "html.parser")


@app.get("/")
def root():
    return {
        "status": "online",
        "message": "AinzScans API is running",
        "endpoints": {
            "latest": "/api/latest?page=1",
            "search": "/api/search?q=judul",
            "detail": "/api/detail/{slug}",
            "chapter": "/api/chapter?url=...",
        },
    }


@app.get("/api/latest")
async def latest(page: int = Query(1, ge=1, description="Nomor halaman")):
    try:
        url = f"{BASE_URL}/allcomic" if page == 1 else f"{BASE_URL}/allcomic/page/{page}/"
        soup = await get_soup(url)
        data = []
        for item in soup.select("div.listupd article, div.manga-item, div.bs"):
            title = item.select_one("h3, div.title, a.tt, h2")
            link = item.select_one("a")
            thumb = item.select_one("img")
            chapter = item.select_one("div.epxs, div.chapter, span.chapter")
            
            if title and link:
                raw_url = link.get("href")
                data.append({
                    "judul": title.get_text(strip=True),
                    "slug": raw_url.strip("/").split("/")[-1] if raw_url else "",
                    "thumbnail": (thumb.get("data-src") or thumb.get("src")) if thumb else None,
                    "chapter": chapter.get_text(strip=True) if chapter else None,
                    "url": urljoin(BASE_URL, raw_url) if raw_url else "",
                })
        return {"status": True, "page": page, "total": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search(q: str = Query(..., min_length=2, description="Kata kunci pencarian")):
    try:
        soup = await get_soup(f"{BASE_URL}/?s={quote(q)}")
        data = []
        for item in soup.select("div.listupd article, div.manga-item, div.bs"):
            title = item.select_one("h3, div.title, a.tt, h2")
            link = item.select_one("a")
            if title and link:
                raw_url = link.get("href")
                data.append({
                    "judul": title.get_text(strip=True),
                    "slug": raw_url.strip("/").split("/")[-1] if raw_url else "",
                    "url": urljoin(BASE_URL, raw_url) if raw_url else "",
                })
        return {"status": True, "query": q, "total": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/detail/{slug}")
async def detail(slug: str):
    try:
        paths = [f"/{slug}", f"/manga/{slug}", f"/komik/{slug}", f"/series/{slug}"]
        results = await asyncio.gather(
            *(get_soup(f"{BASE_URL}{p}") for p in paths),
            return_exceptions=True,
        )
        
        soup = None
        for r in results:
            if isinstance(r, BeautifulSoup) and r.select_one("h1.entry-title, div.infox h1"):
                soup = r
                break
                
        if soup is None:
            raise HTTPException(status_code=404, detail="Komik tidak ditemukan")

        title_el = soup.select_one("h1.entry-title, div.infox h1")
        thumb_el = soup.select_one("img.wp-post-image, div.thumb img")
        sinopsis = soup.select_one("div.entry-content, div.description, div.infox p")
        genres = [g.get_text(strip=True) for g in soup.select("div.genxed a, div.genre a, div.gnr a")]
        
        chapters = []
        # PERBAIKAN: Batas [:50] DIHAPUS. Mengambil SELURUH chapter yang ada.
        for chap in soup.select("div.bxcl li, div.clstyle li, ul.chapter-list li, div.cl li"):
            c_link = chap.select_one("a")
            c_date = chap.select_one("span.chapterdate, span.time, span.date")
            if c_link:
                raw_url = c_link.get("href")
                chapters.append({
                    "judul": c_link.get_text(strip=True),
                    "url": urljoin(BASE_URL, raw_url) if raw_url else "",
                    "tanggal": c_date.get_text(strip=True) if c_date else "Unknown",
                })
        
        return {
            "status": True,
            "data": {
                "judul": title_el.get_text(strip=True),
                "thumbnail": (thumb_el.get("data-src") or thumb_el.get("src")) if thumb_el else None,
                "sinopsis": sinopsis.get_text(strip=True) if sinopsis else "Tidak ada sinopsis",
                "genre": genres,
                "total_chapter": len(chapters),
                "chapters": chapters,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chapter")
async def chapter(url: str = Query(..., description="URL lengkap halaman chapter")):
    try:
        if not url.startswith("http"):
            url = urljoin(BASE_URL, url)
        
        soup = await get_soup(url)
        images = []
        
        # Selector diperluas untuk memastikan gambar komik terambil
        for img in soup.select("div.reading-content img, div.chapter-content img, div.img-landmine img, div#reader-area img"):
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
            if not src:
                continue
            
            src = src.strip()
            
            # Filter iklan berdasarkan URL
            if AD_PATTERN.search(src):
                continue
            
            # Filter iklan berdasarkan ukuran
            width = img.get("width")
            height = img.get("height")
            if width in ["1", "300"] or height in ["1", "250"]:
                continue
            
            images.append(urljoin(BASE_URL, src))
        
        return {
            "status": True,
            "url": url,
            "total_images": len(images),
            "images": images,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Handler WAJIB untuk Vercel (mengubah FastAPI jadi kompatibel dengan AWS Lambda)
handler = Mangum(app, lifespan="off")
