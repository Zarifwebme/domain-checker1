import httpx
import asyncio
from bs4 import BeautifulSoup
import logging
import re
from typing import List, Dict, Any
import time
from concurrent.futures import ThreadPoolExecutor

# Yaxshiroq logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Timeout va qayta urinish sozlamalari
REQUEST_TIMEOUT = 5  # sekund
MAX_RETRIES = 2
RETRY_DELAY = 1  # sekund
MAX_BATCH_SIZE = 8  # Bir vaqtda tekshiriladigan domenlar soni
MAX_CONNECTIONS = 20  # Httpx client uchun maksimal ulanishlar soni
RATE_LIMIT = 25  # Sekunddagi so'rovlar soni
TIMEOUT_COOLDOWN = 60  # Timeoutdan keyin kutish vaqti (sekund)


async def check_domain(client: httpx.AsyncClient, domain: str, timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    """
    Domenni tekshirish va uning holati, turi va sarlavhasini qaytarish.
    """
    result = {
        "domain": domain,
        "status": "Not Working",
        "status_code": None,
        "page_type": "Unknown",
        "title": "No Title"
    }

    # Domain formatini tekshirish va to'g'rilash
    domain = domain.strip().lower()
    if not domain:
        return result

    # HTTP va HTTPS protokollarini olib tashlash
    domain = re.sub(r'^https?://', '', domain)
    # Trailing slash va bo'sh joylarni olib tashlash
    domain = domain.rstrip('/')

    # Domenni tekshirish
    for attempt in range(MAX_RETRIES + 1):
        try:
            url = f"https://{domain}"
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True
            )

            result["status_code"] = response.status_code

            # Status logic - 2xx va 3xx kodlar "Working" hisoblanadi
            if 200 <= response.status_code < 400:
                result["status"] = "Working"
            elif response.status_code in (429, 503):
                result["status"] = "Need to Check"
            else:
                result["status"] = "Not Working"

            # Agar 200 bo'lmasa, parsing qilishga hojat yo'q
            if response.status_code != 200:
                result["page_type"] = "Error"
                result["title"] = f"Status code: {response.status_code}"
                return result

            # Content-Type ni tekshirish
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                result["page_type"] = "Non-HTML"
                result["title"] = f"Type: {content_type[:50]}"
                return result

            # Endi HTML ni parse qilamiz
            try:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Sarlavhani olish
                title_tag = soup.title
                if title_tag and title_tag.string:
                    result["title"] = title_tag.string.strip()[:255]
                else:
                    # Agar title yo'q bo'lsa, meta og:title yoki boshqa elementlarni tekshirish
                    meta_title = soup.find('meta', property='og:title')
                    if meta_title and meta_title.get('content'):
                        result["title"] = meta_title.get('content')[:255]
                    else:
                        h1 = soup.find('h1')
                        if h1 and h1.text:
                            result["title"] = h1.text.strip()[:255]
                        else:
                            result["title"] = "No Title"

                # Sahifa turini aniqlash (Ichki yoki Tashqi)
                login_score = 0
                content_score = 0

                # Login indikatorlarni tekshirish
                login_patterns = [
                    r'\b(login|signin|sign in|log in|sign-in|auth|authenticate|register|kirish|ro\'yxatdan o\'tish)\b',
                    r'\b(username|password|email|foydalanuvchi|parol)\b'
                ]

                # Parolni kiritish maydonlari (kuchli Ichki indikator)
                forms = soup.find_all('form')
                password_inputs = soup.find_all('input', {'type': 'password'})
                if password_inputs:
                    login_score += 3

                # Login bilan bog'liq kalit so'zlarni tekshirish
                page_text = soup.get_text(separator=' ', strip=True).lower()

                for pattern in login_patterns:
                    if re.search(pattern, page_text, re.IGNORECASE):
                        login_score += 1

                # Form attributelarini tekshirish
                for form in forms:
                    form_attrs = ' '.join([str(form.get(attr, '')) for attr in ['action', 'id', 'class']])
                    if any(term in form_attrs.lower() for term in ['login', 'signin', 'auth', 'kirish']):
                        login_score += 1

                # Tashqi kontent indikatorlarini baholash
                content_tags = ['div', 'p', 'article', 'section', 'ul', 'table', 'img', 'h1', 'h2', 'h3']
                for tag in content_tags:
                    elements = soup.find_all(tag)
                    content_score += min(len(elements), 5)  # Har bir teg turi uchun max 5 ball

                # Matn uzunligi kam bo'lsa, ehtimol Ichki
                if len(page_text) < 500:
                    login_score += 1
                else:
                    content_score += 1

                # Sahifa turini aniqlash
                if login_score >= 3 and login_score > content_score:
                    result["page_type"] = "Internal"
                elif content_score > login_score or content_score >= 10:
                    result["page_type"] = "External"
                else:
                    # Default holat
                    result["page_type"] = "External" if content_score >= login_score else "Internal"

            except Exception as e:
                logger.error(f"HTML parse error for {domain}: {str(e)}")
                result["page_type"] = "Error"
                result["title"] = "Parse Error"

            # Muvaffaqiyatli bo'lsa, qaytaring
            return result

        except httpx.HTTPStatusError as e:
            result["status_code"] = e.response.status_code
            result["status"] = "Need to Check" if result["status_code"] in (429, 503) else "Not Working"
        except httpx.TimeoutException:
            if attempt < MAX_RETRIES:
                logger.warning(f"Timeout for {domain}, retry {attempt + 1}/{MAX_RETRIES}")
                await asyncio.sleep(RETRY_DELAY)
                continue
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = "Timeout"
        except httpx.RequestError as e:
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = f"Request Error: {type(e).__name__}"
        except Exception as e:
            logger.error(f"Unexpected error checking {domain}: {str(e)}")
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = "Error"

        # Qayta urinishlardagi xatoliklar uchun kichik kutish
        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)

    return result


