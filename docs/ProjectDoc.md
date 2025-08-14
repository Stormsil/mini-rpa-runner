# Mini?RPA Runner — ProjectDoc

Версия документа: 0.1 (черновик для инициализации репозитория)

## 1. Назначение и контекст

**Mini?RPA Runner** — лёгкий инструмент автоматизации десктопных сценариев под Windows с декларативными сценариями в YAML. Цель: надёжно воспроизводить шаги «запусти команду/программу ? дождись окна ? сфокусируй ? кликни по эталонному изображению ? введи текст/клавиши», без OCR и без глубокого UI?инспектирования DOM. Основной упор — устойчивость и читабельность сценариев.

### Почему не «универсальный монстр»

* Узкий, но продуманный набор функций: окна, клики по изображениям, ввод, ожидания, условия, чекпоинты.
* Без OCR и сложных парсеров. Приоритет — простые, повторяемые пайплайны.
* Фокус на Electron/CEF/«веб в десктопе» и обычные Win32 окна.

## 2. Сводные требования

### 2.1. Функциональные

1. Выполнение сценариев в YAML (DSL).
2. Действия: запуск PowerShell/Bash, запуск программ, ожидание окна/процесса/файла, фокус окна, ввод текста/клавиш, клик по шаблонному изображению (с масштабированием и порогом), логирование, пауза, чекпоинт, условные ветки.
3. Глобальные параметры: таймауты, ретраи, задержки, переменные (Jinja2), скриншот при ошибке.
4. Компактный оверлей?GUI «поверх всех окон» (состояние шага, лог, Пауза/Стоп), размещаемый в углу.
5. «Сухой прогон» (dry?run) без реального ввода/кликов.

### 2.2. Нефункциональные

* Windows?first (Win10/11 x64). В перспективе — Linux/macOS, но сейчас вне объёма.
* Устойчивость к DPI, многомониторности, разным масштабам интерфейса.
* Простое развёртывание (Python + PyInstaller one?file).
* Чёткая структура проекта, автотесты для CV и парсера DSL.

### 2.3. Не?цели (явно)

* Нет OCR.
* Нет «умных» UI?селекторов (UIA/AX) на первом этапе. (Возможна опционально позже.)
* Нет сетевой оркестрации/агентов.

## 3. Архитектура

```
YAML DSL ??> Orchestrator ??> Action Plugins
                         ??> Window Manager (поиск/фокус/ROI)
                         ??> Vision (OpenCV: grab ? match ? click)
                         ??> Input (клавиатура/мышь)
                         ??> EventBus ? Overlay GUI + Logger
```

### Компоненты

* **Orchestrator** — парсит YAML, ведёт контекст, таймауты/ретраи, события для GUI.
* **Actions** — плагины: `run_ps`, `run_program`, `wait_window`, `window_focus`, `type_text`, `press_key`, `click_image`, `wait_file`, `wait_process`, `log`, `pause`, `checkpoint`, `if_condition`.
* **Window Manager** — поиск окна по regex заголовка/класса/пиду; вычисление ROI окна для Vision; фокус/перемещение по желанию.
* **Vision** — захват экрана/ROI (`mss`), матчинг шаблона (multi?scale, grayscale), порог, N?ретраев, центр координат, клик.
* **Input** — безопасные симуляции клавиатуры/мыши (паузируемые), глобальный хоткей «Стоп».
* **Overlay GUI** — компактный статус + мини?лог, всегда поверх, перетаскиваемое окно, не перекрывает целевые области.

## 4. Стек технологий

* Ядро: **Python 3.11+**
* YAML: **PyYAML** (или `ruamel.yaml` при необходимости сохранения комментариев)
* Ввод/скриншот/CV: **pyautogui**, **mss**, **Pillow**, **opencv?python**, **numpy**
* Окна/процессы: **pygetwindow**, **psutil**
* GUI: **PyQt6**
* Логи/CLI: **rich**, **typer** (CLI)
* Шаблоны в YAML: **jinja2**
* Сборка: **PyInstaller**
* Качество кода: **ruff** + **black** + **mypy**, тесты: **pytest**

**Обоснование выбора:** минимальная внешняя зависимость, библиотечный стек устойчив на Windows, богатая экосистема.

## 5. DSL (YAML) — спецификация

### 5.1. Общая форма

```yaml
version: 1
settings:
  defaults:
    timeout: 15s         # шаг по умолчанию
    retries: 2
    retry_delay: 500ms
  vars:
    key: "YOUR_KEY_HERE"

steps:
  - name: <идентификатор или человекочитаемое имя>
    action: <тип действия>
    # параметры зависят от action
```

### 5.2. Единицы времени

`100ms`, `2s`, `1m`. Везде, где применимо.

### 5.3. Переменные

Шаблонизация **Jinja2** внутри строк: `"{{ key }}"`. Доступ: `settings.vars` + runtime?переменные.

### 5.4. Действия и параметры

