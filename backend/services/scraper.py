from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from ..database.config import get_settings
except ImportError:  # pragma: no cover - supports running from backend/ as main:app
    from database.config import get_settings


class ScraperError(ValueError):
    pass


@dataclass(slots=True)
class ScrapedPage:
    url: str
    domain: str
    title: str | None
    description: str | None
    image_url: str | None
    raw_html: str
    text: str


RECIPE_PAGE_HINTS = (
    "/recipe/",
    "/recipes/",
)
LISTING_PAGE_HINTS = (
    "/recipes/",
    "/meat-and-poultry/",
    "/breakfast-and-brunch/",
    "/main-dishes/",
)
KNOWN_BROWSER_ONLY_DOMAINS = {
    "allrecipes.com",
    "www.allrecipes.com",
}


def collapse_whitespace(content: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in content.splitlines()]
    compact_lines = [line for line in lines if line]
    return "\n".join(compact_lines)


def origin_from_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def build_retrying_session() -> requests.Session:
    settings = get_settings()
    retry = Retry(
        total=settings.scraper_max_retries,
        connect=settings.scraper_max_retries,
        read=settings.scraper_max_retries,
        status=settings.scraper_max_retries,
        backoff_factor=settings.scraper_retry_backoff_seconds,
        status_forcelist=(403, 408, 425, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    # Ignore proxy environment variables so local misconfiguration does not break scraping.
    session.trust_env = False
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def build_navigation_headers(url: str, *, referer: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        **({"Referer": referer} if referer else {}),
    }


def build_header_profiles(url: str) -> list[dict[str, str]]:
    origin = origin_from_url(url)
    return [
        build_navigation_headers(url),
        build_navigation_headers(url, referer=origin),
        build_navigation_headers(url, referer=f"{origin}/"),
    ]


def is_recipe_type(value: object) -> bool:
    if isinstance(value, str):
        return value.lower() == "recipe"
    if isinstance(value, list):
        return any(is_recipe_type(item) for item in value)
    return False


def find_recipe_json_ld(payload: object) -> dict | None:
    if isinstance(payload, dict):
        if is_recipe_type(payload.get("@type")):
            return payload
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                match = find_recipe_json_ld(item)
                if match is not None:
                    return match
        for value in payload.values():
            match = find_recipe_json_ld(value)
            if match is not None:
                return match
    elif isinstance(payload, list):
        for item in payload:
            match = find_recipe_json_ld(item)
            if match is not None:
                return match
    return None


def extract_structured_recipe_text(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_content = script.string or script.get_text(strip=True)
        if not raw_content:
            continue
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            continue

        recipe_payload = find_recipe_json_ld(payload)
        if recipe_payload is not None:
            return json.dumps(recipe_payload, ensure_ascii=False, indent=2)
    return None


def extract_recipe_image(payload: object) -> str | None:
    if isinstance(payload, dict):
        image_value = payload.get("image")
        if isinstance(image_value, str):
            return image_value
        if isinstance(image_value, list):
            for item in image_value:
                candidate = extract_recipe_image({"image": item})
                if candidate:
                    return candidate
        if isinstance(image_value, dict):
            for key in ("url", "@id"):
                if isinstance(image_value.get(key), str):
                    return image_value[key]
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                candidate = extract_recipe_image(item)
                if candidate:
                    return candidate
    elif isinstance(payload, list):
        for item in payload:
            candidate = extract_recipe_image(item)
            if candidate:
                return candidate
    return None


def extract_meta_content(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str | None:
    for attr_name, attr_value in selectors:
        tag = soup.find("meta", attrs={attr_name: attr_value})
        if tag and isinstance(tag.get("content"), str):
            content = tag["content"].strip()
            if content:
                return content
    return None


def is_probably_html(response: requests.Response) -> bool:
    content_type = response.headers.get("Content-Type", "").lower()
    if "html" in content_type or "xml" in content_type:
        return True
    body_start = response.text[:200].lstrip().lower()
    return body_start.startswith("<!doctype html") or body_start.startswith("<html")


def has_usable_scraped_content(text: str, structured_recipe_text: str | None) -> bool:
    if structured_recipe_text:
        return True
    stripped_text = text.strip()
    if not stripped_text:
        return False
    return len(stripped_text) >= 500


def seems_like_listing_page(url: str, title: str | None, structured_recipe_text: str | None) -> bool:
    if structured_recipe_text:
        return False

    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    title_value = (title or "").lower()

    if path.count("/") <= 2:
        return True
    if any(path.endswith(hint.rstrip("/")) for hint in LISTING_PAGE_HINTS):
        return True
    if "recipes" in title_value and "recipe" not in title_value.replace("recipes", "", 1):
        return True
    if re.search(r"/recipes/\d+(?:/[^/]+){0,2}$", path):
        return True
    return False


def should_use_browser_first(url: str) -> bool:
    settings = get_settings()
    if not settings.browser_fallback_enabled:
        return False
    domain = urlparse(url).netloc.lower()
    return settings.browser_first_enabled or domain in KNOWN_BROWSER_ONLY_DOMAINS


def extract_page_content(html: str) -> tuple[str | None, str | None, str | None, str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    structured_soup = BeautifulSoup(html, "html.parser")
    structured_recipe_text = extract_structured_recipe_text(structured_soup)
    recipe_image_url: str | None = None
    for script in structured_soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_content = script.string or script.get_text(strip=True)
        if not raw_content:
            continue
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            continue
        recipe_image_url = extract_recipe_image(payload)
        if recipe_image_url:
            break

    for element in soup(["script", "style", "noscript", "svg", "iframe"]):
        element.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description = extract_meta_content(
        soup,
        ("property", "og:description"),
        ("name", "description"),
        ("name", "twitter:description"),
    )
    image_url = recipe_image_url or extract_meta_content(
        soup,
        ("property", "og:image"),
        ("name", "twitter:image"),
    )
    text = collapse_whitespace(soup.get_text(separator="\n"))
    if structured_recipe_text:
        text = f"STRUCTURED_RECIPE_JSON\n{structured_recipe_text}\n\nPAGE_TEXT\n{text}".strip()
    return title, description, image_url, structured_recipe_text, text


def warm_session(session: requests.Session, url: str) -> None:
    settings = get_settings()
    origin = origin_from_url(url)
    warmup_targets = (origin, f"{origin}/")

    for warmup_url in warmup_targets:
        try:
            session.get(
                warmup_url,
                headers=build_navigation_headers(warmup_url),
                timeout=settings.request_timeout_seconds,
                allow_redirects=True,
            )
            return
        except requests.RequestException:
            continue


def fetch_html(session: requests.Session, url: str) -> requests.Response:
    settings = get_settings()
    last_response: requests.Response | None = None
    last_error: requests.RequestException | None = None

    for headers in build_header_profiles(url):
        try:
            response = session.get(
                url,
                headers=headers,
                timeout=settings.request_timeout_seconds,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            last_error = exc
            continue

        last_response = response
        if response.ok:
            return response
        if response.status_code in {403, 429, 451}:
            continue
        response.raise_for_status()

    if last_response is not None:
        if last_response.status_code in {403, 429, 451}:
            return last_response
        last_response.raise_for_status()
    if last_error is not None:
        raise last_error
    raise ScraperError("No response received from the recipe URL.")


def fetch_html_with_browser(url: str) -> str:
    settings = get_settings()
    try:
        import undetected_chromedriver as uc
    except ImportError:
        uc = None

    if uc is not None:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={settings.user_agent}")
        driver = uc.Chrome(
            options=options,
            headless=True,
            driver_executable_path=settings.selenium_driver_path or None,
            use_subprocess=True,
        )
        try:
            driver.get(url)
            time.sleep(3 + random.random() * 2)
            return driver.page_source
        except Exception as exc:
            raise ScraperError(f"Undetected browser failed: {exc}") from exc
        finally:
            driver.quit()

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise ScraperError(
            "Browser fallback is enabled but Selenium is not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={settings.user_agent}")

    service = ChromeService(executable_path=settings.selenium_driver_path) if settings.selenium_driver_path else None
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        WebDriverWait(driver, settings.request_timeout_seconds).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "script[type='application/ld+json'], h1"))
            )
        except Exception:
            pass
        return driver.page_source
    except Exception as exc:
        raise ScraperError(f"Browser fallback failed: {exc}") from exc
    finally:
        driver.quit()


def scrape_recipe_page(url: str) -> ScrapedPage:
    settings = get_settings()
    last_request_error: requests.RequestException | None = None
    response: requests.Response | None = None

    raw_html = ""
    title: str | None = None
    structured_recipe_text: str | None = None
    text = ""

    if should_use_browser_first(url):
        browser_html = fetch_html_with_browser(url)
        raw_html = browser_html
        title, description, image_url, structured_recipe_text, text = extract_page_content(browser_html)
    else:
        description = None
        image_url = None

    if not has_usable_scraped_content(text, structured_recipe_text):
        session = build_retrying_session()
        try:
            warm_session(session, url)
            response = fetch_html(session, url)
        except requests.RequestException as exc:
            last_request_error = exc
        finally:
            session.close()

        if response is not None and is_probably_html(response):
            raw_html = response.text
            title, description, image_url, structured_recipe_text, text = extract_page_content(response.text)

    should_try_browser = (
        settings.browser_fallback_enabled
        and not has_usable_scraped_content(text, structured_recipe_text)
        and (response is None or response.status_code in {403, 429, 451})
    )
    if should_try_browser:
        browser_html = fetch_html_with_browser(url)
        raw_html = browser_html
        title, description, image_url, structured_recipe_text, text = extract_page_content(browser_html)

    if not has_usable_scraped_content(text, structured_recipe_text):
        if response is not None:
            if response.status_code == 403:
                raise ScraperError(
                    "The source site rejected the request with 403 Forbidden. "
                    "This recipe site is blocking direct scraping from this environment."
                )
            if response.status_code == 429:
                raise ScraperError(
                    "The source site rate-limited the request with 429 Too Many Requests. "
                    "Please wait and try again."
                )
            if response.status_code == 451:
                raise ScraperError(
                    "The source site returned 451 Unavailable For Legal Reasons. "
                    "This page cannot be fetched from this environment."
                )
            raise ScraperError(
                f"Unable to fetch recipe URL: source returned {response.status_code} without readable content."
            )
        raise ScraperError(f"Unable to fetch recipe URL: {last_request_error or 'no readable content available.'}")

    if seems_like_listing_page(url, title, structured_recipe_text):
        raise ScraperError(
            "The provided URL looks like a recipe listing page, not a single recipe. "
            "Please paste a direct recipe URL such as an individual dish page."
        )

    if not text:
        raise ScraperError("The page did not contain readable text.")

    domain = urlparse(url).netloc
    return ScrapedPage(
        url=url,
        domain=domain,
        title=title,
        description=description,
        image_url=image_url,
        raw_html=raw_html,
        text=text,
    )
