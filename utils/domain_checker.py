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

# Timeout va qayta urinish sozlamalari - optimized for performance
REQUEST_TIMEOUT = 5  # sekund (increased from 3)
MAX_RETRIES = 2  # Increased from 1
RETRY_DELAY = 1.0  # sekund (increased from 0.3)
MAX_BATCH_SIZE = 3  # Reduced from 5 for more thorough checking
MAX_CONNECTIONS = 10  # Reduced from 20 for more reliable connections
RATE_LIMIT = 20  # Reduced from 30 for better rate limiting
TIMEOUT_COOLDOWN = 30  # Increased from 15
DNS_CACHE_SIZE = 500  # Reduced from 1000 for more frequent fresh checks
CONNECTION_KEEP_ALIVE = 20  # Increased from 10

# DNS keshini yaratish - with size limits
dns_cache = {}
domain_health_cache = {}  # Domain sog'liqi keshi


# Faster DNS lookup with caching
def cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """DNS lookup with caching for faster resolution"""
    # Quick return for known bad domains
    if host in domain_health_cache and domain_health_cache[host] == "poor":
        return None

    if host in dns_cache:
        return dns_cache[host]
    else:
        try:
            # Use a shorter timeout for DNS lookups
            socket.setdefaulttimeout(1.5)
            result = socket.getaddrinfo(host, port, family, type, proto, flags)
            dns_cache[host] = result

            # Cache size limit with periodic cleanup to avoid memory issues
            if len(dns_cache) > DNS_CACHE_SIZE:
                # Random eviction policy - more aggressive cleanup
                keys_to_remove = random.sample(list(dns_cache.keys()), DNS_CACHE_SIZE // 5)
                for key in keys_to_remove:
                    dns_cache.pop(key, None)
            return result
        except socket.gaierror:
            # DNS resolution failed - mark as poor health
            domain_health_cache[host] = "poor"
            return None
        except socket.timeout:
            # DNS timeout - also mark as poor health
            domain_health_cache[host] = "poor"
            return None


# Pre-built lists for faster classification - minimized for speed
login_keywords = {
    'login', 'signin', 'sign in', 'log in', 'auth', 'authenticate',
    'register', 'kirish', 'parol'
}

# Headers for requests to look more like a real browser
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# List of status codes that require check
NEED_CHECK_STATUS_CODES = {400, 403, 429, 503}


async def check_domain(client: httpx.AsyncClient, domain: str, timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    """
    Domenni tekshirish va uning holati, turi va sarlavhasini qaytarish.
    """
    # Default result for quick returns
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

    # Quick optimization - reject obviously invalid domains early
    if len(domain) > 255 or ' ' in domain:
        result["title"] = "Invalid domain format"
        return result

    # Domain malumoti (TLD va h.k.)
    try:
        domain_info = tldextract.extract(domain)
        domain_key = f"{domain_info.domain}.{domain_info.suffix}"

        # Skip domains that don't have a proper TLD
        if not domain_info.suffix:
            result["title"] = "Invalid domain (no TLD)"
            return result
    except:
        # If tldextract fails, just use the domain as is
        domain_key = domain

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
    dns_resolved = False
    try:
        # Fast DNS lookup to fail early for non-existent domains
        host = domain.split('/')[0]  # Only take the domain part
        if cached_getaddrinfo(host, 80) is not None or cached_getaddrinfo(host, 443) is not None:
            dns_resolved = True
    except Exception as dns_error:
        # Log error but continue - some DNS servers might still resolve it
        logger.debug(f"DNS error for {domain}: {str(dns_error)}")

    if not dns_resolved:
        # Try one more time with a longer timeout
        try:
            socket.setdefaulttimeout(3.0)  # Longer timeout for second attempt
            if cached_getaddrinfo(host, 80) is not None or cached_getaddrinfo(host, 443) is not None:
                dns_resolved = True
        except:
            pass

    if not dns_resolved:
        result["status"] = "Not Working"
        result["page_type"] = "Error"
        result["title"] = "DNS resolution failed"
        return result

    # Domenni tekshirish
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Try HTTPS first
            url = f"https://{domain}"
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True,
                headers=BROWSER_HEADERS
            )
            result["status_code"] = response.status_code

            # If HTTPS fails with certain status codes, try HTTP
            if response.status_code in {400, 403, 404, 500, 502, 503, 504}:
                url = f"http://{domain}"
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

            # Optimize HTML parsing with lighter functionality - limit parsed content
            try:
                # Use a faster parsing method for title extraction - only parse first 100KB
                content_to_parse = response.text[:100000] if len(response.text) > 100000 else response.text
                soup = BeautifulSoup(content_to_parse, 'html.parser')

                # Sarlavhani olish
                title_tag = soup.title
                if title_tag and title_tag.string:
                    result["title"] = title_tag.string.strip()[:100]  # Limit title length
                else:
                    # Agar title yo'q bo'lsa, meta og:title yoki boshqa elementlarni tekshirish
                    meta_title = soup.find('meta', property='og:title')
                    if meta_title and meta_title.get('content'):
                        result["title"] = meta_title.get('content')[:100]
                    else:
                        h1 = soup.find('h1')
                        if h1 and h1.text:
                            result["title"] = h1.text.strip()[:100]
                        else:
                            result["title"] = "No Title"

                # Sahifa turini aniqlash - simplified approach
                # Fast check for password inputs (strongest indicator)
                if soup.find('input', {'type': 'password'}):
                    result["page_type"] = "Internal"
                else:
                    # Super quick check for login-related text
                    page_text = soup.get_text()[:3000].lower()  # Only check first 3000 chars
                    if any(keyword in page_text for keyword in login_keywords):
                        result["page_type"] = "Internal"
                    else:
                        result["page_type"] = "External"

            except Exception as e:
                logger.error(f"HTML parse error for {domain}: {str(e)}")
                result["page_type"] = "Error"
                result["title"] = "Parse Error"

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
            result["status"] = "Need to Check"
            result["page_type"] = "Error"
            result["title"] = "Timeout"
        except httpx.RequestError as e:
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = f"Request Error"
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
                "status": "Need to Check",
                "status_code": None,
                "page_type": "Error",
                "title": f"Error: {type(result).__name__}"
            })
        else:
            processed_results.append(result)

    return processed_results


