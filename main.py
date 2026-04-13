import asyncio
from fastapi import FastAPI, HTTPException
from scraper import scrape_product

app = FastAPI()

@app.get("/scrape")
async def scrape(url: str):
    try:
        data = await asyncio.wait_for(scrape_product(url), timeout=120)
        return data
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Scraping timeout - 120 saniye aşıldı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
