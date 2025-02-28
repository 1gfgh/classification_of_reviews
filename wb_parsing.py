from bs4 import BeautifulSoup
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidSessionIdException
from pydantic import BaseModel, EmailStr
import logging
import pandas as pd
import time
logging.basicConfig(level=logging.INFO, filename="wb_parsing_logs.log", filemode='w')

class Review(BaseModel):
    review_text: str
    review_rating: int


def CleanReviewText(func):
    def wrapper(*args, **kwargs):
        reviews = func(*args, **kwargs)
        if reviews is None:
            return None
            
        start_remove_words = ["Достоинства", "Недостатки", "Комментарий"]
        end_remove_words = ["Ещё", "Первоначальный отзыв"]
        cleaned_reviews = []
        for review in reviews:
            review_text = review.review_text
            cleaned_review = review_text
            cleaned_review = cleaned_review.replace(":", " ")
            
            for word in start_remove_words:
                cleaned_review = cleaned_review.replace(word, "", 1)
            
            for word in end_remove_words:
                cleaned_review = cleaned_review.rsplit(word, 1)[0]
            cleaned_review = cleaned_review.replace("  ", " ")
            cleaned_review = cleaned_review.strip()
            review.review_text = cleaned_review
            cleaned_reviews.append(review)
        return cleaned_reviews
    return wrapper

def GetReviewUrl(browser) -> str:
    try:
        WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "j-wba-card-item"))
        )
        logging.info("Found review block")
    except Exception as e:
        logging.warning("Review block wasn't found")
        return None

    soup = BeautifulSoup(browser.page_source, "lxml")
    review_block = soup.find('a', class_="product-review j-wba-card-item")
    
    if review_block and review_block.get("href"):
        logging.info(f"Reviews have an address {review_block.get('href')}")
        return f"https://www.wildberries.ru{review_block.get('href')}"
    else:
        logging.warning("Could not find review URL")
        return None

@CleanReviewText
def getAllReviews(browser) -> list[Review]:
    try:
        WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "feedback__content"))
        )
        logging.info("Found reviews content")
    except Exception as e:
        logging.warning("Reviews content wasn't found")
        return None

    soup = BeautifulSoup(browser.page_source, "lxml")
    review_elements = soup.find_all("div", class_="feedback__content")
    rating_elements = soup.find_all("div", class_="feedback__info")
    
    if review_elements and rating_elements:
        reviews = []
        for review, rating in zip(review_elements, rating_elements):
            review_text = review.find('p', class_="feedback__text")
            review_rating = rating.find("span", class_="feedback__rating")
            if review_text:
                reviews.append(Review(
                    review_text=review_text.get_text().strip(),
                    review_rating=int(review_rating.get("class")[2][-1])
                ))
        
        logging.info(f"Found {len(reviews)} reviews")
        return reviews
    else:
        logging.warning("Could not find any reviews")
        return None
    

def GetGoodName(browser) -> str:
    try:
        WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-page__title"))
        )
        logging.info("Found good's name block")
    except Exception as e:
        logging.warning("Good's name block wasn't found")
        return None

    soup = BeautifulSoup(browser.page_source, "lxml")
    good_name = soup.find('h1', class_="product-page__title")
    if good_name:
        logging.info(f"Good's name: {good_name.get_text().strip()}")
        return good_name.get_text().strip()
    else:
        logging.warning("Could not find good's name")
        return None


def GetGoodDescription(browser) -> str:
    try:
        WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "j-details-btn-desktop"))
        ).click()
    except Exception as e:
        logging.warning("Block of characteristics wasn't found!")
        return None
    try:
        WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-details"))
        )
        logging.info("Good's description block was found")
    except Exception as e:
        logging.warning("Good's description block wasn't found")
        return None
    
    soup = BeautifulSoup(browser.page_source, "lxml")
    description = soup.find('p', class_="option__text")
    if description:
        logging.info(f"Good's description: {description.get_text().strip()}")
        return description.get_text().strip()
    else:
        logging.warning("Could not find good's description")
        return None
    

