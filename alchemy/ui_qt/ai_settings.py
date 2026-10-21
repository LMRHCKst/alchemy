"""Диалог настроек модели: любой OpenAI-совместимый провайдер.

Ключ хранится в профиле пользователя, а не в репозитории. Поле ключа
не показывает значение целиком, а сохранённый ключ маскируется при
открытии окна: чтобы увидеть его, нужно вписать заново.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
    QWidget,
)

from ..ai import local_server, settings_store
from ..ai.client import AiError, ChatClient, Settings
from ..ui import theme


class AiSettingsDialog(QDialog):
    """Окно настройки адреса, ключа и модели."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки модели")
        self.setMinimumWidth(560)
        self.saved = False

        # берём действующие настройки: ключ мог подтянуться из чата сам
        try:
            current, self._origin = settings_store.ensure_ready()
            saved = {
                "api_base": current.api_base,
                "api_key": current.api_key,
                "model": current.model,
                "max_tokens": current.max_tokens,
                "temperature": current.temperature,
            }
        except AiError:
            self._origin = ""
            saved = settings_store.load_saved() or {}

        column = QVBoxLayout(self)
        column.setContentsMargins(18, 16, 18, 16)
        column.setSpacing(10)

        intro = QLabel(
            "Подойдёт любой сервис с OpenAI-совместимым API: GPTunnel, "
            "OpenAI, OpenRouter, DeepSeek, локальные Ollama и LM Studio. "
            "Ключ хранится в профиле пользователя и в репозиторий "
            "не попадает."
        )
        intro.setWordWrap(True)
        intro.setObjectName("PageDesc")
        column.addWidget(intro)

        if self._origin:
            hint = QLabel(f"Сейчас ключ взят оттуда: {self._origin}")
            hint.setWordWrap(True)
            hint.setObjectName("PageDesc")
            column.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self.preset = QComboBox()
        self.preset.addItems([name for name, _url in settings_store.PRESETS])
        self.preset.currentIndexChanged.connect(self._apply_preset)
        form.addRow("Сервис:", self.preset)

        self.base = QLineEdit(str(saved.get("api_base") or ""))
        self.base.setPlaceholderText("https://api.openai.com/v1")
        form.addRow("Адрес API:", self.base)

        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(6)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        existing = str(saved.get("api_key") or "")
        if existing:
            self.key.setPlaceholderText(
                f"сохранён ключ {settings_store.mask(existing)} — оставьте пустым, "
                f"чтобы не менять")
        else:
            self.key.setPlaceholderText("вставьте ключ")
        key_layout.addWidget(self.key, 1)
        self.show_key = QPushButton("Показать")
        self.show_key.setCheckable(True)
        self.show_key.setFixedWidth(110)
        self.show_key.toggled.connect(self._toggle_key)
        key_layout.addWidget(self.show_key)
        form.addRow("Ключ:", key_row)

        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(6)
        self.model = QLineEdit(str(saved.get("model") or ""))
        self.model.setPlaceholderText("например claude-5.5-haiku или gpt-4o-mini")
        model_layout.addWidget(self.model, 1)
        self.check_button = QPushButton("Проверить связь")
        self.check_button.setFixedWidth(160)
        self.check_button.clicked.connect(self._check)
        model_layout.addWidget(self.check_button)
        form.addRow("Модель:", model_row)

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(64, 32000)
        self.max_tokens.setValue(int(saved.get("max_tokens") or 900))
        form.addRow("Максимум токенов:", self.max_tokens)

        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(float(saved.get("temperature") or 0.2))
        form.addRow("Температура:", self.temperature)

        column.addLayout(form)

        # --- локальная модель: движок, файлы, запуск ---
        self.local_box = QWidget()
        local_layout = QVBoxLayout(self.local_box)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(6)

        self.local_hint = QLabel(
            "Локальный режим: llama.cpp поднимает сервер на этом компьютере, "
            "ключ не нужен, интернет не нужен. Модели берутся из папки "
            "models/ рядом с программой или из ALCHEMY_MODELS_DIR.")
        self.local_hint.setWordWrap(True)
        self.local_hint.setObjectName("PageDesc")
        local_layout.addWidget(self.local_hint)

        local_row = QWidget()
        local_buttons = QHBoxLayout(local_row)
        local_buttons.setContentsMargins(0, 0, 0, 0)
        local_buttons.setSpacing(6)

        self.local_models = QComboBox()
        self.local_models.setMinimumWidth(300)
        local_buttons.addWidget(self.local_models, 1)

        self.start_button = QPushButton("Запустить движок")
        self.start_button.setFixedWidth(170)
        self.start_button.clicked.connect(self._start_local)
        local_buttons.addWidget(self.start_button)

        self.stop_button = QPushButton("Остановить")
        self.stop_button.setFixedWidth(120)
        self.stop_button.clicked.connect(self._stop_local)
        local_buttons.addWidget(self.stop_button)

        local_layout.addWidget(local_row)

        self.local_status = QLabel("")
        self.local_status.setWordWrap(True)
        self.local_status.setObjectName("PageDesc")
        local_layout.addWidget(self.local_status)

        column.addWidget(self.local_box)

        self.base.textChanged.connect(self._update_local_visibility)
        self._fill_local_models()
        self._update_local_visibility()

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("PageDesc")
        column.addWidget(self.status)

        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton("Сохранить", QDialogButtonBox.AcceptRole)
        self.clear_button = buttons.addButton("Забыть ключ", QDialogButtonBox.DestructiveRole)
        buttons.addButton("Отмена", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        self.clear_button.clicked.connect(self._forget)
        column.addWidget(buttons)

        # подставить сервис по сохранённому адресу
        for index, (_name, url) in enumerate(settings_store.PRESETS):
            if url and url == self.base.text().strip().rstrip("/"):
                self.preset.setCurrentIndex(index)
                break

    # ---------------- работа ----------------

    def _toggle_key(self, shown: bool) -> None:
        self.key.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)
        self.show_key.setText("Скрыть" if shown else "Показать")

    def _apply_preset(self, index: int) -> None:
        if 0 <= index < len(settings_store.PRESETS):
            url = settings_store.PRESETS[index][1]
            if url:
                self.base.setText(url)
            # для локального режима подставляем файл модели, чтобы
            # облачное имя не осталось в поле
            if url and self._is_local(url) and self.local_models.count():
                current = self.model.text().strip().lower()
                if "gguf" not in current:
                    name = self.local_models.currentText()
                    if name.endswith(".gguf"):
                        self.model.setText(name)

    # ---------------- локальная модель ----------------

    @staticmethod
    def _is_local(url: str) -> bool:
        lowered = (url or "").lower()
        return "127.0.0.1" in lowered or "localhost" in lowered

    def _fill_local_models(self) -> None:
        self.local_models.clear()
        models = local_server.find_models()
        for model in models:
            self.local_models.addItem(model.name, str(model))
        if not models:
            self.local_models.addItem("моделей не найдено", "")
        engine = local_server.find_engine()
        prefix = "движок найден" if engine else "движок не найден"
        self.local_hint.setText(
            f"Локальный режим: llama.cpp поднимает сервер на этом компьютере, "
            f"ключ и интернет не нужны. {prefix}. Модели берутся из папки "
            f"models/ рядом с программой или из ALCHEMY_MODELS_DIR.")

    def _update_local_visibility(self) -> None:
        local = self._is_local(self.base.text())
        self.local_box.setVisible(local)
        if not local:
            return
        if local_server.health():
            self.local_status.setText("Сервер уже работает на этом порту.")
        elif local_server.running():
            self.local_status.setText("Сервер запускается…")
        else:
            self.local_status.setText("Сервер остановлен.")

    def _start_local(self) -> None:
        path = self.local_models.currentData()
        if not path:
            self.local_status.setText(
                "Нет файла модели. Положите .gguf в папку models/ "
                "или укажите путь в ALCHEMY_MODELS_DIR.")
            return

        self.start_button.setEnabled(False)
        self.local_status.setText("Запускаю движок, это может занять до минуты…")
        try:
            ok, message = local_server.start(path)
        finally:
            self.start_button.setEnabled(True)

        self.local_status.setText(message)
        if ok:
            name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
            if not self.model.text().strip() or self._is_local(self.base.text()):
                self.model.setText(name)
            self._check()

    def _stop_local(self) -> None:
        local_server.stop()
        self.local_status.setText("Сервер остановлен.")

    def _values(self) -> dict:
        key = self.key.text().strip()
        if not key:
            saved = settings_store.load_saved() or {}
            key = str(saved.get("api_key") or "")
        # локальной модели ключ не нужен
        if self._is_local(self.base.text()) and not key:
            key = "local"
        return {
            "api_base": self.base.text().strip(),
            "api_key": key,
            "model": self.model.text().strip(),
            "max_tokens": self.max_tokens.value(),
            "temperature": round(self.temperature.value(), 2),
        }

    def _settings(self) -> Settings:
        values = self._values()
        return Settings(
            api_key=values["api_key"],
            api_base=values["api_base"].rstrip("/"),
            model=values["model"],
            max_tokens=values["max_tokens"],
            temperature=values["temperature"],
        )

    def _check(self) -> None:
        """Проверить ключ и, если получится, предложить модели."""
        try:
            settings = self._settings()
        except Exception as exc:  # pragma: no cover - защита от кривого ввода
            self.status.setText(f"Ошибка: {exc}")
            return

        if not settings.api_key or not settings.api_base:
            self.status.setText("Сначала заполните адрес и ключ.")
            return

        self.status.setText("Проверяю…")
        self.check_button.setEnabled(False)
        try:
            names = ChatClient(settings).list_models()
        except AiError as exc:
            self.status.setText(f"Не получилось: {exc}")
            return
        finally:
            self.check_button.setEnabled(True)

        if not names:
            self.status.setText("Связь есть, но список моделей пуст.")
            return

        # подставить текущую модель, если она не введена
        if not self.model.text().strip():
            self.model.setText(names[0])
        preview = ", ".join(names[:6])
        more = f" и ещё {len(names) - 6}" if len(names) > 6 else ""
        self.status.setText(
            f"Связь есть. Моделей доступно: {len(names)}. Например: {preview}{more}.")

    def _save(self) -> None:
        try:
            settings_store.save(self._values())
        except AiError as exc:
            self.status.setText(f"Не сохранено: {exc}")
            return
        self.saved = True
        self.accept()

    def _forget(self) -> None:
        settings_store.clear()
        self.key.clear()
        self.status.setText("Сохранённые настройки удалены из профиля.")
