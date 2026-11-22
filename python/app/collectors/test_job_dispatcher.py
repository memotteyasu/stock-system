import signal
import unittest
from unittest.mock import MagicMock, patch

from collectors import job_dispatcher as dispatcher


class FakeCursor:
    def __init__(self, request=None, requests=None):
        self.request = request
        self.requests = requests or []
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.request

    def fetchall(self):
        return self.requests


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.commits = 0
        self.rollbacks = 0
        self.open = True

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.open = False


class JobDispatcherTest(unittest.TestCase):
    def setUp(self):
        dispatcher.shutdown_requested = False

    def tearDown(self):
        dispatcher.shutdown_requested = False

    def test_worker_command_uses_module_and_optional_limit(self):
        self.assertEqual(
            dispatcher.worker_command(42, limit=1),
            [
                dispatcher.sys.executable,
                "-u",
                "-m",
                "collectors.daily_update_worker_v2",
                "--resume",
                "42",
                "--limit",
                "1",
            ],
        )

    def test_dispatcher_lock_failure_does_not_claim_request(self):
        lock_connection = MagicMock()
        lock_connection.open = True
        lock = MagicMock()
        lock.acquire.return_value = False

        with (
            patch.object(dispatcher, "get_connection", return_value=lock_connection) as get_connection,
            patch.object(dispatcher, "JobLock", return_value=lock),
            patch.object(dispatcher, "claim_next_request") as claim_next_request,
        ):
            self.assertEqual(dispatcher.main(), 4)

        self.assertEqual(get_connection.call_count, 1)
        claim_next_request.assert_not_called()

    def test_stop_worker_forwards_sigint_to_process_group(self):
        process = MagicMock()
        process.pid = 123
        process.poll.return_value = None

        with (
            patch.object(dispatcher, "signal_worker_group") as signal_worker_group,
            patch.object(dispatcher, "wait_for_exit", return_value=True),
        ):
            self.assertFalse(dispatcher.stop_worker(process))

        signal_worker_group.assert_called_once_with(process, signal.SIGINT)

    def test_stop_worker_escalates_only_after_grace_period(self):
        process = MagicMock()
        process.pid = 123
        process.poll.return_value = None

        with (
            patch.object(dispatcher, "signal_worker_group") as signal_worker_group,
            patch.object(dispatcher, "wait_for_exit", side_effect=[False, True]),
        ):
            self.assertTrue(dispatcher.stop_worker(process))

        self.assertEqual(
            [call.args[1] for call in signal_worker_group.call_args_list],
            [signal.SIGINT, signal.SIGTERM],
        )

    def test_recovery_keeps_live_worker_and_never_blindly_requeues_running_run(self):
        self.assertEqual(dispatcher.recovery_action("running", True), "keep")
        self.assertEqual(dispatcher.recovery_action("running", False), "fail")
        self.assertEqual(dispatcher.recovery_action("pending", False), "retry")

    def test_worker_liveness_checks_module_and_resume_arguments(self):
        command_line = (
            b"python\0-u\0-m\0collectors.daily_update_worker_v2\0"
            b"--resume\0" b"42\0"
        )
        with patch.object(dispatcher.Path, "read_bytes", return_value=command_line):
            self.assertTrue(dispatcher.is_expected_worker_alive(123, 42))
            self.assertFalse(dispatcher.is_expected_worker_alive(123, 43))

    def test_recovery_only_requeues_pending_run_without_live_worker(self):
        cursor = FakeCursor(requests=[(1, 2, 123, "running"), (2, 3, None, "pending")])
        connection = FakeConnection(cursor)

        with patch.object(dispatcher, "is_expected_worker_alive", side_effect=[True, False]):
            dispatcher.recover_interrupted_requests(connection)

        self.assertEqual(connection.commits, 1)
        updates = [sql for sql, _params in cursor.executed[1:]]
        self.assertEqual(len(updates), 1)
        self.assertIn("status = 'pending'", updates[0])

    def test_claiming_request_marks_same_run_duplicates_failed(self):
        cursor = FakeCursor(request=(10, 2))
        connection = FakeConnection(cursor)

        self.assertEqual(dispatcher.claim_next_request(connection), (10, 2))

        self.assertEqual(connection.commits, 1)
        self.assertIn("重複起動要求", cursor.executed[1][0])
        self.assertEqual(cursor.executed[1][1], (2, 10))

    def test_shutdown_stops_running_worker_before_returning(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.return_value = 130
        lock = MagicMock()
        dispatcher.shutdown_requested = True

        with patch.object(dispatcher, "stop_worker", return_value=False) as stop_worker:
            self.assertEqual(dispatcher.monitor_worker(process, lock), (130, False))

        stop_worker.assert_called_once_with(process)
        lock.check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
