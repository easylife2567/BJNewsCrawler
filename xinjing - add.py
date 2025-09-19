from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import os
import re

# 创建一个哈希表
hash_table = {"key1":1,"key2":1,"key3":1}


def get_date_urls(url):
    # 配置 Chrome 选项
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无头模式，不显示浏览器窗口
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    # 设置日志级别为 ERROR，忽略 INFO 和 WARNING 级别的日志
    chrome_options.add_argument('--log-level=3')  # 1=WARNING, 2=INFO, 3=FINE

    # 创建 Chrome 浏览器实例
    browser = webdriver.Chrome(options=chrome_options)

    try:
        # 打开网页
        browser.get(url)

        # 显式等待，等待日历组件加载
        try:
            WebDriverWait(browser, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.cal-dates.clearfix'))
            )
            #print("成功加载 .cal-dates.clearfix 元素！")
        except Exception as e:
            print(f"等待 .cal-dates.clearfix 元素超时: {e}")
            return []

        # 定位所有 .cal-date.cal-with-date 元素
        date_elements = browser.find_elements(By.CSS_SELECTOR, '.cal-date.cal-with-date')

        date_urls = []  # 用于存储每个日期页的链接

        for date_element in date_elements:
            try:
                # 获取 <a> 标签
                a_tag = date_element.find_element(By.TAG_NAME, 'a')
                date_num=a_tag.text
                if date_num in hash_table.keys():
                    continue
                else:
                    hash_table[date_num]=1
                href = a_tag.get_attribute('href')

                if href == 'javascript:;':
                    # 模拟点击事件
                    browser.execute_script("arguments[0].click();", a_tag)
                    time.sleep(1)  # 等待页面跳转

                    # 获取当前页面的 URL
                    current_url = browser.current_url
                    print(f"找到有效链接: {current_url}")
                    date_urls.append(current_url)
                else:
                    print(f"无效链接: {href}，跳过...")
                break
            except Exception as e:
                #print(f"处理日期元素时出错: {e}")
                continue

        return date_urls

    except Exception as e:
        print(f"获取网页内容失败: {e}")
        return []
    finally:
        # 关闭浏览器
        browser.quit()

def get_html_with_selenium(url):
    # 配置 Chrome 选项
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无头模式，不显示浏览器窗口
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    # 设置日志级别为 ERROR，忽略 INFO 和 WARNING 级别的日志
    chrome_options.add_argument('--log-level=3')  # 1=WARNING, 2=INFO, 3=FINE

    # 创建 Chrome 浏览器实例
    browser = webdriver.Chrome(options=chrome_options)

    try:
        # 打开网页
        browser.get(url)

        # 显式等待，等待 article-detail 元素出现
        try:
            WebDriverWait(browser,10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.article-detail'))
            )
        except Exception as e:
            print(f"等待元素超时: {e}")

        # 等待页面加载（可根据实际情况调整等待时间）
        time.sleep(5)

        # 获取网页源代码
        html_content = browser.page_source
        return html_content
    except Exception as e:
        print(f"获取网页内容失败: {e}")
        return None
    finally:
        # 关闭浏览器
        browser.quit()

