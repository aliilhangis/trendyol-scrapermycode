import asyncio
from playwright.async_api import async_playwright


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
                '--disable-infobars',
                '--window-size=1920,1080',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
            ignore_https_errors=True,
            extra_http_headers={
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            }
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr'] });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        # ANA SAYFA
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(4000)

        # Çerez popup'ı kapat
        for sel in ['button:has-text("Kabul Et")', 'button#onetrust-accept-btn-handler']:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                await page.click(sel)
                print(f"Çerez kapatıldı: {sel}")
                break
            except:
                continue

        await page.wait_for_timeout(2000)

        # BAŞLIK
        title = ""
        try:
            await page.wait_for_selector('h1', timeout=20000)
            title = await page.locator('h1').first.inner_text()
            print(f"Başlık: {title}")
        except Exception as e:
            print(f"H1 bulunamadı: {e}")
            title = await page.title()

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
            print(f"Yorumlar: {reviews_url}")
            await page.goto(reviews_url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(3000)

            last_count = 0
            same_count_times = 0
            for _ in range(300):
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
                await page.wait_for_timeout(700)

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
                        comments.append({'user': user.strip() or "Anonim", 'text': text.strip(), 'stars': stars})
                except Exception as e:
                    print(f"Yorum parse hatası: {e}")
        except Exception as e:
            print(f"Yorum hatası: {e}")

        print(f"İşlenen yorum: {len(comments)}")

        # Q&A SAYFASI
        qna_list = []
        try:
            print(f"Q&A: {qna_url}")
            await page.goto(qna_url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(3000)

            last_count = 0
            same_count_times = 0
            for _ in range(300):
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
                await page.wait_for_timeout(700)

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
                        qna_list.append({'question': question.strip(), 'answer': answer.strip()})
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
