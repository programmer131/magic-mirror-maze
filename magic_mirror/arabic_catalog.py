"""Picture vocabulary for the live tutor, editable independently of its lesson flow."""
import json
from pathlib import Path

from .learning import ArabicItem

# Common alternate spellings and names children may naturally use.
ALIASES = {
    'book': ('kitab', 'kitaab'),
    'pencil': ('قلم', 'qalam', 'kalam', 'qalam rasas'),
    'door': ('bab', 'baab'),
    'house': ('bayt', 'bait'),
    'chair': ('kursi', 'kursee'),
    'key': ('miftah', 'miftaah'),
    'fan': ('mirwaha', 'mirwahatun', 'mirwah'),
    'wall': ('jidar', 'jidaar'),
}


def load_catalog(path: Path | None = None) -> tuple[ArabicItem, ...]:
    path = path or Path(__file__).with_name('arabic_vocabulary.json')
    entries = json.loads(path.read_text(encoding='utf-8'))
    return tuple(ArabicItem(picture=e['picture'], word=e['word'], roman=e['roman'],
                            meaning=e['meaning'], aliases=ALIASES.get(e['picture'], ()),
                            gender=e['gender']) for e in entries)


TUTOR_ITEMS = load_catalog()
