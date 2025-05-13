import httpx
import asyncio
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_domain(client, domain):
    result = {
        "domain": domain,
        "status": "Not Working",
        "status_code": None,
        "page_type": "Unknown",
        "title": "No Title"
    }

    try:
        url = f"https://{domain}"
        try:
            response = await client.get(url, timeout=3, follow_redirects=True)
            result["status_code"] = response.status_code

            # Status logic
            if 200 <= response.status_code < 400:
                result["status"] = "Working"
            elif response.status_code in (429, 503):
                result["status"] = "Need to Check"
            else:
                result["status"] = "Not Working"

            # Skip parsing for non-200 responses
            if response.status_code != 200:
                result["page_type"] = "Error"
                result["title"] = "Error"
                return result

            # Check if response is HTML
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                result["page_type"] = "Non-HTML"
                result["title"] = "Non-HTML"
                return result

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title_tag = soup.title
            if title_tag and title_tag.string:
                title = title_tag.string.strip()
                result["title"] = title[:255] if title else "No Title"
            else:
                result["title"] = "No Title"

            # Page type detection (Internal vs External)
            login_score = 0
            content_score = 0
            login_indicators = [
                r'\b(login|signin|sign in|log in|sign-in|auth|authenticate|register|kirish|ro\'yxatdan o\'tish)\b',
                r'\b(username|password|email|foydalanuvchi|parol)\b'
            ]
            content_indicators = ['div', 'p', 'article', 'section', 'ul', 'table']

            # Check for forms with password inputs (strong Internal indicator)
            forms = soup.find_all('form')
            has_password_input = any(
                any(input_.get('type') == 'password' for input_ in form.find_all('input'))
                for form in forms
            )
            if has_password_input:
                login_score += 3

            # Check for login-related keywords and form attributes
            try:
                text_content = soup.get_text(separator=' ', strip=True)
                if not isinstance(text_content, str):
                    text_content = ' '.join(str(item) for item in text_content) if isinstance(text_content,
                                                                                              (list, tuple)) else str(
                        text_content)
                text_content = text_content.lower()
                text_length = len(text_content)

                for indicator in login_indicators:
                    if re.search(indicator, text_content, re.IGNORECASE):
                        login_score += 1

                for form in forms:
                    for attr in ['action', 'id', 'class']:
                        attr_value = form.get(attr, '')
                        if isinstance(attr_value, list):
                            attr_value = ' '.join(str(v) for v in attr_value)
                        if any(indicator in attr_value.lower() for indicator in
                               ['login', 'signin', 'sign-in', 'register', 'kirish']):
                            login_score += 1

                # Assess content for External indicators
                for tag in content_indicators:
                    elements = soup.find_all(tag)
                    if elements:
                        content_score += len(elements)

                # If page has minimal text, likely Internal
                if text_length < 500:
                    login_score += 2

                # Determine page type
                if login_score >= 4 and content_score < 10:
                    result["page_type"] = "Internal"
                elif content_score >= 5 or login_score < 3:
                    result["page_type"] = "External"
                else:
                    result["page_type"] = "External" if content_score > login_score else "Internal"

            except (AttributeError, TypeError) as e:
                logger.error(f"Error parsing text for {domain}: {str(e)}")
                result["page_type"] = "Error"
                result["title"] = "Error"

        except httpx.HTTPStatusError as e:
            result["status_code"] = e.response.status_code
            result["status"] = "Need to Check" if result["status_code"] in (429, 503) else "Not Working"
            result["page_type"] = "Error"
            result["title"] = "Error"
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Failed to reach {domain}: {str(e)}")
            result["status"] = "Not Working"
            result["page_type"] = "Error"
            result["title"] = "Error"

    except Exception as e:
        logger.error(f"Unexpected error checking {domain}: {str(e)}")
        result["status"] = "Not Working"
        result["page_type"] = "Error"
        result["title"] = "Error"

    return result


async def check_domains(domains, batch_size=5):
    results = []
    async with httpx.AsyncClient(timeout=3.0) as client:
        for i in range(0, len(domains), batch_size):
            batch = domains[i:i + batch_size]
            logger.info(f"Processing batch of {len(batch)} domains")
            tasks = [check_domain(client, domain) for domain in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend([r for r in batch_results if not isinstance(r, Exception)])
    return results