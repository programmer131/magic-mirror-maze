import unittest

from magic_mirror.board import campaign, reflect, trace


class BoardTests(unittest.TestCase):
    def test_slash_and_backslash(self):
        self.assertEqual(reflect((1, 0), 0), (0, -1))
        self.assertEqual(reflect((1, 0), 1), (0, 1))
        self.assertEqual(reflect((0, 1), 0), (-1, 0))
        self.assertEqual(reflect((0, 1), 1), (1, 0))
        self.assertEqual(reflect((0, -1), 0), (1, 0))
        self.assertEqual(reflect((-1, 0), 1), (0, -1))

    def test_starting_angles_do_not_open_the_chest(self):
        for level in campaign():
            beam = trace(level)
            self.assertFalse(beam.solved, level.name)
            self.assertNotEqual(beam.hit, [1, 2, 3], level.name)

    def test_each_solution_uses_all_three_mirrors(self):
        for level in campaign():
            for mirror, angle in zip(level.mirrors, level.solution):
                mirror.angle = angle
            beam = trace(level)
            self.assertEqual(beam.hit, [1, 2, 3], level.name)
            self.assertTrue(beam.solved, level.name)
            self.assertFalse(beam.blocked, level.name)

    def test_one_wrong_mirror_cannot_win(self):
        for index in range(3):
            for level in campaign():
                for mirror, angle in zip(level.mirrors, level.solution):
                    mirror.angle = angle
                level.mirrors[index].angle = 1 - level.solution[index]
                self.assertFalse(trace(level).solved, f"{level.name} mirror {index + 1}")

    def test_stones_stop_the_wrong_orange_face(self):
        level = campaign()[4]
        for mirror, angle in zip(level.mirrors, level.solution):
            mirror.angle = angle
        level.mirrors[2].angle = 0
        beam = trace(level)
        self.assertTrue(beam.blocked)
        self.assertFalse(beam.solved)

    def test_either_key_flips_then_restores(self):
        mirror = campaign()[0].mirrors[0]
        before = mirror.angle
        mirror.turn(clockwise=True)
        self.assertNotEqual(mirror.angle, before)
        mirror.turn(clockwise=False)
        self.assertEqual(mirror.angle, before)

    def test_campaign_has_six_distinct_levels(self):
        levels = campaign()
        self.assertEqual([level.number for level in levels], [1, 2, 3, 4, 5, 6])
        self.assertEqual(len({level.name for level in levels}), 6)


if __name__ == "__main__":
    unittest.main()
