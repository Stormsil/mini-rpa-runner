# Mini?RPA Runner � ProjectDoc

������ ���������: 0.1 (�������� ��� ������������� �����������)

## 1. ���������� � ��������

**Mini?RPA Runner** � ����� ���������� ������������� ���������� ��������� ��� Windows � �������������� ���������� � YAML. ����: ������ �������������� ���� �������� �������/��������� ? ������� ���� ? ���������� ? ������ �� ���������� ����������� ? ����� �����/�������, ��� OCR � ��� ��������� UI?��������������� DOM. �������� ���� � ������������ � ������������� ���������.

### ������ �� �������������� ������

* �����, �� ����������� ����� �������: ����, ����� �� ������������, ����, ��������, �������, ���������.
* ��� OCR � ������� ��������. ��������� � �������, ����������� ���������.
* ����� �� Electron/CEF/���� � �������� � ������� Win32 ����.

## 2. ������� ����������

### 2.1. ��������������

1. ���������� ��������� � YAML (DSL).
2. ��������: ������ PowerShell/Bash, ������ ��������, �������� ����/��������/�����, ����� ����, ���� ������/������, ���� �� ���������� ����������� (� ���������������� � �������), �����������, �����, ��������, �������� �����.
3. ���������� ���������: ��������, ������, ��������, ���������� (Jinja2), �������� ��� ������.
4. ���������� �������?GUI ������� ���� ���� (��������� ����, ���, �����/����), ����������� � ����.
5. ������ ������ (dry?run) ��� ��������� �����/������.

### 2.2. ����������������

* Windows?first (Win10/11 x64). � ����������� � Linux/macOS, �� ������ ��� ������.
* ������������ � DPI, �����������������, ������ ��������� ����������.
* ������� ������������ (Python + PyInstaller one?file).
* ׸���� ��������� �������, ��������� ��� CV � ������� DSL.

### 2.3. ��?���� (����)

* ��� OCR.
* ��� ������� UI?���������� (UIA/AX) �� ������ �����. (�������� ����������� �����.)
* ��� ������� �����������/�������.

## 3. �����������

```
YAML DSL ??> Orchestrator ??> Action Plugins
                         ??> Window Manager (�����/�����/ROI)
                         ??> Vision (OpenCV: grab ? match ? click)
                         ??> Input (����������/����)
                         ??> EventBus ? Overlay GUI + Logger
```

### ����������

* **Orchestrator** � ������ YAML, ���� ��������, ��������/������, ������� ��� GUI.
* **Actions** � �������: `run_ps`, `run_program`, `wait_window`, `window_focus`, `type_text`, `press_key`, `click_image`, `wait_file`, `wait_process`, `log`, `pause`, `checkpoint`, `if_condition`.
* **Window Manager** � ����� ���� �� regex ���������/������/����; ���������� ROI ���� ��� Vision; �����/����������� �� �������.
* **Vision** � ������ ������/ROI (`mss`), ������� ������� (multi?scale, grayscale), �����, N?�������, ����� ���������, ����.
* **Input** � ���������� ��������� ����������/���� (�����������), ���������� ������ �����.
* **Overlay GUI** � ���������� ������ + ����?���, ������ ������, ��������������� ����, �� ����������� ������� �������.

## 4. ���� ����������

* ����: **Python 3.11+**
* YAML: **PyYAML** (��� `ruamel.yaml` ��� ������������� ���������� ������������)
* ����/��������/CV: **pyautogui**, **mss**, **Pillow**, **opencv?python**, **numpy**
* ����/��������: **pygetwindow**, **psutil**
* GUI: **PyQt6**
* ����/CLI: **rich**, **typer** (CLI)
* ������� � YAML: **jinja2**
* ������: **PyInstaller**
* �������� ����: **ruff** + **black** + **mypy**, �����: **pytest**

**����������� ������:** ����������� ������� �����������, ������������ ���� �������� �� Windows, ������� ����������.

## 5. DSL (YAML) � ������������

### 5.1. ����� �����

