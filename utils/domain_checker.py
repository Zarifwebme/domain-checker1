import httpx
import asyncio
from bs4 import BeautifulSoup
import logging
import re
from typing import List, Dict, Any, Set, Tuple
import time
from concurrent.futures import ThreadPoolExecutor
import socket
import random
from urllib.parse import urlparse
import tldextract

# Yaxshiroq logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Timeout va qayta urinish sozlamalari
REQUEST_TIMEOUT = 4  # sekund (reduced from 5)
MAX_RETRIES = 2
RETRY_DELAY = 0.5  # sekund (reduced from 1)
MAX_BATCH_SIZE = 15  # Bir vaqtda tekshiriladigan domenlar soni (increased from 8)
MAX_CONNECTIONS = 30  # Httpx client uchun maksimal ulanishlar soni (increased from 20)
RATE_LIMIT = 40  # Sekunddagi so'rovlar soni (increased from 25)
TIMEOUT_COOLDOWN = 30  # Timeoutdan keyin kutish vaqti (sekund) (reduced from 60)
DNS_CACHE_SIZE = 5000  # DNS cache size
CONNECTION_KEEP_ALIVE = 20  # Connection keep-alive seconds

# DNS keshini yaratish
dns_cache = {}
domain_health_cache = {}  # Domain sog'liqi keshi


# DNS lookup acceleration
def cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """DNS lookup with caching for faster resolution"""
    if host in dns_cache:
        return dns_cache[host]
    else:
        try:
            result = socket.getaddrinfo(host, port, family, type, proto, flags)
            dns_cache[host] = result
            # Cache size limit
            if len(dns_cache) > DNS_CACHE_SIZE:
                # Random eviction policy
                keys_to_remove = random.sample(list(dns_cache.keys()), DNS_CACHE_SIZE // 10)
                for key in keys_to_remove:
                    dns_cache.pop(key, None)
            return result
        except socket.gaierror:
            # DNS resolution failed
            return None


# Pre-built lists for faster classification
login_keywords = {
    'login', 'signin', 'sign in', 'log in', 'sign-in', 'auth', 'authenticate',
    'register', 'kirish', 'ro\'yxatdan o\'tish', 'username', 'password', 'email',
    'foydalanuvchi', 'parol'
}

# Headers for requests to look more like a real browser
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
}

# List of status codes that require check
NEED_CHECK_STATUS_CODES = {400, 403, 429, 503}


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

    # Domain malumoti (TLD va h.k.)
    domain_info = tldextract.extract(domain)
    domain_key = f"{domain_info.domain}.{domain_info.suffix}"

    # Cached health check - if we've already marked this domain or its root as unreliable
    if domain_key in domain_health_cache and domain_health_cache[domain_key] == "poor":
        result["status"] = "Not Working"
        result["page_type"] = "Error"
        result["title"] = "Previously unreachable domain"
        return result

    # HTTP va HTTPS protokollarini olib tashlash
    domain = re.sub(r'^https?://', '', domain)
    # Trailing slash va bo'sh joylarni olib tashlash
    domain = domain.rstrip('/')

    # First try DNS resolution before even attempting HTTP requests
    try:
        # Fast DNS lookup to fail early for non-existent domains
        host = domain.split('/')[0]  # Only take the domain part
        if cached_getaddrinfo(host, 80) is None and cached_getaddrinfo(host, 443) is None:
            # DNS resolution failed - domain likely doesn't exist
            domain_health_cache[domain_key] = "poor"
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = "DNS resolution failed"
            return result
    except Exception as dns_error:
        # Continue anyway - some DNS servers might still resolve it
        pass

    # Domenni tekshirish
    for attempt in range(MAX_RETRIES + 1):
        try:
            url = f"https://{domain}"

            # Use custom headers to look more like a browser
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True,
                headers=BROWSER_HEADERS
            )

            result["status_code"] = response.status_code

            # Status logic - 2xx va 3xx kodlar "Working" hisoblanadi
            if 200 <= response.status_code < 400:
                result["status"] = "Working"
                # Mark domain as healthy
                domain_health_cache[domain_key] = "good"
            elif response.status_code in NEED_CHECK_STATUS_CODES:
                result["status"] = "Need to Check"
            else:
                result["status"] = "Not Working"
                # For persistent server errors, mark domain as poor health
                if response.status_code >= 500 and response.status_code not in NEED_CHECK_STATUS_CODES:
                    domain_health_cache[domain_key] = "poor"

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

            # Optimize HTML parsing with lighter functionality
            try:
                # Use a faster parsing method for title extraction
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

                # Sahifa turini aniqlash (Ichki yoki Tashqi) - optimized, faster approach
                # Use a simplified scoring algorithm for better performance
                is_internal = False

                # Fast check for password inputs (strongest indicator)
                if soup.find('input', {'type': 'password'}):
                    is_internal = True
                else:
                    # Quick check for login-related text in forms
                    forms = soup.find_all('form', limit=3)  # Only look at first 3 forms
                    for form in forms:
                        form_text = form.get_text().lower()
                        if any(keyword in form_text for keyword in login_keywords):
                            is_internal = True
                            break

                    # If still unsure, check for minimal content as fallback
                    if not is_internal:
                        # Check page size - very small pages often internal
                        page_text = soup.get_text()
                        is_internal = len(page_text) < 800

                result["page_type"] = "Internal" if is_internal else "External"

            except Exception as e:
                logger.error(f"HTML parse error for {domain}: {str(e)}")
                result["page_type"] = "Error"
                result["title"] = "Parse Error"

            # Muvaffaqiyatli bo'lsa, qaytaring
            return result

        except httpx.HTTPStatusError as e:
            result["status_code"] = e.response.status_code
            result["status"] = "Need to Check" if result["status_code"] in NEED_CHECK_STATUS_CODES else "Not Working"
            if result["status_code"] >= 500 and result["status_code"] not in NEED_CHECK_STATUS_CODES:
                domain_health_cache[domain_key] = "poor"
        except httpx.TimeoutException:
            if attempt < MAX_RETRIES:
                logger.warning(f"Timeout for {domain}, retry {attempt + 1}/{MAX_RETRIES}")
                await asyncio.sleep(RETRY_DELAY)
                continue
            result["status"] = "Need to Check"  # Changed from "Not Working" to "Need to Check" for timeout
            result["page_type"] = "Error"
            result["title"] = "Timeout"
        except httpx.RequestError as e:
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = f"Request Error: {type(e).__name__}"
            domain_health_cache[domain_key] = "poor"
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
                "status": "Need to Check",  # Changed from "Not Working" to "Need to Check"
                "status_code": None,
                "page_type": "Error",
                "title": f"Error: {type(result).__name__}"
            })
        else:
            processed_results.append(result)

    return processed_results


