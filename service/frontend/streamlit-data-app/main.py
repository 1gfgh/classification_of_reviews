import streamlit as st
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

STOPWORDS_RU = get_stop_words('russian')

def placeholder(data):
    # Имитация работы API: возвращает случайные метки 0/1 с задержкой
    time.sleep(5)
    y_fake = np.random.randint(0, 2, len(data))
    return ["Positive" if pred_elem else "Negative" for pred_elem in y_fake]

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

st.title("Классификатор отзывов")

data_id = st.query_params.get("data_id", None)
uploaded_file = None
requirement = "Review"
if data_id:
    st.write("Даня работает над этим")
    # Загружаем данные по data_id
    # Показываем предсказания
else:
    uploaded_file = st.file_uploader(f"Загрузите CSV-файл с отзывами (колонка {requirement} обязательна)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    if requirement not in df.columns:
        st.error(f"В файле нет колонки {requirement}!")
    else:
        st.markdown(
            '<div class="custom-success">Файл успешно загружен!</div>',
            unsafe_allow_html=True
        )

        st.write(" ")

        with st.spinner("Идёт классификация это может занять некоторое время..."):
            predictions = placeholder(df[requirement].tolist())
            df["Sentiment"] = predictions
        
        st.markdown(
            '<div class="custom-success">Метки предсказаны!</div>',
            unsafe_allow_html=True
        )
        st.write(" ")

        with st.spinner("Создание CSV с метками..."):
            st.download_button(
                label="Скачать результаты",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"result_{uploaded_file.name}.csv",
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
