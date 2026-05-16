# Установка окружения для C++ Russia 2026

Скрипт `install.py` настраивает окружение для мастер-класса на **Ubuntu 24.04**:

- в начале установки ставит VS Code, если команда `code` ещё недоступна;
- ставит SourceCraft Code Assistant вместо Roo Code;
- ставит CLI SourceCraft;
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
4. Возможность скачать и установить VS Code `.deb` пакет, если команда `code` ещё недоступна.

Скрипт намеренно завершится с ошибкой на другой ОС или другой версии Ubuntu.

## Быстрый запуск

Из директории `roo_install/installation`:

```bash
python3 install.py
```

По умолчанию скрипт клонирует репозитории напрямую в домашнюю директорию:

```text
/home/$USER/roo_install
/home/$USER/cpprussia2026_backend_template
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
  --repo-dir /home/$USER/cpprussia2026_backend_template \
  --userver-repo-dir /home/$USER/userver
```

## Параметры

| Параметр | Назначение |
|---|---|
| `--repo-dir` | Путь, куда клонируется template repository. По умолчанию `/home/$USER/<имя из TEMPLATE_REPO_URL>`, сейчас `/home/$USER/cpprussia2026_backend_template`. |
| `--userver-repo-dir` | Путь, куда клонируется `userver`. По умолчанию `/home/$USER/userver`. |
| `--update-existing-repo` | Если репозиторий уже существует, выполнить `git pull --ff-only`. Без этого существующий checkout не меняется. |
| `--skip-sourcecraft` | Пропустить установку расширения и CLI SourceCraft. |
| `--skip-dependencies` | Пропустить установку системных пакетов, Node.js, Docker и PostgreSQL. |
| `--skip-clone` | Пропустить клонирование/обновление репозитория. |
| `--skip-build-checks` | Пропустить проверку сборки frontend и backend. |

## Что устанавливается

### VS Code

В начале установки скрипт проверяет команду `code`. Если VS Code ещё не установлен, скрипт скачивает официальный `.deb` пакет и устанавливает его через `apt-get install`.

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

3. Устанавливает рекомендованные VS Code extensions для C++/userver разработки:

```text
llvm-vs-code-extensions.vscode-clangd
ms-vscode.cpptools
ms-vscode.cmake-tools
ms-vscode.makefile-tools
vadimcn.vscode-lldb
ms-azuretools.vscode-docker
xaver.clang-format
```

В список включены расширения из `service_template/.devcontainer/devcontainer.json` userver framework, а также C++ и clang-format extensions.

4. Устанавливает CLI:

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

Во время `apt`-установки скрипт временно запрещает автозапуск сервисов через `policy-rc.d`, чтобы установка `nginx` не падала на машинах, где порты `80`/`443` уже заняты. После базовых пакетов скрипт проверяет наличие пакета `libuserver-all-dev`; если пакет уже установлен, повторно `.deb` не скачивается. Если пакета нет, скачивается и устанавливается userver `.deb`:

```text
https://github.com/userver-framework/userver/releases/download/v3.0/ubuntu24.04-libuserver-all-dev_3.0_amd64.deb
```

После установки PostgreSQL включается и запускается явно через `systemctl enable --now postgresql`.

## Проверка репозитория

Template repository задаётся одной переменной `TEMPLATE_REPO_URL` в `install.py`; имя директории по умолчанию вычисляется из этой переменной, без отдельного хардкода. Сейчас используется `https://github.com/Malevrovich/cpprussia2026_backend_template.git`, поэтому после клонирования `cpprussia2026_backend_template` скрипт выполняет:

### Frontend

```bash
cd frontend
npm install
npm run build
```

### Backend

Скрипт поддерживает две раскладки backend:

- если есть `backend/CMakeLists.txt`, сборка выполняется из корня template repository;
- если root `backend/CMakeLists.txt` отсутствует, скрипт выбирает сервисную директорию с `CMakeLists.txt`, приоритетно `backend/auth_service`, иначе первую доступную `backend/*_service` директорию.

Для текущего `cpprussia2026_backend_template` эквивалентная ручная проверка:

```bash
cd backend/example_service
make build-release
```

Backend сборка использует `backend/example_service/CMakeLists.txt`. Если userver не найден локально, логика проекта скачает его через CMake/CPM.

### Docker Compose

После frontend/backend проверки скрипт запускает из корня template repository:

```bash
docker compose build
```

Если текущий пользователь не имеет прямого доступа к Docker daemon, скрипт автоматически попробует выполнить сборку через `sudo docker compose build`.

## Что больше не используется

Старая логика Roo Code удалена из скрипта:

- не нужен параметр `--key`;
- не генерируется `roo_settings.json`;
- не пишется глобальный Roo MCP config;
- не устанавливается расширение `rooveterinaryinc.roo-cline`;
- файлы `config/base_config.json` и `config/base_mcp_config.json` больше не участвуют в установке.

Они могут оставаться в дереве как архивные/устаревшие файлы, но новый `install.py` их не читает.

## Частые сценарии
### Проверить уже установленное окружение без переустановки зависимостей и SourceCraft

```bash
python3 install.py \
  --skip-dependencies \
  --skip-sourcecraft
```


### Обновить существующий checkout шаблона

```bash
python3 install.py \
  --update-existing-repo
```

### Пропустить долгую сборку

```bash
python3 install.py \
  --skip-build-checks
```

## Примечания

- Установка Docker добавляет официальный apt repository Docker.
- Скрипт добавляет текущего пользователя в группу `docker`, чтобы Docker был доступен без `sudo` после перелогина. В текущей сессии, пока новая группа ещё не применена, скрипт использует fallback на `sudo docker`.
- Все команды выполняются с остановкой при первой ошибке и печатают контекст команды/директории.
