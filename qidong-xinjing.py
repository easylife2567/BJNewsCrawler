import datetime
import calendar
import subprocess
import time


def is_last_day_of_month():
    """判断是否是当前月份的最后一天"""
    today = datetime.date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.day == last_day


def run_xinjing():
    """运行 xinjing.py 并处理错误"""
    max_retries = 5  # 最大重试次数
    retries = 0

    while retries < max_retries:
        try:
            print(f"正在运行 xinjing.py (尝试 {retries + 1}/{max_retries})...")
            result = subprocess.run(["python", "xinjing.py"], capture_output=True, text=True)

            if result.returncode == 0:
                print("xinjing.py 运行成功！")
                return True
            else:
                print(f"运行失败，错误信息：{result.stderr}")
                retries += 1
                time.sleep(5)  # 等待5秒后重试
        except Exception as e:
            print(f"运行 xinjing.py 时发生异常：{e}")
            retries += 1
            time.sleep(5)

    print("已达到最大重试次数，程序退出。")
    return False


if __name__ == "__main__":
    if is_last_day_of_month():
        print("今天是本月的最后一天，开始运行 xinjing.py...")
        run_xinjing()
    else:
        print("今天不是本月的最后一天，程序退出。")