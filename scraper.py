import asyncio
import os
from playwright.async_api import async_playwright

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")

def scraperapi_url(target_url: str) -> str:
    return f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={target_url}&render=true&country_code=tr"

async def scrape_product(url):
    base_url = url.split('?')[0].rstrip('/')
    reviews_url = base_url + '/yorumlar'
    qna_url = base_url + '/saticiya-sor'

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
        )

        page = await context.new_page()

        # ANA SAYFA — ScraperAPI üzerinden
        target = scraperapi_url(url)
        print(f"Ana sayfa yükleniyor...")
        await page.goto(target, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(4000)

        # BAŞLIK
        title = ""
        try:
            await page.wait_for_selector('h1', timeout=20000)
            title = await page.locator('h1').first.inner_text()
            print(f"Başlık: {title}")
        except Exception as e:
            print(f"H1 bulunamadı: {e}")
            title = await page.title()
            print(f"Page title: {title}")

        # FİYAT
        price = None
        try:
            el = page.locator('span.discounted')
            if await el.count() > 0:
                price = await el.first.inner_text()
                print(f"Fiyat: {price}")
            else:
                print("Fiyat bulunamadı!")
        except Exception as e:
            print(f"Fiyat hatası: {e}")

        # AÇIKLAMA
        description = ""
        try:
            for sel in ['div.detail-attr-container', 'div#product-description', 'div.product-description']:
                el = page.locator(sel)
                if await el.count() > 0:
                    description = await el.first.inner_text()
                    print(f"Açıklama: {sel}")
                    break
        except Exception as e:
            print(f"Açıklama hatası: {e}")

        # GÖRSELLER
        image_urls = []
        try:
            thumbs = page.locator('div._carouselThumbsContainer_05669af img._carouselThumbsImage_ddecc3e')
            for i in range(await thumbs.count()):
                src = await thumbs.nth(i).get_attribute('src')
                if src and src not in image_urls:
                    image_urls.append(src)
            print(f"Görsel: {len(image_urls)}")
        except Exception as e:
            print(f"Görsel hatası: {e}")

        # YORUMLAR SAYFASI
        comments = []
        try:
            print(f"Yorumlar yükleniyor...")
            await page.goto(scraperapi_url(reviews_url), wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(3000)

            last_count = 0
            same_count_times = 0
            for _ in range(200):
                count = await page.locator('div.review').count()
                print(f"Yorum: {count}")
                if count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= 8:
                    break
                last_count = count
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(800)

            items = page.locator('div.review')
            total = await items.count()
            print(f"Toplam yorum: {total}")

            for i in range(total):
                try:
                    item = items.nth(i)
                    user, text, stars = "", "", 0

                    u = item.locator('span.detail-item.name')
                    if await u.count() > 0:
                        user = await u.first.inner_text()

                    t = item.locator('div.review-comment')
                    if await t.count() > 0:
                        text = await t.first.inner_text()

                    full_stars = item.locator('svg.star-rating-full-star, i.star-rating-full-star, span.star-rating-full-star')
                    stars = await full_stars.count()

                    if text.strip():
                        comments.append({
                            'user': user.strip() or "Anonim",
                            'text': text.strip(),
                            'stars': stars
                        })
                except Exception as e:
                    print(f"Yorum parse hatası: {e}")

        except Exception as e:
            print(f"Yorum hatası: {e}")

        print(f"İşlenen yorum: {len(comments)}")

        # Q&A SAYFASI
        qna_list = []
        try:
            print(f"Q&A yükleniyor...")
            await page.goto(scraperapi_url(qna_url), wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(3000)

            last_count = 0
            same_count_times = 0
            for _ in range(200):
                count = await page.locator('div.question-answer-card').count()
                print(f"Q&A: {count}")
                if count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= 8:
                    break
                last_count = count
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(800)

            items = page.locator('div.question-answer-card')
            total = await items.count()
            print(f"Toplam Q&A: {total}")

            for i in range(total):
                try:
                    item = items.nth(i)
                    question, answer = "", ""

                    q = item.locator('div.question-answer-card-question-text')
                    if await q.count() > 0:
                        question = await q.first.inner_text()

                    a = item.locator('div.seller-answer-content-text')
                    if await a.count() > 0:
                        answer = await a.first.inner_text()

                    if question.strip() or answer.strip():
                        qna_list.append({
                            'question': question.strip(),
                            'answer': answer.strip()
                        })
                except Exception as e:
                    print(f"Q&A parse hatası: {e}")

        except Exception as e:
            print(f"Q&A hatası: {e}")

        print(f"İşlenen Q&A: {len(qna_list)}")
        await browser.close()

        return {
            'title': title.strip(),
            'price': price.strip() if price else None,
            'description': description.strip(),
            'images': image_urls,
            'comments': comments,
            'qna': qna_list
        }
