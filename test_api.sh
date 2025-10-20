#!/bin/bash
# Скрипт для тестирования API endpoints

echo "🧪 Тестирование ML Data Pipeline API"
echo "======================================"
echo ""

API_URL="http://localhost:8000"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для тестирования endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    echo -e "${YELLOW}Тест: $name${NC}"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ OK${NC} (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $http_code)"
        echo "$body"
    fi
    
    echo ""
}

# Проверка что сервер запущен
echo "1️⃣  Проверка подключения..."
if ! curl -s "$API_URL" > /dev/null 2>&1; then
    echo -e "${RED}❌ API не доступен на $API_URL${NC}"
    echo "💡 Запустите сервер: docker-compose up -d"
    echo "   или: python -m uvicorn src.api:app"
    exit 1
fi
echo -e "${GREEN}✅ API доступен${NC}"
echo ""

# Тесты
test_endpoint "Главная страница" "GET" "/"

test_endpoint "Health Check" "GET" "/health"

test_endpoint "Классификация текстов" "POST" "/classify" \
    '{"texts": ["передать показания счетчика", "оплатить питание"]}'

test_endpoint "Список версий" "GET" "/versions"

test_endpoint "Статистика компонентов" "GET" "/stats"

# Тест загрузки файла (если есть тестовый файл)
if [ -f "test_logs.csv" ]; then
    echo -e "${YELLOW}Тест: Загрузка файла${NC}"
    upload_response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/upload" \
        -F "file=@test_logs.csv")
    
    upload_code=$(echo "$upload_response" | tail -n1)
    upload_body=$(echo "$upload_response" | head -n-1)
    
    if [ "$upload_code" -eq 200 ]; then
        echo -e "${GREEN}✅ OK${NC} (HTTP $upload_code)"
        echo "$upload_body" | jq '.'
        
        # Получаем путь к файлу
        file_path=$(echo "$upload_body" | jq -r '.path')
        
        echo ""
        echo -e "${YELLOW}Тест: Обработка файла${NC}"
        
        process_response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/process" \
            -H "Content-Type: application/json" \
            -d "{\"file_path\": \"$file_path\", \"balance_domains\": true, \"augment\": false, \"create_version\": true}")
        
        process_code=$(echo "$process_response" | tail -n1)
        process_body=$(echo "$process_response" | head -n-1)
        
        if [ "$process_code" -eq 200 ]; then
            echo -e "${GREEN}✅ OK${NC} (HTTP $process_code)"
            echo "$process_body" | jq '.'
        else
            echo -e "${RED}❌ FAIL${NC} (HTTP $process_code)"
            echo "$process_body"
        fi
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $upload_code)"
        echo "$upload_body"
    fi
    
    echo ""
fi

# Итоговое резюме
echo "======================================"
echo -e "${GREEN}🎉 Тестирование завершено${NC}"
echo "======================================"
echo ""
echo "Для детального просмотра API:"
echo "   http://localhost:8000/docs"
echo ""

