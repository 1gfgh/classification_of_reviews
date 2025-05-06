import os
import asyncio
import datetime
from io import BytesIO
from contextlib import asynccontextmanager
from typing import Annotated, List, Tuple
import logging
from pathlib import Path
import numpy as np
import asyncpg
import boto3
import pickle
import pandas as pd
import rsa
from dotenv import load_dotenv
import uvicorn

from fastapi import FastAPI, HTTPException, UploadFile, Form, File, Depends
from asyncpg import Pool
from rsa import decrypt, PrivateKey
import constants
from parsers.parser_must import parser_must
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=log_dir / "backend_logs.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
pool: Pool = None
app = FastAPI()

try:
    logger.info("Loading base models")
    session = boto3.session.Session()
    s3 = session.client(
        service_name="s3",
        endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=os.getenv("access_key"),
        aws_secret_access_key=os.getenv("secret_access_key")
    )
    buffer = BytesIO()
    s3.download_fileobj("classification.reviews", "model_wb.pkl", buffer)
    buffer.seek(0)
    model_wb = pickle.load(buffer)
    buffer.close()
    buffer = BytesIO()
    s3.download_fileobj("classification.reviews", "model_lamoda.pkl", buffer)
    buffer.seek(0)
    model_lamoda = pickle.load(buffer)
    buffer.close()
    buffer = BytesIO()
    s3.download_fileobj("classification.reviews", "model_mustapp.pkl", buffer)
    buffer.seek(0)
    model_mustapp = pickle.load(buffer)
    buffer.close()
    buffer = BytesIO()
    s3.download_fileobj("classification.reviews", "model_wb_and_lamoda.pkl", buffer)
    buffer.seek(0)
    model_both = pickle.load(buffer)
    buffer.close()
    model_user = None
    logger.info("Models loaded successfully")
except Exception as error:
    logger.error(f"Error loading models: {str(error)}")
    raise


async def get_connection():
    async with pool.acquire() as connection:
        yield connection


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    global pool
    try:
        pool = await asyncpg.create_pool(
            dsn=os.getenv("DSN"),
            min_size=5,
            max_size=20
        )
        logger.info("Database pool created successfully")
        yield
    except Exception as error:
        logger.error(f"Error creating database pool: {str(error)}")
        raise
    finally:
        await pool.close()
        logger.info("Database pool closed")


app.router.lifespan_context = lifespan


@app.post("/register")
async def register(
        name: Annotated[str, Form()],
        login: Annotated[str, Form()],
        password: Annotated[UploadFile, File()],
        db=Depends(get_connection)
) -> bool:
    logger.info(f"Registration attempt for user: {login}")
    read_password = await password.read()
    user = await db.fetchrow(
        "SELECT * FROM classification_reviews.users WHERE login = $1",
        login)
    if user is None:
        await db.execute(
            """
            INSERT INTO classification_reviews.users (name, login, password)
            VALUES ($1, $2, $3)
            """,
            name, login, read_password
        )
        logger.info(f"User {login} registered successfully")
        return True
    logger.warning(f"Registration failed - login {login} already in use")
    raise HTTPException(status_code=423, detail="Login already in use")


@app.post("/login")
async def login(
        login: Annotated[str, Form()],
        password: Annotated[UploadFile, File()],
        db=Depends(get_connection)
) -> bool:
    logger.info(f"Login attempt for user: {login}")
    user = await db.fetchrow(
        "SELECT * FROM classification_reviews.users WHERE login = $1",
        login)
    if user is None:
        logger.warning(f"Login failed - user {login} not found")
        raise HTTPException(status_code=404, detail="Login not found")
    pem_key = os.getenv("PRIVATE_KEY").encode()
    privkey = PrivateKey.load_pkcs1(pem_key)
    read_password = await password.read()
    read_password = decrypt(read_password, privkey)
    correct_password = decrypt(user["password"], privkey)
    result = (read_password == correct_password)
    if result:
        logger.info(f"User {login} logged in successfully")
    else:
        logger.warning(f"Login failed - incorrect password for user {login}")
    return result


