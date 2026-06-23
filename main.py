import asyncio
from urllib.parse import urlparse, urlencode, parse_qs
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from scraper import scrape_product

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    keep = {k: v for k, v in params.items() if k in ['boutiqueId', 'merchantId']}
    clean_query = urlencode(keep, doseq=True)
    return parsed._replace(query=clean_query).geturl()

@app.get("/scrape")
async def scrape(url: str):
    try:
        cleaned = clean_url(url)
        print(f"Temizlenen URL: {cleaned}")
        data = await asyncio.wait_for(scrape_product(cleaned), timeout=120)
        return data
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
