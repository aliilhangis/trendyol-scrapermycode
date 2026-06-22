import os
import requests
from bs4 import BeautifulSoup

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")

def fetch(url: str) -> BeautifulSoup:
    api_url = "https://api.scraperapi.com/"
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "render": "true",
        "country_code": "tr",
        "wait_for_selector": "h1",
    }
    print(f"Fetching: {url}")
    response = requests.get(api_url, params=params, timeout=90)
    print(f"Status: {response.status_code} | Size: {len(response.text)} chars")
    return BeautifulSoup(response.text, "html.parser")

async def scrape_product(url: str):
    base_url = url.split('?')[0].rstrip('/')
    reviews_url = base_url + '/yorumlar'
    qna_url = base_url + '/saticiya-sor'

    # ANA SAYFA
    soup = fetch(url)

    # BAŞLIK
    title = ""
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
        print(f"Başlık: {title}")
    else:
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ""
        print(f"H1 yok, title: {title}")

    # FİYAT
    price = None
    price_el = soup.find('span', class_='discounted')
    if price_el:
        price = price_el.get_text(strip=True)
        print(f"Fiyat: {price}")
    else:
        print("Fiyat bulunamadı!")

    # AÇIKLAMA
    description = ""
    for sel in ['detail-attr-container', 'product-description']:
        el = soup.find('div', id=sel) or soup.find('div', class_=sel)
        if el:
            description = el.get_text(separator='\n', strip=True)
            print(f"Açıklama bulundu: {sel}")
            break

    # GÖRSELLER
    image_urls = []
    for img in soup.select('img[src*="cdn.dsmcdn.com"]'):
        src = img.get('src', '')
        if src and src not in image_urls:
            image_urls.append(src)
    print(f"Görsel: {len(image_urls)}")

    # YORUMLAR SAYFASI
    comments = []
    try:
        review_soup = fetch(reviews_url)
        review_cards = review_soup.find_all('div', class_='review')
        print(f"Yorum kartı: {len(review_cards)}")

        for card in review_cards:
            try:
                user_el = card.find('span', class_=lambda c: c and 'name' in c)
                text_el = card.find('div', class_='review-comment')
                full_stars = card.find_all(class_=lambda c: c and 'full-star' in c) if card else []

                user = user_el.get_text(strip=True) if user_el else "Anonim"
                text = text_el.get_text(strip=True) if text_el else ""
                stars = len(full_stars)

                if text:
                    comments.append({'user': user, 'text': text, 'stars': stars})
            except Exception as e:
                print(f"Yorum parse hatası: {e}")
    except Exception as e:
        print(f"Yorum hatası: {e}")

    print(f"İşlenen yorum: {len(comments)}")

    # Q&A SAYFASI
    qna_list = []
    try:
        qna_soup = fetch(qna_url)
        qna_cards = qna_soup.find_all('div', class_='question-answer-card')
        print(f"Q&A kartı: {len(qna_cards)}")

        for card in qna_cards:
            try:
                q_el = card.find('div', class_='question-answer-card-question-text')
                a_el = card.find('div', class_='seller-answer-content-text')

                question = q_el.get_text(strip=True) if q_el else ""
                answer = a_el.get_text(strip=True) if a_el else ""

                if question or answer:
                    qna_list.append({'question': question, 'answer': answer})
            except Exception as e:
                print(f"Q&A parse hatası: {e}")
    except Exception as e:
        print(f"Q&A hatası: {e}")

    print(f"İşlenen Q&A: {len(qna_list)}")

    return {
        'title': title,
        'price': price,
        'description': description,
        'images': image_urls,
        'comments': comments,
        'qna': qna_list
    }
