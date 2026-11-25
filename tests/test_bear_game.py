import unittest

from magic_mirror.bear_game import BEAR_LEVELS, BearJourney


class BearJourneyTests(unittest.TestCase):
    def test_three_turns_open_gates_and_bear_reaches_home(self):
        journey = BearJourney()
        for expected in (1, 2, 3):
            self.assertTrue(journey.open_next_gate(expected))
            self.assertEqual(journey.gates_open, expected)
            self.assertFalse(journey.open_next_gate(expected))
            journey.tick(2.0)
        self.assertTrue(journey.home)
        self.assertEqual(journey.position, 3.0)
        self.assertFalse(journey.open_next_gate(3))

    def test_waits_for_another_gesture_at_each_gate(self):
        journey = BearJourney()
        journey.open_next_gate(1)
        journey.tick(5.0)
        journey.tick(5.0)
        self.assertEqual(journey.gates_open, 1)
        self.assertEqual(journey.position, 1.0)
        self.assertFalse(journey.home)

    def test_negative_time_does_not_move_bear(self):
        journey = BearJourney()
        journey.open_next_gate(1)
        journey.tick(-1.0)
        self.assertEqual(journey.position, 0.0)

    def test_only_the_current_players_gesture_opens_their_gate(self):
        journey = BearJourney()
        self.assertEqual(journey.current_player, 1)
        self.assertFalse(journey.open_next_gate(2))
        self.assertEqual(journey.gates_open, 0)
        self.assertTrue(journey.open_next_gate(1))
        journey.tick(2.0)
        self.assertEqual(journey.current_player, 2)
        self.assertFalse(journey.open_next_gate(1))
        self.assertTrue(journey.open_next_gate(2))
        journey.tick(2.0)
        self.assertEqual(journey.current_player, 3)

    def test_twelve_easy_levels_each_have_one_gate_per_player(self):
        self.assertEqual(len(BEAR_LEVELS), 12)
        for level in BEAR_LEVELS:
            self.assertEqual(sorted(level.order), [1, 2, 3])
        self.assertGreater(len({level.order for level in BEAR_LEVELS}), 1)

    def test_level_uses_its_displayed_gate_order(self):
        journey = BearJourney(level=2)
        order = BEAR_LEVELS[1].order
        self.assertEqual(journey.current_player, order[0])
        self.assertFalse(journey.open_next_gate(order[1]))
        self.assertTrue(journey.open_next_gate(order[0]))
        journey.tick(2.0)
        self.assertEqual(journey.current_player, order[1])


if __name__ == '__main__':
    unittest.main()
