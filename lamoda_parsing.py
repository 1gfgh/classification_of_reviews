from bs4 import BeautifulSoup
import os
import math
import time
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(level=logging.INFO, filename="lamoda_parsing_logs.log", filemode='w')

class Review(BaseModel):
    review_text: str
    review_rating: int

def CleanReviewText(func):
    def wrapper(*args, **kwargs):
        reviews = func(*args, **kwargs)
        if reviews is None:
            return []
        cleaned_reviews = []
        for review in reviews:
            review_text = review.review_text.strip()
            cleaned_review = review_text.replace("\n", " ").replace("  ", " ").strip()
            if "Куплен" in cleaned_review:
                cleaned_review = cleaned_review.split("Куплен")[0].strip()
            review.review_text = cleaned_review
            cleaned_reviews.append(review)
        return cleaned_reviews
    return wrapper

def scroll_down(browser, max_scrolls=5, wait_time=2):
    for _ in range(max_scrolls):
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)

def GetReviewsSection(browser) -> bool:
    try:
        reviews_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Отзывы')]"))
        )
        reviews_button.click()
        logging.info("Кликнули на вкладку 'Отзывы'")

        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_root_1dixh_6"))
        )
        logging.info("Отзывы успешно загружены!")
        return True

    except Exception as e:
        logging.warning(f"Ошибка при загрузке отзывов: {e}")
        return False

@CleanReviewText
def getAllReviews(browser) -> list[Review]:
    soup = BeautifulSoup(browser.page_source, "lxml")
    review_elements = soup.find_all('div', class_="_root_1dixh_6")
    reviews = []

    for review in review_elements:
        review_text_tag = review.find("div", class_="_description_1dixh_42")
        review_text = review_text_tag.get_text().strip() if review_text_tag else "Отзыв отсутствует"
        rating_tag = review.find("div", class_="_starsInner_100pf_16")

        try:
            width_value = rating_tag["style"].split(":")[1].strip().replace("%;", "")
            review_rating = round(float(width_value) / 20) if width_value else 0
        except:
            review_rating = 0

        reviews.append(Review(review_text=review_text, review_rating=review_rating))

    logging.info(f"Нашли {len(reviews)} отзывов")
    return reviews

def GetGoodName(browser) -> str:
    try:
        soup = BeautifulSoup(browser.page_source, "lxml")
        good_name_tag = soup.find("div", class_="_modelName_mnqvr_21")
        if good_name_tag:
            name = good_name_tag.get_text().strip()
            logging.info(f"Название товара: {name}")
            return name
        else:
            logging.warning("Название товара не найдено")
            return "Не найдено"
    except Exception as e:
        logging.error(f"Ошибка при получении названия: {e}")
        return "Не найдено"

def GetGoodDescription(browser) -> str:
    try:
        soup = BeautifulSoup(browser.page_source, "lxml")
        description = soup.find('div', class_="_description_795ct_30")
        if description:
            desc = description.get_text().strip()
            logging.info(f"Описание товара: {desc}")
            return desc
        else:
            logging.warning("Описание товара не найдено")
            return "Не найдено"
    except Exception as e:
        logging.error(f"Ошибка при получении описания: {e}")
        return "Не найдено"

def UploadReviews(reviews: list[Review], name: str, description: str, append_mode=True) -> None:
    data = pd.DataFrame(columns=["Good's name", "Description", "Review", "Rating"])
    for review in reviews:
        data.loc[data.shape[0]] = {
            "Good's name": name,
            "Description": description,
            "Review": review.review_text,
            "Rating": review.review_rating
        }
    
    filename = "lamoda_reviews.csv"
    mode = 'a' if append_mode else 'w'
    header = not os.path.exists(filename) if append_mode else True
    data.to_csv(filename, mode=mode, index=False, header=header)

    logging.info(f"Сохранено {len(reviews)} отзывов")

def parse(url: str) -> None:
    try:
        with open("links.txt", 'a') as file:
            file.write(f"{url}\n")
        logging.info("Ссылка сохранена!")
    except FileNotFoundError:
        logging.fatal("Файл 'links.txt' не найден!")
        return

    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(180)

    try:
        logging.info(f"Открываю страницу: {url}")
        browser.get(url)
        time.sleep(3)

        scroll_down(browser, max_scrolls=3, wait_time=2)

        good_name = GetGoodName(browser)
        good_description = GetGoodDescription(browser)

        reviews = []
        if GetReviewsSection(browser):
            page = 1
            while True:
                logging.info(f"Собираю отзывы со страницы {page}")

                scroll_down(browser, max_scrolls=2, wait_time=2)

                new_reviews = getAllReviews(browser)
                if new_reviews:
                    reviews.extend(new_reviews)

                    if len(reviews) >= 100:
                        UploadReviews(reviews, good_name, good_description, append_mode=True)
                        reviews.clear()

                try:
                    next_button = WebDriverWait(browser, 5).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "icon_pagination-arrow-right-black"))
                    )
                    next_button.click()
                    time.sleep(3)
                    page += 1
                except:
                    logging.info("Кнопка 'Следующая страница' больше не доступна.")
                    break

        if reviews:
            UploadReviews(reviews, good_name, good_description, append_mode=True)

        logging.info(f"Парсинг завершён для товара: {good_name}")

    except Exception as e:
        logging.error(f"Ошибка при парсинге {url}: {e}")

    finally:
        browser.quit()

def main():
    urls = [
        "https://www.lamoda.ru/p/rtlabk223203/shoes-reebok-krossovki/",
        "https://www.lamoda.ru/p/mp002xm1i4v0/shoes-fila-krossovki/",
        "https://www.lamoda.ru/p/rtlacv920301/shoes-reebok-kedy/",
        "https://www.lamoda.ru/p/rtladw395201/shoes-adidasoriginals-kedy/",
        "https://www.lamoda.ru/p/rtlacy380701/shoes-adidasoriginals-krossovki/",
        "https://www.lamoda.ru/p/rtladf853601/shoes-adidasoriginals-kedy/",
        "https://www.lamoda.ru/p/mp002xm0vodq/clothes-fila-trusy-sht/",
        "https://www.lamoda.ru/p/mp002xm1rmxr/clothes-henderson-trusy-sht/",
        "https://www.lamoda.ru/p/mp002xm1rmxq/clothes-henderson-trusy-sht/",
        "https://www.lamoda.ru/p/mp002xm08s1e/clothes-toraeblack-khudi/",
        "https://www.lamoda.ru/p/rtlade364802/clothes-adidas-bryuki-sportivnye/",
        "https://www.lamoda.ru/p/mp002xm23tqd/clothes-thecave-futbolka/",
    ]
    for url in urls:
        parse(url)

if __name__ == "__main__":
    main()