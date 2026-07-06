import os
import sys
from datetime import datetime
import asyncio
import asyncpg
from playwright.async_api import async_playwright, Playwright

# Database connection parameters
db_params = {
    'host': 'host.docker.internal',
    'port': 5432,
    'user': 'postgres',
    'password': 'password',
    'database': 'stocks',
    'min_size': 5,
    'max_size': 20  # Adjust based on your database's capacity
}

# Function to connect to the database and fetch news to process
async def get_news_to_process(pool):
    async with pool.acquire() as conn:
        try:
            # Query to fetch news where detail is empty
            query = """
            SELECT stock_code, date, url 
            FROM stock_news 
            WHERE detail = '' AND url != 'https://finance.yahoo.com/news/';
            """
            rows = await conn.fetch(query)
            return rows
        except Exception as e:
            print(f"Error fetching news to process: {e}")
            return []

# Function to update the database with the fetched details
async def update_news_in_database(pool, stock_code, date, url, detail):
    async with pool.acquire() as conn:
        try:
            query = """
            UPDATE stock_news
            SET detail = $1
            WHERE stock_code = $2 AND date = $3 AND url = $4;
            """
            await conn.execute(query, detail, stock_code, date, url)
            print(f"Updated stock: {stock_code}, URL: {url}, date: {date}")
        except Exception as e:
            print(f"Error updating the database for URL {url}: {e}")

# Function to process a single URL
async def process_url(playwright: Playwright, url, browser):
    page = None
    try:
        page = await browser.new_page()
        print(f"Processing URL: {url}")
        await page.goto(url, timeout=30000)
        await page.wait_for_selector('div.body', timeout=5000)

        story_button = await page.query_selector('button:has-text("Story continues")')
        if story_button:
            await story_button.click()

        # Extract the article text
        article_text = await page.evaluate('''() => {
            const contentDiv = document.querySelector('div.body');  
            return contentDiv ? contentDiv.innerText : 'No content found';
        }''')
        return article_text
    except Exception as e:
        print(f"Error processing URL {url}: {e}")
        return ""
    finally:
        if page:
            await page.close()

# Main function to process news concurrently
async def run(playwright: Playwright, pool):
    news_to_process = await get_news_to_process(pool)

    if not news_to_process:
        print("No news to process.")
        return

    print(f"Found {len(news_to_process)} news entries to process.")

    semaphore = asyncio.Semaphore(4)  # Limit to 12 concurrent tasks
    browser = await playwright.chromium.launch(headless=True)

    async def process_news(news):
        async with semaphore:
            stock_code = news['stock_code']
            date = news['date']
            url = news['url']

            print(f"Processing stock: {stock_code}, URL: {url}, date: {date}")
            article_text = await process_url(playwright, url, browser)

            # Update the database with the fetched details
            await update_news_in_database(pool, stock_code, date, url, article_text)

    # Process news concurrently with a limit
    await asyncio.gather(*(process_news(news) for news in news_to_process))
    await browser.close()

# Entry point of the script
async def main():
    pool = await asyncpg.create_pool(**db_params)
    async with async_playwright() as playwright:
        await run(playwright, pool)
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())