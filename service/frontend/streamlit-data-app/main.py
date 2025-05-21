import logging
from pathlib import Path
from collections import Counter
import itertools
from io import StringIO
import os
import re
import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from stop_words import get_stop_words
from nltk import bigrams
from dotenv import load_dotenv

st.set_page_config(
    page_title="Rate me!", page_icon="🏆", initial_sidebar_state="collapsed"
)

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=log_dir / "streamlit.log",
    level=logging.INFO,
    format="[ %(asctime)s %(levelname)s ] %(message)s",
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
STOPWORDS_RU = get_stop_words("russian")


def get_csv_from_s3(csv_id):
    """Trying to get CSV from Yandex Storage by csv_id and user login"""
    logger.info(
        "Trying to get CSV fron object storage for user %s, csv_id %s", login, csv_id
    )
    answer_result_csv = requests.get(f"{YANDEX_S3}/{login}_{csv_id}.csv", timeout=600)
    if answer_result_csv.status_code == 200:
        logger.info("CSV received successfully")
        answer_result_csv.encoding = "utf-8"
        return StringIO(answer_result_csv.text)
    if answer_result_csv.status_code == 404:
        logger.error("File %s_%s.csv not found in object storage", login, csv_id)
        st.error(f"Файл {login}_{csv_id}.csv не найден")
    else:
        logger.error("Object storage error")
        st.error("Yandex storage не отвечает O_o...")
    return None


def predict_request(reviews):
    """Trying to get labels from API's models"""
    logger.info("Trying to get predict (%s) for user %s", model, login)
    answer_predict = requests.post(
        f"{URL}/predict/csv/{model}",
        data={"login": f"{login}"},
        files={"data_csv": ("input.csv", reviews.to_csv(index=False))},
        timeout=600,
    )
    if answer_predict.status_code == 200:
        logger.info("Predict received successfully")
        result = pd.read_csv(get_csv_from_s3(answer_predict.text))
        result["predict"] = result["predict"].apply(
            lambda x: "Positive" if x else "Negative"
        )
        return result["predict"].tolist()
    if answer_predict.status_code == 404:
        logger.error("There is no user with this login, or the model is incorrect.")
        st.error(
            "Не существует пользователя с таким логином, либо указана неверная модель"
        )
    else:
        logger.error("Critical error on server side")
        st.error("Критическая серверная ошибка")
    return None


def get_top_bigrams(texts, n=10):
    """Top n bigrams"""
    all_bigrams = list(itertools.chain(*[bigrams(str(text).split()) for text in texts]))
    bigram_counts = Counter(all_bigrams)
    return pd.Series(dict(bigram_counts.most_common(n)))


def preprocess_text(text):
    """Lower text and punkt. clear"""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text


def selector_formatter(user_models_map):
    """Mapping text to basic and user models"""

    def wrapper(raw_input):
        if raw_input == "goods":
            return "Товары"
        if raw_input == "clothes":
            return "Одежда"
        if raw_input == "films":
            return "Фильмы"
        if raw_input == "goods-and-clothes":
            return "Товары и одежда"
        return user_models_map[raw_input]

    return wrapper


