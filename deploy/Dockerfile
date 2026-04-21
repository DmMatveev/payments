FROM python:3.13-slim

WORKDIR /code

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && uv pip install --system --no-cache .

COPY . .

ENV PYTHONPATH=/code/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
