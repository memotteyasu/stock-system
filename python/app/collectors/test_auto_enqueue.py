import unittest
from unittest.mock import MagicMock
from datetime import date

from collectors.auto_enqueue import enqueue


class AutoEnqueueTest(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value.__enter__.return_value
        self.cursor.lastrowid = 55

    def test_creates_run_and_request_atomically(self):
        self.cursor.fetchone.side_effect = [(2,), None, None, None]
        self.assertEqual(enqueue(self.conn, date(2026, 11, 25)), 55)
        self.conn.commit.assert_called_once()
        self.assertEqual(self.cursor.execute.call_count, 6)

    def test_existing_date_is_not_duplicated(self):
        self.cursor.fetchone.side_effect = [(2,), (42,)]
        self.assertEqual(enqueue(self.conn, date(2026, 11, 25)), "already_exists")
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_existing_queued_request_prevents_new_run(self):
        self.cursor.fetchone.side_effect = [(2,), None, None, (7,)]
        with self.assertRaises(RuntimeError):
            enqueue(self.conn, date(2026, 11, 25))
        self.conn.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
