# 🔒 Перенос проекта в приватный GitLab

## Способы переноса в закрытый GitLab репозиторий

---

## Вариант 1: Импорт через GitLab UI (проще всего)

### Шаг 1: В GitLab создайте новый проект

1. Откройте ваш GitLab
2. New Project → Import project
3. Выберите "Import from GitHub"
4. Авторизуйтесь в GitHub
5. Выберите `VasilyKolbenev/Agentic_Trainer_Logs`
6. Установите visibility: **Private** 🔒
7. Import project

**Готово!** GitLab автоматически перенесет всё.

---

## Вариант 2: Через Git remote (больше контроля)

### Шаг 1: Создайте пустой репозиторий в GitLab

1. GitLab → New Project → Create blank project
2. Название: `agentic-trainer-logs` (или любое)
3. Visibility: **Private** 🔒
4. **НЕ** инициализируйте с README
5. Create project

### Шаг 2: Получите URL репозитория

GitLab покажет что-то вроде:
```
https://gitlab.com/your-username/agentic-trainer-logs.git
```

### Шаг 3: Добавьте GitLab как remote

```bash
cd C:\Users\Василий\Downloads\esk-agent-llm-pro

# Добавьте GitLab remote
git remote add gitlab https://gitlab.com/your-username/agentic-trainer-logs.git

# Проверьте
git remote -v

# Должно показать:
# origin    https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git
# gitlab    https://gitlab.com/your-username/agentic-trainer-logs.git
```

### Шаг 4: Push в GitLab

```bash
# Push весь проект
git push gitlab main --all

# Или если main не существует:
git push gitlab main

# Push теги (если есть)
git push gitlab --tags
```

---

## Вариант 3: Mirror (автоматическая синхронизация)

### В GitLab настройте зеркало:

1. GitLab → Settings → Repository → Mirroring repositories
2. Git repository URL: `https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git`
3. Mirror direction: **Pull**
4. Authentication: Personal access token (если нужен)
5. Mirror repository

**Результат:** GitLab будет автоматически синхронизироваться с GitHub!

---

## Вариант 4: Прямой клон (свежий старт)

```bash
# 1. Клонируйте с GitHub
git clone https://github.com/VasilyKolbenev/Agentic_Trainer_Logs.git
cd Agentic_Trainer_Logs

# 2. Измените remote на GitLab
git remote set-url origin https://gitlab.com/your-username/agentic-trainer-logs.git

# 3. Push
git push -u origin main
```

---

## 🔐 Авторизация в GitLab

### Personal Access Token:

1. GitLab → Settings → Access Tokens
2. Token name: `git-access`
3. Scopes: `read_repository`, `write_repository`
4. Create token
5. Скопируйте token

### При push используйте:
```
Username: ваш_username
Password: скопированный_token
```

---

## 🔒 Настройки приватности

### В GitLab репозитории:

1. Settings → General → Visibility
2. Выберите: **Private** 🔒
3. Save changes

**Опции:**
- **Private** - только вы и кто вы добавите
- **Internal** - все пользователи вашего GitLab instance
- **Public** - все в интернете

Для закрытого контура выбирайте **Private**!

---

## 📋 После переноса в GitLab

### Проверьте что всё на месте:

- ✅ src/ со всеми компонентами
- ✅ Dockerfile и docker-compose файлы
- ✅ README.md отображается
- ✅ Документация доступна
- ✅ .gitignore работает (data/ не попала)

### Обновите CI/CD (опционально):

GitLab CI/CD (.gitlab-ci.yml):

```yaml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  image: python:3.10
  script:
    - pip install -r requirements.txt
    - python test_pipeline.py

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t ml-pipeline:latest .

deploy:
  stage: deploy
  script:
    - docker-compose up -d
  only:
    - main
```

---

## 🚀 Быстрая команда

Создам bat файл для переноса:

```bash
# transfer_to_gitlab.bat

@echo off
set /p GITLAB_URL="Введите GitLab URL (например: https://gitlab.com/username/repo.git): "

git remote add gitlab %GITLAB_URL%
git push gitlab main --all
git push gitlab --tags

echo Готово! Проект в GitLab.
pause
```

---

## ✅ Преимущества GitLab для закрытого контура

- ✅ **Self-hosted** опция - полный контроль
- ✅ **Private** репозитории бесплатно
- ✅ **CI/CD** встроенный
- ✅ **Container Registry** для Docker образов
- ✅ **Runner** для автоматизации

---

## 🎯 Рекомендация для закрытого контура:

### Self-hosted GitLab:

```bash
# Развертывание GitLab в вашей инфраструктуре
docker run -d \
  --hostname gitlab.your-domain.local \
  --publish 443:443 --publish 80:80 --publish 22:22 \
  --name gitlab \
  --volume /srv/gitlab/config:/etc/gitlab \
  --volume /srv/gitlab/logs:/var/log/gitlab \
  --volume /srv/gitlab/data:/var/opt/gitlab \
  gitlab/gitlab-ce:latest
```

Тогда **всё** (код + Git + CI/CD + Registry) в вашем закрытом контуре! 🔒

---

## 🎉 Итого:

**Да, легко переносится в GitLab!**

**Рекомендую:** Вариант 1 (Import через UI) - быстро и просто.

**Для максимальной безопасности:** Self-hosted GitLab в вашей инфраструктуре.

**Проект готов к работе в любом Git системе! ✅**

