import os
import sys
from datetime import datetime
import asyncio
import json
from playwright.async_api import async_playwright, Playwright
from ollama import AsyncClient
from bs4 import BeautifulSoup

def create_directory_structure(stock_code):
    # Get the current date in yyyy-MM-dd format
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Create the folder with the current date
    date_folder = os.path.join("/app/local/stocks/scrapper/news", current_date)
    os.makedirs(date_folder, exist_ok=True)

    # Create the stock code folder in uppercase
    stock_code_folder = os.path.join(date_folder, stock_code.upper())
    os.makedirs(stock_code_folder, exist_ok=True)

    # Create the "head" folder inside the stock code folder
    head_folder = os.path.join(stock_code_folder, 'head')
    os.makedirs(head_folder, exist_ok=True)

    print(f"Created directory structure: {head_folder}")
    return head_folder

async def pull_news(playwright, stock_code, directory):
    urlMain = f"https://finance.yahoo.com/news/why-airbnb-abnb-2-since-153106384.html"
    chromium = playwright.chromium  # or "firefox" or "webkit".
    print("chromium created")
    browser = await chromium.launch(headless=True)
    print("chromium.launch() executed")
    page = await browser.new_page()
    print("page created. Starting go to ...")
    
    await page.goto(urlMain, timeout=90000)
    
    await page.wait_for_selector('div.caas-body')  # Adjust the selector if necessary
    await page.click('button:has-text("Story continues")')
    # Extract the article text
    article_text = await page.evaluate('''() => {
        const contentDiv = document.querySelector('div.caas-body');  
        return contentDiv ? contentDiv.innerText : 'No content found';
    }''')

    print(article_text) 
    return ""

async def run(playwright: Playwright):
    if len(sys.argv) != 2:
        print("Usage: python scrapper-collector.py <STOCK_CODE>")
        sys.exit(1)

    stock_code = sys.argv[1]
    #directory = create_directory_structure(stock_code)
    html_content = await pull_news(playwright, stock_code, "")

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

asyncio.run(main())


# ollama env  http://172.17.0.3:11434