async def process_batch(client: httpx.AsyncClient, domains: List[str]) -> List[Dict[str, Any]]:
    """Domenlar guruhini parallel tekshirish"""
    tasks = [check_domain(client, domain) for domain in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Xatoliklarni boshqarish
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error processing domain {domains[i]}: {str(result)}")
            processed_results.append({
                "domain": domains[i],
                "status": "Not Working",
                "status_code": None,
                "page_type": "Error",
                "title": f"Error: {type(result).__name__}"
            })
        else:
            processed_results.append(result)

    return processed_results


async def check_domains(domains: List[str], batch_size: int = MAX_BATCH_SIZE) -> List[Dict[str, Any]]:
    """
    Domenlar ro'yxatini tekshirish va natijalarni qaytarish.
    Katta ro'yxatlar uchun batching va rate limiting qo'llaniladi.
    """
    all_results = []
    total_domains = len(domains)

    # Dublikatlarni olib tashlash va tekshirish
    unique_domains = list(set(domains))
    logger.info(f"Checking {len(unique_domains)} unique domains (from {total_domains} total)")

    # Client limits settings
    limits = httpx.Limits(
        max_keepalive_connections=MAX_CONNECTIONS,
        max_connections=MAX_CONNECTIONS,
        keepalive_expiry=10
    )

    # Asinxron HTTP klient yaratish
    timeout_config = httpx.Timeout(REQUEST_TIMEOUT, connect=3.0)

    async with httpx.AsyncClient(
            timeout=timeout_config,
            limits=limits,
            follow_redirects=True
    ) as client:

        # Domenlarni kichik guruhlarga bo'lish
        batch_size = min(batch_size, MAX_BATCH_SIZE)  # Max batch size bilan cheklash
        batches = [unique_domains[i:i + batch_size] for i in range(0, len(unique_domains), batch_size)]

        logger.info(f"Processing {len(batches)} batches of {batch_size} domains each")

        batch_count = len(batches)
        for i, batch in enumerate(batches):
            try:
                logger.info(f"Processing batch {i + 1}/{batch_count} ({len(batch)} domains)")
                start_time = time.time()

                # Batch ni parallel tekshirish
                batch_results = await process_batch(client, batch)
                all_results.extend(batch_results)

                # Rate limiting - har bir batch dan keyin kutish
                elapsed = time.time() - start_time
                sleep_time = max(0, (len(batch) / RATE_LIMIT) - elapsed)

                if sleep_time > 0 and i < batch_count - 1:  # So'nggi batch emas
                    logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error processing batch {i + 1}: {str(e)}")
                # Batch muvaffaqiyatsiz bo'lgan taqdirda, domenlarni alohida-alohida tekshirishga o'tish
                logger.info(f"Falling back to individual processing for batch {i + 1}")
                for domain in batch:
                    try:
                        # Har bir domenni alohida tekshirish
                        result = await check_domain(client, domain)
                        all_results.append(result)
                        # Xizmatlarni ortiqcha yuklamaslik uchun qisqa kutish
                        await asyncio.sleep(0.5)
                    except Exception as domain_error:
                        logger.error(f"Individual domain error for {domain}: {str(domain_error)}")
                        all_results.append({
                            "domain": domain,
                            "status": "Not Working",
                            "status_code": None,
                            "page_type": "Error",
                            "title": "Processing Error"
                        })

    logger.info(f"Completed checking {len(all_results)} domains")
    return all_results