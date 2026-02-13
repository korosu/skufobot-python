-- init_tables.sql
-- Таблицы для SkufBot

-- Таблица подписчиков (аналог chat_subscriber)
CREATE TABLE IF NOT EXISTS chat_subscriber (
    chat_id BIGINT PRIMARY KEY,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица GIF
CREATE TABLE IF NOT EXISTS skuf_gif (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(255),
    day_of_week INTEGER
);

ALTER TABLE chat_subscriber ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_gif_day ON skuf_gif(day_of_week);
CREATE INDEX IF NOT EXISTS idx_gif_file_id ON skuf_gif(file_id);