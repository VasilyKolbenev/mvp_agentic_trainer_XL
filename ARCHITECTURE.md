# 🏗️ Архитектура локальных LLM

## Текущее состояние

Система уже поддерживает локальные LLM через OpenAI-совместимые API. Используется единый `LLMClient` с настраиваемыми `api_base` и `model`.

## Планируемые улучшения

### 1. **Адаптивные промпты (ModelPromptAdapter)**

```python
class ModelPromptAdapter:
    """Адаптирует промпты под специфику разных моделей"""
    
    ADAPTERS = {
        # OpenAI модели
        "gpt-4": {"system_role": "system", "max_tokens": 4096},
        "gpt-3.5-turbo": {"system_role": "system", "max_tokens": 4096},
        
        # Локальные модели
        "llama3.1": {
            "system_role": "system", 
            "max_tokens": 2048,
            "template": "### Instruction:\n{system}\n\n### Input:\n{user}\n\n### Response:",
            "stop_tokens": ["###", "\n\n"]
        },
        
        "mistral": {
            "system_role": "system",
            "template": "[INST] {system}\n{user} [/INST]",
            "max_tokens": 2048
        },
        
        "qwen": {
            "system_role": "system", 
            "template": "<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant",
            "stop_tokens": ["<|im_end|>"]
        }
    }
    
    def adapt_prompt(self, model: str, messages: List[Dict]) -> Dict:
        """Адаптирует промпт под конкретную модель"""
        # Логика адаптации промптов
        pass
```

### 2. **Автодетекция возможностей модели**

```python
class ModelCapabilityDetector:
    """Определяет возможности локальной модели"""
    
    async def detect_capabilities(self, client: LLMClient) -> Dict:
        """
        Тестирует модель на различных задачах:
        - Поддержка JSON ответов
        - Максимальная длина контекста  
        - Качество следования инструкциям
        - Поддержка system role
        """
        
        capabilities = {
            "supports_json": await self._test_json_output(client),
            "max_context": await self._test_context_length(client),
            "instruction_following": await self._test_instructions(client),
            "system_role": await self._test_system_role(client)
        }
        
        return capabilities
```

### 3. **Фоллбэк стратегии**

```python
class LLMFallbackManager:
    """Управляет фоллбэками между разными моделями"""
    
    def __init__(self, primary_client: LLMClient, fallback_clients: List[LLMClient]):
        self.primary = primary_client
        self.fallbacks = fallback_clients
        self.failure_count = 0
    
    async def chat_with_fallback(self, messages: List[Dict]) -> str:
        """
        Пытается выполнить запрос с фоллбэком:
        1. Локальная модель (быстро, бесплатно)
        2. OpenAI API (надежно, платно)
        """
        
        for client in [self.primary] + self.fallbacks:
            try:
                return await client.chat(messages)
            except Exception as e:
                logger.warning(f"Model {client.model} failed: {e}")
                continue
        
        raise Exception("All models failed")
```

### 4. **Конфигурация моделей**

```python
# config.py расширения
@dataclass 
class ModelConfig:
    name: str
    api_base: str
    api_key: str
    capabilities: Dict[str, Any]
    prompt_template: Optional[str] = None
    max_tokens: int = 2048
    temperature_range: Tuple[float, float] = (0.1, 1.0)

class MultiModelSettings(Settings):
    # Основная модель
    primary_model: ModelConfig
    
    # Фоллбэк модели
    fallback_models: List[ModelConfig] = []
    
    # Специализированные модели для задач
    classification_model: Optional[ModelConfig] = None
    augmentation_model: Optional[ModelConfig] = None
    
    # Настройки фоллбэка
    fallback_enabled: bool = True
    max_retries: int = 3
    timeout_seconds: int = 30
```

### 5. **Мониторинг производительности**

```python
class ModelPerformanceMonitor:
    """Отслеживает производительность разных моделей"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
    
    def log_request(self, model: str, task: str, 
                   latency: float, success: bool, tokens: int):
        """Логирует метрики запроса"""
        self.metrics[model].append({
            "task": task,
            "latency": latency, 
            "success": success,
            "tokens": tokens,
            "timestamp": datetime.now()
        })
    
    def get_model_stats(self, model: str) -> Dict:
        """Возвращает статистику модели"""
        data = self.metrics[model]
        if not data:
            return {}
            
        return {
            "avg_latency": np.mean([d["latency"] for d in data]),
            "success_rate": np.mean([d["success"] for d in data]),
            "total_tokens": sum([d["tokens"] for d in data]),
            "requests_count": len(data)
        }
```

## Поэтапная реализация

### Фаза 1: Улучшение совместимости
- [ ] Адаптивные промпты для популярных локальных моделей
- [ ] Автодетекция возможностей модели
- [ ] Улучшенная обработка ошибок

### Фаза 2: Мульти-модельная архитектура  
- [ ] Поддержка нескольких моделей одновременно
- [ ] Фоллбэк между локальными и облачными моделями
- [ ] Специализация моделей по задачам

### Фаза 3: Оптимизация производительности
- [ ] Мониторинг производительности моделей
- [ ] Автоматический выбор оптимальной модели
- [ ] Балансировка нагрузки между моделями

## Поддерживаемые локальные решения

### Ollama
```bash
# Установка и запуск
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve
ollama pull llama3.1:8b

# Конфигурация бота
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=dummy
```

### vLLM  
```bash
# Установка
pip install vllm

# Запуск сервера
python -m vllm.entrypoints.openai.api_server \
  --model microsoft/DialoGPT-large \
  --port 8000

# Конфигурация бота  
LLM_API_BASE=http://localhost:8000/v1
LLM_MODEL=microsoft/DialoGPT-large
```

### LM Studio
```bash
# Запустить LM Studio GUI
# Загрузить модель
# Запустить локальный сервер

# Конфигурация бота
LLM_API_BASE=http://localhost:1234/v1  
LLM_MODEL=local-model
LLM_API_KEY=dummy
```

### Text Generation WebUI
```bash
# Установка Oobabooga
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui
pip install -r requirements.txt

# Запуск с OpenAI API
python server.py --api --listen

# Конфигурация бота
LLM_API_BASE=http://localhost:5000/v1
LLM_MODEL=local-model
```

## Преимущества архитектуры

1. **Гибкость** - легко добавлять новые модели и провайдеры
2. **Надежность** - фоллбэк между локальными и облачными моделями  
3. **Производительность** - автоматический выбор оптимальной модели
4. **Экономичность** - приоритет локальным моделям, облачные как фоллбэк
5. **Мониторинг** - полная видимость производительности каждой модели

## Миграция

Текущий код **полностью совместим** с планируемыми изменениями. Все улучшения будут добавляться инкрементально без ломающих изменений.
