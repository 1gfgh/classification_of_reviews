import logging
from pathlib import Path
import os
import streamlit as st
import requests
from dotenv import load_dotenv

st.set_page_config(
    page_title="User model", page_icon="⚙️", initial_sidebar_state="collapsed"
)

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

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=log_dir / "streamlit.log",
    level=logging.INFO,
    format="[ %(asctime)s %(levelname)s ] %(message)s",
)
logger_upload = logging.getLogger(__name__)

load_dotenv()
URL = os.getenv("BACKEND_URL")
login = st.query_params.get("login", None)

st.title("Загрузка пользовательской модели в систему")

if login is not None:
    model_name = st.text_input("Придумайте название для модели")
    if model_name:
        logger_upload.info("Waiting for user file")
        UPLOADED_FILE = st.file_uploader(
            "Загрузите модель или данные для обучения (Review и Sentiment обязательны)",
            type=["pkl", "csv"],
        )
        if UPLOADED_FILE is not None:
            with st.spinner("Отправка данных..."):
                answer = requests.post(
                    f"{URL}/fit/{UPLOADED_FILE.name.split('.')[-1]}",
                    data={"login": f"{login}", "model_name": f"{model_name}"},
                    files={"data": UPLOADED_FILE},
                    timeout=600,
                )
                if answer.status_code == 200:
                    logger_upload.info("New model created successfully")
                    st.markdown(
                        '<div class="custom-success">Модель загружена</div>',
                        unsafe_allow_html=True,
                    )
                elif answer.status_code == 400:
                    logger_upload.error(answer.json()["detail"])
                    st.error(
                        "Ошибка чтения, возможно, нет колонок Review или Sentiment"
                    )
                elif answer.status_code == 404:
                    logger_upload.error(answer.json()["detail"])
                    st.error("Неверный тип данных")
                else:
                    logger_upload.error("Critical error on server side")
                    st.error("Критическая серверная ошибка")
else:
    st.error("Сначала войдите в свой аккаунт")
