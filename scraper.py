import asyncio
from playwright.async_api import async_playwright

async def scrape_product(url):
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
            extra_http_headers={
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            }
        )

        # Playwright'ın bot izlerini gizle
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr'] });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Çerez popup'ı kapat
        cookie_selectors = [
            'button:has-text("Kabul Et")',
            'button#onetrust-accept-btn-handler',
            'button:has-text("Çerezleri Kabul Et")',
            'button[data-testid="cookie-accept-button"]',
            'button:has-text("Accept All")'
        ]
        for sel in cookie_selectors:
            try:
                await page.wait_for_selector(sel, timeout=2000)
                await page.click(sel)
                print(f"Çerez popup'ı kapatıldı: {sel}")
                break
            except:
                continue

        await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
        await page.wait_for_timeout(1500)

        # --- BAŞLIK ---
        title = await page.locator('h1').first.inner_text()
        print(f"Başlık: {title}")

        # --- FİYAT ---
        price = None
        price_selectors = [
            'span.prc-dsc',
            'span.prc-org',
            'p.prc-dsc',
            'span.price-view-original',
            'div.pr-bx-pr-dsc span',
            'span.prc-slg',
        ]
        for sel in price_selectors:
            price_locator = page.locator(sel)
            if await price_locator.count() > 0:
                price = await price_locator.first.inner_text()
                print(f"Fiyat bulundu ({sel}): {price}")
                break
        if not price:
            print("Fiyat bulunamadı!")

        # --- AÇIKLAMA ---
        description = ""
        try:
            desc_selectors = [
                'div.detail-attr-container',
                'div.product-feature-container',
                'div.detail-desc-list',
                'div#product-description',
                'div.product-description',
                'div#productDetail'
            ]
            for sel in desc_selectors:
                desc_element = page.locator(sel)
                if await desc_element.count() > 0:
                    description = await desc_element.first.inner_text()
                    print(f"Açıklama bulundu ({sel})")
                    break
        except Exception as e:
            print(f"Açıklama hatası: {e}")

        # --- GÖRSELLER ---
        image_urls = []
        thumbs = page.locator('div._carouselThumbsContainer_05669af img._carouselThumbsImage_ddecc3e')
        thumbs_count = await thumbs.count()
        for i in range(thumbs_count):
            src = await thumbs.nth(i).get_attribute('src')
            if src and src not in image_urls:
                image_urls.append(src)
        print(f"Görsel sayısı: {len(image_urls)}")

        # --- YORUMLAR ---
        comments = []
        try:
            print("Yorumlar aranıyor...")
            btn_selectors = [
                'a[data-testid="show-more-button"] span:has-text("TÜM YORUMLARI GÖSTER")',
                'a[data-testid="show-more-button"]',
                'a:has-text("TÜM YORUMLARI GÖSTER")',
                'button:has-text("TÜM YORUMLARI GÖSTER")'
            ]
            for selector in btn_selectors:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    print(f"Yorum butonu: {selector}")
                    await btn.first.click()
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(2000)
                    break

            last_count = 0
            same_count_times = 0
            comment_items = None

            for _ in range(500):
                for selector in ['div.reviews-wrapper div.comment', 'div.comment', 'div[data-testid="comment"]', 'div.review-item']:
                    items = page.locator(selector)
                    count = await items.count()
                    if count > 0:
                        comment_items = items
                        comment_count = count
                        break
                else:
                    comment_count = 0

                print(f"Yorum sayısı: {comment_count}")
                if comment_count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= 10:
                    print("Yorum artmıyor, duruluyor.")
                    break
                last_count = comment_count
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.75)")
                await page.wait_for_timeout(800)

            if comment_items:
                for i in range(min(await comment_items.count(), 200)):
                    try:
                        user, text, stars = "", "", 0
                        for s in ['div.comment-info-item', 'span.user-name', 'div.user-info span']:
                            e = comment_items.nth(i).locator(s)
                            if await e.count() > 0:
                                user = await e.first.inner_text()
                                break
                        for s in ['div.comment-text p', 'div.comment-text', 'p', 'div.text']:
                            e = comment_items.nth(i).locator(s)
                            if await e.count() > 0:
                                text = await e.first.inner_text()
                                break
                        ratings_block = comment_items.nth(i).locator('div.ratings.readonly')
                        if await ratings_block.count() > 0:
                            star_ws = ratings_block.first.locator('div.star-w')
                            for j in range(await star_ws.count()):
                                full = star_ws.nth(j).locator('div.full')
                                if await full.count() > 0:
                                    width = await full.first.evaluate("el => el.style.width")
                                    if width:
                                        try:
                                            stars += float(width.replace('%', '')) / 100
                                        except:
                                            pass
                        if text.strip():
                            comments.append({'user': user.strip() or "Anonim", 'text': text.strip(), 'stars': stars})
                    except Exception as e:
                        print(f"Yorum parse hatası: {e}")
        except Exception as e:
            print(f"Yorum hatası: {e}")

        print(f"Toplam yorum: {len(comments)}")

        # --- Q&A ---
        qna_list = []
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            print("Q&A aranıyor...")

            qna_btn = None
            for _ in range(20):
                for selector in ['a:has-text("Tüm Soruları Göster")', 'button:has-text("Tüm Soruları Göster")', 'a[data-testid="show-more-button"]']:
                    btn = page.locator(selector)
                    if await btn.count() > 0:
                        qna_btn = btn
                        break
                if qna_btn:
                    break
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.75)")
                await page.wait_for_timeout(800)

            if qna_btn:
                await qna_btn.first.click()
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)
            else:
                print("Q&A butonu bulunamadı!")

            last_count = 0
            same_count_times = 0
            qna_items = None

            for _ in range(500):
                qna_items = page.locator('div.qna-item')
                qna_count = await qna_items.count()
                print(f"Q&A sayısı: {qna_count}")
                if qna_count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= 10:
                    print("Q&A artmıyor, duruluyor.")
                    break
                last_count = qna_count
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.75)")
                await page.wait_for_timeout(800)

            if qna_items:
                for i in range(await qna_items.count()):
                    try:
                        question, answer = "", ""
                        q = qna_items.nth(i).locator('h4')
                        if await q.count() > 0:
                            question = await q.first.inner_text()
                        a = qna_items.nth(i).locator('div.answer h5')
                        if await a.count() > 0:
                            answer = await a.first.inner_text()
                        if question.strip() or answer.strip():
                            qna_list.append({'question': question.strip(), 'answer': answer.strip()})
                    except Exception as e:
                        print(f"Q&A parse hatası: {e}")
        except Exception as e:
            print(f"Q&A hatası: {e}")

        print(f"Toplam Q&A: {len(qna_list)}")
        await browser.close()

        return {
            'title': title.strip(),
            'price': price.strip() if price else None,
            'description': description.strip(),
            'images': image_urls,
            'comments': comments,
            'qna': qna_list
        }