async def predict_async(
        model_name: str,
        data: pd.Series,
        login: str = None
) -> np.ndarray:
    loop = asyncio.get_running_loop()

    async def get_model():
        match model_name:
            case "goods":
                return model_wb
            case "clothes":
                return model_lamoda
            case "films":
                return model_mustapp
            case "goods-and-clothes":
                return model_both
            case _:
                try:
                    model_id = int(model_name)
                    if model_id <= 0:
                        logger.warning(
                            f"Invalid model number: {model_id} - must be positive")
                        raise HTTPException(
                            status_code=422, detail="Model number must be positive")
                except ValueError:
                    logger.warning(
                        f"Invalid model format: {model_name} - must be a number")
                    raise HTTPException(
                        status_code=422, detail="Model must be a number")

                try:
                    return await download_model_from_s3(login, model_id)
                except Exception as error:
                    logger.error(
                        f"Error downloading model from S3: {str(error)}")
                    raise HTTPException(
                        status_code=500, detail=f"Error downloading model from S3: {str(error)}")

    model = await get_model()
    return await loop.run_in_executor(None, lambda: model.predict(data))


async def download_model_from_s3(login: str, model_id: int):
    session = boto3.session.Session()
    s3 = session.client(
        service_name="s3",
        endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=os.getenv("access_key"),
        aws_secret_access_key=os.getenv("secret_access_key")
    )
    buffer = BytesIO()
    s3.download_fileobj("classification.reviews",
                        f"{login}_{model_id}.pkl", buffer)
    buffer.seek(0)
    user_model = pickle.load(buffer)
    buffer.close()
    return user_model


@app.post("/predict/{data_type}/{model}")
async def get_predict(
        model: str,
        data_type: str,
        login: Annotated[str, Form()],
        data_csv: Annotated[UploadFile, File()],
        db=Depends(get_connection)
) -> int:
    logger.info(
        f"Prediction request from user {login} using model {model} and data type {data_type}")
    user = await db.fetchrow("SELECT * FROM classification_reviews.users WHERE login = $1", login)
    if user is None:
        logger.warning(f"Prediction failed - user {login} not found")
        raise HTTPException(status_code=404, detail="Login not found")

    content = await data_csv.read()
    try:
        match data_type:
            case "csv":
                data = pd.read_csv(BytesIO(content))
            case "excel":
                data = pd.read_excel(BytesIO(content))
            case _:
                logger.warning(f"Invalid data type: {data_type}")
                raise HTTPException(
                    status_code=404, detail="Data type not found")
    except Exception as error:
        logger.error(f"Error reading {data_type} file: {str(error)}")
        raise HTTPException(
            status_code=400, detail=f"Error reading {data_type} file: {str(error)}")

    if "Review" not in data.columns:
        logger.warning("Review column not found in input data")
        raise HTTPException(status_code=422, detail="Review column not found")

    try:
        y_pred = await predict_async(model, data["Review"], login)
        if model.isdigit():
            model = f"{login}_{model}"
    except Exception as error:
        logger.error(f"Error during prediction: {str(error)}")
        raise HTTPException(
            status_code=500, detail=f"Prediction error: {str(error)}")

    data["predict"] = y_pred
    query = """
            INSERT INTO classification_reviews.predicts (owner, used_model, predict_date) VALUES
            ($1, $2, $3)
            RETURNING id;
            """
    predict_id = await db.fetchval(query, user["login"], model, datetime.date.today())

    csv_buffer = BytesIO()
    data.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    try:
        session = boto3.session.Session()
        s3 = session.client(
            service_name="s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=os.getenv("access_key"),
            aws_secret_access_key=os.getenv("secret_access_key")
        )
        s3.upload_fileobj(csv_buffer, "classification.reviews",
                          f"{user['login']}_{predict_id}.csv")
        logger.info(
            f"Prediction results uploaded to S3 for user {login}, predict_id {predict_id}")
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error saving results: {str(e)}")

    return predict_id


