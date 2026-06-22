import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Origin": "https://www.trendyol.com",
    "Referer": "https://www.trendyol.com/",
    "storefront-id": "1",
    "culture": "tr-TR",
    "channel-id": "1",
    "platform": "WEB",
}

BASE_API = "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/api"
REVIEW_API = "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/api/product-reviews"
QNA_API = "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/api/qna"

def extract_product_id(url: str) -> str:
    match = re.search(r'-p-(\d+)', url)
    if not match:
        raise ValueError(f"Ürün ID bulunamadı: {url}")
    return match.group(1)

async def scrape_product(url: str):
    product_id = extract_product_id(url)
    print(f"Ürün ID: {product_id}")

    # ANA ÜRÜN BİLGİSİ
    product_url = f"{BASE_API}/productDetail?contentId={product_id}"
    print(f"API isteği: {product_url}")
    resp = requests.get(product_url, headers=HEADERS, timeout=30)
    print(f"Ürün API status: {resp.status_code}")

    title = ""
    price = None
    description = ""
    image_urls = []

    if resp.status_code == 200:
        data = resp.json()
        print(f"API response keys: {list(data.keys())}")

        # Başlık
        title = data.get("name", "") or data.get("title", "") or data.get("displayName", "")

        # Fiyat
        price_data = data.get("priceWithDiscountedTax") or data.get("price") or data.get("salePrice")
        if price_data:
            price = f"{price_data} TL"

        # Açıklama
        description = data.get("description", "") or data.get("productDetailAttributes", "")

        # Görseller
        images = data.get("images", [])
        for img in images:
            if isinstance(img, str):
                image_urls.append(img)
            elif isinstance(img, dict):
                src = img.get("url") or img.get("imageUrl") or img.get("src")
                if src:
                    image_urls.append(src)

        print(f"Başlık: {title}")
        print(f"Fiyat: {price}")
        print(f"Görsel: {len(image_urls)}")
    else:
        print(f"API yanıtı: {resp.text[:500]}")

    # YORUMLAR
    comments = []
    try:
        page = 0
        while len(comments) < 200:
            review_url = f"{REVIEW_API}?productId={product_id}&page={page}&size=20"
            r = requests.get(review_url, headers=HEADERS, timeout=30)
            print(f"Yorum API status ({page}): {r.status_code}")
            if r.status_code != 200:
                break
            review_data = r.json()
            items = review_data.get("reviews", review_data.get("content", review_data.get("items", [])))
            if not items:
                break
            for item in items:
                text = item.get("text", "") or item.get("comment", "") or item.get("content", "")
                user = item.get("userFullName", "") or item.get("userName", "") or item.get("user", {}).get("name", "Anonim")
                stars = item.get("rate", 0) or item.get("rating", 0) or item.get("star", 0)
                if text:
                    comments.append({"user": str(user), "text": str(text), "stars": float(stars)})
            total_pages = review_data.get("totalPages", review_data.get("pageCount", 1))
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
        while len(qna_list) < 200:
            qna_url = f"{QNA_API}?productId={product_id}&page={page}&size=20"
            r = requests.get(qna_url, headers=HEADERS, timeout=30)
            print(f"Q&A API status ({page}): {r.status_code}")
            if r.status_code != 200:
                break
            qna_data = r.json()
            items = qna_data.get("questions", qna_data.get("content", qna_data.get("items", [])))
            if not items:
                break
            for item in items:
                question = item.get("text", "") or item.get("question", "") or item.get("questionText", "")
                answer = ""
                answers = item.get("answers", [])
                if answers and isinstance(answers, list):
                    answer = answers[0].get("text", "") or answers[0].get("answer", "") or answers[0].get("answerText", "")
                if question or answer:
                    qna_list.append({"question": str(question), "answer": str(answer)})
            total_pages = qna_data.get("totalPages", qna_data.get("pageCount", 1))
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
