import unittest

from workflow import poll_for_transcript


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class TranscriptPollingTests(unittest.TestCase):
    def test_returns_only_fresh_nonempty_text(self):
        responses = iter([("WAITING", None), ("WAITING", None), ("TEXT", "fresh text")])
        clock = FakeClock()
        result = poll_for_transcript(
            lambda: next(responses),
            lambda: True,
            2,
            0.1,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        self.assertEqual((result.status, result.text), ("TEXT", "fresh text"))

    def test_timeout_is_bounded(self):
        clock = FakeClock()
        result = poll_for_transcript(
            lambda: ("WAITING", None),
            lambda: True,
            0.3,
            0.1,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        self.assertEqual(result.status, "TIMEOUT")
        self.assertAlmostEqual(clock.now, 0.3)

    def test_cancelled_session_stops_before_read(self):
        reads = 0

        def reader():
            nonlocal reads
            reads += 1
            return "TEXT", "must not be used"

        result = poll_for_transcript(reader, lambda: False, 1, 0.1)
        self.assertEqual(result.status, "CANCELLED")
        self.assertEqual(reads, 0)

    def test_error_and_empty_text_fail_closed(self):
        for response, expected in [
            (("COMPOSER_NOT_FOUND", None), "COMPOSER_NOT_FOUND"),
            (("TEXT", ""), "EMPTY_TRANSCRIPT"),
        ]:
            with self.subTest(response=response):
                result = poll_for_transcript(
                    lambda response=response: response, lambda: True, 1, 0.1
                )
                self.assertEqual(result.status, expected)
                self.assertIsNone(result.text)


if __name__ == "__main__":
    unittest.main()
