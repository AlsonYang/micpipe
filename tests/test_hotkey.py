import unittest

from hotkey import DoubleTapDetector


class DoubleTapDetectorTests(unittest.TestCase):
    def test_two_clean_taps_trigger(self):
        detector = DoubleTapDetector()
        self.assertFalse(detector.modifier_changed(58, True, 1.00))
        self.assertFalse(detector.modifier_changed(58, False, 1.05))
        self.assertFalse(detector.modifier_changed(58, True, 1.20))
        self.assertTrue(detector.modifier_changed(58, False, 1.25))

    def test_single_tap_does_not_trigger(self):
        detector = DoubleTapDetector()
        detector.modifier_changed(58, True, 1.0)
        self.assertFalse(detector.modifier_changed(58, False, 1.1))

    def test_slow_gap_does_not_trigger(self):
        detector = DoubleTapDetector(max_gap_seconds=0.4)
        detector.modifier_changed(58, True, 1.0)
        detector.modifier_changed(58, False, 1.1)
        detector.modifier_changed(58, True, 1.6)
        self.assertFalse(detector.modifier_changed(58, False, 1.7))

    def test_long_press_does_not_count(self):
        detector = DoubleTapDetector(max_press_seconds=0.3)
        detector.modifier_changed(58, True, 1.0)
        detector.modifier_changed(58, False, 1.5)
        detector.modifier_changed(58, True, 1.6)
        self.assertFalse(detector.modifier_changed(58, False, 1.7))

    def test_ordinary_key_invalidates_sequence(self):
        detector = DoubleTapDetector()
        detector.modifier_changed(58, True, 1.0)
        detector.ordinary_key_pressed()
        detector.modifier_changed(58, False, 1.1)
        detector.modifier_changed(58, True, 1.2)
        self.assertFalse(detector.modifier_changed(58, False, 1.3))

    def test_other_modifier_and_mixed_release_fail_closed(self):
        detector = DoubleTapDetector()
        detector.modifier_changed(58, True, 1.0, clean=False)
        detector.modifier_changed(58, False, 1.1)
        detector.modifier_changed(58, True, 1.2)
        self.assertFalse(detector.modifier_changed(61, False, 1.3))


if __name__ == "__main__":
    unittest.main()