```yaml
version: 1
settings:
  defaults:
    timeout: 15s         # ��� �� ���������
    retries: 2
    retry_delay: 500ms
  vars:
    key: "YOUR_KEY_HERE"

steps:
  - name: <������������� ��� ���������������� ���>
    action: <��� ��������>
    # ��������� ������� �� action
```

### 5.2. ������� �������

`100ms`, `2s`, `1m`. �����, ��� ���������.

### 5.3. ����������

������������ **Jinja2** ������ �����: `"{{ key }}"`. ������: `settings.vars` + runtime?����������.

### 5.4. �������� � ���������

* `run_ps`

  * `script: <���� .ps1>` ��� `inline: <������>`
  * `args?: [..]` (������������)
  * `timeout?`, `expect_code?` (�� ��������� 0)
* `run_program`

  * `path: <exe>`
  * `args?: [..]`, `cwd?`, `timeout?` (�������� �������� �����������)
* `wait_window`

  * `title: <regex>`
  * `class?: <regex>`
  * `timeout?`
  * `exists: true|false` (�� ��������� true)
* `window_focus`

  * `title: <regex>`
  * `timeout?`
* `type_text`

  * `text: <������>`
  * `per_char_delay?: 20ms`
* `press_key`

  * `key: <enter|tab|esc|�>` ��� `hotkey: ["ctrl","s"]`
* `click_image`

  * `image: <png>`
  * `region?: screen | window | {left,top,width,height}`
  * `threshold?: 0.87`
  * `scale_range?: [0.8,1.2]`
  * `retries?: 2`
  * `retry_delay?: 400ms`
* `wait_file`

  * `path: <������>`
  * `exists: true|false` (�� ��������� true)
  * `timeout?`
* `wait_process`

  * `name: <regex>` ��� `pid: <�����>`
  * `exists: true|false`
  * `timeout?`
* `log`

  * `message: <������>`
* `pause` � ��������� �� ������� ����������� (������� � GUI)
* `checkpoint`

  * `id: <������>` � ����������� � ����������/�������
* `if_condition`

  * `condition: { type: <image_exists|window_exists|file_exists|process_exists>, ... }`
  * `then: [ ���� ]`
  * `else?: [ ���� ]`

### 5.5. ������� (condition)

* `image_exists`

  * `image`, `region?`, `threshold?`, `scale_range?`, `timeout?`
* `window_exists`

  * `title`, `class?`, `timeout?`
* `file_exists`

  * `path`, `timeout?`
* `process_exists`

  * `name|pid`, `timeout?`

### 5.6. ������ � �������

����� ��� ����� ��������� `timeout`, `retries`, `retry_delay`. ��� ���������� � ������ ��������, �������� � ���������.

## 6. ������ �������� (������������� Resilio/Proxifier)

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

## 7. ������ ��������� �����������

**����:** ������������� ���������� ������� ��� ������ ��������� ����������.

**������� ���������� ��������:**

* ���� ������ �� ������� �������� ���� (ROI), ��� �����/����.
* ������ �������� 20�120 px �� ������� �������; ��� �������� (�������� �������, �������).
* �������������� ��� � ������ ���������; ��� ������������� � �������� ����� (�����?�����).
* ��������� ���������������� �� ������ ��������� ���������� (100�150%).
* ������� � `images/` � ���������� ������� � �������������� ���������.

**���������� � ������������ �������:**

* ����������� ������� ����� ��� �������� �����.
* �������������� � PNG ��� ������.
* ��������� ������/��������� ��� ������� ��������� �������.

## 8. �������� Vision. �������� Vision

1. ������ ROI (����� ������ ��� ������ ��������� ����) ����� `mss`.
2. ���������� � grayscale.
3. ������� ��������� (`scale_range`, �� ��������� 0.8�1.2, ��� 0.1).
4. `cv2.matchTemplate(..., TM_CCOEFF_NORMED)` ? �������� ����������.
5. ��������� � `threshold` (�� ��������� 0.87).
6. ������������ ������� (N �������) � ���������.
7. ���� � ����� ���������� ��������������.

## 9. Overlay?GUI (����������)

