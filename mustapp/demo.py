from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="w")

test_url = "https://mustapp.com/p/1"
logging.info("   ======================  8453942 ======================")
options = webdriver.ChromeOptions()
options.add_argument("headless")
browser = webdriver.Chrome(options=options)
browser.get(test_url)

try:
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "productWatches__list"))
    )
    logging.info("   Блок отзывов найден")
except Exception as e:
    logging.info("   Блок отзывов не найден!")
    logging.warning(e)
    browser.close()
    # continue

soup = BeautifulSoup(browser.page_source, "lxml")

productWatches__list = soup.find("div", class_="productWatches__list js_list")
reviews = productWatches__list.find_all("div", class_="productWatches__item_info")
if reviews:
    logging.info(f"   Были найдены отзывы в количестве {len(reviews)} шт.")

for review in reviews:
    rating = review.find("div", class_="productWatches__item_rate")
    if not rating:
        continue
    try:
        rating = int(rating.get("class")[1][7:])
    except IndexError:
        logging.warning("Не удалось извлечь оценку")
        continue
    text_review = review.find("div", class_="productWatches__item_review")
    if not text_review:
        continue
    prefix = text_review.find("div", class_="productWatches__item_review_title")
    if prefix:
        prefix = prefix.text
        text_review = text_review.text[len(prefix) + 1 :]
    else:
        text_review = text_review.text
    print(f"{rating}: {text_review}")

browser.close()
