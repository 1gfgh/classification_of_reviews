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
    
    logging.info("Начинаем сбор ссылок на товары с текущей страницы...")

    try:
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.x-product-card__pic-catalog"))
        )
    except:
        logging.warning("Не найдено товаров на странице!")
        return []

    scroll_down(browser, max_scrolls=5, wait_time=2)
    
    soup = BeautifulSoup(browser.page_source, "lxml")
    product_links = []

    product_cards = soup.find_all("a", class_="x-product-card__pic-catalog")
    if not product_cards:
        product_cards = soup.find_all("a", class_="_root_aroml_2 _label_aroml_17")

    for card in product_cards:
        href = card.get("href")
        if href and href.startswith("/p/"):
            product_links.append(f"https://www.lamoda.ru{href}")

    logging.info(f"Найдено {len(product_links)} товаров на странице.")
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
        logging.info("Отзывы загружены!")
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

    logging.info(f"Собрано {len(reviews)} отзывов с текущей страницы.")
    return reviews

def GetGoodName(browser) -> str:
    """Получает название товара"""
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
    """Получает описание товара"""
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
    """Записывает отзывы в CSV каждые 100 штук"""
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

    logging.info(f"Сохранено {len(reviews)} отзывов в файл.")

def load_processed_links():
    """Загружает обработанные ссылки из файла"""
    if os.path.exists("links.txt"):
        with open("links.txt", "r") as file:
            return set(file.read().splitlines())
    return set()

def save_processed_link(url):
    """Сохраняет обработанную ссылку в файл"""
    with open("links.txt", "a") as file:
        file.write(url + "\n")

def parse_product(browser, url, processed_links):
    """Парсит один товар"""
    if url in processed_links:
        logging.info(f"Товар уже обработан: {url} (пропускаем)")
        return

    browser.execute_script(f"window.open('{url}', '_blank');")
    browser.switch_to.window(browser.window_handles[-1])

    try:
        logging.info(f"Открываю страницу товара: {url}")
        browser.get(url)
        time.sleep(3)

        scroll_down(browser, max_scrolls=3, wait_time=2)

        good_name = GetGoodName(browser)
        good_description = GetGoodDescription(browser)

        reviews = []
        if GetReviewsSection(browser):
            while True:
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
                except:
                    logging.info("Достигли последней страницы отзывов")
                    break

        if reviews:
            UploadReviews(reviews, good_name, good_description, append_mode=True)

        save_processed_link(url)
    except Exception as e:
        logging.error(f"Ошибка при парсинге товара {url}: {e}")
    finally:
        browser.close()
        browser.switch_to.window(browser.window_handles[0])

def parse_catalog(url, n):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(180)

    processed_links = load_processed_links()

    try:
        browser.get(url)
        time.sleep(3)

        while True:
            product_links = get_product_links(browser)
            for product_url in product_links:
                parse_product(browser, product_url, processed_links)

            scroll_down(browser, max_scrolls=3, wait_time=2)
            logging.info(f"страница номер {n} готова")
            break
    finally:
        browser.quit()

def main():
    for i in range(1, 100):
        parse_catalog(f"https://www.lamoda.ru/c/4154/default-kids/?display_locations=outlet&is_sale=1&sitelink=topmenuK&l=13&page={i}", i)

if __name__ == "__main__":
    main()