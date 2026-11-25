import unittest

from magic_mirror.team_games import TEAM_GAMES, TeamGame


class TeamGamesTests(unittest.TestCase):
    def test_each_game_has_three_cooperative_turns_and_no_loss(self):
        for kind in TEAM_GAMES:
            game = TeamGame(kind=kind, level=1)
            self.assertFalse(game.act(2), kind)
            self.assertEqual(game.completed, 0)
            for player in (1, 2, 3):
                self.assertTrue(game.act(player), kind)
                self.assertFalse(game.act(player), kind)
                game.tick(2.0)
            self.assertTrue(game.finished, kind)

    def test_later_levels_change_turn_order(self):
        game = TeamGame(kind='rainbow', level=2)
        self.assertEqual(game.current_player, 2)
        self.assertFalse(game.act(1))
        self.assertTrue(game.act(2))


if __name__ == '__main__':
    unittest.main()
