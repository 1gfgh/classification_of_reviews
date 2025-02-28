from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidSessionIdException

import pandas as pd
import logging

import time

# logging.basicConfig(level=logging.INFO, filename="logs.log",filemode="w")
logging.basicConfig(level=logging.INFO)

"""
Must хранит все страницы с контентом по url с шаблоном
https://mustapp.com/p/i
где i — id фильма/сериала/аниме/etc.
Спарсятся шапки отзывов на страницах с id от 1 до MAX_PAGES.
(Если отзывы на контент вообще были оставлены)
"""

# ======================  Настройка тут  ======================
START_PAGE = 11001  # понятно
MAX_PAGES = 12000  # ну понятно
MAX_BUF = 2000  # каждые MAX_BUF страниц делать пресейв
# =============================================================

COUNT_BUF = 0
COUNT_FLUSHES = 1

data = pd.DataFrame(
    columns=[
        "Mustapp page ID",
        "Title",
        "Description",
        "Review text",
        "Score (out of 10)",
    ]
)

# Не хочу постоянно открывающийся браузер
options = webdriver.ChromeOptions()
options.add_argument("headless")

for i in range(START_PAGE, MAX_PAGES + 1):
    url = f"https://mustapp.com/p/{i}"

    logging.info(f"======================  {i}  ======================")
    start_time = time.time()
    try:
        browser = webdriver.Chrome(options=options)
        browser.get(url)
    except InvalidSessionIdException as e:
        logging.info(f"GET {url} отдыхает")
        COUNT_BUF += 1
        continue
    end_time = time.time()
    elapsed_time = end_time - start_time
    logging.info(f"Подключение заняло {elapsed_time:.2f} сек.")

    soup = BeautifulSoup(browser.page_source, "lxml")

    # Название, описание, количество отзывов в информационном блоке, поиск блока отзывов
    try:
        metaBlock = soup.find("div", class_="productPage__meta")
        if metaBlock:
            logging.info(f"Обработка мета блока")

            title = soup.find("h1", class_="productPage__title")
            if title:
                title = title.text
                logging.info(f"{title}")
            else:
                logging.info(f"Название не найдено")

            description = soup.find(
                "div", class_="productPage__overview_text m_hidden js_overview_full"
            )
            if description:
                description = description.text
                logging.info(f"Описание найдено")
            else:
                logging.info(f"Описание не найдено")

            metaBlock_items = metaBlock.find_all("div", class_="productPage__meta_item")
            review_count = int(
                metaBlock_items[3].find("div", class_="productPage__meta_value").text
            )

            if review_count == 0:
                logging.info(f"Нет отзывов")
                browser.close()
                COUNT_BUF += 1
                continue
            else:
                logging.info(f"Отзывов в мета блоке {review_count}")
        else:
            logging.info(f"Мета блок не найден (что?)")

        WebDriverWait(browser, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "productWatches__list"))
        )
        logging.info("Блок отзывов найден")
    except Exception: #as e:
        logging.info("Блок меты/отзывов не найден!")
        # logging.info(e)
        browser.close()
        COUNT_BUF += 1
        continue

    soup = BeautifulSoup(browser.page_source, "lxml")

    # Прогружаем все (почти) отзывы
    start_time = time.time()
    preloader = soup.find("div", class_="preloader m_big")
    while (preloader and (time.time() - start_time < 20)):
        browser.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        soup = BeautifulSoup(browser.page_source, "lxml")
        preloader = soup.find("div", class_="preloader m_big")

    productWatches_list = soup.find("div", class_="productWatches__list js_list")
    reviews = productWatches_list.find_all("div", class_="productWatches__item_info")

    if reviews:
        logging.info(f"Были найдены отзывы в количестве {len(reviews)} шт.")

    for review in reviews:
        rating = review.find("div", class_="productWatches__item_rate")

        if not rating:
            continue

        try:
            rating = int(rating.get("class")[1][7:])
        except IndexError as e:
            logging.info("Не удалось извлечь оценку")
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

        new_row = {
            "Mustapp page ID": i,
            "Title": title,
            "Description": description,
            "Review text": text_review,
            "Score (out of 10)": rating,
        }
        data.loc[len(data)] = new_row

    COUNT_BUF += 1

    if COUNT_BUF >= MAX_BUF:
        data.to_csv(
            f"presave{COUNT_FLUSHES}_mustapp_reviews_{START_PAGE}-{i}.csv", index=False
        )
        logging.info(f"Пресейв №{COUNT_FLUSHES} ({START_PAGE} — {i})")
        COUNT_FLUSHES += 1
        COUNT_BUF = 0

    browser.close()

data.to_csv(f"mustapp_reviews_{START_PAGE}-{MAX_PAGES}.csv", index=False)

logging.info(f"Завершение, было добавлено {len(data)} отзывов")

browser.quit()