@app.post("/predict_by_link/{parser}/{model}")
async def predict_by_link(
    model: str,
    parser: str,
    link: Annotated[str, Form()],
    login: Annotated[str, Form()],
    db=Depends(get_connection)
) -> int:
    logger.info(
        f"Prediction request from user {login} using model {model} and link {link}")
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
    if user is None:
        logger.warning(f"Prediction failed - user {login} not found")
        raise HTTPException(status_code=404, detail="Login not found")
    try:
        match parser:
            case "mustapp":
                data = await parser_must(link)
                logger.info(f"Data from mustapp parser: {data.head()}")
            case _:
                logger.warning(f"Invalid parser: {parser}")
                raise HTTPException(status_code=404, detail="Parser not found")
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Prediction error: {str(e)}")
    y_pred = await predict_async(model, data["Review"], login)
    query = """
            INSERT INTO classification_reviews.predicts (owner, used_model, predict_date) VALUES
            ($1, $2, $3)
            RETURNING id;
            """
    predict_id = await db.fetchval(query, user["login"], model, datetime.date.today())

    csv_buffer = BytesIO()
    data.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    try:
        session = boto3.session.Session()
        s3 = session.client(
            service_name="s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=os.getenv("access_key"),
            aws_secret_access_key=os.getenv("secret_access_key")
        )
        s3.upload_fileobj(csv_buffer, "classification.reviews",
                          f"{user['login']}_{predict_id}.csv")
        logger.info(
            f"Prediction results uploaded to S3 for user {login}, predict_id {predict_id}")
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error saving results: {str(e)}")

    return predict_id


@app.post("/get_history")
async def get_history(
    login: Annotated[str, Form()],
    db=Depends(get_connection)
) -> List[Tuple[int, datetime.date]]:
    logger.info(f"History request from user: {login}")
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
    if user is None:
        logger.warning(f"History request failed - user {login} not found")
        raise HTTPException(status_code=404, detail="Login not found")

    query = """ Select id, predict_date from classification_reviews.predicts
            Where owner = $1
            """
    predicts = await db.fetch(query, login)
    logger.info(f"Retrieved {len(predicts)} predictions for user {login}")
    return [(predict["id"], predict["predict_date"]) for predict in predicts]


async def logreg_fit(data: pd.DataFrame):
    logreg_model = Pipeline([
        ('tf', TfidfVectorizer()),
        ('clf', LogisticRegression(random_state=42))
    ])
    logreg_model.fit(data["Review"], data["Sentiment"])
    return logreg_model


@app.post("/fit/{type}")
async def fit(
    type: str,
    data: Annotated[UploadFile, File()],
    login: Annotated[str, Form()],
    model_name: Annotated[str, Form()],
    db=Depends(get_connection)
) -> int:
    logger.info(f"Fitting request for type: {type}")
    content = await data.read()
    try:
        match type:
            case "csv":
                data = pd.read_csv(BytesIO(content))
                if "Review" not in data.columns or "Sentiment" not in data.columns:
                    logger.warning(
                        "CSV file missing required columns: Review and/or Sentiment")
                    raise HTTPException(
                        status_code=400,
                        detail="CSV file must contain 'Review' and 'Sentiment' columns")
                model_user = await logreg_fit(data)
                logger.info("User model fitted successfully from input data")
            case "pkl":
                model_user = pickle.loads(content)
                logger.info("User model loaded successfully from pkl file")
            case _:
                logger.warning(f"Invalid data type: {type}")
                raise HTTPException(
                    status_code=404, detail="Data type not found")
    except Exception as e:
        logger.error(f"Error reading {type} file: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Error reading {type} file: {str(e)}")

    if model_user is None:
        logger.warning("User model not loaded")
        raise HTTPException(status_code=400, detail="Failed to load model")

    query = """
            INSERT INTO classification_reviews.models (owner, model_name) VALUES
            ($1, $2)
            RETURNING id;
            """
    model_id = await db.fetchval(query, login, model_name)
    buffer = BytesIO()
    pickle.dump(model_user, buffer)
    buffer.seek(0)
    try:
        session = boto3.session.Session()
        s3 = session.client(
            service_name="s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=os.getenv("access_key"),
            aws_secret_access_key=os.getenv("secret_access_key")
        )
        s3.upload_fileobj(buffer, "classification.reviews",
                          f"{login}_{model_id}.pkl")
        logger.info(
            f"Model uploaded to S3 for user {login}, model_id {model_id}")
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error saving results: {str(e)}")
    return model_id


@app.get("/get_models")
async def get_models(
    login: Annotated[str, Form()],
    db=Depends(get_connection)
) -> List[Tuple[int, str]]:
    logger.info(f"Models request from user: {login}")
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
    if user is None:
        logger.warning(f"Models request failed - user {login} not found")
        raise HTTPException(status_code=404, detail="Login not found")

    query = """
            SELECT id, model_name FROM classification_reviews.models
            WHERE owner = $1
            """
    models = await db.fetch(query, login)
    return [(model["id"], model["model_name"]) for model in models]


if __name__ == "__main__":
    logger.info("Starting server")
    uvicorn.run(app, host=constants.IP, port=constants.PORT)
