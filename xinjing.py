import os
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bjnews_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    content: str
    date: str
    edition: str


class BJNewsCrawler:
    BASE_URL = 'https://epaper.bjnews.com.cn/'

    def __init__(self, output_dir: str = './bjnews_data'):
        self.output_dir = output_dir
        self.driver = None
        self.wait = None
        self._setup_output_dir()

    def _setup_output_dir(self):
        # 输出目录结构
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"输出目录设置为: {self.output_dir}")

    def _get_chrome_options(self, headless: bool = True) -> Options:
        options = Options()

        # 基础配置
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--log-level=3')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        options.page_load_strategy = 'normal'
        options.add_argument('--window-size=1920,1080')

        if headless:
            options.add_argument('--headless')

        return options

    def _init_driver(self, headless: bool = True):
        # 初始化WebDriver
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

        options = self._get_chrome_options(headless)
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })

        self.driver.implicitly_wait(5)
        logger.info("WebDriver初始化成功")

    def _safe_click(self, element, use_js=False):
        # 安全点击元素
        try:
            if use_js:
                self.driver.execute_script("arguments[0].click();", element)
            else:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)

                try:
                    element.click()
                except ElementClickInterceptedException:
                    self.driver.execute_script("arguments[0].click();", element)
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return False

    def navigate_to_date(self, date_str: str) -> bool:
        # 导航到指定日期
        try:
            self.driver.get(self.BASE_URL)
            time.sleep(3)  # 等待页面加载

            # 解析日期
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])

            logger.info(f"尝试导航到日期: {year}-{month:02d}-{day:02d}")
            calendar_xpath = "/html/body/div[3]/div/div[2]/div/div[2]/div[2]/div[2]/div/div/div[3]/div[2]"

            try:
                # 等待日历加载
                calendar = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, calendar_xpath))
                )

                # 查找所有日期链接
                date_links = calendar.find_elements(By.XPATH, "//*[@id='calendar-1']/div[3]/div[2]/div[2]/span/a")

                for link in date_links:
                    link_text = link.text.strip()
                    if link_text == str(day):
                        # 找到目标日期，点击
                        logger.info(f"找到日期 {day}，点击跳转")
                        self._safe_click(link)
                        time.sleep(2)
                        return True

                # 如果没找到，可能需要切换月份
                logger.warning(f"未找到日期 {day}，尝试其他方法")

                # 尝试直接通过XPath定位
                day_xpath = f"{calendar_xpath}/div[{day + 1}]/span/a"
                try:
                    day_element = self.driver.find_element(By.XPATH, day_xpath)
                    self._safe_click(day_element)
                    time.sleep(2)
                    return True
                except:
                    pass

            except TimeoutException:
                logger.error("日历未加载")

            return False

        except Exception as e:
            logger.error(f"导航到日期失败: {e}")
            return False

    def get_editions_by_click(self) -> List[str]:
        # 通过点击获取当前日期的所有版面
        editions = []

        try:
            edition_list_xpath = "/html/body/div[3]/div/div[2]/div/div[1]/div/div[1]/div[2]/ul"

            edition_ul = self.wait.until(
                EC.presence_of_element_located((By.XPATH, edition_list_xpath))
            )
            edition_links = edition_ul.find_elements(By.TAG_NAME, "a")

            for link in edition_links:
                edition_text = link.text.strip()
                # 提取版面代码 (如 A01, A02,,, AXX)
                edition_match = re.search(r'(A\d{2})', edition_text)
                if edition_match:
                    edition_code = edition_match.group(1)
                    if edition_code not in editions:
                        editions.append(edition_code)
                        logger.debug(f"发现版面: {edition_code}")

            logger.info(f"找到 {len(editions)} 个版面: {', '.join(editions)}")

        except Exception as e:
            logger.error(f"获取版面列表失败: {e}")
            if not editions:
                editions.append("A01")

        return editions

    def click_edition_by_index(self, edition_index: int) -> bool:
        # 通过索引点击版面
        try:
            edition_xpath = f"/html/body/div[3]/div/div[2]/div/div[1]/div/div[1]/div[2]/ul/li[{edition_index + 1}]/a"
            edition_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, edition_xpath))
            )

            edition_text = edition_link.text.strip()
            logger.info(f"点击版面 {edition_index + 1}: {edition_text}")
            self._safe_click(edition_link)
            time.sleep(2)
            return True

        except Exception as e:
            logger.error(f"点击版面失败: {e}")
            return False

    def get_article_links_in_edition(self) -> List[Dict]:
        # 获取当前版面的所有文章链接
        articles = []

        try:
            # 文章列表的XPath
            article_list_xpath = "/html/body/div[3]/div/div[2]/div/div[2]/div[1]/div[2]/ul"
            article_ul = self.wait.until(
                EC.presence_of_element_located((By.XPATH, article_list_xpath))
            )
            # 用li获取所有文章链接
            article_items = article_ul.find_elements(By.XPATH, ".//li")

            for idx, item in enumerate(article_items, 1):
                try:
                    link = item.find_element(By.TAG_NAME, "a")

                    # 获取链接的全部HTML内容，然后处理<br>标签
                    title_html = link.get_attribute('innerHTML')

                    # 将<br>替换为空格
                    title = re.sub(r'<br\s*/?>', ' ', title_html)
                    title = re.sub(r'<[^>]+>', '', title)
                    title = ' '.join(title.split())
                    title = title.strip()

                    if title:
                        articles.append({
                            'index': idx,
                            'title': title,
                            'element': link
                        })
                        logger.debug(f"  文章 {idx}: {title[:30]}...")
                except:
                    continue

            logger.info(f"  找到 {len(articles)} 篇文章")

        except Exception as e:
            logger.error(f"获取文章列表失败: {e}")

        return articles

    def extract_article_content(self) -> Optional[Article]:
        # 提取当前页面的文章内容
        try:
            time.sleep(1)
            # 提取标题
            title = "无标题"
            try:
                title_xpath = "/html/body/div[3]/div/div[3]/div/div[1]"
                title_div = self.driver.find_element(By.XPATH, title_xpath)

                h_tags = title_div.find_elements(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6")
                titles = []
                for h_tag in h_tags:
                    h_text = h_tag.text.strip()
                    if h_text:
                        titles.append(h_text)

                if titles:
                    title = " ".join(titles)
                    logger.debug(f"    提取到 {len(titles)} 个标题: {title[:50]}...")
            except Exception as e:
                logger.debug(f"    标题提取异常: {e}")
                pass

            # 提取正文
            content = ""
            try:
                content_xpath = "/html/body/div[3]/div/div[3]/div/div[3]"
                content_div = self.driver.find_element(By.XPATH, content_xpath)
                p_tags = content_div.find_elements(By.TAG_NAME, "p")
                content = '\n'.join([p.text.strip() for p in p_tags if p.text.strip()])
            except:
                pass

            if not content:
                return None

            return Article(
                title=title,
                content=content,
                date="",
                edition=""
            )

        except Exception as e:
            logger.error(f"提取文章内容失败: {e}")
            return None

    def generate_filename(self, title: str, date_str: str, edition: str, article_num: int) -> str:
        # 生成文件名（不包含路径）
        safe_title = title.replace('\n', ' ').replace('\r', ' ')
        # 移除Windows文件名非法字符
        safe_title = re.sub(r'[\\/*?:"<>|]', '', safe_title)
        # 清理多余空格
        safe_title = ' '.join(safe_title.split())
        safe_title = safe_title[:50]
        # 文件名
        filename = f"{date_str}_{article_num:03d}_{edition}_{safe_title}.txt"
        return filename

    def check_article_exists(self, title: str, date_str: str, edition: str, article_num: int) -> bool:
        #检查文章文件是否已存在
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        month_dir = os.path.join(self.output_dir, f"{year}-{month}")
        day_dir = os.path.join(month_dir, day)

        # 生成预期的文件名
        filename = self.generate_filename(title, date_str, edition, article_num)
        filepath = os.path.join(day_dir, filename)

        # 检查主文件名
        if os.path.exists(filepath):
            return True

        # 检查备用文件名
        safe_filename = f"{date_str}_{article_num:03d}_{edition}_article.txt"
        safe_filepath = os.path.join(day_dir, safe_filename)
        if os.path.exists(safe_filepath):
            return True

        return False

    def crawl_date_with_click(self, date_str: str) -> int:
        # Selenium爬取指定日期的所有文章
        total_articles = 0
        actual_saved = 0  # 实际保存的文章数
        skipped_articles = 0  # 跳过的文章数

        logger.info(f"\n{'=' * 60}")
        logger.info(f"开始爬取日期: {date_str}")
        logger.info(f"{'=' * 60}")

        try:
            # 导航到指定日期
            if not self.navigate_to_date(date_str):
                logger.error(f"无法导航到日期 {date_str}")
                return 0

            # 获取所有版面
            editions = self.get_editions_by_click()

            for edition_idx, edition_code in enumerate(editions):
                logger.info(f"处理版面 {edition_code}...")

                # 如果不是第一个版面，需要点击对应版面
                if edition_idx > 0:
                    if not self.click_edition_by_index(edition_idx):
                        logger.error(f"无法切换到版面 {edition_code}")
                        continue
                else:
                    self.click_edition_by_index(0)

                # 获取该版面的所有文章
                articles = self.get_article_links_in_edition()

                edition_articles = 0
                edition_skipped = 0

                # 处理每篇文章
                for article_info in articles:
                    total_articles += 1

                    # 先检查文章是否已存在
                    if self.check_article_exists(
                            article_info['title'],
                            date_str,
                            edition_code,
                            total_articles
                    ):
                        logger.info(f"  文章已存在，跳过: {article_info['title'][:30]}...")
                        skipped_articles += 1
                        edition_skipped += 1
                        continue

                    try:
                        # 文章不存在，进行爬取
                        logger.debug(f"  点击文章 {article_info['index']}: {article_info['title'][:30]}...")
                        self._safe_click(article_info['element'])
                        time.sleep(1.5)

                        # 提取文章内容
                        article = self.extract_article_content()

                        if article:
                            # 设置日期和版面
                            article.date = date_str
                            article.edition = edition_code

                            # 保存文章
                            saved = self.save_article(article, total_articles)
                            if saved:
                                actual_saved += 1
                                edition_articles += 1
                                logger.debug(f"    成功提取并保存: {article.title[:30]}...")

                        # 返回版面页
                        self.driver.back()
                        time.sleep(1.5)

                        # 等待文章列表加载
                        self.wait.until(
                            EC.presence_of_element_located(
                                (By.XPATH, "/html/body/div[3]/div/div[2]/div/div[2]/div[1]/div[2]/ul")
                            )
                        )

                    except Exception as e:
                        logger.error(f"  处理文章失败: {e}")

                        try:
                            self.driver.back()
                            time.sleep(1)
                        except:
                            self.navigate_to_date(date_str)
                            self.click_edition_by_index(edition_idx)

                logger.info(f"  版面 {edition_code} 完成: 新保存 {edition_articles} 篇，跳过 {edition_skipped} 篇")

        except Exception as e:
            logger.error(f"爬取日期 {date_str} 失败: {e}")

        logger.info(
            f"日期 {date_str} 完成: 共 {total_articles} 篇文章，新保存 {actual_saved} 篇，跳过 {skipped_articles} 篇\n")
        return actual_saved

    def save_article(self, article: Article, article_num: int) -> bool:
        # 保存文章，如果文件已存在则跳过
        if not article.date:
            return False

        year = article.date[:4]
        month = article.date[4:6]
        day = article.date[6:8]
        month_dir = os.path.join(self.output_dir, f"{year}-{month}")
        day_dir = os.path.join(month_dir, day)
        os.makedirs(day_dir, exist_ok=True)

        filename = self.generate_filename(article.title, article.date, article.edition, article_num)
        filepath = os.path.join(day_dir, filename)

        # 检查文件是否存在
        if os.path.exists(filepath):
            logger.info(f"文件已存在，跳过保存: {filename}")
            return False

        # 保存
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"标题: {article.title}\n")
                f.write(f"版面: {article.edition}\n")
                f.write(f"日期: {article.date}\n")
                f.write(f"内容:\n{article.content}\n")

            logger.debug(f"    保存成功: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存失败: {e}")
            # 尝试备用文件名
            safe_filename = f"{article.date}_{article_num:03d}_{article.edition}_article.txt"
            safe_filepath = os.path.join(day_dir, safe_filename)

            # 检查备用文件是否存在
            if os.path.exists(safe_filepath):
                logger.info(f"备用文件已存在，跳过保存: {safe_filename}")
                return False

            try:
                with open(safe_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"标题: {article.title}\n")
                    f.write(f"版面: {article.edition}\n")
                    f.write(f"日期: {article.date}\n")
                    f.write(f"内容:\n{article.content}\n")

                logger.debug(f"    使用备用文件名保存成功: {safe_filename}")
                return True
            except Exception as e2:
                logger.error(f"备用保存也失败: {e2}")
                return False

    def is_weekend(self, date_str: str) -> bool:
        # 判断日期是否为周末（周六或周日）
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        date_obj = datetime(year, month, day)
        # weekday() 返回 0-6，其中 5=周六，6=周日
        weekday = date_obj.weekday()

        if weekday in [5, 6]:  # 周六或周日
            weekday_name = "周六" if weekday == 5 else "周日"
            return True, weekday_name
        return False, None

    def crawl_current_month(self):
        # 爬取当前月份从1号到今天的所有文章

        # 获取当前日期
        today = datetime.now()
        current_year = today.year
        current_month = today.month
        current_day = today.day

        logger.info(f"\n{'#' * 60}")
        logger.info(f"开始爬取 {current_year}年{current_month}月 的新京报")
        logger.info(f"日期范围: 1日 到 {current_day}日")
        logger.info(f"注意：周六周日报纸不发行，将自动跳过")
        logger.info(f"{'#' * 60}\n")

        # 初始化
        self._init_driver(headless=False)

        total_saved = 0
        total_skipped = 0
        success_days = 0
        weekend_days = 0
        failed_dates = []
        weekend_dates = []

        # 按天爬取
        for day in range(1, current_day + 1):
            date_str = f"{current_year}{current_month:02d}{day:02d}"

            # 检查是否为周末
            is_weekend_day, weekday_name = self.is_weekend(date_str)
            if is_weekend_day:
                logger.info(f"跳过 {date_str} ({weekday_name}，报纸不发行)")
                weekend_days += 1
                weekend_dates.append(f"{date_str}({weekday_name})")
                continue

            try:
                # 爬取这天的所有版面
                saved_count = self.crawl_date_with_click(date_str)

                if saved_count >= 0:  # 即使没有新保存的文章，也算成功
                    success_days += 1
                    total_saved += saved_count
                else:
                    failed_dates.append(date_str)

            except Exception as e:
                logger.error(f"爬取日期 {date_str} 失败: {e}")
                failed_dates.append(date_str)

            time.sleep(2)

        # 日志
        logger.info(f"\n{'#' * 60}")
        logger.info(f"爬取完成统计:")
        logger.info(f"  - 总天数: {current_day}")
        logger.info(f"  - 工作日: {current_day - weekend_days}")
        logger.info(f"  - 周末天数: {weekend_days}")
        logger.info(f"  - 成功爬取天数: {success_days}")
        logger.info(f"  - 失败天数: {len(failed_dates)}")
        if weekend_dates:
            logger.info(f"  - 跳过的周末: {', '.join(weekend_dates[:5])}{'...' if len(weekend_dates) > 5 else ''}")
        if failed_dates:
            logger.info(f"  - 失败日期: {', '.join(failed_dates)}")
        logger.info(f"  - 新保存文章数: {total_saved}")
        if success_days > 0:
            logger.info(f"  - 平均速度: {total_saved / success_days:.1f} 篇/天")
        logger.info(f"{'#' * 60}\n")

    def crawl_specific_date(self, date_str: str):
        # 爬取特定日期（用于测试）
        logger.info(f"\n测试爬取日期: {date_str}")

        # 检查是否为周末
        is_weekend_day, weekday_name = self.is_weekend(date_str)
        if is_weekend_day:
            logger.warning(f"日期 {date_str} 是{weekday_name}，新京报不发行")
            user_input = input("是否仍要尝试爬取？(y/n): ")
            if user_input.lower() != 'y':
                logger.info("跳过周末爬取")
                return

        self._init_driver(headless=False)

        try:
            count = self.crawl_date_with_click(date_str)
            logger.info(f"完成: 新保存 {count} 篇文章")
        except Exception as e:
            logger.error(f"失败: {e}")

    def crawl_date_range(self, start_date: str, end_date: str, skip_weekends: bool = True):
        # 爬取指定日期范围内的所有报纸
        from datetime import timedelta

        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")

        logger.info(f"\n{'#' * 60}")
        logger.info(f"开始爬取日期范围: {start_date} 至 {end_date}")
        if skip_weekends:
            logger.info(f"注意：将自动跳过周六周日")
        logger.info(f"{'#' * 60}\n")

        # 初始化
        self._init_driver(headless=False)

        total_saved = 0
        success_days = 0
        weekend_days = 0
        failed_dates = []

        current = start
        while current <= end:
            date_str = current.strftime("%Y%m%d")

            # 检查是否为周末
            if skip_weekends:
                is_weekend_day, weekday_name = self.is_weekend(date_str)
                if is_weekend_day:
                    logger.info(f"跳过 {date_str} ({weekday_name})")
                    weekend_days += 1
                    current += timedelta(days=1)
                    continue

            try:
                saved_count = self.crawl_date_with_click(date_str)
                if saved_count >= 0:
                    success_days += 1
                    total_saved += saved_count
                else:
                    failed_dates.append(date_str)
            except Exception as e:
                logger.error(f"爬取日期 {date_str} 失败: {e}")
                failed_dates.append(date_str)

            current += timedelta(days=1)
            time.sleep(2)

        # 统计
        total_days = (end - start).days + 1
        logger.info(f"\n{'#' * 60}")
        logger.info(f"爬取完成统计:")
        logger.info(f"  - 日期范围天数: {total_days}")
        logger.info(f"  - 跳过周末天数: {weekend_days}")
        logger.info(f"  - 实际爬取天数: {success_days}")
        logger.info(f"  - 失败天数: {len(failed_dates)}")
        logger.info(f"  - 新保存文章数: {total_saved}")
        if success_days > 0:
            logger.info(f"  - 平均速度: {total_saved / success_days:.1f} 篇/天")
        logger.info(f"{'#' * 60}\n")

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass


def main():
    # 输出目录
    output_directory = r"D:\CENTER\Data\2025\报纸\报纸源文本\新京"

    crawler = BJNewsCrawler(output_dir=output_directory)

    try:
        # 多种使用方式示例：

        # 1. 爬取当前月份（自动跳过周末）
        crawler.crawl_current_month()

        # 2. 爬取特定日期（会提示是否为周末）
        # crawler.crawl_specific_date("20250104")  # 周六

        # 3. 爬取指定日期范围（自动跳过周末）
        # crawler.crawl_date_range("20250101", "20250110", skip_weekends=True)

        # 4. 爬取指定日期范围（包含周末，用于特殊情况）
        # crawler.crawl_date_range("20250101", "20250110", skip_weekends=False)

    except KeyboardInterrupt:
        logger.info("\n用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}")
    finally:
        del crawler


if __name__ == '__main__':
    main()