"""Single-instance Qt desktop shell with a tray icon and embedded web view."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QThread, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon

from .cli import PORT, URL, health
from .db import HabitStore, default_database_path
from .reminders import ReminderScheduler
from .server import HabitHTTPServer


log = logging.getLogger(__name__)
ICON = Path(__file__).parent / "static" / "icon.svg"


def instance_name() -> str:
    return f"habit-garden-{os.getuid()}"


def instance_lock() -> QLockFile:
    location = QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)
    if not location:
        location = QStandardPaths.writableLocation(QStandardPaths.TempLocation)
    directory = Path(location) / "habit-garden"
    directory.mkdir(parents=True, exist_ok=True)
    return QLockFile(str(directory / "instance.lock"))


def send_to_instance(command: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(instance_name())
    if not socket.waitForConnected(400):
        return False
    socket.write(f"{command}\n".encode("ascii"))
    socket.waitForBytesWritten(400)
    socket.disconnectFromServer()
    return True


def stop_legacy_server() -> None:
    """Retire the earlier browser-based server before binding the same port."""
    status = health()
    if not status or status["pid"] == os.getpid():
        return
    os.kill(int(status["pid"]), signal.SIGTERM)
    for _ in range(30):
        if not health():
            return
        time.sleep(0.1)
    raise RuntimeError("Предыдущая версия приложения не освободила локальный порт")


class GardenWindow(QMainWindow):
    def __init__(self, icon: QIcon):
        super().__init__()
        self.setWindowTitle("Сад привычек")
        self.setWindowIcon(icon)
        self.resize(1240, 870)
        self.setMinimumSize(700, 520)
        self._quit_requested = False
        self._view: QWebEngineView | None = None
        self._new_after_load = False
        self.tray: QSystemTrayIcon | None = None
        self._setup_tray(icon)

    def _setup_tray(self, icon: QIcon) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("Системный трей недоступен; окно будет закрываться обычным образом")
            return
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Сад привычек")
        menu = QMenu(self)
        open_action = QAction("Открыть Сад привычек", self)
        open_action.triggered.connect(self.show_from_tray)
        menu.addAction(open_action)
        new_action = QAction("Новое задание", self)
        new_action.triggered.connect(self.create_task)
        menu.addAction(new_action)
        menu.addSeparator()
        quit_action = QAction("Выйти", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_from_tray()

    def _load_view(self) -> None:
        self._view = QWebEngineView(self)
        self._view.loadFinished.connect(self._on_loaded)
        self.setCentralWidget(self._view)
        self._view.setUrl(QUrl(URL))

    def _on_loaded(self, ok: bool) -> None:
        if ok and self._new_after_load and self._view:
            self._new_after_load = False
            self._view.page().runJavaScript("openNew()")

    def show_from_tray(self) -> None:
        if self._view is None:
            self._load_view()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def create_task(self) -> None:
        if self._view is None:
            self._new_after_load = True
            self.show_from_tray()
        else:
            self.show_from_tray()
            self._view.page().runJavaScript("openNew()")

    def quit_application(self) -> None:
        self._quit_requested = True
        if self.tray:
            self.tray.hide()
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.tray and self.tray.isVisible() and not self._quit_requested:
            self.hide()
            # Release Chromium's renderer while only the lightweight tray remains.
            old_view = self.takeCentralWidget()
            self._view = None
            if old_view:
                old_view.deleteLater()
            event.ignore()
            return
        event.accept()
        if not self._quit_requested:
            QApplication.instance().quit()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    command = args[0] if args else "launch"
    if command not in ("launch", "background", "stop"):
        raise SystemExit("Использование: run.sh [launch|background|stop]")

    app = QApplication(["habit-garden"])
    app.setApplicationName("habit-garden")
    app.setApplicationDisplayName("Сад привычек")
    app.setOrganizationName("Local")
    app.setDesktopFileName("habit-garden")
    app.setQuitOnLastWindowClosed(False)

    lock = instance_lock()
    if not lock.tryLock(0):
        if command == "background":
            return 0
        request = "quit" if command == "stop" else "show"
        for _ in range(15):
            if send_to_instance(request):
                return 0
            QThread.msleep(100)
        raise RuntimeError("Работающий экземпляр приложения не отвечает")

    try:
        if command == "stop":
            stop_legacy_server()
            return 0

        QLocalServer.removeServer(instance_name())
        singleton_server = QLocalServer(app)
        if not singleton_server.listen(instance_name()):
            raise RuntimeError("Не удалось создать канал единственного экземпляра")

        stop_legacy_server()
        store = HabitStore(default_database_path())
        scheduler = ReminderScheduler(store)
        try:
            http_server = HabitHTTPServer(("127.0.0.1", PORT), store, scheduler)
        except Exception:
            store.close()
            raise
        http_thread = threading.Thread(
            target=http_server.serve_forever,
            kwargs={"poll_interval": 0.5},
            name="habit-http",
            daemon=True,
        )
        scheduler.start()
        http_thread.start()

        window = GardenWindow(QIcon(str(ICON)))

        def handle_connection() -> None:
            while singleton_server.hasPendingConnections():
                connection = singleton_server.nextPendingConnection()
                if connection.waitForReadyRead(400):
                    message = bytes(connection.readAll()).decode("ascii", errors="ignore").strip()
                    if message == "show":
                        window.show_from_tray()
                    elif message == "quit":
                        window.quit_application()
                connection.disconnectFromServer()

        singleton_server.newConnection.connect(handle_connection)
        if command == "launch" or window.tray is None:
            window.show_from_tray()
        try:
            return app.exec()
        finally:
            singleton_server.close()
            if window.tray:
                window.tray.hide()
            http_server.shutdown()
            http_thread.join(timeout=2)
            http_server.server_close()
            scheduler.stop()
            store.close()
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
