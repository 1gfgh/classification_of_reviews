from fastapi import FastAPI, HTTPException, UploadFile, Form, File, Body, Depends
from fastapi.responses import FileResponse
from fastapi.logger import logger
import uvicorn
from io import BytesIO
import constants
import asyncpg
import asyncio
from asyncpg import Pool
from contextlib import asynccontextmanager
from typing import Annotated
from rsa import decrypt, PrivateKey
import pickle
import pandas as pd
import os
import boto3
from dotenv import load_dotenv


load_dotenv()
pool: Pool = None
app = FastAPI()
with open(constants.path_model_wb, "rb") as f:
    model_wb = pickle.load(f)


async def get_connection():
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(
        dsn=os.getenv("DSN"),
        min_size=5,
        max_size=20
    )
    yield
    await pool.close()


app.router.lifespan_context = lifespan


@app.post("/register")
async def register(
        name: Annotated[str, Form()],
        login: Annotated[str, Form()],
        password: Annotated[UploadFile, File()],
        db=Depends(get_connection)
    ) -> bool:
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
        return True
    else:
        raise HTTPException(status_code=423, detail="Login already in use")
    

@app.get("/login")
async def login(
        login: Annotated[str, Form()],
        password: Annotated[UploadFile, File()],
        db=Depends(get_connection)
    ) -> bool:
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
    if user is None: 
        raise HTTPException(status_code=404, detail="Login not found")
    pem_key = os.getenv("PRIVATE_KEY").encode()
    privkey = PrivateKey.load_pkcs1(pem_key)
    read_password = await password.read()
    read_password = decrypt(read_password, privkey)
    correct_password = decrypt(user["password"], privkey)
    return (read_password == correct_password)


async def predict_async(model, data):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: model.predict(data))


@app.post("/predict/csv/{model}")
async def get_predict(
        model: str,
        login: Annotated[str, Form()],
        data_csv: Annotated[UploadFile, File()], 
        db=Depends(get_connection)
    ) -> int:
    user = await db.fetchrow("Select * from classification_reviews.users where login = $1", login)
    if user is None: 
        raise HTTPException(status_code=404, detail="Login not found")
    content = await data_csv.read()
    data = pd.read_csv(BytesIO(content))
    if "Review" not in data.columns:
        raise HTTPException(status_code=422, detail="Review column not found")
    match model:
        case "wb":
            y_pred = await predict_async(model_wb, data["Review"])
        case _:
            raise HTTPException(status_code=404, detail="Model not found")
    data["predict"] = y_pred
    query = """
            INSERT INTO classification_reviews.predicts (owner, used_model) VALUES
            ($1, $2)
            RETURNING id;
            """
    predict_id = await db.fetchval(query, user["login"], model)

    csv_buffer = BytesIO()
    data.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    session = boto3.session.Session()
    s3 = session.client(
        service_name="s3",
        endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=os.getenv("access_key"),            
        aws_secret_access_key=os.getenv("secret_access_key")       
    )
    s3.upload_fileobj(csv_buffer, "classification.reviews", f"{user['login']}_{predict_id}.csv")

    return predict_id



if __name__ == "__main__":
    uvicorn.run(app, host=constants.IP, port=constants.PORT)