# Improved batch organization prioritizing domain health
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
            if "unknown" not in tld_groups:
                tld_groups["unknown"] = []
            tld_groups["unknown"].append(domain)

    # Create smaller batches for better performance
    batches = []
    for tld, domains in tld_groups.items():
        for i in range(0, len(domains), MAX_BATCH_SIZE):
            batch = domains[i:i + MAX_BATCH_SIZE]
            batches.append(batch)

    return batches


async def check_domains(domains: List[str], batch_size: int = MAX_BATCH_SIZE) -> List[Dict[str, Any]]:
    """
    Domenlar ro'yxatini tekshirish va natijalarni qaytarish.
    Katta ro'yxatlar uchun batching va rate limiting qo'llaniladi.
    """
    # Track processed domains to provide partial results on timeout
    _domains_processed = []

    # Store reference to partial results to allow for timeout recovery
    check_domains._domains_processed = _domains_processed

    all_results = []
    total_domains = len(domains)

    # Dublikatlarni olib tashlash va tekshirish
    unique_domains = list(set(domains))
    logger.info(f"Checking {len(unique_domains)} unique domains (from {total_domains} total)")

    # Limit to reasonable number to prevent timeouts
    if len(unique_domains) > 1000:
        logger.warning(f"Too many domains to check in one request. Limiting to 1000.")
        unique_domains = unique_domains[:1000]

    # Client limits settings - reduced for better performance
    limits = httpx.Limits(
        max_keepalive_connections=MAX_CONNECTIONS // 2,
        max_connections=MAX_CONNECTIONS,
        keepalive_expiry=CONNECTION_KEEP_ALIVE
    )

    # Asinxron HTTP klient yaratish - with reduced timeouts
    timeout_config = httpx.Timeout(REQUEST_TIMEOUT, connect=1.5)

    # Set up connection pool with relaxed settings
    transport = httpx.AsyncHTTPTransport(
        limits=limits,
        retries=0,  # We handle our own retries
        http2=False  # Disable HTTP/2 for better compatibility
    )

    async with httpx.AsyncClient(
            timeout=timeout_config,
            transport=transport,
            follow_redirects=True,
            http2=False  # Disable HTTP/2 for reliability
    ) as client:
        # Optimize domain grouping by TLD with smaller batches
        batches = sort_domains_by_tld(unique_domains)
        adjusted_batch_size = min(batch_size, MAX_BATCH_SIZE)

        # Re-batch into smaller groups if needed
        if adjusted_batch_size < batch_size:
            new_batches = []
            for batch in batches:
                for i in range(0, len(batch), adjusted_batch_size):
                    new_batches.append(batch[i:i + adjusted_batch_size])
            batches = new_batches

        logger.info(f"Processing {len(batches)} optimized batches (max {adjusted_batch_size} domains per batch)")

        # Process batches with stricter concurrency control
        semaphore = asyncio.Semaphore(3)  # Limit concurrent batches

        async def process_batch_with_limits(batch):
            async with semaphore:
                try:
                    results = await process_batch(client, batch)
                    # Track successful domain processing
                    _domains_processed.extend(results)
                    return results
                except Exception as e:
                    logger.error(f"Batch processing error: {str(e)}")
                    # Return basic error results for the batch
                    error_results = [{
                        "domain": domain,
                        "status": "Need to Check",
                        "status_code": None,
                        "page_type": "Error",
                        "title": "Batch processing error"
                    } for domain in batch]
                    _domains_processed.extend(error_results)
                    return error_results

        # Process batches with rate limiting
        for i in range(0, len(batches), 3):  # Process 3 batches at a time
            batch_group = batches[i:i + 3]
            batch_tasks = [process_batch_with_limits(batch) for batch in batch_group]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Handle results
            for batch_result in batch_results:
                if isinstance(batch_result, Exception):
                    logger.error(f"Failed batch: {str(batch_result)}")
                    continue
                all_results.extend(batch_result)

            # Rate limiting pause between batch groups
            if i + 3 < len(batches):
                await asyncio.sleep(0.5)  # Short pause between batch groups

    logger.info(f"Completed checking {len(all_results)} domains")
    return all_results