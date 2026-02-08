FROM python:3.11-slim

WORKDIR /app

# Минимальные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаём директорию для БД
RUN mkdir -p /app/data

CMD ["python", "-m", "bot.main"]