* 260?140 px, ������ ������, ���������� ����������.
* ���� �������� ���, ����?��� (10�20 �����), ������ `�����`, `����������`, `����`.
* ������� ������� ���������� ��������: `Ctrl+Alt+Esc`.
* ����������� �DRY?RUN� ��� ������� ��������.

## 10. �����������: ���������

```
mini-rpa-runner/
  docs/
    ProjectDoc.md
    README.md
  runner/
    __init__.py
    cli.py              # Typer CLI: run/capture/dry-run
    orchestrator.py
    dsl.py              # ��������� YAML, �����
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
      match.py          # OpenCV ��������
    ui/
      overlay.py
    utils/
      timing.py, paths.py, events.py
  examples/
    resilio_setup.yaml
  tests/
    test_dsl.py
    test_match.py
  pyproject.toml        # �����������, black/ruff/mypy/pytest
  .editorconfig
  .gitignore
```

## 11. �������� ���� � �����

* **PEP8** + ���������� (**black**) + ���� (**ruff**), ��������� (**mypy**).
* �������: **Conventional Commits** (`feat:`, `fix:`, `docs:` �).
* ���������������: **SemVer**.

## 12. ���������� �� ���������

��������� ���������� �� ���������, ��������� � �������� ��������� �� ���������� � ������������ �������. ��� ������������ ���� � ���������� ������� ����������� � ����/issue?������������. � ������������ �������� ������ �����������, ������������ � ����������.

## 13. CLI (������������)

* `run` � ��������� ��������; ������������ ������� � ��������������� ����������.
* `capture` � ��������������� ���������� ��� ���������� ��������� �����������.
* `check` � ����������� ��������� ��������� � ��������.
* ����������: ����������������� ���� ������; ��������� ��� � ���� � ������� �������� � �������.
  CLI (����)
* `runner run <file.yaml> [--vars key=VALUE] [--dry-run] [--log-level info]`
* `runner capture --window <regex> --save <png> [--region window|screen|x,y,w,h]`
* `runner check <file.yaml>` � ��������� DSL

## 14. �������� ������/�������

* ������ ��� ��������� `defaults` � ����� ��������������.
* ��� �������: ���, �������� ROI, ����� �������������� ��� ������������ ����� �������� �������� (�����).

## 15. ������������

* ����?����� DSL (��������/���������� YAML, ������ ����������).
* ����?����� Vision �� ��������� ����������� (�����, �������, ������������������).
* �������������� ������� �� �����?���� (Qt?����������?��������).

## 16. DPI � �����������������

* ��� ������ ��������� ��������������� � ������������ �������.
* ��� `region: window` � ROI = ���������� ������� ����, ��� �����/����.
* ��������� � ���������� ����������� � ������������ DPI.

## 17. ������������

* �������� ��������� �������/�������: ��������������� �� ������ ��������.
* ������� ���������� ����� `--vars`/ENV (�� ������� � YAML). ���� ��� ��������.

## 18. �������� ����� (��������)

**�������� 0 � Bootstrap**

* [ ] ��������� ��������, ������� �����������, CLI?������
* [ ] Orchestrator + ������ YAML + ��������

**�������� 1 � ������� actions**

* [ ] `run_ps`, `run_program`
* [ ] `wait_window`, `window_focus`
* [ ] `type_text`, `press_key`

**�������� 2 � Vision**

* [ ] ������ ������/ROI, multi?scale match, `click_image`, `image_exists`
* [ ] ��������/������/�������� ��� ������

**�������� 3 � Flow/�������/���������**

* [ ] `if_condition`, `pause`, `checkpoint`, `log`

**�������� 4 � Overlay GUI**

* [ ] ����?����, �������, ������� �������, �����/����

**�������� 5 � ���������/������**

* [ ] PyInstaller, DPI?��������, ������ `resilio_setup.yaml`
* [ ] ������������ `README.md`

## 19. ��������

MIT (�� ���������; ����� ���������������).

## 20. �������� ������� (�� �������)

* ����� �� ��������� ������� ����� (������/������)? ���� ��� ������.
* ����� �� �������?������� YAML (`include`, `extends`)? �������� ����� MVP.
* ��������� �� UIA ��� ������������ Vision ��� Electron? �����������.
