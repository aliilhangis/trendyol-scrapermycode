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
        for sel in ['button:has-text("Kabul Et")', 'button#onetrust-accept-btn-handler', 'button:has-text("Accept All")']:
            try:
                await page.wait_for_selector(sel, timeout=2000)
                await page.click(sel)
                print(f"Çerez kapatıldı: {sel}")
                break
            except:
                continue

        await page.wait_for_timeout(2000)

        # --- BAŞLIK ---
        title = await page.locator('h1').first.inner_text()
        print(f"Başlık: {title}")

        # --- FİYAT ---
        price = None
        try:
            price_locator = page.locator('span.discounted')
            if await price_locator.count() > 0:
                price = await price_locator.first.inner_text()
                print(f"Fiyat: {price}")
            else:
                print("Fiyat bulunamadı!")
        except Exception as e:
            print(f"Fiyat hatası: {e}")

        # --- AÇIKLAMA ---
        description = ""
        try:
            for sel in ['div.detail-attr-container', 'div#product-description', 'div.product-description']:
                el = page.locator(sel)
                if await el.count() > 0:
                    description = await el.first.inner_text()
                    print(f"Açıklama bulundu: {sel}")
                    break
        except Exception as e:
            print(f"Açıklama hatası: {e}")

        # --- GÖRSELLER ---
        image_urls = []
        thumbs = page.locator('div._carouselThumbsContainer_05669af img._carouselThumbsImage_ddecc3e')
        for i in range(await thumbs.count()):
            src = await thumbs.nth(i).get_attribute('src')
            if src and src not in image_urls:
                image_urls.append(src)
        print(f"Görsel sayısı: {len(image_urls)}")

        # --- YORUMLAR ---
        comments = []
        try:
            print("Yorumlar aranıyor...")

            # Yorum bölümüne scroll et ve yüklenmeyi bekle
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            # "Tüm Yorumları Göster" butonuna tıkla
            for sel in [
                'a[data-testid="show-more-button"] span:has-text("TÜM YORUMLARI GÖSTER")',
                'a:has-text("TÜM YORUMLARI GÖSTER")',
                'div.reviews-summary-reviews-detail a',
            ]:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    print(f"Yorum butonu: {sel}")
                    await btn.first.click()
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(2000)
                    break

            # Yorum kartlarını topla (scroll ile lazy-load)
            last_count = 0
            same_count_times = 0
            for _ in range(200):
                items = page.locator('div.review-review')
                count = await items.count()
                print(f"Yorum sayısı: {count}")
                if count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= 8:
                    break
                last_count = count
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(800)

            items = page.locator('div.review-review')
            total = await items.count()
            print(f"Toplam yorum elementi: {total}")

            for i in range(total):
                try:
                    item = items.nth(i)
                    user, text, stars = "", "", 0

                    # Kullanıcı adı
                    for s in ['div.review-author', 'span.user-name', 'div.comment-info-item']:
                        e = item.locator(s)
                        if await e.count() > 0:
                            user = await e.first.inner_text()
                            break

                    # Yorum metni
                    for s in ['div.review-description', 'div.comment-text p', 'div.comment-text', 'p']:
                        e = item.locator(s)
                        if await e.count() > 0:
                            text = await e.first.inner_text()
                            break

                    # Yıldız
                    rating_el = item.locator('[class*="rating"], [class*="star"], div.ratings')
                    if await rating_el.count() > 0:
                        rating_text = await rating_el.first.inner_text()
                        try:
                            stars = float(rating_text.strip().split()[0].replace(',', '.'))
                        except:
                            pass

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

        print(f"Toplam yorum: {len(comments)}")

        # --- Q&A ---
        qna_list = []
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            print("Q&A aranıyor...")

            # Sayfayı aşağı scroll et, Q&A bölümü lazy-load
            for _ in range(15):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(600)

            # "Tüm Soruları Göster" butonu
            qna_btn = None
            for sel in [
                'a:has-text("Tüm Soruları Göster")',
                'button:has-text("Tüm Soruları Göster")',
                'div.questions-summary-questions-summary a',
            ]:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    qna_btn = btn
                    print(f"Q&A butonu: {sel}")
                    break

            if qna_btn:
                await qna_btn.first.click()
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)
            else:
                print("Q&A butonu bulunamadı!")

            # Q&A scroll ile yükle
            last_count = 0
            same_count_times = 0
            for _ in range(200):
                items = page.locator('div.questions-question-wrapper')
                count = await items.count()
                print(f"Q&A sayısı: {count}")
                if count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= 8:
                    break
                last_count = count
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(800)

            items = page.locator('div.questions-question-wrapper')
            total = await items.count()
            print(f"Toplam Q&A elementi: {total}")

            for i in range(total):
                try:
                    item = items.nth(i)
                    question, answer = "", ""

                    q = item.locator('div.questions-question')
                    if await q.count() > 0:
                        question = await q.first.inner_text()

                    a = item.locator('div.questions-answer')
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
