import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
import logging
from pathlib import Path
import matplotlib.pyplot as plt
from stop_words import get_stop_words
import re
from collections import Counter
import itertools
import nltk
from nltk import bigrams
from dotenv import load_dotenv
from io import StringIO
import os

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=log_dir/"streamlit.log",
    level=logging.INFO,
    format='[ %(asctime)s %(levelname)s ] %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
URL = os.getenv("BACKEND_URL")
YANDEX_S3 = os.getenv("OBJ_URL")
data_id = st.query_params.get("data_id", None)
login = st.query_params.get("login", "guest")
model = st.query_params.get("model", None)
uploaded_file = None
requirement = "Review"
STOPWORDS_RU = get_stop_words('russian')

def get_csv_from_s3(csv_id):
    logger.info(f"Trying to get CSV fron object storage for user {login}, csv_id {csv_id}")
    answer_result_csv = requests.get(f"{YANDEX_S3}/{login}_{csv_id}.csv")
    if answer_result_csv.status_code == 200:
        logger.info("CSV received successfully")
        answer_result_csv.encoding = 'utf-8'
        return StringIO(answer_result_csv.text)
    elif answer_result_csv.status_code == 404:
        logger.error(f"File {login}_{csv_id}.csv not found in object storage")
        st.error(f"Файл {login}_{csv_id}.csv не найден")
    else:
        logger.error(f"Object storage error")
        st.error("Yandex storage не отвечает O_o...")
    return None

def predict_request(data):
    logger.info(f"Trying to get predict ({model}) for user {login}")
    answer = requests.post(f"{URL}/predict/csv/{model}",
                           data={"login": f"{login}"},
                           files={'data_csv': ("input.csv", data.to_csv(index=False))})
    if answer.status_code == 200:
        logger.info("Predict received successfully")
        result = pd.read_csv(get_csv_from_s3(answer.text))
        result["predict"] = result["predict"].apply(lambda x: "Positive" if x else "Negative")
        return result["predict"].tolist()
    elif answer.status_code == 404:
        logger.error("There is no user with this login, or the model is incorrect.")
        st.error("Не существует пользователя с таким логином, либо указана неверная модель")
    else:
        logger.error("Critical error on server side")
        st.error("Критическая серверная ошибка")
    return None

def get_top_bigrams(texts, n=10):
    all_bigrams = list(itertools.chain(*[bigrams(str(text).split()) for text in texts]))
    bigram_counts = Counter(all_bigrams)
    return pd.Series(dict(bigram_counts.most_common(n)))

def preprocess_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def selector_formatter(raw_input):
    if raw_input == "goods": return "Товары"
    if raw_input == "clothes": return "Одежда"
    if raw_input == "films": return "Фильмы"
    if raw_input == "goods-and-clothes": return "Товары и одежда"

st.markdown("""
    <style>
        .custom-success {
            border-left: 4px solid #A476F3;
            padding: 1em;
            background-color: #EEE4FF;
        }
    </style>
""", unsafe_allow_html=True)

st.title(f"Классификатор отзывов")

try:
    if data_id:
        logger.info("Get analys mode")
        with st.spinner("Получение файла..."):
            uploaded_file = get_csv_from_s3(data_id)
    else:
        logger.info("Predict and get analys mode")
        if not model:
            model = st.selectbox(
                "Выберите модель",
                ("goods", "clothes", "films", "goods-and-clothes"),
                format_func=selector_formatter
            )
        st.write(f"Пользователь {login}, модель {model}")
        uploaded_file = st.file_uploader(f"Загрузите CSV-файл с отзывами (колонка {requirement} обязательна)", type=["csv", "xls", "xlsx", "xlsm", "xlsb", "odf", "ods", "odt"])
except Exception as e:
    logger.error(f"Error while CSV get: {str(e)}")

