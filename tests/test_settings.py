import json
import tempfile
import unittest
from pathlib import Path

from magic_mirror.settings import load_settings


class SettingsTests(unittest.TestCase):
    def test_loads_names_and_falls_back_when_configuration_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            self.assertEqual(load_settings(path)['players'][0]['name'], 'Player 1')
            path.write_text(json.dumps({'players': [{'name': 'Amna'}, {'name': 'Maryam'}, {'name': 'Abdullah'}]}))
            self.assertEqual([p['name'] for p in load_settings(path)['players']], ['Amna', 'Maryam', 'Abdullah'])


if __name__ == '__main__':
    unittest.main()
