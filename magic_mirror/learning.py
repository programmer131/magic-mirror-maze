"""Small, forgiving vocabulary rounds shared by three children."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class ArabicItem:
    picture: str
    word: str
    roman: str
    meaning: str
    aliases: tuple[str, ...] = ()
    gender: str = 'm'


ARABIC_ITEMS = (
    ArabicItem('book', 'كتاب', 'kitaab', 'Book', ('kitab', 'kitaab')),
    ArabicItem('pencil', 'قلم', 'qalam', 'Pencil', ('qalam', 'kalam')),
    ArabicItem('door', 'باب', 'baab', 'Door', ('bab', 'baab')),
    ArabicItem('house', 'بيت', 'bayt', 'House', ('bayt', 'bait')),
    ArabicItem('chair', 'كرسي', 'kursi', 'Chair', ('kursi', 'kursee')),
    ArabicItem('key', 'مفتاح', 'miftaah', 'Key', ('miftah', 'miftaah')),
)

LETTERS = tuple('ABCDEFGHIJKL')
WORD_HINTS = {
    'A': ('apple', 'ant', 'animal'), 'B': ('ball', 'banana', 'bear'),
    'C': ('cat', 'car', 'cake'), 'D': ('dog', 'duck', 'door'),
    'E': ('egg', 'elephant', 'ear'), 'F': ('fish', 'flower', 'frog'),
    'G': ('goat', 'grapes', 'garden'), 'H': ('hat', 'hen', 'house'),
    'I': ('ice', 'insect', 'island'), 'J': ('jam', 'juice', 'jar'),
    'K': ('key', 'kite', 'king'), 'L': ('lion', 'lemon', 'leaf'),
}
PLACES = {
    'P': ('pakistan', 'paris', 'peru', 'portugal', 'poland'),
    'L': ('lahore', 'london', 'libya', 'lebanon'),
    'K': ('karachi', 'kenya', 'kuwait'),
    'I': ('islamabad', 'india', 'indonesia'),
    'C': ('canada', 'china', 'cairo'),
    'S': ('spain', 'sweden', 'sydney', 'saudi'),
}
ANIMALS = ('cat', 'rabbit', 'bird')


def _known_places() -> tuple[str, ...]:
    """Use the computer's country and time-zone city names, plus our examples."""
    names = {name for examples in PLACES.values() for name in examples}
    try:
        countries = json.loads(Path('/usr/share/iso-codes/json/iso_3166-1.json').read_text())['3166-1']
        names.update(country[key].casefold() for country in countries for key in ('name', 'common_name') if key in country)
    except (OSError, ValueError, KeyError):
        pass
    try:
        for line in Path('/usr/share/zoneinfo/zone.tab').read_text().splitlines():
            if not line.startswith('#'):
                fields = line.split('\t')
                if len(fields) >= 3:
                    names.add(fields[2].rsplit('/', 1)[-1].replace('_', ' ').casefold())
    except OSError:
        pass
    return tuple(sorted(names, key=len, reverse=True))


KNOWN_PLACES = _known_places()


def _arabic_normalize(value: str) -> str:
    value = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', value)
    return value.translate(str.maketrans({
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه',
        'ی': 'ي', 'ے': 'ي', 'ک': 'ك', 'ہ': 'ه', 'ھ': 'ه', 'ۀ': 'ه',
    })).casefold()


def arabic_matches(text: str, item: ArabicItem) -> bool:
    words = re.findall(r'[\u0621-\u064a]+|[a-z]+', _arabic_normalize(text))
    for candidate in (item.word, item.roman, *item.aliases):
        target = re.findall(r'[\u0621-\u064a]+|[a-z]+', _arabic_normalize(candidate))
        if not target:
            continue
        for start in range(len(words) - len(target) + 1):
            actual = words[start:start + len(target)]
            if actual == target or (actual[0] == f'ال{target[0]}' and actual[1:] == target[1:]):
                return True
    return False


def english_word(text: str, letter: str) -> str:
    fillers = {'a', 'an', 'and', 'am', 'the', 'i', 'is', 'it'}
    for word in re.findall(r'[a-z]+', text.casefold()):
        if word not in fillers and word.startswith(letter.casefold()):
            return word
    return ''


@dataclass
class VoiceRound:
    kind: str
    level: int = 1
    turn: int = 0
    answers: list[str] = field(default_factory=list)

    @property
    def current_player(self) -> int | None:
        return self.turn + 1 if self.turn < 3 else None

    @property
    def complete(self) -> bool:
        return self.turn >= 3

    @property
    def letter(self) -> str:
        options = tuple(PLACES) if self.kind == 'places' else LETTERS
        return options[(self.level - 1) % len(options)]

    @property
    def item(self) -> ArabicItem:
        return ARABIC_ITEMS[((self.level - 1) * 3 + self.turn) % len(ARABIC_ITEMS)]

    def accept(self, text: str) -> bool:
        if self.complete:
            return False
        clean = ' '.join(re.findall(r'[a-z]+', text.casefold()))
        answer = ''
        if self.kind == 'arabic':
            if arabic_matches(text, self.item):
                answer = self.item.word
        elif self.kind == 'word_garden':
            answer = english_word(text, self.letter)
        elif self.kind == 'places':
            answer = next((name for name in KNOWN_PLACES if name.startswith(self.letter.casefold())
                           and re.search(r'(?<![a-z])' + re.escape(name) + r'(?![a-z])', clean)), '')
        elif self.kind == 'animals':
            answer = next((name for name in ANIMALS if name in clean.split()), '')
        else:
            answer = clean[:40]
        if not answer:
            return False
        self.answers.append(answer)
        self.turn += 1
        return True
