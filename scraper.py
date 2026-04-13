import asyncio
import json
from playwright.async_api import async_playwright

async def scrape_product(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Çerez/KVKK popup'ı varsa otomatik kapat
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
                print(f"Çerez popup'ı otomatik kapatıldı: {sel}")
                break
            except:
                continue

        await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)")
        await page.wait_for_timeout(1000)

        # --- ÜRÜN BAŞLIĞI ---
        title = await page.locator('h1').first.inner_text()

        # --- ÜRÜN FİYATI ---
        price = None
        price_selectors = [
            'span.prc-dsc',
            'span.prc-org',
            'p.prc-dsc',
            'span.price-view-original'
        ]
        for sel in price_selectors:
            price_locator = page.locator(sel)
            if await price_locator.count() > 0:
                price = await price_locator.first.inner_text()
                break

        # --- ÜRÜN AÇIKLAMASI ---
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
                    break
        except Exception as e:
            print(f"Açıklama alınırken hata: {e}")

        # --- ÜRÜN GÖRSELLERİ ---
        image_urls = []
        thumbs = page.locator('div._carouselThumbsContainer_05669af img._carouselThumbsImage_ddecc3e')
        thumbs_count = await thumbs.count()
        for i in range(thumbs_count):
            src = await thumbs.nth(i).get_attribute('src')
            if src and src not in image_urls:
                image_urls.append(src)

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
                    print(f"Yorum butonu bulundu: {selector}")
                    await btn.first.click()
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(2000)
                    break

            last_count = 0
            same_count_times = 0
            max_no_increase = 10
            comment_items = None

            for _ in range(500):
                comment_selectors = [
                    'div.reviews-wrapper div.comment',
                    'div.comment',
                    'div[data-testid="comment"]',
                    'div.review-item'
                ]
                for selector in comment_selectors:
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
                if same_count_times >= max_no_increase:
                    print("Yorum sayısı artmıyor, durduruluyor.")
                    break
                last_count = comment_count
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.75)")
                await page.wait_for_timeout(800)

            if comment_items:
                for i in range(min(await comment_items.count(), 200)):
                    try:
                        user = ""
                        text = ""
                        stars = 0

                        for user_sel in ['div.comment-info-item', 'span.user-name', 'div.user-info span']:
                            user_elem = comment_items.nth(i).locator(user_sel)
                            if await user_elem.count() > 0:
                                user = await user_elem.first.inner_text()
                                break

                        for text_sel in ['div.comment-text p', 'div.comment-text', 'p', 'div.text']:
                            text_elem = comment_items.nth(i).locator(text_sel)
                            if await text_elem.count() > 0:
                                text = await text_elem.first.inner_text()
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
                                            continue

                        if text.strip():
                            comments.append({
                                'user': user.strip() if user else "Anonim",
                                'text': text.strip(),
                                'stars': stars
                            })
                    except Exception as e:
                        print(f"Yorum işlenirken hata: {e}")
                        continue
        except Exception as e:
            print(f"Yorumlar alınırken hata: {e}")

        # --- SORU-CEVAP (Q&A) ---
        qna_list = []
        try:
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            print("Q&A aranıyor...")

            qna_btn = None
            qna_btn_selectors = [
                'a[data-testid="show-more-button"] span:has-text("Tüm Soruları Göster")',
                'a[data-testid="show-more-button"]',
                'a:has-text("Tüm Soruları Göster")',
                'button:has-text("Tüm Soruları Göster")'
            ]
            for _ in range(20):
                for selector in qna_btn_selectors:
                    btn = page.locator(selector)
                    if await btn.count() > 0:
                        qna_btn = btn
                        print(f"Q&A butonu bulundu: {selector}")
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
            max_no_increase = 10
            qna_items = None

            for _ in range(500):
                qna_items = page.locator('div.qna-item')
                qna_count = await qna_items.count()
                print(f"Q&A sayısı: {qna_count}")
                if qna_count == last_count:
                    same_count_times += 1
                else:
                    same_count_times = 0
                if same_count_times >= max_no_increase:
                    print("Q&A sayısı artmıyor, durduruluyor.")
                    break
                last_count = qna_count
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.75)")
                await page.wait_for_timeout(800)

            if qna_items:
                for i in range(await qna_items.count()):
                    try:
                        question = ""
                        answer = ""
                        question_elem = qna_items.nth(i).locator('h4')
                        if await question_elem.count() > 0:
                            question = await question_elem.first.inner_text()
                        answer_elem = qna_items.nth(i).locator('div.answer h5')
                        if await answer_elem.count() > 0:
                            answer = await answer_elem.first.inner_text()
                        if question.strip() or answer.strip():
                            qna_list.append({
                                'question': question.strip() if question else "",
                                'answer': answer.strip() if answer else ""
                            })
                    except Exception as e:
                        print(f"Q&A işlenirken hata: {e}")
                        continue
        except Exception as e:
            print(f"Q&A alınırken hata: {e}")

        await browser.close()

        return {
            'title': title.strip(),
            'price': price.strip() if price else None,
            'description': description.strip(),
            'images': image_urls,
            'comments': comments,
            'qna': qna_list
        }
