"""Catalog and simple level counts for the family game hub."""

from .team_games import TEAM_GAMES

VOICE_GAMES = {
    'word_garden': {'title': 'Word Garden', 'urdu': 'الفاظ کا باغ', 'scene': 'bear_meadow', 'levels': 12},
    'village': {'title': 'Build a Village', 'urdu': 'گاؤں بنائیں', 'scene': 'scene_village', 'levels': 6},
    'animals': {'title': 'Animal Rescue', 'urdu': 'جانوروں کی مدد', 'scene': 'scene_animals', 'levels': 6},
    'story': {'title': 'Story Builder', 'urdu': 'کہانی بنائیں', 'scene': 'scene_music', 'levels': 6},
    'places': {'title': 'Cities & Countries', 'urdu': 'شہر اور ملک', 'scene': 'scene_rainbow', 'levels': 6},
    'arabic': {'title': 'Arabic Pictures', 'urdu': 'عربی الفاظ', 'scene': 'scene_music', 'levels': 2},
}

HUB_KINDS = tuple(TEAM_GAMES) + tuple(VOICE_GAMES)


def activity_info(kind: str) -> dict:
    if kind in TEAM_GAMES:
        return {**TEAM_GAMES[kind], 'levels': 12}
    return VOICE_GAMES[kind]
