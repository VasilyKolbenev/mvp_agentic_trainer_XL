# 🚀 Перенос проекта в новый GitHub репозиторий

## 📋 Инструкция для переноса в https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git

---

## Вариант 1: Полный перенос (рекомендуется)

### Шаг 1: Подготовка текущего репозитория

```bash
cd C:\Users\Василий\Downloads\esk-agent-llm-pro

# Проверьте статус
git status

# Добавьте все изменения
git add .

# Commit всех изменений
git commit -m "feat: v2.0 - ML Data Pipeline с PydanticAI и контролем качества

Complete rewrite:
- Модульная архитектура (9 компонентов)
- FastAPI REST API (убран Telegram бот)
- PydanticAI для AI-агентов
- 5 уровней контроля качества Labeler
- QualityControl с cosine + Levenshtein
- Docker для закрытого контура (Mistral + Qwen)
- Версионирование датасетов
- Полная документация (15,000+ строк)"
```

---

### Шаг 2: Подключение нового remote

```bash
# Добавьте новый remote
git remote add new-origin https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git

# Проверьте remotes
git remote -v

# Должно показать:
# new-origin https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git (fetch)
# new-origin https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git (push)
# origin ... (старый remote)
```

---

### Шаг 3: Push в новый репозиторий

```bash
# Push в новый репозиторий
git push new-origin main

# Или если ветка называется master:
# git push new-origin master

# Если попросит авторизацию - введите GitHub credentials
```

---

### Шаг 4: Установка нового origin по умолчанию (опционально)

```bash
# Удалите старый origin
git remote remove origin

# Переименуйте new-origin в origin
git remote rename new-origin origin

# Проверьте
git remote -v
# Должно показать только новый репозиторий
```

---

## Вариант 2: Свежий клон (если нужно начать с нуля)

### Шаг 1: Создайте архив текущего проекта

```bash
# Перейдите в папку выше
cd C:\Users\Василий\Downloads

# Создайте архив (через проводник или командой)
# Zip всю папку esk-agent-llm-pro
```

### Шаг 2: Клонируйте новый репозиторий

```bash
# Клонируйте пустой репозиторий
git clone https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git

cd Agentic_Trainer_Logs
```

### Шаг 3: Скопируйте все файлы

```bash
# Скопируйте всё из esk-agent-llm-pro в Agentic_Trainer_Logs
# (через проводник или командой)

# ВАЖНО: Скопируйте всё КРОМЕ:
# - .git/ (не копируйте!)
# - .venv/ (не копируйте!)
# - __pycache__/ (не копируйте!)
# - data/ (опционально - может содержать чувствительные данные)
```

### Шаг 4: Commit и Push

```bash
git add .

git commit -m "feat: Initial commit - ML Data Pipeline v2.0

- Backend ML Pipeline с FastAPI
- 9 компонентов с модульной архитектурой
- PydanticAI для AI-агентов
- 5 уровней контроля качества
- Docker для закрытого контура
- Полная документация"

git push origin main
```

---

## ✅ Проверка успешного переноса

После push откройте в браузере:
```
https://github.com/VasilyKolbenev/Agentic_Trainer_Logs
```

Должны увидеть:
- ✅ README.md с описанием проекта
- ✅ src/pipeline/ с компонентами
- ✅ Dockerfile и docker-compose.yml
- ✅ Документацию (ARCHITECTURE_V2.md, etc.)
- ✅ requirements.txt

---

## 🔐 GitHub Authentication

Если попросит авторизацию:

### Windows:
```bash
# GitHub CLI (рекомендуется)
winget install GitHub.cli
gh auth login

# Или через Git Credential Manager
# Установится автоматически с Git for Windows
```

### Personal Access Token:
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Выберите scopes: `repo`, `workflow`
4. Скопируйте token
5. Используйте вместо пароля при git push

---

## 📁 Что будет в новом репозитории

```
Agentic_Trainer_Logs/
├── src/
│   ├── api.py                      FastAPI backend
│   ├── pipeline/                   9 компонентов
│   │   ├── etl.py
│   │   ├── labeler_agent.py
│   │   ├── labeler_validator.py   (5 уровней контроля)
│   │   ├── augmenter_agent.py
│   │   ├── quality_control.py     (cosine + Levenshtein)
│   │   ├── review_dataset.py
│   │   ├── data_writer.py
│   │   └── data_storage.py
│   └── config_v2.py
│
├── Dockerfile
├── docker-compose.yml
├── docker-compose.local-llm.yml    (Mistral + Qwen)
│
├── README.md
├── ARCHITECTURE_V2.md
├── PIPELINE_FLOW.md
├── QUALITY_ASSURANCE.md
├── LOCAL_LLM_SETUP.md
├── TESTING_GUIDE.md
└── ... (остальная документация)
```

---

## 🎯 После переноса

### Обновите README.md на GitHub:

Замените ссылки в документации:
```bash
# Старое:
https://github.com/your-username/esk-agent-llm-pro

# Новое:
https://github.com/VasilyKolbenev/Agentic_Trainer_Logs
```

Это можно сделать позже через GitHub Web UI.

---

## 🚀 Готово!

После успешного push:

1. ✅ Проект доступен на GitHub
2. ✅ Можно клонировать: `git clone https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git`
3. ✅ Можно запускать: `docker-compose up -d`
4. ✅ Можно изучать код и документацию

**Успешного переноса! 🎊**

