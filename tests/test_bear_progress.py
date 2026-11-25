import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from magic_mirror.progress import load_bear_progress, save_bear_progress


class BearProgressTests(unittest.TestCase):
    def test_progress_is_saved_separately_and_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bear_progress.json'
            with patch('magic_mirror.progress.BEAR_PATH', path):
                self.assertEqual(load_bear_progress(), [])
                save_bear_progress([3, 1, 3])
                self.assertEqual(load_bear_progress(), [1, 3])


if __name__ == '__main__':
    unittest.main()
