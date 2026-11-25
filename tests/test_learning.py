import unittest

from magic_mirror.learning import ArabicItem, VoiceRound, arabic_matches, english_word


class LearningTests(unittest.TestCase):
    def test_arabic_answer_accepts_vowels_and_article_but_not_other_objects(self):
        book = ArabicItem('book', 'كتاب', 'kitaab', 'Book', ('kitab', 'kitaab'))
        self.assertTrue(arabic_matches('هَذَا كِتَابٌ', book))
        self.assertTrue(arabic_matches('هذا الكتاب', book))
        self.assertTrue(arabic_matches('haza kitaab', book))
        self.assertFalse(arabic_matches('هذا قلم', book))

    def test_english_word_must_start_with_requested_letter(self):
        self.assertEqual(english_word('an apple', 'A'), 'apple')
        self.assertEqual(english_word('banana', 'A'), '')
        self.assertEqual(english_word('a', 'A'), '')

    def test_voice_round_is_cooperative_and_only_advances_for_a_valid_answer(self):
        game = VoiceRound('word_garden', level=1)
        self.assertEqual(game.current_player, 1)
        self.assertFalse(game.accept('banana'))
        self.assertEqual(game.current_player, 1)
        self.assertTrue(game.accept('apple'))
        self.assertEqual(game.current_player, 2)
        self.assertTrue(game.accept('ant'))
        self.assertTrue(game.accept('apple'))
        self.assertTrue(game.complete)

    def test_arabic_round_accepts_book_without_competitive_failure(self):
        game = VoiceRound('arabic', level=1)
        self.assertEqual(game.item.word, 'كتاب')
        self.assertFalse(game.accept('هذا قلم'))
        self.assertEqual(game.current_player, 1)
        self.assertTrue(game.accept('هذا كتاب'))
        self.assertEqual(game.current_player, 2)
        self.assertEqual(game.item.word, 'قلم')

    def test_places_accepts_more_than_the_displayed_examples(self):
        game = VoiceRound('places', level=1)
        self.assertTrue(game.accept('Poland'))
        self.assertFalse(game.accept('London'))


if __name__ == '__main__':
    unittest.main()
