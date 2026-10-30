# AinzScans API by Nat

REST API komik dari **AinzScans** (`v3.ainzscans01.com`) memakai API resmi `api.ainzscans01.com`.

## Fitur
- Latest / katalog
- Search
- Detail + **semua chapter** (`units`)
- Gambar chapter (`pages`)

## Endpoint

| Metode | Path | Keterangan |
|--------|------|------------|
| GET | `/` | Status |
| GET | `/api/latest?page=1` | Daftar komik |
| GET | `/api/search?q=judul` | Cari |
| GET | `/api/detail/{slug}` | Detail + chapter |
| GET | `/api/chapter?slug=...&chapter=...` | Gambar chapter |
| GET | `/api/chapter?url=https://v3.../comic/.../chapter/...` | Gambar via URL web |

## Deploy Vercel
1. Push repo ke GitHub
2. Import project di Vercel
3. Deploy

## Lokal
```bash
pip install -r requirements.txt
uvicorn index:app --reload
```

By: Nat