def UploadReviews(reviews: list[Review], name: str, description: str) -> None:
    data = pd.DataFrame()
    try:
        with open("wb_reviews.csv", 'r') as file:
            data = pd.read_csv(file)
    except FileNotFoundError:
        data = pd.DataFrame(columns=["Good's name", "Description", "Review", "Rating"])
    time_point = time.time()
    for review in reviews:
        elem = {
            "Good's name": name, 
            "Description": description, 
            "Review": review.review_text, 
            "Rating": review.review_rating
        }
        data.loc[data.shape[0]] = elem
        if time.time() - time_point > 600:
            data.to_csv(f"presave_wb_reviews.csv", index=False)
            logging.info("Presave of data has been done!")
    data.to_csv(f"wb_reviews.csv", index=False)
    logging.info(f"Size of our DataFrame is {data.shape[0]}")


def parse(url: str) -> None:
    try:
        with open("links.txt", 'r') as file:
            if url in file.read():
                logging.error(f"{url} is already processed!")
                return
    except FileNotFoundError:
        logging.fatal("No file 'links.txt' to save ur link!")
        return
    try:
        with open("links.txt", 'a') as file:
            file.write(f"{url}\n")
        logging.info("Link has been saved!")
    except FileNotFoundError:
        logging.fatal("No file 'links.txt' to save ur link!")
        return
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9230")
    browser = webdriver.Chrome(options=options)
    browser.get(url)
    good_name = GetGoodName(browser)
    if good_name:
        print("\n" + "="*50)
        print(f"Good's name: {good_name}")
        print("="*50 + "\n")
    else:
        print("\nNo good name found")
    reviews_url = GetReviewUrl(browser)
    good_description = GetGoodDescription(browser)
    if good_description:
        print("\n" + "="*50)
        print(f"Good's description: {good_description}")
        print("="*50 + "\n")
    else:
        print("\nNo good's description found")
    if reviews_url:
        browser.get(reviews_url)
        start_time = time.time()
        last_height = browser.execute_script("return document.body.scrollHeight")
        while True:
            if time.time() - start_time > 3600:
                logging.info("Reached timeout, stopping scroll")
                break
                
            browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            time.sleep(10)
            
            new_height = browser.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        reviews = getAllReviews(browser)
        if reviews:
            print("\n" + "="*50)
            print(f"Found {len(reviews)} reviews:")
            print("="*50 + "\n")
            for i, review in enumerate(reviews, 1):
                print(f"Review #{i}:")
                print(f"Text: '{review.review_text}'")
                print(f"Rating: {review.review_rating}")
                print("-"*50 + "\n")
        else:
            print("\nNo reviews found")
    else:
        logging.warning("Could not find review URL")
    if reviews:
        UploadReviews(reviews, good_name, good_description)
    browser.stop_client()
    browser.close()
    browser.quit()


def getUrls() -> list[str]:
    url = "https://www.wildberries.ru"
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9230")
    browser = webdriver.Chrome(options=options)
    browser.get(url) 
    try:
        WebDriverWait(browser, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-card__wrapper"))
        )
        logging.info("Goods were found")
    except Exception as e:
        logging.warning("Goods were not found")
        return None
    soup = BeautifulSoup(browser.page_source, "lxml")
    goods = soup.find_all('a', class_="product-card__link j-card-link j-open-full-product-card")
    urls = []
    start_time = time.time()
    time_limit = 300
    for good in goods:
        logging.info(f"""Found new good: {good.get("href")}""")
        urls.append(good.get("href"))
        if time.time() > start_time + time_limit:
            break
    browser.stop_client()
    browser.close()
    browser.quit()
    return urls


def main():
    start_time = time.time()
    time_limit = 3600
    while time.time() - start_time < time_limit:
        logging.info("Start of the new interation")
        urls = getUrls()
        for url in urls:
            parse(url)
    return


if __name__ == "__main__":
    main()