FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r parsers/requirements.txt

ENV PYTHONUNBUFFERED=1

EXPOSE 1233

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "1233"]