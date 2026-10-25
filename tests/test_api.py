import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from habit_garden.db import HabitStore
from habit_garden.order import HabitOrder
from habit_garden.server import HabitHTTPServer


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = HabitStore(Path(self.temp.name) / "habits.db")
        self.order_path = Path(self.temp.name) / "order.json"
        self.server = HabitHTTPServer(("127.0.0.1", 0), self.store, order=HabitOrder(self.order_path))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.close()
        self.temp.cleanup()

    def request(self, path, method="GET", data=None, headers=None):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(self.base + path, data=body, method=method, headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_end_to_end_api(self):
        status, created = self.request("/api/tasks", "POST", {"name": "Читать", "label_emoji": "📚"})
        self.assertEqual(status, 201)
        self.assertEqual(created["label_emoji"], "📚")
        task_id = created["id"]
        today = created["created_on"]
        status, completed = self.request(f"/api/tasks/{task_id}/days/{today}", "PUT", {"completed": True})
        self.assertEqual(status, 200)
        self.assertTrue(completed["completed_today"])
        self.assertEqual(completed["completion_percent"], 100)
        _, month = self.request(f"/api/tasks/{task_id}/month?year={today[:4]}&month={int(today[5:7])}")
        self.assertEqual(month["days"], [today])
        _, archived = self.request(f"/api/tasks/{task_id}", "PATCH", {"archived": True})
        self.assertTrue(archived["archived"])
        status, _ = self.request(f"/api/tasks/{task_id}/days/{today}", "PUT", {"completed": False})
        self.assertEqual(status, 400)
        _, listing = self.request("/api/tasks")
        self.assertEqual(len(listing["tasks"]), 1)
        self.assertEqual(listing["tasks"][0]["id"], task_id)
        self.assertEqual(listing["tasks"][0]["label_emoji"], "📚")

    def test_rejects_cross_site_mutations_and_serves_interface(self):
        status, _ = self.request("/api/tasks", "POST", {"name": "Сон"}, {"Origin": "https://example.org"})
        self.assertEqual(status, 403)
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertIn("Сад привычек", response.read().decode())
        with urllib.request.urlopen(self.base + "/icon.svg") as response:
            self.assertIn(b"<svg", response.read())
        with urllib.request.urlopen(self.base + "/emoji-catalog.json") as response:
            catalog = json.load(response)
            self.assertEqual(catalog["emojiVersion"], "18.0")
            self.assertGreater(len(catalog["items"]), 1000)

    def test_order_is_kept_in_a_local_file(self):
        _, first = self.request("/api/tasks", "POST", {"name": "Первое"})
        _, second = self.request("/api/tasks", "POST", {"name": "Второе"})
        ids = [first["id"], second["id"]]
        _, listing = self.request("/api/tasks")
        self.assertEqual([task["id"] for task in listing["tasks"]], ids[::-1])
        status, _ = self.request("/api/order", "PUT", {"ids": ids})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(self.order_path.read_text()), ids)
        self.assertEqual(HabitOrder(self.order_path).load(), ids)
        _, listing = self.request("/api/tasks")
        self.assertEqual([task["id"] for task in listing["tasks"]], ids)
        self.assertEqual([task["id"] for task in self.store.list()], ids[::-1])
        _, new_task = self.request("/api/tasks", "POST", {"name": "Новое"})
        _, listing = self.request("/api/tasks")
        self.assertEqual([task["id"] for task in listing["tasks"]], [new_task["id"], *ids])
        self.request(f"/api/tasks/{first['id']}", "PATCH", {"archived": True})
        _, listing = self.request("/api/tasks")
        self.assertEqual([task["id"] for task in listing["tasks"]], [new_task["id"], *ids])
        with sqlite3.connect(self.store.path) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(habits)")]
        self.assertNotIn("sort_order", columns)
        status, _ = self.request("/api/order", "PUT", {"ids": [first["id"], first["id"]]})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
