from fastapi import FastAPI
from scraper import scrape_product
import asyncio

app = FastAPI()

@app.get("/scrape")
async def scrape(url: str):
    data = await scrape_product(url)
    return data
