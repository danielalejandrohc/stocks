import os
import sys
import re
from datetime import datetime, timezone, timedelta
import asyncio
import json
from playwright.async_api import async_playwright, Playwright
from bs4 import BeautifulSoup
import logging
import multiprocessing

# Configure logging for performance tracking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_directory_structure(stock_code):
    # Get the current date in yyyy-MM-dd format in GMT-6 (Central Standard Time)
    tz_gmt_minus_6 = timezone(timedelta(hours=-6))
    current_date = datetime.now(tz_gmt_minus_6).strftime('%Y-%m-%d')
    logging.info(f"Creating directory structure for stock code: {stock_code} on date: {current_date}")

    # Create the folder with the current date
    date_folder = os.path.join("/app/local/stocks/scrapper/news", current_date)
    os.makedirs(date_folder, exist_ok=True)

    # Create the stock code folder in uppercase
    stock_code_folder = os.path.join(date_folder, stock_code.upper())
    os.makedirs(stock_code_folder, exist_ok=True)

    # Create the "head" and "detail" folders
    head_folder = os.path.join(stock_code_folder, "head")
    detail_folder = os.path.join(stock_code_folder, "detail")
    os.makedirs(head_folder, exist_ok=True)
    os.makedirs(detail_folder, exist_ok=True)

    logging.info(f"Created directory structure: {head_folder}")
    return stock_code_folder

async def pull_news(playwright: Playwright, stock_code: str, directory: str) -> str:
    url_main = f"https://finance.yahoo.com/quote/{stock_code}/news/"
    browser = await playwright.chromium.launch(headless=True)
    try:
        page = await browser.new_page()
        logging.info(f"pull_news@page created for {url_main}. Loading...")
        
        # Navigate with faster loading (domcontentloaded)
        await page.goto(url_main, wait_until="domcontentloaded", timeout=60000)
        logging.info(f"pull_news@page loaded: {url_main}")
        
        # Get HTML content
        html_content = await page.content()
        
        # Write HTML to file
        destination_html = os.path.join(directory, "head", "content.html")
        with open(destination_html, "w", encoding="utf-8") as file:
            file.write(html_content)
        
        # Save screenshot
        screenshot_path = os.path.join(directory, "head", "screenshot.png")
        await page.screenshot(path=screenshot_path)
        logging.info(f"pull_news@screenshot saved to {screenshot_path}")
        
        return html_content
    finally:
        await browser.close()

def processHTML(html_content: str, directory: str) -> list:
    data = []
    # Parse HTML with lxml (fastest parser)
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Match any Yahoo Finance article URL regardless of CSS class changes.
    # Covers: /news/<slug>.html, /m/<uuid>/<slug>.html, /markets/*/articles/<slug>.html
    _article_url = re.compile(
        r'https://finance\.yahoo\.com/(?:news|m|markets/[^/]+/articles)/\S+\.html'
    )
    seen = set()
    for link in soup.find_all("a", href=True):
        href = link['href'].split('?')[0].rstrip('/')  # strip query params and trailing slash
        text = link.text.strip()
        if text and _article_url.match(href) and href not in seen:
            seen.add(href)
            data.append({"url": href, "title": text})
    
    # Write news as JSON
    file_path = os.path.join(directory, "head", "news.json")
    with open(file_path, 'w', encoding="utf-8") as file:
        json.dump(data, file, indent=4)
    
    logging.info(f"processHTML@extracted {len(data)} news links")
    return data

async def process_entry(browser, entry: dict, retries: int = 2) -> dict:
    url = entry['url']
    for attempt in range(retries + 1):
        try:
            page = await browser.new_page()
            try:
                start_time = datetime.now()
                logging.info(f"process_entry@url: {url} (attempt {attempt + 1})")
                
                # Navigate with faster loading
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for article content using the new preferred selector
                await page.wait_for_selector('div[data-testid="article-content-wrapper"], div.caas-body, div.caas-content, article', timeout=20000)
                
                # Click "Story continues" button if present
                story_button = await page.query_selector('button:has-text("Story continues")')
                if story_button:
                    logging.info(f"process_entry@clicking 'Story continues' button for {url}")
                    await story_button.click()
                    await page.wait_for_timeout(1000)  # Reduced delay for faster processing
                
                # Extract article text
                article_text = await page.evaluate('''() => {
                    const selectors = [
                        'div[data-testid="article-content-wrapper"]',
                        'div.caas-body',
                        'div.caas-content',
                        'article'
                    ];
                    for (const selector of selectors) {
                        const contentDiv = document.querySelector(selector);
                        if (contentDiv) {
                            return contentDiv.innerText.trim() || 'No content found';
                        }
                    }
                    return 'No content found';
                }''')
                
                entry['detail'] = article_text
                logging.info(f"process_entry@extracted content for {url}: {article_text[:100]}... (took {(datetime.now() - start_time).total_seconds():.2f}s)")
                return entry
            finally:
                await page.close()
        except Exception as e:
            logging.error(f"process_entry@error with {url} (attempt {attempt + 1}): {str(e)}")
            if attempt == retries:
                entry['detail'] = f'Error processing after {retries + 1} attempts: {str(e)}'
                return entry
            await asyncio.sleep(1)

async def process_batch(browser, batch: list, max_concurrency: int = None) -> list:
    # Dynamically set concurrency based on CPU cores or default to 16
    max_concurrency = max_concurrency or max(16, multiprocessing.cpu_count() * 2)
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def sem_task(entry):
        async with semaphore:
            return await process_entry(browser, entry)
    
    tasks = [sem_task(entry) for entry in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    logging.info(f"process_batch@completed processing {len(batch)} articles")
    return results

async def processData(playwright: Playwright, data: list, directory: str) -> list:
    # Use a single browser instance
    browser = await playwright.chromium.launch(headless=True)
    try:
        # Process data in batches
        batch_size = 32  # Increased batch size for better throughput
        results = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_results = await process_batch(browser, batch)
            results.extend([r for r in batch_results if not isinstance(r, Exception)])
        
        # Write results to JSON
        file_path = os.path.join(directory, "detail", "news.json")
        with open(file_path, 'w', encoding="utf-8") as file:
            json.dump(results, file, indent=4)
        
        logging.info(f"processData@saved {len(results)} articles to {file_path}")
        return results
    finally:
        await browser.close()

async def run(playwright: Playwright):
    if len(sys.argv) != 2:
        logging.error("Usage: python scrapper-collector.py <STOCK_CODE>")
        sys.exit(1)

    stock_code = sys.argv[1]
    directory = create_directory_structure(stock_code)
    html_content = await pull_news(playwright, stock_code, directory)
    data = processHTML(html_content, directory)
    data_detailed = await processData(playwright, data, directory)

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

if __name__ == "__main__":
    asyncio.run(main())
