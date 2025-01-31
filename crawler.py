import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def init_browser():
    """初始化 Selenium 浏览器"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # 使用新 headless 模式
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
    AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), 
                                options=options)
    return driver

def get_guba_links(url, max_pages=5):
    """
    爬取东方财富股吧多页帖子链接
    :param url: 起始页网址
    :param max_pages: 最大翻页数
    :return: 所有爬取的帖子链接
    """
    driver = init_browser()
    all_links = []
    page_count = 0

    while url and page_count < max_pages:  # 限制最大页数，防止无限翻页
        driver.get(url)

        try:
            # 确保帖子列表加载完成
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "listbody"))
            )
        except:
            print(f"网页加载失败: {url}")
            break

        # 解析 HTML
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # 1️⃣ 获取帖子链接
        tbody = soup.find("tbody", class_="listbody")
        if tbody:
            for tr in tbody.find_all("tr", class_="listitem"):
                a_tag = tr.find("a", href=True)
                if a_tag and a_tag["href"].startswith("/news"):
                    full_url = "https://guba.eastmoney.com" + a_tag["href"]
                    all_links.append(full_url)

        # 2️⃣ 查找下一页按钮
        next_page = soup.find("a", class_="next")
        if next_page and "href" in next_page.attrs:
            url = "https://guba.eastmoney.com" + next_page["href"]  # 构造下一页 URL
        else:
            url = None  # 没有下一页，停止爬取

        print(f"已爬取第 {page_count + 1} 页，共 {len(all_links)} 个帖子")
        page_count += 1

    driver.quit()
    return all_links

def scrape_post_details(url, driver):
    """
    访问帖子页面，提取正文时间、正文内容、评论
    :param url: 帖子 URL
    :param driver: Selenium WebDriver 实例
    :return: 包含正文时间、正文内容、评论的字典
    """
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "newstext"))
        )
    except:
        print(f"帖子加载失败: {url}")
        return None

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # **创建一个字典，存储正文和评论**
    post_data = {}

    # 1️⃣ 获取正文时间
    time_tag = soup.find("div", class_="time")
    post_time = time_tag.text.strip() if time_tag else "未知"

    # 2️⃣ 获取正文内容
    content_tag = soup.find("div", class_="newstext")
    post_content = content_tag.text.strip() if content_tag else "无正文"

    # **把正文加入字典**
    post_data[post_time] = post_content

    # 3️⃣ 获取评论（按照 `comment_time: comment_text` 格式存入字典）
    reply_items = soup.find_all("div", class_="reply_item cl")
    for reply in reply_items:
        comment_time_tag = reply.find("span", class_="pubtime")
        comment_text_tag = reply.find("span", class_="reply_title_span")

        comment_time = comment_time_tag.text.strip() if comment_time_tag else "未知"
        comment_text = comment_text_tag.text.strip() if comment_text_tag else "无评论"

        # **把评论也存入字典**
        post_data[comment_time] = comment_text

    return post_data

def scrape_all_posts(start_url, max_pages=5):
    """
    爬取多个帖子及其内容，并保存到 JSON 文件
    :param start_url: 股吧起始页
    :param max_pages: 爬取的最大页数
    """
    driver = init_browser()
    post_links = get_guba_links(start_url, max_pages)

    all_data = []
    for i, post_url in enumerate(post_links):  # **不限制帖子数量**
        print(f"正在爬取帖子 {i + 1}/{len(post_links)}: {post_url}")
        post_data = scrape_post_details(post_url, driver)
        if post_data:
            all_data.append(post_data)
        time.sleep(2)  # 避免请求过快

    driver.quit()

    # 保存为 JSON 文件
    with open("guba_posts.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)

    print(f"爬取完成，数据已保存到 guba_posts.json")

# 运行爬虫
if __name__ == "__main__":
    start_url = "https://guba.eastmoney.com/list,zssh000001.html"
    scrape_all_posts(start_url, max_pages=2)