# Parallel group sorting function
def sort_domains_by_tld(domains: List[str]) -> List[List[str]]:
    """Sort domains into groups by TLD for more efficient batch processing"""
    tld_groups = {}

    for domain in domains:
        clean_domain = domain.strip().lower()
        clean_domain = re.sub(r'^https?://', '', clean_domain)

        try:
            extract_result = tldextract.extract(clean_domain)
            tld = extract_result.suffix

            if not tld:
                tld = "unknown"

            if tld not in tld_groups:
                tld_groups[tld] = []

            tld_groups[tld].append(domain)
        except:
            # Fall back to simple domain parsing if tldextract fails
            parts = clean_domain.split('.')
            if len(parts) >= 2:
                tld = parts[-1]
                if tld not in tld_groups:
                    tld_groups[tld] = []
                tld_groups[tld].append(domain)
            else:
                # Can't determine TLD
                if "unknown" not in tld_groups:
                    tld_groups["unknown"] = []
                tld_groups["unknown"].append(domain)

    # Convert to batches, keeping domains with the same TLD together when possible
    batches = []
    for tld, domains in tld_groups.items():
        for i in range(0, len(domains), MAX_BATCH_SIZE):
            batch = domains[i:i + MAX_BATCH_SIZE]
            batches.append(batch)

    # If there are partial batches, combine them to optimize batch sizes
    partial_batches = [b for b in batches if len(b) < MAX_BATCH_SIZE // 2]
    full_batches = [b for b in batches if len(b) >= MAX_BATCH_SIZE // 2]

    if partial_batches:
        # Combine partial batches
        combined = []
        current_batch = []

        for batch in partial_batches:
            if len(current_batch) + len(batch) <= MAX_BATCH_SIZE:
                current_batch.extend(batch)
            else:
                combined.append(current_batch)
                current_batch = batch

        if current_batch:
            combined.append(current_batch)

        batches = full_batches + combined
    else:
        batches = full_batches

    return batches


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
        keepalive_expiry=CONNECTION_KEEP_ALIVE
    )

    # Asinxron HTTP klient yaratish
    timeout_config = httpx.Timeout(REQUEST_TIMEOUT, connect=2.0)

    # Set up connection pool and other optimizations
    transport = httpx.AsyncHTTPTransport(
        limits=limits,
        retries=1,  # We handle our own retries
    )

    async with httpx.AsyncClient(
            timeout=timeout_config,
            transport=transport,
            follow_redirects=True,
            http2=True  # Enable HTTP/2 for efficiency
    ) as client:
        # Optimize domain grouping by TLD to reduce DNS lookups
        batches = sort_domains_by_tld(unique_domains)

        logger.info(f"Processing {len(batches)} optimized batches (max {MAX_BATCH_SIZE} domains per batch)")

        # Process batches concurrently, but with a limit to prevent overloading
        max_concurrent_batches = 3
        batch_semaphore = asyncio.Semaphore(max_concurrent_batches)

        async def process_batch_with_limit(batch):
            async with batch_semaphore:
                return await process_batch(client, batch)

        batch_tasks = [process_batch_with_limit(batch) for batch in batches]
        batch_results_list = await asyncio.gather(*batch_tasks)

        # Flatten results
        for batch_results in batch_results_list:
            all_results.extend(batch_results)

    logger.info(f"Completed checking {len(all_results)} domains")
    return all_results