* `run_ps`

  * `script: <путь .ps1>` или `inline: <строка>`
  * `args?: [..]` (экранируются)
  * `timeout?`, `expect_code?` (по умолчанию 0)
* `run_program`

  * `path: <exe>`
  * `args?: [..]`, `cwd?`, `timeout?` (ожидание возврата опционально)
* `wait_window`

  * `title: <regex>`
  * `class?: <regex>`
  * `timeout?`
  * `exists: true|false` (по умолчанию true)
* `window_focus`

  * `title: <regex>`
  * `timeout?`
* `type_text`

  * `text: <строка>`
  * `per_char_delay?: 20ms`
* `press_key`

  * `key: <enter|tab|esc|…>` или `hotkey: ["ctrl","s"]`
* `click_image`

  * `image: <png>`
  * `region?: screen | window | {left,top,width,height}`
  * `threshold?: 0.87`
  * `scale_range?: [0.8,1.2]`
  * `retries?: 2`
  * `retry_delay?: 400ms`
* `wait_file`

  * `path: <строка>`
  * `exists: true|false` (по умолчанию true)
  * `timeout?`
* `wait_process`

  * `name: <regex>` или `pid: <число>`
  * `exists: true|false`
  * `timeout?`
* `log`

  * `message: <строка>`
* `pause` — остановка до ручного продолжения (кнопкой в GUI)
* `checkpoint`

  * `id: <строка>` — сохраняется в артефактах/журнале
* `if_condition`

  * `condition: { type: <image_exists|window_exists|file_exists|process_exists>, ... }`
  * `then: [ шаги… ]`
  * `else?: [ шаги… ]`

### 5.5. Условия (condition)

* `image_exists`

  * `image`, `region?`, `threshold?`, `scale_range?`, `timeout?`
* `window_exists`

  * `title`, `class?`, `timeout?`
* `file_exists`

  * `path`, `timeout?`
* `process_exists`

  * `name|pid`, `timeout?`

### 5.6. Ошибки и повторы

Любой шаг может указывать `timeout`, `retries`, `retry_delay`. При исчерпании — ошибка сценария, скриншот в артефакты.

## 6. Пример сценария (конкретизация Resilio/Proxifier)

```yaml
version: 1
settings:
  defaults: { timeout: 20s, retries: 2, retry_delay: 400ms }
  vars:
    resilio_exe: "C:/Program Files/Resilio Sync/Resilio Sync.exe"
    key: "YOUR_KEY_HERE"

steps:
  - name: Install Resilio Silent
    action: run_ps
    script: D:/install_resilio.ps1

  - name: Open Resilio
    action: run_program
    path: "{{ resilio_exe }}"

  - name: Wait Resilio Window
    action: wait_window
    title: /Resilio Sync/i
    timeout: 15s

  - name: Focus Resilio
    action: window_focus
    title: /Resilio Sync/i

  - name: Enter Key if Field Visible
    action: if_condition
    condition:
      type: image_exists
      image: images/key_field.png
      region: window
      threshold: 0.88
      scale_range: [0.9, 1.1]
      timeout: 5s
    then:
      - action: click_image
        image: images/key_field.png
        region: window
        threshold: 0.88
      - action: type_text
        text: "{{ key }}"
      - action: press_key
        key: enter
    else:
      - action: log
        message: "Key field not found, pausing..."
      - action: pause

  - name: Setup Proxifier
    action: run_ps
    script: D:/config_proxifier.ps1

  - name: Activate DNS Leak Prevention
    action: if_condition
    condition:
      type: image_exists
      image: images/dns_checkbox_unchecked.png
      region: window
      threshold: 0.9
    then:
      - action: click_image
        image: images/dns_checkbox_unchecked.png
        region: window
    else:
      - action: log
        message: "DNS already set"

  - name: Checkpoint
    action: checkpoint
    id: setup_complete
```

## 7. Захват эталонных изображений

**Цель:** зафиксировать устойчивые шаблоны для поиска элементов интерфейса.

**Правила подготовки эталонов:**

* Кадр берётся из области целевого окна (ROI), без рамок/тени.
* Размер шаблонов 20–120 px по большей стороне; без динамики (мигающие курсоры, таймеры).
* Минимизировать фон и лишние градиенты; при необходимости — добавить маску (альфа?канал).
* Проверять распознаваемость на разных масштабах интерфейса (100–150%).
* Хранить в `images/` с говорящими именами и версионировать изменения.

**Требования к инструментам захвата:**

* Возможность выбрать «окно» как источник кадра.
* Автосохранение в PNG без потерь.
* Индикатор «сетку»/наведение для точного вырезания виджета.

## 8. Алгоритм Vision. Алгоритм Vision

1. Захват ROI (всего экрана или границ активного окна) через `mss`.
2. Приведение к grayscale.
3. Перебор масштабов (`scale_range`, по умолчанию 0.8–1.2, шаг 0.1).
4. `cv2.matchTemplate(..., TM_CCOEFF_NORMED)` ? максимум корреляции.
5. Сравнение с `threshold` (по умолчанию 0.87).
6. Опциональные повторы (N ретраев) с задержкой.
7. Клик в центр найденного прямоугольника.

