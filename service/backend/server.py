from fastapi import FastAPI, HTTPException, UploadFile, Form, File, Body, Depends
from fastapi.responses import FileResponse
from fastapi.logger import logger
import uvicorn
import constants
import asyncpg
import asyncio
from asyncpg import Pool
from contextlib import asynccontextmanager


pool: Pool = None
app = FastAPI()


async def get_connection():
    async with pool.acquire() as conn:
        yield conn


async def get_pool() -> Pool:
    return await asyncpg.create_pool(
        dsn=constants.DSN,
        min_size=5, 
        max_size=20
    )


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



@app.get("/test_db")
async def test_db(db=Depends(get_connection)):
    users = await db.fetch("SELECT * FROM classification_review.users")
    return [dict(user) for user in users]


if __name__ == "__main__":
    uvicorn.run(app, host=constants.IP, port=constants.PORT)