st.markdown(
    """
    <style>
        .custom-success {
            border-left: 4px solid #A476F3;
            padding: 1em;
            background-color: #EEE4FF;
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("Классификатор отзывов")

if data_id:
    logger.info("Get analys mode")
    with st.spinner("Получение файла..."):
        uploaded_file = get_csv_from_s3(data_id)
else:
    logger.info("Predict and get analys mode")
    if not model:
        user_models = {}
        if login != "guest":
            logger.info("Trying to get user models list")
            answer = requests.post(
                f"{URL}/get_models", data={"login": f"{login}"}, timeout=600
            )
            if answer.status_code == 200:
                data = answer.json()
                for [model_id, model_name] in data:
                    user_models[model_id] = model_name
            else:
                logger.info("Error while getting user models")
        model = st.selectbox(
            "Выберите модель",
            ("goods", "clothes", "films", "goods-and-clothes")
            + tuple(user_models.keys()),
            format_func=selector_formatter(user_models),
        )
    uploaded_file = st.file_uploader(
        f"Загрузите CSV-файл с отзывами (колонка {requirement} обязательна)",
        type=["csv", "xls", "xlsx", "xlsm", "xlsb", "odf", "ods", "odt"],
    )

if uploaded_file is not None:
    logger.info("Converting to DataFrame")
    with st.spinner("Получение файла..."):
        df = pd.read_csv(uploaded_file)

    if requirement not in df.columns:
        logger.error("CSV column «Review» require")
        st.error(f"В файле нет колонки {requirement}!")
    else:
        st.markdown(
            '<div class="custom-success">Файл успешно загружен!</div>',
            unsafe_allow_html=True,
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
                    unsafe_allow_html=True,
                )
                st.write(" ")

            logger.info("Result summarize (csv with labels)")
            with st.spinner("Создание CSV с метками..."):
                st.download_button(
                    label="Скачать результаты",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=(
                        f"result_{login}_{data_id}.csv"
                        if data_id
                        else f"result_{uploaded_file.name}.csv"
                    ),
                    mime="text/csv",
                )

            logger.info("Analys result")
            if not df.empty:
                st.subheader("Распределение предсказаний")
                with st.spinner("Анализируем..."):
                    fig1, ax1 = plt.subplots()
                    df["Sentiment"].value_counts().plot(
                        kind="pie",
                        colors=["#A476F3", "#FFFFFF"],
                        autopct="%1.1f%%",
                        startangle=90,
                        ax=ax1,
                    )
                    ax1.set_ylabel("")
                    st.pyplot(fig1)

                if not df[df["Sentiment"] == "Positive"][requirement].empty:
                    st.subheader("Частотность слов в положительных отзывах")
                    with st.spinner("Анализируем..."):
                        word_counts = pd.Series(
                            [
                                word
                                for word in " ".join(
                                    df[df["Sentiment"] == "Positive"][
                                        requirement
                                    ].apply(preprocess_text)
                                ).split()
                                if word not in STOPWORDS_RU
                            ]
                        ).value_counts()[:10]
                        fig2, ax2 = plt.subplots()
                        word_counts.plot(kind="barh", color="#A476F3", ax=ax2)
                        st.pyplot(fig2)

                if not df[df["Sentiment"] == "Negative"][requirement].empty:
                    st.subheader("Частотность слов в отрицательных отзывах")
                    with st.spinner("Анализируем..."):
                        word_counts = pd.Series(
                            [
                                word
                                for word in " ".join(
                                    df[df["Sentiment"] == "Negative"][
                                        requirement
                                    ].apply(preprocess_text)
                                ).split()
                                if word not in STOPWORDS_RU
                            ]
                        ).value_counts()[:10]
                        fig3, ax3 = plt.subplots()
                        word_counts.plot(kind="barh", color="#A476F3", ax=ax3)
                        st.pyplot(fig3)

                if not df[df["Sentiment"] == "Positive"][requirement].empty:
                    st.subheader("Топ биграмм в положительных отзывах")
                    with st.spinner("Анализируем..."):
                        top_bigrams = get_top_bigrams(
                            df[df["Sentiment"] == "Positive"][requirement]
                        )
                        fig4, ax4 = plt.subplots()
                        top_bigrams.plot(kind="barh", color="#A476F3", ax=ax4)
                        st.pyplot(fig4)

                if not df[df["Sentiment"] == "Negative"][requirement].empty:
                    st.subheader("Топ биграмм в отрицательных отзывах")
                    with st.spinner("Анализируем..."):
                        top_bigrams = get_top_bigrams(
                            df[df["Sentiment"] == "Negative"][requirement]
                        )
                        fig5, ax5 = plt.subplots()
                        top_bigrams.plot(kind="barh", color="#A476F3", ax=ax5)
                        st.pyplot(fig5)