## 9. Overlay?GUI (требования)

* 260?140 px, всегда поверх, минимально навязчивый.
* Поле «Текущий шаг», мини?лог (10–20 строк), кнопки `Пауза`, `Продолжить`, `Стоп`.
* Горячая клавиша аварийного останова: `Ctrl+Alt+Esc`.
* Отображение «DRY?RUN» при пробном прогонах.

## 10. Репозиторий: структура

```
mini-rpa-runner/
  docs/
    ProjectDoc.md
    README.md
  runner/
    __init__.py
    cli.py              # Typer CLI: run/capture/dry-run
    orchestrator.py
    dsl.py              # валидация YAML, схемы
    actions/
      base.py
      run.py            # run_ps, run_program
      window.py         # wait_window, window_focus
      input.py          # type_text, press_key
      vision.py         # click_image, image_exists
      fs.py             # wait_file
      process.py        # wait_process
      flow.py           # log, pause, checkpoint, if_condition
    vision/
      grab.py           # mss
      match.py          # OpenCV матчинги
    ui/
      overlay.py
    utils/
      timing.py, paths.py, events.py
  examples/
    resilio_setup.yaml
  tests/
    test_dsl.py
    test_match.py
  pyproject.toml        # зависимости, black/ruff/mypy/pytest
  .editorconfig
  .gitignore
```

## 11. Качество кода и стили

* **PEP8** + автоформат (**black**) + линт (**ruff**), типизация (**mypy**).
* Коммиты: **Conventional Commits** (`feat:`, `fix:`, `docs:` …).
* Версионирование: **SemVer**.

## 12. Примечание по установке

Пошаговые инструкции по установке, окружению и командам намеренно не включаются в документацию проекта. Все операционные шаги и конкретные команды фиксируются в чате/issue?комментариях. В документации остаются только архитектура, спецификации и требования.

## 13. CLI (спецификация)

* `run` — выполняет сценарий; поддерживает профили и переопределения параметров.
* `capture` — вспомогательный инструмент для подготовки эталонных изображений.
* `check` — статическая валидация сценариев и конфигов.
* Требования: детерминированные коды выхода; подробный лог в файл и краткий прогресс в оверлее.
  CLI (план)
* `runner run <file.yaml> [--vars key=VALUE] [--dry-run] [--log-level info]`
* `runner capture --window <regex> --save <png> [--region window|screen|x,y,w,h]`
* `runner check <file.yaml>` — валидация DSL

## 14. Политика ошибок/ретраев

* Каждый шаг наследует `defaults` и может переопределить.
* При падении: лог, скриншот ROI, опция «остановиться» или «продолжить» через политику сценария (позже).

## 15. Тестирование

* Юнит?тесты DSL (валидные/невалидные YAML, рендер переменных).
* Юнит?тесты Vision на фикстурах изображений (порог, масштаб, отказоустойчивость).
* Интеграционные прогоны на «демо?окне» (Qt?приложение?заглушка).

## 16. DPI и многомониторность

* При старте фиксируем масштабирование и координатные системы.
* Для `region: window` — ROI = клиентская область окна, без рамки/тени.
* Скриншоты и координаты нормализуем к фактическому DPI.

## 17. Безопасность

* Сценарии запускают команды/скрипты: ответственность на авторе сценария.
* Секреты передавать через `--vars`/ENV (не хранить в YAML). Логи без секретов.

## 18. Дорожная карта (итерации)

**Итерация 0 — Bootstrap**

* [ ] Структура каталога, базовые зависимости, CLI?каркас
* [ ] Orchestrator + парсер YAML + контекст

**Итерация 1 — Базовые actions**

* [ ] `run_ps`, `run_program`
* [ ] `wait_window`, `window_focus`
* [ ] `type_text`, `press_key`

**Итерация 2 — Vision**

* [ ] Захват экрана/ROI, multi?scale match, `click_image`, `image_exists`
* [ ] Таймауты/ретраи/скриншот при ошибке

**Итерация 3 — Flow/условия/чекпоинты**

* [ ] `if_condition`, `pause`, `checkpoint`, `log`

**Итерация 4 — Overlay GUI**

* [ ] Мини?окно, события, горячие клавиши, пауза/стоп

**Итерация 5 — Полировка/сборка**

* [ ] PyInstaller, DPI?манифест, пример `resilio_setup.yaml`
* [ ] Документация `README.md`

## 19. Лицензия

MIT (по умолчанию; можно скорректировать).

## 20. Открытые вопросы (на будущее)

* Нужно ли добавлять «реплеи» ввода (запись/повтор)? Пока вне объёма.
* Нужны ли шаблоны?макросы YAML (`include`, `extends`)? Вероятно после MVP.
* Добавлять ли UIA как альтернативу Vision для Electron? Опционально.
