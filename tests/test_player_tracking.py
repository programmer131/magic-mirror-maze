import unittest
from unittest.mock import patch

from magic_mirror.player_tracking import PlayerTracker, calibrate_three


class PlayerTrackerTests(unittest.TestCase):
    def test_three_player_calibration_requires_three_separate_people(self):
        self.assertIsNone(calibrate_three([0.2, 0.6]))
        self.assertIsNone(calibrate_three([0.2, 0.24, 0.8]))
        self.assertEqual(calibrate_three([0.8, 0.2, 0.5]), [3, 1, 2])

    def test_missing_player_does_not_renumber_others(self):
        tracker = PlayerTracker()
        self.assertEqual(tracker.assign([0.2, 0.5, 0.8]), [1, 2, 3])
        self.assertEqual(tracker.assign([0.2, 0.8]), [1, 3])
        self.assertEqual(tracker.assign([0.2, 0.5, 0.8]), [1, 2, 3])

    def test_order_of_detections_does_not_change_identity(self):
        tracker = PlayerTracker()
        tracker.assign([0.2, 0.5, 0.8])
        self.assertEqual(tracker.assign([0.79, 0.21, 0.51]), [3, 1, 2])

    def test_ambiguous_position_is_not_assigned_to_wrong_player(self):
        tracker = PlayerTracker()
        tracker.assign([0.35, 0.45])
        self.assertEqual(tracker.assign([0.40]), [None])

    def test_new_player_can_join_without_stealing_existing_identity(self):
        tracker = PlayerTracker()
        tracker.assign([0.25])
        self.assertEqual(tracker.assign([0.25, 0.75]), [1, 2])

    def test_tracked_player_does_not_take_missing_players_slot(self):
        tracker = PlayerTracker()
        tracker.assign([0.2, 0.5, 0.8])
        tracker.assign([0.5, 0.8])
        self.assertEqual(tracker.assign([0.36, 0.8]), [2, 3])
        self.assertEqual(tracker.assign([0.23, 0.8]), [2, 3])

    def test_recovers_when_visible_players_cannot_match_stale_positions(self):
        tracker = PlayerTracker()
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=1.0):
            tracker.assign([0.1, 0.3, 0.5])
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=2.0):
            self.assertEqual(tracker.assign([0.75, 0.95]), [None, None])
            self.assertFalse(tracker.reassigned)
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=3.6):
            self.assertEqual(tracker.assign([0.75, 0.95]), [1, 2])
            self.assertTrue(tracker.reassigned)

    def test_overlapping_players_do_not_trigger_reassignment(self):
        tracker = PlayerTracker()
        tracker.assign([0.1, 0.3, 0.5])
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=2.0):
            tracker.assign([0.8, 0.81])
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=5.0):
            self.assertEqual(tracker.assign([0.8, 0.81]), [None, None])
            self.assertFalse(tracker.reassigned)

    def test_intermittent_partial_assignment_recovers_unassigned_player(self):
        tracker = PlayerTracker()
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=1.0):
            tracker.assign([0.1, 0.3, 0.5])
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=2.0):
            self.assertEqual(tracker.assign([0.3, 0.95]), [2, None])
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=2.5):
            self.assertEqual(tracker.assign([0.3]), [2])
        with patch('magic_mirror.player_tracking.time.monotonic', return_value=3.6):
            players = tracker.assign([0.3, 0.95])
            self.assertEqual(players[0], 2)
            self.assertIsNotNone(players[1])
            self.assertNotEqual(players[0], players[1])
            self.assertTrue(tracker.reassigned)


if __name__ == '__main__':
    unittest.main()
