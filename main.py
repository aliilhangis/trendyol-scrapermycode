import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # ← 1) bu import'u ekle
from scraper import scrape_product

app = FastAPI()

# ← 2) app = FastAPI() ile route arasına bunu ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/scrape")
async def scrape(url: str):
    try:
        data = await asyncio.wait_for(scrape_product(url), timeout=120)
        return data
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Scraping timeout - 120 saniye aşıldı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
