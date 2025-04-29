import os
import asyncio
import datetime
from io import BytesIO
from contextlib import asynccontextmanager
from typing import Annotated, List, Tuple
import logging
from pathlib import Path

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
    with open(constants.path_model_wb, "rb") as f:
        model_wb = pickle.load(f)
    with open(constants.path_model_lamoda, "rb") as f:
        model_lamoda = pickle.load(f)
    with open(constants.path_model_mustapp, "rb") as f:
        model_mustapp = pickle.load(f)
    with open(constants.path_model_both, "rb") as f:
        model_both = pickle.load(f)
    logger.info("Models loaded successfully")
except Exception as e:
    logger.error(f"Error loading models: {str(e)}")
    raise

async def get_connection():
    async with pool.acquire() as conn:
        yield conn

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    try:
        pool = await asyncpg.create_pool(
            dsn=os.getenv("DSN"),
            min_size=5,
            max_size=20
        )
        logger.info("Database pool created successfully")
        yield
    except Exception as e:
        logger.error(f"Error creating database pool: {str(e)}")
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
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
    if user is None: 
        await db.execute(
            """
            INSERT INTO classification_reviews.users (name, login, password) VALUES
            ($1, $2, $3)
            """,
            name, login, read_password
        )
        logger.info(f"User {login} registered successfully")
        return True
    else:
        logger.warning(f"Registration failed - login {login} already in use")
        raise HTTPException(status_code=423, detail="Login already in use")

@app.post("/login")
async def login(
        login: Annotated[str, Form()],
        password: Annotated[UploadFile, File()],
        db=Depends(get_connection)
    ) -> bool:
    logger.info(f"Login attempt for user: {login}")
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
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

async def predict_async(model, data):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: model.predict(data))

@app.post("/predict/{data_type}/{model}")
async def get_predict(
        model: str,
        data_type: str,
        login: Annotated[str, Form()],
        data_csv: Annotated[UploadFile, File()], 
        db=Depends(get_connection)
    ) -> int:
    logger.info(f"Prediction request from user {login} using model {model} and data type {data_type}")
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
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
                raise HTTPException(status_code=404, detail="Data type not found")
    except Exception as e:
        logger.error(f"Error reading {data_type} file: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error reading {data_type} file: {str(e)}")
        
    if "Review" not in data.columns:
        logger.warning("Review column not found in input data")
        raise HTTPException(status_code=422, detail="Review column not found")
    
    try:
        match model:
            case "goods":
                y_pred = await predict_async(model_wb, data["Review"])
            case "clothes":
                y_pred = await predict_async(model_lamoda, data["Review"])
            case "films":
                y_pred = await predict_async(model_mustapp, data["Review"])
            case "goods-and-clothes":
                y_pred = await predict_async(model_both, data["Review"])
            case _:
                logger.warning(f"Invalid model type: {model}")
                raise HTTPException(status_code=404, detail="Model not found")
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

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
        s3.upload_fileobj(csv_buffer, "classification.reviews", f"{user['login']}_{predict_id}.csv")
        logger.info(f"Prediction results uploaded to S3 for user {login}, predict_id {predict_id}")
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving results: {str(e)}")

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

if __name__ == "__main__":
    logger.info("Starting server")
    uvicorn.run(app, host=constants.IP, port=constants.PORT)