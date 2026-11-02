"""Settings dialog for uploading finished clips to Discord through a webhook."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from clipshrinker.config import AppConfig
from clipshrinker.discord import DiscordError, get_webhook_info, normalize_webhook_url, parse_webhook_url
from clipshrinker.ui import theme


class _CheckSignals(QObject):
    done = Signal(object, str)  # webhook info dict or None, error


class _CheckTask(QRunnable):
    def __init__(self, url: str, signals: _CheckSignals):
        super().__init__()
        self.url, self.signals = url, signals

    def run(self) -> None:
        try:
            self.signals.done.emit(get_webhook_info(self.url), "")
        except DiscordError as exc:
            self.signals.done.emit(None, str(exc))


class DiscordDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Discord upload")
        self.setMinimumWidth(540)
        self._info = None
        self._checked_url = ""
        self._accept_after_check = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        title = QLabel("Upload finished clips to Discord")
        title.setObjectName("Title")
        lay.addWidget(title)
        intro = QLabel(
            "When this is on, every clip that finishes compressing is posted to the channel the "
            "webhook belongs to. Turn it on or off any time with the <b>Discord</b> switch next to "
            "<b>Start</b>."
        )
        intro.setObjectName("Hint")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit(config.discord_webhook)
        self.url_edit.setPlaceholderText("https://discord.com/api/webhooks/…")
        self.url_edit.setEchoMode(QLineEdit.Password)
        self.show_btn = QPushButton("Show")
        self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(
            lambda on: (self.url_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password),
                        self.show_btn.setText("Hide" if on else "Show"))
        )
        self.test_btn = QPushButton("Test")
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.show_btn)
        url_row.addWidget(self.test_btn)
        form.addRow("Webhook URL", url_row)
        self.message_edit = QLineEdit(config.discord_message)
        self.message_edit.setPlaceholderText("Leave empty to post only the video")
        form.addRow("Message", self.message_edit)
        lay.addLayout(form)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.RichText)
        lay.addWidget(self.status)

        help_text = QLabel(
            "<b>Getting a webhook URL:</b> in Discord open <i>Server Settings → Integrations → "
            "Webhooks → New Webhook</i>, pick the channel, then click <i>Copy Webhook URL</i>.<br>"
            "<b>Message:</b> <code>{name}</code> = clip name, <code>{size}</code> = file size. "
            "Mentions such as @everyone are never triggered.<br>"
            "Discord rejects files over the server's upload limit, so pick a matching Discord "
            "preset. Keep the URL private: anyone who has it can post to that channel."
        )
        help_text.setObjectName("Hint")
        help_text.setWordWrap(True)
        lay.addWidget(help_text)

        self.enable_check = QCheckBox("Upload finished clips automatically")
        self.enable_check.setChecked(config.discord_enabled)
        lay.addWidget(self.enable_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.save_btn = buttons.button(QDialogButtonBox.Save)
        lay.addWidget(buttons)

        self._signals = _CheckSignals()
        self._signals.done.connect(self._on_checked)
        self.test_btn.clicked.connect(self._test)
        self.url_edit.textChanged.connect(self._on_url_changed)

        if config.discord_webhook and config.discord_webhook_name:
            self._info = {"name": config.discord_webhook_name, "guild_id": config.discord_guild_id}
            self._checked_url = config.discord_webhook
            self._show_connected()

    def _on_url_changed(self) -> None:
        self._info = None
        self.status.clear()

    def _test(self) -> bool:
        url = self.url_edit.text().strip()
        if not parse_webhook_url(url):
            self._set_status("That doesn't look like a Discord webhook URL.", theme.DANGER)
            return False
        self._set_status("Checking the webhook…", theme.MUTED)
        self.test_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        QThreadPool.globalInstance().start(_CheckTask(normalize_webhook_url(url), self._signals))
        return True

    def _on_checked(self, info, err: str) -> None:
        self.test_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        if err:
            self._accept_after_check = False
            self._set_status(err, theme.DANGER)
            return
        self._info = info
        self._checked_url = normalize_webhook_url(self.url_edit.text())
        self._show_connected()
        if self._accept_after_check:
            self._accept_after_check = False
            self.accept()

    def _show_connected(self) -> None:
        name = (self._info or {}).get("name") or "webhook"
        self._set_status(f"✓ Connected: clips will be posted as <b>{name}</b>.", theme.SUCCESS)

    def _set_status(self, text: str, color: str) -> None:
        self.status.setText(f"<span style='color:{color}'>{text}</span>")

    def accept(self) -> None:
        url = self.url_edit.text().strip()
        if url and not parse_webhook_url(url):
            self._set_status("That doesn't look like a Discord webhook URL.", theme.DANGER)
            return
        if self.enable_check.isChecked() and not url:
            self._set_status("Paste a webhook URL to turn uploading on.", theme.DANGER)
            return
        if url and (self._info is None or self._checked_url != normalize_webhook_url(url)):
            # Make sure the webhook works before saving it; save once the check succeeds.
            self._accept_after_check = True
            self._test()
            return
        c = self.config
        c.discord_webhook = normalize_webhook_url(url) if url else ""
        c.discord_message = self.message_edit.text()
        c.discord_enabled = self.enable_check.isChecked() and bool(url)
        c.discord_webhook_name = (self._info or {}).get("name", "") if url else ""
        c.discord_guild_id = (self._info or {}).get("guild_id", "") or "" if url else ""
        super().accept()
