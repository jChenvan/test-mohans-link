import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_site(url: str) -> str | None:
    """
    Fetches the main article text of a URL using Playwright and BeautifulSoup.

    Args:
        url: The URL of the website to fetch.

    Returns:
        A string containing the main text content of the page, or None on error.
    """
    print(f"fetching {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Strategy: Find the main content container
            # First, try to find a <main> tag. If not, look for an <article> tag.
            # You can add more fallbacks based on common website structures,
            # e.g., soup.find('div', id='content')
            main_content = soup.find('main')
            if not main_content:
                main_content = soup.find('article')

            # If a main content area is found, extract text from it.
            if main_content:
                
                # (Optional) Remove unwanted elements like scripts or ads from within the main content
                for element in main_content(['script', 'style', 'aside']): # type: ignore
                    element.decompose()

                print(f"SUCCESSFUL FETCH: {url}")
                # .get_text() with separator and strip for cleaner output
                return main_content.get_text(separator='\n', strip=True)
            else:
                # Fallback if no specific container is found (less reliable)
                print("WARNING: No main content container found. Falling back to body.")
                if soup.body:
                    body_text = soup.body.get_text(separator='\n', strip=True)
                    print(f"SUCCESSFUL FETCH: {url}")
                    return body_text
            
        except Exception as e:
            print(f"FAILED FETCH: {url}")
            print(f"An error occurred: {e}")
            return None
            
        finally:
            await browser.close()

# Example usage:
# asyncio.run(fetch_site("https://www.example.com"))