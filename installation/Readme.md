# Установка окружения для C++ Russia 2026

Скрипт `install.py` настраивает окружение для мастер-класса на **Ubuntu 24.04**:

- ставит SourceCraft Code Assistant вместо Roo Code;
- ставит CLI SourceCraft;
- копирует правила, `AGENTS.md` и skills в рабочую директорию;
- ставит системные зависимости для frontend/backend разработки;
- ставит последнюю Node.js из NodeSource;
- ставит Docker Engine, Docker Compose plugin и локальный PostgreSQL;
- ставит prebuilt `libuserver-all-dev` пакет для Ubuntu 24.04;
- клонирует template repository и `userver` repository в домашнюю директорию пользователя;
- проверяет сборку frontend и backend из template repository.

## Требования

1. Ubuntu 24.04.
2. Доступ в интернет.
3. Пользователь с правами `sudo`.
4. Графическая/серверная установка VS Code с доступной командой `code` либо возможность поставить VS Code через `.deb` пакет.

Скрипт намеренно завершится с ошибкой на другой ОС или другой версии Ubuntu.

## Быстрый запуск

Из директории `roo_install/installation`:

```bash
python3 install.py \
  --target-folder /home/$USER/cpprussia2026_workspace
```

По умолчанию скрипт копирует правила из `../service`, а репозитории клонирует напрямую в домашнюю директорию:

```text
/home/$USER/roo_install
/home/$USER/cpprussia2026_template
/home/$USER/userver
```

`roo_install` — это репозиторий, из которого запускается сам установщик. Его нужно заранее склонировать или обновить в домашней директории, например:

```bash
git clone https://github.com/Rexarrior/roo_install.git /home/$USER/roo_install
cd /home/$USER/roo_install/installation
python3 install.py
```

## Полный пример

```bash
python3 install.py \
  --target-folder /home/$USER/cpprussia2026_workspace \
  --config-folder ../service \
  --repo-dir /home/$USER/cpprussia2026_template \
  --userver-repo-dir /home/$USER/userver
```

## Параметры

| Параметр | Назначение |
|---|---|
| `--target-folder` / `--target_folder` | Рабочая директория, куда копируются `AGENTS.md`, `rules/` и `skills/`. |
| `--config-folder` / `--config_folder` | Источник правил для агента. По умолчанию `../service`. |
| `--repo-dir` | Путь, куда клонируется template repository. По умолчанию `/home/$USER/<имя из TEMPLATE_REPO_URL>`, сейчас `/home/$USER/cpprussia2026_template`. |
| `--userver-repo-dir` | Путь, куда клонируется `userver`. По умолчанию `/home/$USER/userver`. |
| `--update-existing-repo` | Если репозиторий уже существует, выполнить `git pull --ff-only`. Без этого существующий checkout не меняется. |
| `--skip-sourcecraft` | Пропустить установку расширения и CLI SourceCraft. |
| `--skip-dependencies` | Пропустить установку системных пакетов, Node.js, Docker и PostgreSQL. |
| `--skip-clone` | Пропустить клонирование/обновление репозитория. |
| `--skip-build-checks` | Пропустить проверку сборки frontend и backend. |

## Что устанавливается

### SourceCraft

Скрипт выполняет действия из `install_log.md`:

1. Скачивает VS Code расширение:

```text
https://storage.yandexcloud.net/yandex-code-assistant/plugins/vscode/yandex-code-assist.vsix
```

2. Устанавливает его командой:

```bash
code --install-extension yandex-code-assist.vsix --force
```

3. Устанавливает CLI:

```bash
curl -fsSL https://s3.yandexcloud.net/sourcecraft-cli/install.sh | sh
src code install
```

### Системные зависимости

Скрипт ставит через `apt` набор пакетов для сборки userver-сервисов и frontend:

- GCC/G++ с проверкой версии `>= 11.2`;
- Clang с проверкой версии `>= 16` и `clang-format` для генерации userver/chaotic;
- CMake, Make, Ninja, pkg-config;
- OpenSSL, Boost, jemalloc и другие dev-библиотеки, нужные для userver;
- prebuilt userver development package `ubuntu24.04-libuserver-all-dev_3.0_amd64.deb` из GitHub Releases;
- Python 3, venv/pip;
- Git, curl, wget, unzip;
- PostgreSQL server и contrib;
- Nginx для локального reverse proxy/static serving;
- Docker Engine, Docker Compose plugin, Buildx из официального Docker repository;
- Node.js последней доступной версии из NodeSource `setup_current.x`.

Во время `apt`-установки скрипт временно запрещает автозапуск сервисов через `policy-rc.d`, чтобы установка `nginx` не падала на машинах, где порты `80`/`443` уже заняты. После базовых пакетов скачивается и устанавливается userver `.deb`:

```text
https://github.com/userver-framework/userver/releases/download/v3.0/ubuntu24.04-libuserver-all-dev_3.0_amd64.deb
```

После установки PostgreSQL включается и запускается явно через `systemctl enable --now postgresql`.

## Проверка репозитория

Template repository задаётся одной переменной `TEMPLATE_REPO_URL` в `install.py`; имя директории по умолчанию вычисляется из этой переменной, без отдельного хардкода. После клонирования `cpprussia2026_template` скрипт выполняет:

### Frontend

```bash
cd frontend
npm ci
npm run build
```

Если `package-lock.json` отсутствует, вместо `npm ci` будет использовано `npm install`.

### Backend

Скрипт поддерживает две раскладки backend:

- если есть `backend/CMakeLists.txt`, сборка выполняется из корня template repository;
- если root `backend/CMakeLists.txt` отсутствует, скрипт выбирает сервисную директорию с `CMakeLists.txt`, приоритетно `backend/auth_service`.

Для текущего template repository эквивалентная ручная проверка:

```bash
cd backend/auth_service
cmake -B build -S .
cmake --build build -j$(nproc)
```

Backend сборка использует `backend/auth_service/CMakeLists.txt`. Если userver не найден локально, логика проекта скачает его через CMake/CPM.

## Что больше не используется

Старая логика Roo Code удалена из скрипта:

- не нужен параметр `--key`;
- не генерируется `roo_settings.json`;
- не пишется глобальный Roo MCP config;
- не устанавливается расширение `rooveterinaryinc.roo-cline`;
- файлы `config/base_config.json` и `config/base_mcp_config.json` больше не участвуют в установке.

Они могут оставаться в дереве как архивные/устаревшие файлы, но новый `install.py` их не читает.

## Частые сценарии

### Только скопировать правила и проверить уже установленное окружение

```bash
python3 install.py \
  --target-folder /home/$USER/cpprussia2026_workspace \
  --skip-dependencies \
  --skip-sourcecraft
```

### Обновить существующий checkout шаблона

```bash
python3 install.py \
  --target-folder /home/$USER/cpprussia2026_workspace \
  --update-existing-repo
```

### Пропустить долгую сборку

```bash
python3 install.py \
  --target-folder /home/$USER/cpprussia2026_workspace \
  --skip-build-checks
```

## Примечания

- Установка Docker добавляет официальный apt repository Docker.
- Для запуска Docker без `sudo` пользователю может понадобиться отдельное добавление в группу `docker` и перелогин. Скрипт не делает это автоматически, чтобы не менять сессию пользователя неожиданно.
- Все команды выполняются с остановкой при первой ошибке и печатают контекст команды/директории.
