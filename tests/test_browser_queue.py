import unittest

from ade.browser_queue import BrowserQueue


class BrowserQueueTests(unittest.TestCase):
    def test_snapshot_is_read_only(self):
        queue = BrowserQueue()
        command = queue.submit("snapshot")
        self.assertEqual(command["action"], "snapshot")
        self.assertEqual(queue.next()["id"], command["id"])

    def test_click_requires_approval(self):
        queue = BrowserQueue()
        with self.assertRaises(PermissionError):
            queue.submit("click", "button")
        self.assertEqual(queue.submit("click", "button", approved=True)["action"], "click")


if __name__ == "__main__":
    unittest.main()