if uploaded_file is not None:
    try:
        logger.info("Converting to DataFrame")
        with st.spinner("Получение файла..."):
            df = pd.read_csv(uploaded_file)
    except Exception as e:
        logger.error(f"Fail while converting to DataFrame: {str(e)}")
    
    if requirement not in df.columns:
        logger.error("CSV column «Review» require")
        st.error(f"В файле нет колонки {requirement}!")
    else:
        st.markdown(
            '<div class="custom-success">Файл успешно загружен!</div>',
            unsafe_allow_html=True
        )
        st.write(" ")
        predictions = None
        try:
            if data_id is None:
                with st.spinner("Идёт классификация, это может занять некоторое время..."):
                    predictions = predict_request(df[[requirement]])
                    df["Sentiment"] = predictions
            else:
                predictions = df["predict"].apply(lambda x: "Positive" if x else "Negative")
                df["Sentiment"] = predictions
                df = df.drop(["predict"], axis=1)
        except Exception as e:
            logger.error(f"Error while predict: {str(e)}")
        
        if predictions is not None:
            if data_id is None:
                st.markdown(
                    '<div class="custom-success">Метки предсказаны!</div>',
                    unsafe_allow_html=True
                )
                st.write(" ")

            try:
                logger.info("Result summarize (csv with labels)")
                with st.spinner("Создание CSV с метками..."):
                    st.download_button(
                        label="Скачать результаты",
                        data=df.to_csv(index=False).encode("utf-8"),
                        file_name=f"result_{login}_{data_id}.csv" if data_id else f"result_{uploaded_file.name}.csv",
                        mime="text/csv"
                    )
            except Exception as e:
                logger.error(f"Error while summarize: {str(e)}")

            try:
                logger.info("Analys result")
                if not df.empty:
                    st.subheader("Распределение предсказаний")
                    with st.spinner("Анализируем..."):
                        fig1, ax1 = plt.subplots()
                        df["Sentiment"].value_counts().plot(kind="pie", colors=["#A476F3", "#FFFFFF"], autopct="%1.1f%%", startangle=90, ax=ax1)
                        ax1.set_ylabel("")
                        st.pyplot(fig1)

                    if not df[df["Sentiment"] == "Positive"][requirement].empty:
                        st.subheader("Частотность слов в положительных отзывах")
                        with st.spinner("Анализируем..."):
                            word_counts = pd.Series([word for word in " ".join(df[df["Sentiment"] == "Positive"][requirement].apply(preprocess_text)).split() if word not in STOPWORDS_RU]).value_counts()[:10]
                            fig2, ax2 = plt.subplots()
                            word_counts.plot(kind="barh", color="#A476F3", ax=ax2)
                            st.pyplot(fig2)

                    if not df[df["Sentiment"] == "Negative"][requirement].empty:
                        st.subheader("Частотность слов в отрицательных отзывах")
                        with st.spinner("Анализируем..."):
                            word_counts = pd.Series([word for word in " ".join(df[df["Sentiment"] == "Negative"][requirement].apply(preprocess_text)).split() if word not in STOPWORDS_RU]).value_counts()[:10]
                            fig3, ax3 = plt.subplots()
                            word_counts.plot(kind="barh", color="#A476F3", ax=ax3)
                            st.pyplot(fig3)
                    
                    if not df[df["Sentiment"] == "Positive"][requirement].empty:
                        st.subheader("Топ биграмм в положительных отзывах")
                        with st.spinner("Анализируем..."):
                            top_bigrams = get_top_bigrams(df[df["Sentiment"] == "Positive"][requirement])
                            fig4, ax4 = plt.subplots()
                            top_bigrams.plot(kind="barh", color="#A476F3", ax=ax4)
                            st.pyplot(fig4)

                    if not df[df["Sentiment"] == "Negative"][requirement].empty:
                        st.subheader("Топ биграмм в отрицательных отзывах")
                        with st.spinner("Анализируем..."):
                            top_bigrams = get_top_bigrams(df[df["Sentiment"] == "Negative"][requirement])
                            fig5, ax5 = plt.subplots()
                            top_bigrams.plot(kind="barh", color="#A476F3", ax=ax5)
                            st.pyplot(fig5)
            except Exception as e:
                logger.error(f"Error while analys: {str(e)}")
