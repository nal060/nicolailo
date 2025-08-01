import asyncio
import os
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

async def main():
    # URL of the page
    url = "https://www.faa.gov/air_traffic/flight_info/aeronav/Aero_Data/NFDD/"

    # Where you want to save the PDFs
    download_folder = "../../data/faa_pdfs"
    os.makedirs(download_folder, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # show the browser
        page = await browser.new_page()
        await page.goto(url)

        print("Page loaded. Please interact with it now (click any buttons you need).")
        input("Press Enter here when you are ready to start downloading PDFs...")

        # Get the current page HTML after manual interaction
        content = await page.content()

        # Use BeautifulSoup to parse it
        soup = BeautifulSoup(content, "html.parser")

        # Find all PDF links
        pdf_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.lower().endswith(".pdf"):
                # Handle relative URLs
                if href.startswith("/"):
                    full_url = "https://www.faa.gov" + href
                else:
                    full_url = href
                pdf_links.append(full_url)

        print(f"Found {len(pdf_links)} PDF files. Starting download...")

        # Download PDFs
        for pdf_url in pdf_links:
            filename = os.path.join(download_folder, os.path.basename(pdf_url))
            print(f"Downloading {pdf_url}...")
            response = requests.get(pdf_url)
            response.raise_for_status()
            with open(filename, "wb") as f:
                f.write(response.content)

        print("All PDFs downloaded.")
        await browser.close()

# Run the async main
if __name__ == "__main__":
    asyncio.run(main())