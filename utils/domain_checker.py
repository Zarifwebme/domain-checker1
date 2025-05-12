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
        urls = [f"https://{domain}", f"http://{domain}"]
        for url in urls:
            try:
                response = await client.get(url, timeout=10, follow_redirects=True)
                result["status_code"] = response.status_code
                result["status"] = "Working" if response.status_code < 400 else "Not Working"

                # Only analyze content for successful responses
                if response.status_code >= 400:
                    result["page_type"] = "Error Page"
                    result["title"] = "Error"
                    break

                # Check if response is HTML
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    result["page_type"] = "Non-HTML Content"
                    result["title"] = "Non-HTML"
                    break

                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract title
                title_tag = soup.title
                if title_tag and title_tag.string:
                    title = title_tag.string.strip()
                    # Limit title length to 255 chars to avoid Excel issues
                    result["title"] = title[:255] if title else "No Title"
                else:
                    result["title"] = "No Title"

                # Page type detection
                login_score = 0
                login_indicators = [
                    r'\b(login|signin|sign in|log in|sign-in|auth|authenticate)\b',
                    r'\b(username|password|email)\b'
                ]

                # Check for forms with password inputs
                forms = soup.find_all('form')
                has_password_input = any(
                    any(input_.get('type') == 'password' for input_ in form.find_all('input'))
                    for form in forms
                )
                if has_password_input:
                    login_score += 2  # High confidence for password input

                # Check for login-related keywords in HTML
                text_content = soup.get_text().lower()
                for indicator in login_indicators:
                    if re.search(indicator, text_content, re.IGNORECASE):
                        login_score += 1

                # Check for login-related attributes in forms
                for form in forms:
                    if any(
                            indicator in (form.get(attr, '').lower() for attr in ['action', 'id', 'class'])
                            for indicator in ['login', 'signin', 'sign-in']
                    ):
                        login_score += 1

                # Determine page type based on score
                result["page_type"] = "Login Page" if login_score >= 2 else "Functional Page"

                break  # Stop if we get a valid response

            except httpx.HTTPStatusError as e:
                result["status_code"] = e.response.status_code
                result["status"] = "Not Working"
                result["page_type"] = "Error Page"
                result["title"] = "Error"
            except (httpx.RequestError, httpx.TimeoutException):
                continue

    except Exception as e:
        logger.error(f"Error checking {domain}: {str(e)}")
        result["page_type"] = "Error"
        result["title"] = "Error"

    return result


async def check_domains(domains):
    async with httpx.AsyncClient() as client:
        tasks = [check_domain(client, domain) for domain in domains]
        return await asyncio.gather(*tasks, return_exceptions=True)