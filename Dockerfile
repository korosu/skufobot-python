# Используем официальный Python образ
FROM python:3.10-slim

# Устанавливаем системные зависимости для PostgreSQL
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем папку для логов
RUN mkdir -p /app/logs

# Копируем весь проект
COPY . .

# Команда запуска
CMD ["python", "run.py"]