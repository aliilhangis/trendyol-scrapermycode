import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Origin": "https://www.trendyol.com",
    "Referer": "https://www.trendyol.com/",
    "channelId": "1",
    "storefrontId": "1",
    "culture": "tr-TR",
    "platform": "WEB",
}

BASE = "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/api"

def extract_ids(url: str):
    product_id = re.search(r'-p-(\d+)', url)
    seller_id = re.search(r'merchantId=(\d+)', url)
    if not product_id:
        raise ValueError(f"Ürün ID bulunamadı: {url}")
    return product_id.group(1), (seller_id.group(1) if seller_id else None)

async def scrape_product(url: str):
    product_id, seller_id = extract_ids(url)
    print(f"Ürün ID: {product_id} | Satıcı ID: {seller_id}")

    # ANA ÜRÜN — breadcrumb-seo'dan başlık al
    title = ""
    price = None
    description = ""
    image_urls = []

    try:
        slug_match = re.search(r'trendyol\.com/([^?]+)', url)
        slug = slug_match.group(1) if slug_match else f"p-{product_id}"

        # Breadcrumb'dan başlık
        breadcrumb_url = (
            f"https://apigw.trendyol.com/discovery-storefrontmarketing-marketinggw-service"
            f"/breadcrumb-seo/{slug}"
            f"?__renderMode=stream&platform=WEB&enableRedirect=true&pageType=product"
            f"&channelId=1&storefrontId=1&language=tr&countryCode=TR&tld=.com&subPathStrategy=no-subpath"
        )
        r = requests.get(breadcrumb_url, headers=HEADERS, timeout=30)
        print(f"Breadcrumb status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            html = data.get("main", "")
            match = re.search(r'<span>([^<]+)</span>\s*</li>\s*</ul>', html)
            if match:
                title = match.group(1).strip()
                print(f"Başlık: {title}")

        # product-detail-seo'dan fiyat ve görseller
        seo_url = (
            f"https://apigw.trendyol.com/discovery-storefrontmarketing-marketinggw-service"
            f"/product-detail-seo/{slug}"
            f"?__renderMode=stream&platform=WEB&enableRedirect=true&skipBreadcrumbPartial=true"
            f"&channelId=1&storefrontId=1&language=tr&countryCode=TR&tld=.com&subPathStrategy=no-subpath"
        )
        r2 = requests.get(seo_url, headers=HEADERS, timeout=30)
        print(f"SEO status: {r2.status_code}")
        if r2.status_code == 200:
            seo_data = r2.json()
            seo_html = seo_data.get("main", "") or str(seo_data)
            print(f"SEO response ilk 300: {seo_html[:300]}")

            # Fiyat - JSON-LD içinden çek
            price_match = re.search(r'"price"\s*:\s*"?([\d.]+)"?', seo_html)
            if price_match:
                price = f"{price_match.group(1)} TL"
                print(f"Fiyat: {price}")

            # Görseller - JSON-LD veya og:image içinden
            img_matches = re.findall(r'https://cdn\.dsmcdn\.com[^"'\s]+(?:jpg|jpeg|png|webp)', seo_html)
            for img in img_matches:
                if img not in image_urls:
                    image_urls.append(img)
            print(f"Görsel: {len(image_urls)}")

    except Exception as e:
        print(f"Başlık/SEO hatası: {e}")

    # YORUMLAR
    comments = []
    try:
        page = 0
        while len(comments) < 500:
            r = requests.get(
                f"{BASE}/review-read/product-reviews/detailed",
                params={"channelId": 1, "contentId": product_id, "page": page, "pageSize": 20},
                headers=HEADERS, timeout=30
            )
            print(f"Yorum API ({page}): {r.status_code}")
            if r.status_code != 200:
                break
            data = r.json()
            result = data.get("result", {})
            items = result.get("reviews", [])
            if not items:
                break
            for item in items:
                text = item.get("comment", "")
                user = item.get("userFullName", "Anonim")
                stars = item.get("rate", 0)
                if text:
                    comments.append({"user": str(user), "text": str(text), "stars": float(stars)})
            total_pages = result.get("summary", {}).get("totalPages", 1)
            page += 1
            if page >= total_pages:
                break
        print(f"Toplam yorum: {len(comments)}")
    except Exception as e:
        print(f"Yorum hatası: {e}")

    # Q&A
    qna_list = []
    try:
        page = 0
        while len(qna_list) < 500:
            r = requests.get(
                f"{BASE}/merchant-questions/content/{product_id}/answered",
                params={"channelId": 1, "isMobile": "false", "fulfilmentType[]": "MP", "page": page, "size": 20},
                headers=HEADERS, timeout=30
            )
            print(f"Q&A API ({page}): {r.status_code}")
            if r.status_code != 200:
                break
            data = r.json()
            questions_block = data.get("questions", {})
            items = questions_block.get("content", [])
            if not items:
                break
            for item in items:
                question = item.get("text", "")
                answer_obj = item.get("answer", {})
                answer = answer_obj.get("text", "") if isinstance(answer_obj, dict) else ""
                if question or answer:
                    qna_list.append({"question": str(question), "answer": str(answer)})
            total_pages = questions_block.get("totalPages", 1)
            page += 1
            if page >= total_pages:
                break
        print(f"Toplam Q&A: {len(qna_list)}")
    except Exception as e:
        print(f"Q&A hatası: {e}")

    return {
        "title": title,
        "price": price,
        "description": description,
        "images": image_urls,
        "comments": comments,
        "qna": qna_list,
    }
