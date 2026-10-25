"""Smoke test the actual emoji picker in Qt's embedded browser."""

import os
import tempfile
import threading
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer, QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QApplication = None

from habit_garden.db import HabitStore
from habit_garden.order import HabitOrder
from habit_garden.server import HabitHTTPServer


def wait(milliseconds):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def evaluate(view, script):
    values = []
    loop = QEventLoop()
    view.page().runJavaScript(script, lambda value: (values.append(value), loop.quit()))
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    if not values:
        raise AssertionError("JavaScript did not respond")
    return values[0]


@unittest.skipUnless(QApplication is not None and (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")), "Qt display is unavailable")
class EmojiPickerUITests(unittest.TestCase):
    def test_search_select_save_emoji_and_reorder_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HabitStore(Path(directory) / "test.db")
            order_path = Path(directory) / "order.json"
            server = HabitHTTPServer(("127.0.0.1", 0), store, order=HabitOrder(order_path))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            app = QApplication.instance() or QApplication(["habit-garden-ui-test"])
            view = QWebEngineView()
            try:
                loaded = []
                loop = QEventLoop()
                view.loadFinished.connect(lambda ok: (loaded.append(ok), loop.quit()))
                view.setUrl(QUrl(f"http://127.0.0.1:{server.server_port}"))
                view.show()
                QTimer.singleShot(5000, loop.quit)
                loop.exec()
                self.assertEqual(loaded, [True])
                evaluate(view, "document.querySelector('#newButton').click(); document.querySelector('#emojiTrigger').click();")
                for _ in range(30):
                    if evaluate(view, "document.querySelector('#emojiGrid').children.length") > 20:
                        break
                    wait(100)
                else:
                    self.fail("Emoji picker did not load")
                evaluate(view, "const s=document.querySelector('#emojiSearch'); s.value='книги'; s.dispatchEvent(new Event('input'));")
                self.assertTrue(evaluate(view, "Array.from(document.querySelectorAll('#emojiGrid button')).some(b=>b.textContent==='📚')"))
                evaluate(view, "Array.from(document.querySelectorAll('#emojiGrid button')).find(b=>b.textContent==='📚').click(); document.querySelector('#taskName').value='Читать'; document.querySelector('#taskForm').requestSubmit();")
                for _ in range(30):
                    if store.list():
                        break
                    wait(100)
                self.assertEqual(store.list()[0]["label_emoji"], "📚")
                for _ in range(30):
                    if evaluate(view, "document.querySelector('.card-emoji')?.textContent") == "📚":
                        break
                    wait(100)
                else:
                    self.fail("Saved emoji was not shown on the card")
                self.assertFalse(evaluate(view, "Boolean(document.querySelector('.status-symbol'))"))
                self.assertEqual(evaluate(view, "getComputedStyle(document.querySelector('.card-emoji')).filter"), "grayscale(1)")
                evaluate(view, "document.querySelector('.task-card').click()")
                for _ in range(30):
                    if store.list()[0]["completed_today"] and evaluate(view, "document.querySelector('.task-card')?.classList.contains('is-done')"):
                        break
                    wait(100)
                else:
                    self.fail("Card did not switch to the completed state")
                self.assertEqual(evaluate(view, "getComputedStyle(document.querySelector('.card-emoji')).filter"), "none")
                first_id = store.list()[0]["id"]
                second_id = store.create({"name": "Прогулка"})["id"]
                evaluate(view, "refresh()")
                for _ in range(30):
                    if evaluate(view, "document.querySelectorAll('.task-card').length") == 2:
                        break
                    wait(100)
                self.assertEqual(evaluate(view, "Array.from(document.querySelectorAll('.task-card')).map(c => c.dataset.taskId).join(',')"), f"{second_id},{first_id}")
                evaluate(view, f"""
                    const source = document.querySelector('[data-task-id="{first_id}"] .drag-handle');
                    const target = document.querySelector('[data-task-id="{second_id}"]');
                    const rect = target.getBoundingClientRect();
                    const data = new DataTransfer();
                    source.dispatchEvent(new DragEvent('dragstart', {{ bubbles: true, dataTransfer: data }}));
                    target.dispatchEvent(new DragEvent('dragover', {{ bubbles: true, cancelable: true, dataTransfer: data, clientX: rect.left + 2, clientY: rect.top + 2 }}));
                    target.dispatchEvent(new DragEvent('drop', {{ bubbles: true, cancelable: true, dataTransfer: data, clientX: rect.left + 2, clientY: rect.top + 2 }}));
                """)
                for _ in range(30):
                    if order_path.exists():
                        break
                    wait(100)
                self.assertEqual(HabitOrder(order_path).load(), [first_id, second_id])
                self.assertEqual(evaluate(view, "Array.from(document.querySelectorAll('.task-card')).map(c => c.dataset.taskId).join(',')"), f"{first_id},{second_id}")
                self.assertTrue(store.get(first_id)["completed_today"])
                self.assertFalse(store.get(second_id)["completed_today"])
                reloaded = []
                reload_loop = QEventLoop()
                view.loadFinished.connect(lambda ok: (reloaded.append(ok), reload_loop.quit()))
                view.reload()
                QTimer.singleShot(5000, reload_loop.quit)
                reload_loop.exec()
                self.assertEqual(reloaded, [True])
                for _ in range(30):
                    order = evaluate(view, "Array.from(document.querySelectorAll('.task-card')).map(c => c.dataset.taskId).join(',')")
                    if order == f"{first_id},{second_id}":
                        break
                    wait(100)
                else:
                    self.fail("Saved order was not restored after reloading the interface")
            finally:
                view.close()
                view.page().deleteLater()
                view.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                app.processEvents()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                store.close()


if __name__ == "__main__":
    unittest.main()