def extract_hrefs(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = soup.select('.article-content ul li a')
    hrefs = []
    for link in links:
        href = link.get('href')
        if href:
            hrefs.append(href)
    return hrefs

def extract_title_and_subtitle(html_content):
    if html_content:
        soup = BeautifulSoup(html_content, 'html.parser')
        # 尝试更灵活的选择器
        article_detail = soup.find(lambda tag: tag.name == 'div' and 'article-detail' in tag.get('class', []))
        if article_detail:
            title_box = article_detail.find('div', class_='title-box')
            if title_box:
                h1_tag = title_box.find('h1')
                h3_tag = title_box.find('h3')
                h4_tag = title_box.find('h4')

                title = h1_tag.text.strip() if h1_tag else "未找到标题"
                content_parts = []
                if h3_tag:
                    content_parts.append(h3_tag.text.strip())
                if h4_tag:
                    content_parts.append(h4_tag.text.strip())
                content = ' '.join(content_parts) if content_parts else "未找到内容"
                return title, content
    return "未找到标题", "未找到内容"

def save_article(title, content, output_dir, year, mon, day,counter):
    # 处理标题中的非法字符
    valid_title = re.sub(r'[\\/*?:"<>|]', '', title)
    # 构建存储路径，格式为 新京/2025-01/27
    month_dir = os.path.join(output_dir, f"{year}-{mon:02d}")
    date_dir = os.path.join(month_dir, f"{day:02d}")
    os.makedirs(date_dir, exist_ok=True)
    file_name = f"{year}{mon:02d}{day:02d}_{counter:02d}_{valid_title}.txt"
    file_path = os.path.join(date_dir, file_name)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(f"标题: {title}\n")
        f.write(f"内容: {content}\n")
    print(f"文章已保存到: {file_path}")


# 定义一个函数来处理每个链接
def process_url(href, output_dir):
    # 使用正则表达式提取日期部分
    date_pattern = r'(\d{4})/(\d{8})'
    match = re.search(date_pattern, href)

    if match:
        year = int(match.group(1))
        date_part = match.group(2)
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        date_key = f"{year}{month:02d}{day:02d}"

        # 初始化或递增当天的计数器
        date_counter = {}
        if date_key not in date_counter:
            date_counter[date_key] = 1
        counter = date_counter[date_key]
        date_counter[date_key] += 1

        # 构造基础路径
        base_path = f"http://epaper.bjnews.com.cn/html/{year}/{year}{month:02d}{day:02d}/{year}{month:02d}{day:02d}_A01"

        # 获取网页内容
        html = get_html_with_selenium(href)
        if html:
            hrefs = extract_hrefs(html)
            # 遍历每个 href，拼接完整的 URL
            for href in hrefs:
                full_url = f"{base_path}/{href}"
                print(f"正在获取 {full_url} 的内容...")
                day_home_html = get_html_with_selenium(full_url)
                if day_home_html:
                    title, content = extract_title_and_subtitle(day_home_html)
                    save_article(title, content, output_dir, year, month, day, counter)
                    counter += 1
    else:
        print("未找到日期信息")


# 定义一个函数来收集所有 URL
def collect_date_urls(url):
    date_urls_list = []
    seen_urls = set()  # 用于存储已经见过的 URL
    while True:
        # 假设 get_date_urls(url) 返回的是一个包含 URL 的列表
        date_url = get_date_urls(url)
        #print(date_url)

        # 提取列表中的第一个元素（假设列表中只有一个 URL）
        if isinstance(date_url, list) and len(date_url) > 0:
            date_url_str = date_url[0]
        else:
            date_url_str = date_url  # 如果不是列表，直接使用

        # 去除多余的引号和括号，提取纯净的 URL
        clean_url = (
            date_url_str.replace("'", "")
            .replace("[", "")
            .replace("]", "")
            .replace("<url>", "")
            .replace("</url>", "")
            .strip()
        )

        # 检查是否已经见过这个 URL
        if clean_url in seen_urls:
            print("检测到重复链接，停止收集 URL")
            break

        # 将新的 URL 添加到集合和列表中
        seen_urls.add(clean_url)
        date_urls_list.append(clean_url)

        # 添加最大循环次数限制，防止无限循环
        if len(date_urls_list) >= 31:  # 最多收集 31 个 URL
            print("达到最大 URL 数量，停止收集")
            break

    return date_urls_list

# 主函数
if __name__ == '__main__':
    url = 'http://epaper.bjnews.com.cn/html/2025/20250401/20250401_A01/20250401_A01_3011.html'  # 新京报首页 URL
    output_dir = r"D:\CENTER\Data\2025\报纸\报纸源文本\新京"

# 收集所有 URL
    date_urls_list = collect_date_urls(url)

# 循环结束后，输出所有 URL
    print("收集到的 URL 列表:")
    for idx, url_del in enumerate(date_urls_list, start=1):
        print(f"{idx}: {url_del}")

# 遍历每个链接，获取内容
    for href in date_urls_list:
        process_url(href, output_dir)
