# AinzScans API

REST API untuk mengambil data komik (Manga/Manhwa/Manhua) dari `v3.ainzscans01.com`.

## ✨ Fitur
- ✅ **Seluruh Chapter**: Mengambil 100% daftar chapter (tanpa batas).
- ✅ **Gambar Komik**: Selector diperluas agar gambar chapter pasti terambil.
- ✅ **Bebas Iklan**: Filter otomatis untuk banner dan gambar iklan.
- ✅ **Pencarian Akurat**: Search engine yang berfungsi penuh.

## 🚀 Jalankan di Lokal
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn api.index:app --reload
```
Buka dokumentasi: http://127.0.0.1:8000/docs

## 📡 Endpoint
| Metode | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/latest?page=1` | Komik terbaru |
| GET | `/api/search?q=judul` | Cari komik |
| GET | `/api/detail/{slug}` | Detail komik + SEMUA chapter |
| GET | `/api/chapter?url=...` | Gambar chapter (URL lengkap) |

## 🌐 Deploy ke Vercel
1. Push kode ini ke GitHub.
2. Buka [vercel.com](https://vercel.com), login dengan GitHub.
3. Klik **Add New Project** → pilih repository ini.
4. Klik **Deploy**. Selesai!

---
**Dibuat oleh: Nat🥜**
