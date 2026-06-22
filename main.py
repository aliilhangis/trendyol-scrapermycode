import asyncio
from urllib.parse import urlparse, urlencode, parse_qs
from fastapi import FastAPI, HTTPException
from scraper import scrape_product

app = FastAPI()

def clean_url(url: str) -> str:
    """Trendyol URL'inden gereksiz parametreleri temizle"""
    parsed = urlparse(url)
    # Sadece boutiqueId ve merchantId'yi tut, diğerlerini at
    params = parse_qs(parsed.query)
    keep = {k: v for k, v in params.items() if k in ['boutiqueId', 'merchantId']}
    clean_query = urlencode(keep, doseq=True)
    clean = parsed._replace(query=clean_query)
    return clean.geturl()

@app.get("/scrape")
async def scrape(url: str):
    try:
        cleaned = clean_url(url)
        print(f"Temizlenen URL: {cleaned}")
        data = await asyncio.wait_for(scrape_product(cleaned), timeout=120)
        return data
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Scraping timeout - 120 saniye aşıldı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
