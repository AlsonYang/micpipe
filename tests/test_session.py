import unittest

from session import SessionGuard, SessionState


class SessionGuardTests(unittest.TestCase):
    def test_happy_path(self):
        guard = SessionGuard()
        token = guard.begin()
        self.assertIsNotNone(token)
        self.assertTrue(guard.mark_recording(token))
        self.assertEqual(guard.begin_processing(), token)
        self.assertTrue(guard.finish(token))
        self.assertEqual(guard.state, SessionState.IDLE)

    def test_overlapping_start_is_rejected(self):
        guard = SessionGuard()
        self.assertIsNotNone(guard.begin())
        self.assertIsNone(guard.begin())

    def test_cancel_invalidates_late_result(self):
        guard = SessionGuard()
        token = guard.begin()
        guard.mark_recording(token)
        self.assertTrue(guard.cancel())
        self.assertFalse(guard.finish(token))
        self.assertFalse(guard.is_current(token, SessionState.PROCESSING))

    def test_wrong_state_cannot_finish_or_process(self):
        guard = SessionGuard()
        token = guard.begin()
        self.assertIsNone(guard.begin_processing())
        self.assertFalse(guard.finish(token))

    def test_stale_failure_does_not_reset_new_session(self):
        guard = SessionGuard()
        old = guard.begin()
        guard.cancel()
        new = guard.begin()
        self.assertFalse(guard.fail(old))
        self.assertTrue(guard.is_current(new, SessionState.STARTING))


if __name__ == "__main__":
    unittest.main()
