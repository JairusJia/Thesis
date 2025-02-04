import json
import time
import random
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Thread-safe lock for JSON file writing
json_lock = threading.Lock()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

def init_browser():
    """Initialize Selenium WebDriver with optimized settings."""
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--headless=new")  
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")  
    options.add_argument("--log-level=3")  
    options.add_argument("--start-maximized")  
    options.add_experimental_option("excludeSwitches", ["enable-automation"])  
    options.add_experimental_option("useAutomationExtension", False)  

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), 
                              options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', \
                          {get: () => undefined})")

    return driver

def get_guba_links(url, max_pages, driver):
    """Scrape multiple pages of post links."""
    all_links = []
    page_count = 0

    while url and page_count < max_pages:

        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "listbody"))
            )
        except Exception as e:
            print(f"⚠️ Page load timeout, skipping: {e}")
            break

        soup = BeautifulSoup(driver.page_source, "lxml")

        for tr in soup.find_all("tr", class_="listitem"):
            a_tag = tr.find("a", href=True)
            if a_tag and a_tag["href"].startswith("/news"):
                full_url = f"https://guba.eastmoney.com" + a_tag['href']
                all_links.append(full_url)

        next_page = soup.find("a", class_="nextp")
        if next_page and "href" in next_page.attrs:
            url = next_page["href"]
        else:
            print("✅ No more pages, stopping scrape.")
            break

        page_count += 1
        time.sleep(random.uniform(1, 3))  # Avoid being blocked

    print(f"✅ Found {len(all_links)} post links.")
    return all_links

def scrape_post_details(url, driver):
    """Extract post details (time, content, comments)."""
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "newstext"))
        )

        soup = BeautifulSoup(driver.page_source, "lxml")
        post_data = {}

        # Extract post time
        time_tag = soup.find("div", class_="time")
        post_time = time_tag.text.strip() if time_tag else "Unknown"

        # Extract post content
        content_tag = soup.find("div", class_="newstext")
        post_content = content_tag.text.strip() if content_tag else "No content"

        post_data[post_time] = post_content

        # Extract comments
        reply_items = soup.find_all("div", class_="l1items1")
        for reply in reply_items:
            comment_time_tag = reply.find("span", class_="pubtime")
            comment_text_tag = reply.find("div", class_="short_text")

            comment_time = comment_time_tag.text.strip() if \
                comment_time_tag else "Unknown"
            comment_text = comment_text_tag.text.strip() if \
                comment_text_tag else "No comment"

            post_data[comment_time] = comment_text

        return post_data

    except Exception as e:
        print(f"Failed to scrape post: {url}, Error: {e}")
        return None

def save_to_json(post_data, file_path="guba_posts_3127.json"):
    """Save scraped data to JSON (Thread-Safe)."""
    with json_lock:
        if post_data:
            try:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                else:
                    existing_data = {}

                existing_data.update(post_data)

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"Failed to write JSON: {e}")

thread_local = threading.local()

def get_driver():
    """Ensure each thread gets its own WebDriver."""
    if not hasattr(thread_local, "driver"):
        thread_local.driver = init_browser()  
    return thread_local.driver

def scrape_with_thread_driver(url):
    """Each thread reuses its WebDriver for multiple URLs."""
    driver = get_driver()  
    post_data = scrape_post_details(url, driver)
    return post_data

def scrape_all_posts(start_url, max_pages, max_threads=5):
    """Parallel scraping with one WebDriver per thread (not per URL)."""
    driver = init_browser()
    post_links = get_guba_links(start_url, max_pages, driver)
    driver.quit()  

    with ThreadPoolExecutor(max_threads) as executor:
        results = executor.map(scrape_with_thread_driver, post_links)

        for post_data in results:
            if post_data:
                save_to_json(post_data)

    for thread in threading.enumerate():
        if hasattr(thread_local, "driver"):
            thread_local.driver.quit()
            del thread_local.driver  


if __name__ == "__main__":
    start_url = "https://guba.eastmoney.com/list,zssh000001_3127.html"

    while True:
        try:
            max_pages = int(input("Enter the number of pages \
                                  to scrape (e.g., 5): "))
            if max_pages > 0:
                break
            else:
                print("Please enter an integer greater than 0.")
        except ValueError:
            print("Please enter a valid number.")

    scrape_all_posts(start_url, max_pages, max_threads=5)
