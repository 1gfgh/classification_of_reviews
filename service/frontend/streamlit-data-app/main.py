import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
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
    answer_result_csv = requests.get(f"{YANDEX_S3}/{login}_{csv_id}.csv")
    if answer_result_csv.status_code == 200:
        answer_result_csv.encoding = 'utf-8'
        return StringIO(answer_result_csv.text)
    elif answer_result_csv.status_code == 404:
        st.error(f"Файл {login}_{csv_id}.csv не найден")
    else:
        st.error("Yandex storage не отвечает O_o...")
    return None

def predict_request(data):
    answer = requests.post(f"{URL}/predict/csv/{model}",
                           data={"login": f"{login}"},
                           files={'data_csv': ("input.csv", data.to_csv(index=False))})
    if answer.status_code == 200:
        result = pd.read_csv(get_csv_from_s3(answer.text))
        result["predict"] = result["predict"].apply(lambda x: "Positive" if x else "Negative")
        return result["predict"].tolist()
    elif answer.status_code == 404:
        st.error("Не существует пользователя с таким логином, либо указана неверная модель")
    else:
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

if data_id:
    with st.spinner("Получение файла..."):
        uploaded_file = get_csv_from_s3(data_id)
else:
    if not model:
        model = st.selectbox(
            "Выберите модель",
            ("wb"),
        )
    st.write(f"Пользователь {login}, модель {model}")
    uploaded_file = st.file_uploader(f"Загрузите CSV-файл с отзывами (колонка {requirement} обязательна)", type=["csv"])

if uploaded_file is not None:
    with st.spinner("Получение файла..."):
        df = pd.read_csv(uploaded_file)
    
    if requirement not in df.columns:
        st.error(f"В файле нет колонки {requirement}!")
    else:
        st.markdown(
            '<div class="custom-success">Файл успешно загружен!</div>',
            unsafe_allow_html=True
        )
        st.write(" ")
        predictions = None
        if data_id is None:
            with st.spinner("Идёт классификация, это может занять некоторое время..."):
                predictions = predict_request(df[[requirement]])
                df["Sentiment"] = predictions
        else:
            predictions = df["predict"].apply(lambda x: "Positive" if x else "Negative")
            df["Sentiment"] = predictions
            df = df.drop(["predict"], axis=1)
        
        if predictions is not None:
            if data_id is None:
                st.markdown(
                    '<div class="custom-success">Метки предсказаны!</div>',
                    unsafe_allow_html=True
                )
                st.write(" ")

            with st.spinner("Создание CSV с метками..."):
                st.download_button(
                    label="Скачать результаты",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=f"result_{login}_{data_id}.csv" if data_id else f"result_{uploaded_file.name}.csv",
                    mime="text/csv"
                )

            st.subheader("Распределение предсказаний")
            with st.spinner("Анализируем..."):
                fig1, ax1 = plt.subplots()
                df["Sentiment"].value_counts().plot(kind="pie", colors=["#A476F3", "#FFFFFF"], autopct="%1.1f%%", startangle=90, ax=ax1)
                ax1.set_ylabel("")
                st.pyplot(fig1)

            st.subheader("Частотность слов в положительных отзывах")
            with st.spinner("Анализируем..."):
                word_counts = pd.Series([word for word in " ".join(df[df["Sentiment"] == "Positive"][requirement].apply(preprocess_text)).split() if word not in STOPWORDS_RU]).value_counts()[:10]
                fig2, ax2 = plt.subplots()
                word_counts.plot(kind="barh", color="#A476F3", ax=ax2)
                st.pyplot(fig2)

            st.subheader("Частотность слов в отрицательных отзывах")
            with st.spinner("Анализируем..."):
                word_counts = pd.Series([word for word in " ".join(df[df["Sentiment"] == "Negative"][requirement].apply(preprocess_text)).split() if word not in STOPWORDS_RU]).value_counts()[:10]
                fig3, ax3 = plt.subplots()
                word_counts.plot(kind="barh", color="#A476F3", ax=ax3)
                st.pyplot(fig3)

            st.subheader("Топ биграмм в положительных отзывах")
            with st.spinner("Анализируем..."):
                top_bigrams = get_top_bigrams(df[df["Sentiment"] == "Positive"][requirement])
                fig4, ax4 = plt.subplots()
                top_bigrams.plot(kind="barh", color="#A476F3", ax=ax4)
                st.pyplot(fig4)

            st.subheader("Топ биграмм в отрицательных отзывах")
            with st.spinner("Анализируем..."):
                top_bigrams = get_top_bigrams(df[df["Sentiment"] == "Negative"][requirement])
                fig5, ax5 = plt.subplots()
                top_bigrams.plot(kind="barh", color="#A476F3", ax=ax5)
                st.pyplot(fig5)
