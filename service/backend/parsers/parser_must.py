import httpx
from fastapi import HTTPException
import pandas as pd
import math

BASE_URL = "https://mustapp.com/api/products"
headers = {"content-type": "application/json;v=1873", "accept-language": "ru"}
page_size = 20


async def parser_must(url: str) -> pd.DataFrame:
    """
    Args:
        url: expected url like https://mustapp.com/p/{num}
    Raises:
        HTTPException: the input url does not match the template
        HTTPException: an error occurred while parsing
    Returns:
        pd.DataFrame: DataFrame with one column of text data
    """
    url_splited = url.split("/")
    if url_splited[-3] == "mustapp.com" and url_splited[-2] == "p":
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/{url_splited[-1]}/watches?limit=1&with_reviews=true",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                reviews = {"Review": []}
                total_count = data["total"]
                total_pages = math.ceil(total_count / page_size)
                for page in range(total_pages):
                    response = await client.get(
                        f"{BASE_URL}/{url_splited[-1]}/watches?limit={page_size}&offset={page}&with_reviews=true",
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                    batch = data["watches"]
                    for user in batch:
                        reviews["Review"].append(user["review"]["body"])
                df = pd.DataFrame(reviews)
                return df
            except:
                raise HTTPException(status_code=400, detail="Mustapp parser error")
    else:
        raise HTTPException(
            status_code=400,
            detail="Incorrect string format (must parser expected https://mustapp.com/p/{num})",
        )
