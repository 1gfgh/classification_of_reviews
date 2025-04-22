from fastapi import FastAPI, HTTPException, UploadFile, Form, File, Body, Depends
from fastapi.responses import FileResponse
from fastapi.logger import logger
import uvicorn
import constants
import asyncpg
import asyncio
from asyncpg import Pool
from contextlib import asynccontextmanager
from typing import Annotated
from rsa import decrypt


pool: Pool = None
app = FastAPI()


async def get_connection():
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(
        dsn=constants.DSN,
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
    user = await db.fetchrow("Select * from classification_review.users where login = $1", login)
    if user is None: 
        await db.execute(
            """
            INSERT INTO classification_review.users (name, login, password) VALUES
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
    user = await db.fetchrow("Select * from classification_review.users where login = $1", login)
    if user is None: 
        raise HTTPException(status_code=404, detail="Login not found")
    read_password = await password.read()
    read_password = decrypt(read_password, constants.privkey)
    correct_password = decrypt(user["password"], constants.privkey)
    return (read_password == correct_password)


if __name__ == "__main__":
    uvicorn.run(app, host=constants.IP, port=constants.PORT)