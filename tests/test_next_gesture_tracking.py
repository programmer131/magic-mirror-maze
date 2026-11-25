import unittest

from magic_mirror.next_gesture import NextGesture
from magic_mirror.pose_track import Body


class NextGestureTrackingTests(unittest.TestCase):
    def test_short_dropouts_and_unassigned_pose_do_not_cancel_hold(self):
        gesture = NextGesture()
        down = Body(0.4, False, False, None)
        up = Body(0.4, True, True, None)
        self.assertFalse(gesture.update([down], 1.0))
        self.assertTrue(gesture.ready)
        self.assertFalse(gesture.update([up], 1.1))
        self.assertFalse(gesture.update([up], 1.5))
        self.assertFalse(gesture.update([], 1.6))
        self.assertFalse(gesture.update([up], 1.9))
        self.assertFalse(gesture.update([up], 2.4))
        self.assertFalse(gesture.update([up], 2.9))
        self.assertTrue(gesture.update([up], 3.2))
        self.assertFalse(gesture.update([up], 3.5))

    def test_occluded_wrist_does_not_falsely_arm_or_cancel(self):
        gesture = NextGesture()
        uncertain = Body(0.4, False, False, None, False, False)
        up = Body(0.4, True, True, None)
        self.assertFalse(gesture.update([uncertain], 1.0))
        self.assertFalse(gesture.ready)
        self.assertFalse(gesture.update([Body(0.4, False, False, None)], 1.1))
        self.assertFalse(gesture.update([up], 1.2))
        self.assertFalse(gesture.update([up], 1.6))
        self.assertFalse(gesture.update([uncertain], 1.7))
        self.assertFalse(gesture.update([up], 2.0))
        self.assertFalse(gesture.update([up], 2.5))
        self.assertFalse(gesture.update([up], 3.0))
        self.assertTrue(gesture.update([up], 3.3))

    def test_one_visible_arm_can_advance_while_other_is_occluded(self):
        gesture = NextGesture()
        down = Body(0.4, False, False, None, True, False)
        up = Body(0.4, True, False, None, True, False)
        self.assertFalse(gesture.update([down], 1.0))
        self.assertTrue(gesture.ready)
        for t in (1.2, 1.7, 2.2, 2.7, 3.1):
            self.assertFalse(gesture.update([up], t))
        self.assertTrue(gesture.update([up], 3.3))

    def test_an_occluded_raised_arm_cannot_be_armed_by_other_arm(self):
        gesture = NextGesture()
        gesture.update([Body(0.4, False, False, None, False, True)], 1.0)
        up = Body(0.4, True, False, None, True, False)
        for t in (1.1, 1.5, 2.0, 2.5, 3.0, 3.5):
            self.assertFalse(gesture.update([up], t))

    def test_long_absence_requires_lowering_arms_again(self):
        gesture = NextGesture()
        down = Body(0.4, False, False, None)
        up = Body(0.4, True, True, None)
        gesture.update([down], 1.0)
        gesture.update([up], 1.1)
        gesture.update([], 2.1)
        gesture.update([up], 2.2)
        self.assertFalse(gesture.ready)
        for t in (2.5, 3.0, 3.5, 4.0, 4.5):
            self.assertFalse(gesture.update([up], t))


if __name__ == '__main__':
    unittest.main()
