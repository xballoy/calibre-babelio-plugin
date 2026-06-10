"""Configuration UI and persistent preferences for the Babelio plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from calibre.utils.config import JSONConfig
from qt.core import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    Qt,
    QThread,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from .client import ConnectionStatus
from .parser import TagCategory
from .worker import WorkerConfig

if TYPE_CHECKING:

    def _(text: str) -> str: ...


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# String keys persisted in JSON, in the genre/thème/lieu/quand order Babelio uses.
_TAG_CATEGORY_KEYS = ("genre", "theme", "place", "period")
_DEFAULT_TAG_RELEVANCE = 12

prefs = JSONConfig("plugins/babelio")
prefs.defaults["jsts_token"] = ""
prefs.defaults["user_agent"] = _DEFAULT_USER_AGENT
prefs.defaults["min_interval"] = 1.2
prefs.defaults["max_results"] = 5
prefs.defaults["comments"] = True
prefs.defaults["pubdate"] = True
prefs.defaults["publisher"] = True
prefs.defaults["rating"] = True
prefs.defaults["series"] = True
prefs.defaults["tags"] = True
prefs.defaults["verbosity"] = 5
prefs.defaults["allow_covers"] = True
prefs.defaults["tag_relevance"] = dict.fromkeys(_TAG_CATEGORY_KEYS, _DEFAULT_TAG_RELEVANCE)


def worker_config_from_prefs() -> WorkerConfig:
    stored = prefs["tag_relevance"]
    relevance = {
        TagCategory(key): int(stored.get(key, _DEFAULT_TAG_RELEVANCE))
        for key in _TAG_CATEGORY_KEYS
    }
    return WorkerConfig(
        comments=prefs["comments"],
        pubdate=prefs["pubdate"],
        publisher=prefs["publisher"],
        rating=prefs["rating"],
        series=prefs["series"],
        tags=prefs["tags"],
        tag_relevance=relevance,
    )


class _TestConnectionWorker(QThread):  # type: ignore[misc]
    """Runs the Babelio connection test off the GUI thread; emits the `ConnectionResult`."""

    result_ready = pyqtSignal(object)

    def __init__(
        self, cookie: str, user_agent: str, min_interval: float, parent: QWidget
    ) -> None:
        super().__init__(parent)
        self._cookie = cookie
        self._user_agent = user_agent
        self._min_interval = min_interval

    def run(self) -> None:
        from calibre import browser

        from .client import BabelioClient, ConnectionResult

        try:
            client = BabelioClient(
                browser(), self._cookie, self._user_agent, min_interval=self._min_interval
            )
            result = client.test_connection()
        except Exception as exc:  # noqa: BLE001 — UI worker must never raise across the thread.
            result = ConnectionResult(ConnectionStatus.ERROR, str(exc))
        self.result_ready.emit(result)


class ConfigWidget(QWidget):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(self._build_connection_group())
        layout.addWidget(self._build_fields_group())
        layout.addWidget(self._build_options_group())
        layout.addStretch(1)
        self._load_from_prefs()

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox(_("Babelio connection (anti-bot)"), self)
        outer = QVBoxLayout(group)

        help_label = QLabel(
            _(
                "Babelio blocks automated requests. The <b>jstsToken</b> cookie proves a request "
                "comes from a real logged-in browser session, so the plugin needs a copy of yours:"
            )
            + "<ol>"
            + "<li>"
            + _("Open www.babelio.com in your browser and log in.")
            + "</li><li>"
            + _(
                "Open DevTools (F12) → <b>Application</b> tab → <b>Storage ▸ Cookies</b> → "
                "<code>https://www.babelio.com</code>."
            )
            + "</li><li>"
            + _("Find the <b>jstsToken</b> row and copy its <b>Value</b>.")
            + "</li><li>"
            + _("Paste it below.")
            + "</li></ol>"
            + _(
                "<i>This token expires after about 3 weeks — when imports start failing, repeat "
                "these steps to paste a fresh one.</i>"
            ),
            group,
        )
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)
        help_label.setOpenExternalLinks(True)
        outer.addWidget(help_label)

        form = QFormLayout()
        outer.addLayout(form)

        self.jsts_token = QLineEdit(group)
        self.jsts_token.setPlaceholderText(_("Paste the jstsToken value here"))
        self.jsts_token.setToolTip(
            _("The Babelio session cookie. Expires after about 3 weeks; paste a fresh one when "
              "imports start failing.")
        )
        form.addRow(_("Babelio cookie (jstsToken):"), self.jsts_token)

        self.user_agent = QLineEdit(group)
        self.user_agent.setPlaceholderText(_DEFAULT_USER_AGENT)
        self.user_agent.setToolTip(
            _("Sent with every request; leave as-is unless requests are being blocked. Use the "
              "same browser you copied the cookie from for best results.")
        )
        form.addRow(_("Browser User-Agent (optional):"), self.user_agent)

        self.min_interval = QDoubleSpinBox(group)
        self.min_interval.setRange(0.5, 10.0)
        self.min_interval.setSingleStep(0.1)
        self.min_interval.setSuffix(" s")
        self.min_interval.setToolTip(
            _("Minimum pause between requests to Babelio. Higher is slower but safer against "
              "rate-limiting.")
        )
        form.addRow(_("Minimum delay between requests:"), self.min_interval)

        test_row = QHBoxLayout()
        self.test_button = QPushButton(_("Test connection"), group)
        self.test_button.clicked.connect(self._on_test_connection)
        test_row.addWidget(self.test_button)
        self.test_status = QLabel("", group)
        self.test_status.setTextFormat(Qt.TextFormat.RichText)
        test_row.addWidget(self.test_status, 1)
        outer.addLayout(test_row)

        return group

    def _build_fields_group(self) -> QGroupBox:
        group = QGroupBox(_("Metadata to import"), self)
        outer = QVBoxLayout(group)
        outer.addWidget(QLabel(_("Choose which fields to fetch from Babelio."), group))

        grid = QGridLayout()
        outer.addLayout(grid)
        self.comments = QCheckBox(_("Comments"), group)
        self.pubdate = QCheckBox(_("Published date"), group)
        self.publisher = QCheckBox(_("Publisher"), group)
        self.rating = QCheckBox(_("Rating"), group)
        self.series = QCheckBox(_("Series"), group)
        self.tags = QCheckBox(_("Tags"), group)
        for index, box in enumerate(
            (self.comments, self.pubdate, self.publisher, self.rating, self.series, self.tags)
        ):
            grid.addWidget(box, index // 2, index % 2)

        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox(_("Advanced options"), self)
        outer = QVBoxLayout(group)
        form = QFormLayout()
        outer.addLayout(form)

        self.max_results = QSpinBox(group)
        self.max_results.setRange(1, 20)
        self.max_results.setToolTip(
            _("How many search hits to look up — higher finds more but is slower and riskier.")
        )
        form.addRow(_("Max results:"), self.max_results)

        self.allow_covers = QCheckBox(_("Allow cover download"), group)
        form.addRow(self.allow_covers)

        self.verbosity = QSpinBox(group)
        self.verbosity.setRange(0, 15)
        self.verbosity.setToolTip(_("Higher = more diagnostic logging."))
        form.addRow(_("Verbosity:"), self.verbosity)

        outer.addWidget(self._build_tag_relevance_group(group))
        return group

    def _build_tag_relevance_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox(_("Tag relevance thresholds"), parent)
        outer = QVBoxLayout(group)
        intro = QLabel(
            _(
                "Babelio scores each tag by how strongly readers associate it with the book — its "
                "<b>relevance</b>. For each category, only tags scoring <b>at or above</b> your "
                "threshold are imported; the rest are dropped. <b>Higher = stricter</b> (fewer, more "
                "popular tags); <b>0 = keep every tag</b>. The default of 12 keeps widely-shared "
                "tags and filters out one-offs."
            ),
            group,
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(intro)
        form = QFormLayout()
        outer.addLayout(form)

        tooltip = _(
            "Minimum Babelio relevance score (0–100) a tag must reach to be imported in this "
            "category. 0 keeps all tags; higher keeps only the most popular."
        )
        labels = {
            "genre": _("Genre:"),
            "theme": _("Thème:"),
            "place": _("Lieu:"),
            "period": _("Quand:"),
        }
        self.tag_relevance: dict[str, QSpinBox] = {}
        for key in _TAG_CATEGORY_KEYS:
            spin = QSpinBox(group)
            spin.setRange(0, 100)
            spin.setToolTip(tooltip)
            self.tag_relevance[key] = spin
            form.addRow(labels[key], spin)

        return group

    def _load_from_prefs(self) -> None:
        self.jsts_token.setText(prefs["jsts_token"])
        self.user_agent.setText(prefs["user_agent"])
        self.min_interval.setValue(prefs["min_interval"])
        self.max_results.setValue(prefs["max_results"])
        self.comments.setChecked(prefs["comments"])
        self.pubdate.setChecked(prefs["pubdate"])
        self.publisher.setChecked(prefs["publisher"])
        self.rating.setChecked(prefs["rating"])
        self.series.setChecked(prefs["series"])
        self.tags.setChecked(prefs["tags"])
        self.verbosity.setValue(prefs["verbosity"])
        self.allow_covers.setChecked(prefs["allow_covers"])
        stored = prefs["tag_relevance"]
        for key, spin in self.tag_relevance.items():
            spin.setValue(int(stored.get(key, _DEFAULT_TAG_RELEVANCE)))

    def _on_test_connection(self) -> None:
        cookie = self.jsts_token.text().strip()
        user_agent = self.user_agent.text().strip() or _DEFAULT_USER_AGENT
        if not cookie:
            QMessageBox.warning(
                self, _("Test connection"), _("Enter a jstsToken cookie first.")
            )
            return

        self.test_button.setEnabled(False)
        self.test_status.setText(_("Testing…"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        self._test_worker = _TestConnectionWorker(
            cookie, user_agent, self.min_interval.value(), self
        )
        self._test_worker.result_ready.connect(self._on_test_finished)
        self._test_worker.finished.connect(self._test_worker.deleteLater)
        self._test_worker.start()

    def _on_test_finished(self, result: object) -> None:
        QApplication.restoreOverrideCursor()
        self.test_button.setEnabled(True)

        status = result.status  # type: ignore[attr-defined]
        if status is ConnectionStatus.OK:
            ok_text = _("Connection OK")
            self.test_status.setText(f"<span style='color: green;'>✅ {ok_text}</span>")
            QMessageBox.information(self, _("Test connection"), ok_text)
            return

        message = self._connection_error_message(status, result.detail)  # type: ignore[attr-defined]
        self.test_status.setText(f"<span style='color: red;'>❌ {message}</span>")
        QMessageBox.warning(self, _("Test connection"), message)

    @staticmethod
    def _connection_error_message(status: ConnectionStatus, detail: str) -> str:
        if status is ConnectionStatus.TOKEN_EXPIRED:
            return _(
                "Babelio cookie is missing or expired — paste a fresh jstsToken in the plugin "
                "settings (Preferences → Metadata download → Babelio → Configure)."
            )
        if status is ConnectionStatus.CIRCUIT_OPEN:
            return _("Babelio access is temporarily blocked to avoid an IP ban; try again later.")
        return _("Connection failed: {error}").format(error=detail)

    def save_settings(self) -> None:
        cookie = self.jsts_token.text().strip()
        user_agent = self.user_agent.text().strip()
        if not cookie or not user_agent:
            QMessageBox.warning(
                self,
                _("Babelio settings"),
                _("The Babelio cookie and User-Agent are both required for imports to work. "
                  "Saving anyway, but identify will fail until they are filled in."),
            )

        prefs["jsts_token"] = cookie
        prefs["user_agent"] = user_agent
        prefs["min_interval"] = self.min_interval.value()
        prefs["max_results"] = self.max_results.value()
        prefs["comments"] = self.comments.isChecked()
        prefs["pubdate"] = self.pubdate.isChecked()
        prefs["publisher"] = self.publisher.isChecked()
        prefs["rating"] = self.rating.isChecked()
        prefs["series"] = self.series.isChecked()
        prefs["tags"] = self.tags.isChecked()
        prefs["verbosity"] = self.verbosity.value()
        prefs["allow_covers"] = self.allow_covers.isChecked()
        prefs["tag_relevance"] = {key: spin.value() for key, spin in self.tag_relevance.items()}
