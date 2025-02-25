from bs4 import BeautifulSoup
import os
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

def scroll_down(browser, max_scrolls=5, wait_time=2):
    """Скроллит страницу вниз несколько раз"""
    for _ in range(max_scrolls):
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)

def get_product_links(browser):
    """Собирает ссылки на все товары на странице каталога"""
    scroll_down(browser, max_scrolls=5, wait_time=2)
    soup = BeautifulSoup(browser.page_source, "lxml")
    product_links = []

    product_cards = soup.find_all("a", class_="_root_aroml_2 _label_aroml_17")  # Класс ссылки товара
    for card in product_cards:
        href = card.get("href")
        if href and href.startswith("/p/"):
            product_links.append(f"https://www.lamoda.ru{href}")

    logging.info(f"Найдено {len(product_links)} товаров")
    return product_links

def GetReviewsSection(browser) -> bool:
    """Кликает на вкладку 'Отзывы' и проверяет, загрузились ли они"""
    try:
        reviews_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Отзывы')]"))
        )
        reviews_button.click()
        logging.info("Кликнули на вкладку 'Отзывы'")

        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_root_1dixh_6"))
        )
        logging.info("Отзывы загружены")
        return True
    except Exception as e:
        logging.warning(f"Ошибка при загрузке отзывов: {e}")
        return False

def getAllReviews(browser) -> list[Review]:
    """Собирает все отзывы с текущей страницы"""
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

    logging.info(f"Собрано {len(reviews)} отзывов")
    return reviews

def parse_product(browser, url):
    """Парсит один товар"""
    browser.execute_script(f"window.open('{url}', '_blank');")  # Открываем в новой вкладке
    browser.switch_to.window(browser.window_handles[-1])  # Переключаемся на новую вкладку

    try:
        logging.info(f"Открываю страницу товара: {url}")
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

        UploadReviews(reviews, good_name, good_description, append_mode=True)

        logging.info(f"Парсинг завершён для товара: {good_name}")

    except Exception as e:
        logging.error(f"Ошибка при парсинге товара {url}: {e}")

    finally:
        browser.close()  # Закрываем вкладку
        browser.switch_to.window(browser.window_handles[0])  # Возвращаемся в каталог

def parse_catalog(url):
    """Парсит все товары со страницы каталога"""
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(180)

    try:
        logging.info(f"Открываю страницу каталога: {url}")
        browser.get(url)
        time.sleep(3)

        while True:
            product_links = get_product_links(browser)

            for product_url in product_links:
                parse_product(browser, product_url)

            # Скроллим страницу перед поиском кнопки "Дальше"
            scroll_down(browser, max_scrolls=3, wait_time=2)

            try:
                next_button = WebDriverWait(browser, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "_nextPage_6v5hm_74"))
                )
                next_button.click()
                time.sleep(3)
            except:
                logging.info("Кнопка 'Дальше' больше не доступна.")
                break

    except Exception as e:
        logging.error(f"Ошибка при парсинге каталога {url}: {e}")

    finally:
        browser.quit()

def main():
    catalog_urls = [
        "https://www.lamoda.ru/c/4151/clothes-muzhskie-bryuki/",
        "https://www.lamoda.ru/c/4152/clothes-muzhskie-futbolki/",
        "https://www.lamoda.ru/c/4153/clothes-muzhskie-dzhinsy/",
    ]
    for url in catalog_urls:
        parse_catalog(url)

if __name__ == "__main__":
    main()