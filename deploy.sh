#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "=============================="
echo "  KartochkaPRO - Deploy"
echo "=============================="
echo ""

# Определяем директорию скрипта (работает откуда угодно)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/5] Проверяю Docker..."

if ! command -v docker &> /dev/null; then
    echo "  -> Docker не найден, устанавливаю..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl
    curl -fsSL https://get.docker.com | sh
    echo "  -> Docker установлен"
fi

if ! docker compose version &> /dev/null; then
    echo "  -> Docker Compose не найден, устанавливаю..."
    apt-get update -qq
    apt-get install -y -qq docker-compose-plugin
fi

echo "  -> Docker $(docker --version | grep -oP '\d+\.\d+\.\d+')"
echo "  -> Compose $(docker compose version --short)"

echo ""
echo "[2/5] Проверяю .env..."

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo ""
        echo "  ОШИБКА: файл .env не найден!"
        echo ""
        echo "  Выполните:"
        echo "    cp .env.example .env"
        echo "    nano .env"
        echo ""
        echo "  Заполните BOT_TOKEN, OPENAI_API_KEY и ADMIN_IDS"
        echo ""
    else
        echo "  ОШИБКА: не найдены .env и .env.example"
        echo "  Убедитесь, что вы в директории проекта"
    fi
    exit 1
fi

# Проверяем что токены заполнены
source .env
if [ -z "${BOT_TOKEN:-}" ] || [ "$BOT_TOKEN" = "ваш-токен-от-BotFather" ]; then
    echo "  ОШИБКА: BOT_TOKEN не заполнен в .env"
    exit 1
fi
if [ -z "${OPENAI_API_KEY:-}" ] || [ "$OPENAI_API_KEY" = "ваш-ключ-от-proxyapi" ]; then
    echo "  ОШИБКА: OPENAI_API_KEY не заполнен в .env"
    exit 1
fi

echo "  -> .env OK"

echo ""
echo "[3/5] Создаю директорию данных..."
mkdir -p data
echo "  -> data/"

echo ""
echo "[4/5] Собираю Docker-образ..."
docker compose build --quiet 2>&1 | tail -5

echo ""
echo "[5/5] Запускаю бота..."

# Останавливаем старый контейнер если есть
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d

echo ""
echo "=============================="
echo "  Бот запущен!"
echo "=============================="
echo ""
echo "  Логи:        docker compose logs -f"
echo "  Перезапуск:  docker compose restart"
echo "  Остановка:   docker compose down"
echo "  Обновление:  docker compose up -d --build"
echo ""

# Показываем статус
docker compose ps
