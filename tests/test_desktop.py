"""The desktop shell must keep the reminder process alive when its window closes."""

import unittest

try:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from habit_garden.desktop import GardenWindow, ICON
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 is not installed")
class DesktopWindowTests(unittest.TestCase):
    def test_close_hides_to_tray_and_reopen_restores_window(self):
        app = QApplication.instance() or QApplication(["habit-garden-test"])
        app.setQuitOnLastWindowClosed(False)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.skipTest("System tray is unavailable")
        window = GardenWindow(QIcon(str(ICON)))
        self.assertTrue(window.tray.isVisible())
        self.assertIsNone(window._view)
        window.show()
        app.processEvents()
        window.close()
        app.processEvents()
        self.assertTrue(window.isHidden())
        self.assertTrue(window.tray.isVisible())
        window.show_from_tray()
        app.processEvents()
        self.assertTrue(window.isVisible())
        window.quit_application()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
