import html
import io
import json
import math
import time
import unicodedata
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import picture_sphere

st.set_page_config(page_title="HexSphere Studio", page_icon="Hex", layout="wide")

APP_VERSION = "1.0.0"

MATERIAL_PRESETS = {
    "Matte": {"alpha": 1.0, "flatshading": True},
    "Glossy": {"alpha": 0.85, "flatshading": False},
    "Metallic": {"alpha": 0.7, "flatshading": False},
}

WALL_END_OPTIONS = ["Empty", "Filter", "Lense", "Hollow Magnet", "Solid Magnet"]

# (start, end, name) — standard Unicode block ranges (public Unicode Consortium data).
UNICODE_BLOCKS = [
    (0x0000, 0x007F, "Basic Latin"),
    (0x0080, 0x00FF, "Latin-1 Supplement"),
    (0x0100, 0x017F, "Latin Extended-A"),
    (0x0180, 0x024F, "Latin Extended-B"),
    (0x0250, 0x02AF, "IPA Extensions"),
    (0x02B0, 0x02FF, "Spacing Modifier Letters"),
    (0x0300, 0x036F, "Combining Diacritical Marks"),
    (0x0370, 0x03FF, "Greek and Coptic"),
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0500, 0x052F, "Cyrillic Supplement"),
    (0x0530, 0x058F, "Armenian"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0700, 0x074F, "Syriac"),
    (0x0750, 0x077F, "Arabic Supplement"),
    (0x0780, 0x07BF, "Thaana"),
    (0x07C0, 0x07FF, "NKo"),
    (0x0800, 0x083F, "Samaritan"),
    (0x0840, 0x085F, "Mandaic"),
    (0x08A0, 0x08FF, "Arabic Extended-A"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Oriya"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0D80, 0x0DFF, "Sinhala"),
    (0x0E00, 0x0E7F, "Thai"),
    (0x0E80, 0x0EFF, "Lao"),
    (0x0F00, 0x0FFF, "Tibetan"),
    (0x1000, 0x109F, "Myanmar"),
    (0x10A0, 0x10FF, "Georgian"),
    (0x1100, 0x11FF, "Hangul Jamo"),
    (0x1200, 0x137F, "Ethiopic"),
    (0x1380, 0x139F, "Ethiopic Supplement"),
    (0x13A0, 0x13FF, "Cherokee"),
    (0x1400, 0x167F, "Unified Canadian Aboriginal Syllabics"),
    (0x1680, 0x169F, "Ogham"),
    (0x16A0, 0x16FF, "Runic"),
    (0x1700, 0x171F, "Tagalog"),
    (0x1720, 0x173F, "Hanunoo"),
    (0x1740, 0x175F, "Buhid"),
    (0x1760, 0x177F, "Tagbanwa"),
    (0x1780, 0x17FF, "Khmer"),
    (0x1800, 0x18AF, "Mongolian"),
    (0x1900, 0x194F, "Limbu"),
    (0x1950, 0x197F, "Tai Le"),
    (0x1980, 0x19DF, "New Tai Lue"),
    (0x19E0, 0x19FF, "Khmer Symbols"),
    (0x1A00, 0x1A1F, "Buginese"),
    (0x1A20, 0x1AAF, "Tai Tham"),
    (0x1B00, 0x1B7F, "Balinese"),
    (0x1B80, 0x1BBF, "Sundanese"),
    (0x1BC0, 0x1BFF, "Batak"),
    (0x1C00, 0x1C4F, "Lepcha"),
    (0x1C50, 0x1C7F, "Ol Chiki"),
    (0x1CD0, 0x1CFF, "Vedic Extensions"),
    (0x1D00, 0x1D7F, "Phonetic Extensions"),
    (0x1D80, 0x1DBF, "Phonetic Extensions Supplement"),
    (0x1DC0, 0x1DFF, "Combining Diacritical Marks Supplement"),
    (0x1E00, 0x1EFF, "Latin Extended Additional"),
    (0x1F00, 0x1FFF, "Greek Extended"),
    (0x2000, 0x206F, "General Punctuation"),
    (0x2070, 0x209F, "Superscripts and Subscripts"),
    (0x20A0, 0x20CF, "Currency Symbols"),
    (0x20D0, 0x20FF, "Combining Diacritical Marks for Symbols"),
    (0x2100, 0x214F, "Letterlike Symbols"),
    (0x2150, 0x218F, "Number Forms"),
    (0x2190, 0x21FF, "Arrows"),
    (0x2200, 0x22FF, "Mathematical Operators"),
    (0x2300, 0x23FF, "Miscellaneous Technical"),
    (0x2400, 0x243F, "Control Pictures"),
    (0x2440, 0x245F, "Optical Character Recognition"),
    (0x2460, 0x24FF, "Enclosed Alphanumerics"),
    (0x2500, 0x257F, "Box Drawing"),
    (0x2580, 0x259F, "Block Elements"),
    (0x25A0, 0x25FF, "Geometric Shapes"),
    (0x2600, 0x26FF, "Miscellaneous Symbols"),
    (0x2700, 0x27BF, "Dingbats"),
    (0x27C0, 0x27EF, "Miscellaneous Mathematical Symbols-A"),
    (0x27F0, 0x27FF, "Supplemental Arrows-A"),
    (0x2800, 0x28FF, "Braille Patterns"),
    (0x2900, 0x297F, "Supplemental Arrows-B"),
    (0x2980, 0x29FF, "Miscellaneous Mathematical Symbols-B"),
    (0x2A00, 0x2AFF, "Supplemental Mathematical Operators"),
    (0x2B00, 0x2BFF, "Miscellaneous Symbols and Arrows"),
    (0x2C00, 0x2C5F, "Glagolitic"),
    (0x2C60, 0x2C7F, "Latin Extended-C"),
    (0x2C80, 0x2CFF, "Coptic"),
    (0x2D00, 0x2D2F, "Georgian Supplement"),
    (0x2D30, 0x2D7F, "Tifinagh"),
    (0x2D80, 0x2DDF, "Ethiopic Extended"),
    (0x2DE0, 0x2DFF, "Cyrillic Extended-A"),
    (0x2E00, 0x2E7F, "Supplemental Punctuation"),
    (0x2E80, 0x2EFF, "CJK Radicals Supplement"),
    (0x2F00, 0x2FDF, "Kangxi Radicals"),
    (0x2FF0, 0x2FFF, "Ideographic Description Characters"),
    (0x3000, 0x303F, "CJK Symbols and Punctuation"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x3100, 0x312F, "Bopomofo"),
    (0x3130, 0x318F, "Hangul Compatibility Jamo"),
    (0x3190, 0x319F, "Kanbun"),
    (0x31A0, 0x31BF, "Bopomofo Extended"),
    (0x31C0, 0x31EF, "CJK Strokes"),
    (0x31F0, 0x31FF, "Katakana Phonetic Extensions"),
    (0x3200, 0x32FF, "Enclosed CJK Letters and Months"),
    (0x3300, 0x33FF, "CJK Compatibility"),
    (0x3400, 0x4DBF, "CJK Unified Ideographs Extension A"),
    (0x4DC0, 0x4DFF, "Yijing Hexagram Symbols"),
    (0x4E00, 0x9FFF, "CJK Unified Ideographs"),
    (0xA000, 0xA48F, "Yi Syllables"),
    (0xA490, 0xA4CF, "Yi Radicals"),
    (0xA4D0, 0xA4FF, "Lisu"),
    (0xA500, 0xA63F, "Vai"),
    (0xA640, 0xA69F, "Cyrillic Extended-B"),
    (0xA6A0, 0xA6FF, "Bamum"),
    (0xA700, 0xA71F, "Modifier Tone Letters"),
    (0xA720, 0xA7FF, "Latin Extended-D"),
    (0xA800, 0xA82F, "Syloti Nagri"),
    (0xA830, 0xA83F, "Common Indic Number Forms"),
    (0xA840, 0xA87F, "Phags-pa"),
    (0xA880, 0xA8DF, "Saurashtra"),
    (0xA8E0, 0xA8FF, "Devanagari Extended"),
    (0xA900, 0xA92F, "Kayah Li"),
    (0xA930, 0xA95F, "Rejang"),
    (0xA960, 0xA97F, "Hangul Jamo Extended-A"),
    (0xA980, 0xA9DF, "Javanese"),
    (0xAA00, 0xAA5F, "Cham"),
    (0xAA60, 0xAA7F, "Myanmar Extended-A"),
    (0xAA80, 0xAADF, "Tai Viet"),
    (0xAAE0, 0xAAFF, "Meetei Mayek Extensions"),
    (0xAB00, 0xAB2F, "Ethiopic Extended-A"),
    (0xAB30, 0xAB6F, "Latin Extended-E"),
    (0xAB70, 0xABBF, "Cherokee Supplement"),
    (0xABC0, 0xABFF, "Meetei Mayek"),
    (0xAC00, 0xD7AF, "Hangul Syllables"),
    (0xD7B0, 0xD7FF, "Hangul Jamo Extended-B"),
    (0xD800, 0xDB7F, "High Surrogates"),
    (0xDB80, 0xDBFF, "High Private Use Surrogates"),
    (0xDC00, 0xDFFF, "Low Surrogates"),
    (0xE000, 0xF8FF, "Private Use Area"),
    (0xF900, 0xFAFF, "CJK Compatibility Ideographs"),
    (0xFB00, 0xFB4F, "Alphabetic Presentation Forms"),
    (0xFB50, 0xFDFF, "Arabic Presentation Forms-A"),
    (0xFE00, 0xFE0F, "Variation Selectors"),
    (0xFE10, 0xFE1F, "Vertical Forms"),
    (0xFE20, 0xFE2F, "Combining Half Marks"),
    (0xFE30, 0xFE4F, "CJK Compatibility Forms"),
    (0xFE50, 0xFE6F, "Small Form Variants"),
    (0xFE70, 0xFEFF, "Arabic Presentation Forms-B"),
    (0xFF00, 0xFFEF, "Halfwidth and Fullwidth Forms"),
    (0xFFF0, 0xFFFF, "Specials"),
    (0x10000, 0x1007F, "Linear B Syllabary"),
    (0x10100, 0x1013F, "Aegean Numbers"),
    (0x10140, 0x1018F, "Ancient Greek Numbers"),
    (0x10190, 0x101CF, "Ancient Symbols"),
    (0x101D0, 0x101FF, "Phaistos Disc"),
    (0x10280, 0x1029F, "Lycian"),
    (0x102A0, 0x102DF, "Carian"),
    (0x102E0, 0x102FF, "Coptic Epact Numbers"),
    (0x10300, 0x1032F, "Old Italic"),
    (0x10330, 0x1034F, "Gothic"),
    (0x10350, 0x1037F, "Old Permic"),
    (0x10380, 0x1039F, "Ugaritic"),
    (0x103A0, 0x103DF, "Old Persian"),
    (0x10400, 0x1044F, "Deseret"),
    (0x10450, 0x1047F, "Shavian"),
    (0x10480, 0x104AF, "Osmanya"),
    (0x104B0, 0x104FF, "Osage"),
    (0x10500, 0x1052F, "Elbasan"),
    (0x10530, 0x1056F, "Caucasian Albanian"),
    (0x10600, 0x1077F, "Linear A"),
    (0x10800, 0x1083F, "Cypriot Syllabary"),
    (0x10840, 0x1085F, "Imperial Aramaic"),
    (0x10860, 0x1087F, "Palmyrene"),
    (0x10880, 0x108AF, "Nabataean"),
    (0x108E0, 0x108FF, "Hatran"),
    (0x10900, 0x1091F, "Phoenician"),
    (0x10920, 0x1093F, "Lydian"),
    (0x10980, 0x1099F, "Meroitic Hieroglyphs"),
    (0x109A0, 0x109FF, "Meroitic Cursive"),
    (0x10A00, 0x10A5F, "Kharoshthi"),
    (0x10A60, 0x10A7F, "Old South Arabian"),
    (0x10A80, 0x10A9F, "Old North Arabian"),
    (0x10AC0, 0x10AFF, "Manichaean"),
    (0x10B00, 0x10B3F, "Avestan"),
    (0x10B40, 0x10B5F, "Inscriptional Parthian"),
    (0x10B60, 0x10B7F, "Inscriptional Pahlavi"),
    (0x10B80, 0x10BAF, "Psalter Pahlavi"),
    (0x10C00, 0x10C4F, "Old Turkic"),
    (0x10C80, 0x10CFF, "Old Hungarian"),
    (0x10D00, 0x10D3F, "Hanifi Rohingya"),
    (0x10E60, 0x10E7F, "Rumi Numeral Symbols"),
    (0x10E80, 0x10EBF, "Yezidi"),
    (0x10F00, 0x10F2F, "Old Sogdian"),
    (0x10F30, 0x10F6F, "Sogdian"),
    (0x10FB0, 0x10FDF, "Chorasmian"),
    (0x10FE0, 0x10FFF, "Elymaic"),
    (0x11000, 0x1107F, "Brahmi"),
    (0x11080, 0x110CF, "Kaithi"),
    (0x110D0, 0x110FF, "Sora Sompeng"),
    (0x11100, 0x1114F, "Chakma"),
    (0x11150, 0x1117F, "Mahajani"),
    (0x11180, 0x111DF, "Sharada"),
    (0x111E0, 0x111FF, "Sinhala Archaic Numbers"),
    (0x11200, 0x1124F, "Khojki"),
    (0x11280, 0x112AF, "Multani"),
    (0x112B0, 0x112FF, "Khudawadi"),
    (0x11300, 0x1137F, "Grantha"),
    (0x11400, 0x1147F, "Newa"),
    (0x11480, 0x114DF, "Tirhuta"),
    (0x11580, 0x115FF, "Siddham"),
    (0x11600, 0x1165F, "Modi"),
    (0x11660, 0x1167F, "Mongolian Supplement"),
    (0x11680, 0x116CF, "Takri"),
    (0x11700, 0x1174F, "Ahom"),
    (0x11800, 0x1184F, "Dogra"),
    (0x118A0, 0x118FF, "Warang Citi"),
    (0x11900, 0x1195F, "Dives Akuru"),
    (0x119A0, 0x119FF, "Nandinagari"),
    (0x11A00, 0x11A4F, "Zanabazar Square"),
    (0x11A50, 0x11AAF, "Soyombo"),
    (0x11AC0, 0x11AFF, "Pau Cin Hau"),
    (0x11C00, 0x11C6F, "Bhaiksuki"),
    (0x11C70, 0x11CBF, "Marchen"),
    (0x11D00, 0x11D5F, "Masaram Gondi"),
    (0x11D60, 0x11DAF, "Gunjala Gondi"),
    (0x11EE0, 0x11EFF, "Makasar"),
    (0x11F00, 0x11F5F, "Kawi"),
    (0x12000, 0x123FF, "Cuneiform"),
    (0x12400, 0x1247F, "Cuneiform Numbers and Punctuation"),
    (0x12480, 0x1254F, "Early Dynastic Cuneiform"),
    (0x13000, 0x1342F, "Egyptian Hieroglyphs"),
    (0x13430, 0x1345F, "Egyptian Hieroglyph Format Controls"),
    (0x14400, 0x1467F, "Anatolian Hieroglyphs"),
    (0x16800, 0x16A3F, "Bamum Supplement"),
    (0x16A40, 0x16A6F, "Mro"),
    (0x16AD0, 0x16AFF, "Bassa Vah"),
    (0x16B00, 0x16B8F, "Pahawh Hmong"),
    (0x16E40, 0x16E9F, "Medefaidrin"),
    (0x16F00, 0x16F9F, "Miao"),
    (0x16FE0, 0x16FFF, "Ideographic Symbols and Punctuation"),
    (0x17000, 0x187FF, "Tangut"),
    (0x18800, 0x18AFF, "Tangut Components"),
    (0x18B00, 0x18CFF, "Khitan Small Script"),
    (0x18D00, 0x18D7F, "Tangut Supplement"),
    (0x1B000, 0x1B0FF, "Kana Supplement"),
    (0x1B100, 0x1B12F, "Kana Extended-A"),
    (0x1B130, 0x1B16F, "Small Kana Extension"),
    (0x1B170, 0x1B2FF, "Nushu"),
    (0x1BC00, 0x1BC9F, "Duployan"),
    (0x1BCA0, 0x1BCAF, "Shorthand Format Controls"),
    (0x1CF00, 0x1CFCF, "Znamenny Musical Notation"),
    (0x1D000, 0x1D0FF, "Byzantine Musical Symbols"),
    (0x1D100, 0x1D1FF, "Musical Symbols"),
    (0x1D200, 0x1D24F, "Ancient Greek Musical Notation"),
    (0x1D2C0, 0x1D2DF, "Kaktovik Numerals"),
    (0x1D2E0, 0x1D2FF, "Mayan Numerals"),
    (0x1D300, 0x1D35F, "Tai Xuan Jing Symbols"),
    (0x1D360, 0x1D37F, "Counting Rod Numerals"),
    (0x1D400, 0x1D7FF, "Mathematical Alphanumeric Symbols"),
    (0x1D800, 0x1DAAF, "Sutton SignWriting"),
    (0x1DF00, 0x1DFFF, "Latin Extended-G"),
    (0x1E000, 0x1E02F, "Glagolitic Supplement"),
    (0x1E030, 0x1E08F, "Cyrillic Extended-D"),
    (0x1E100, 0x1E14F, "Nyiakeng Puachue Hmong"),
    (0x1E290, 0x1E2BF, "Toto"),
    (0x1E2C0, 0x1E2FF, "Wancho"),
    (0x1E4D0, 0x1E4FF, "Nag Mundari"),
    (0x1E7E0, 0x1E7FF, "Ethiopic Extended-B"),
    (0x1E800, 0x1E8DF, "Mende Kikakui"),
    (0x1E900, 0x1E95F, "Adlam"),
    (0x1EC70, 0x1ECBF, "Indic Siyaq Numbers"),
    (0x1ED00, 0x1ED4F, "Ottoman Siyaq Numbers"),
    (0x1EE00, 0x1EEFF, "Arabic Mathematical Alphabetic Symbols"),
    (0x1F000, 0x1F02F, "Mahjong Tiles"),
    (0x1F030, 0x1F09F, "Domino Tiles"),
    (0x1F0A0, 0x1F0FF, "Playing Cards"),
    (0x1F100, 0x1F1FF, "Enclosed Alphanumeric Supplement"),
    (0x1F200, 0x1F2FF, "Enclosed Ideographic Supplement"),
    (0x1F300, 0x1F5FF, "Miscellaneous Symbols and Pictographs"),
    (0x1F600, 0x1F64F, "Emoticons"),
    (0x1F650, 0x1F67F, "Ornamental Dingbats"),
    (0x1F680, 0x1F6FF, "Transport and Map Symbols"),
    (0x1F700, 0x1F77F, "Alchemical Symbols"),
    (0x1F780, 0x1F7FF, "Geometric Shapes Extended"),
    (0x1F800, 0x1F8FF, "Supplemental Arrows-C"),
    (0x1F900, 0x1F9FF, "Supplemental Symbols and Pictographs"),
    (0x1FA00, 0x1FA6F, "Chess Symbols"),
    (0x1FA70, 0x1FAFF, "Symbols and Pictographs Extended-A"),
    (0x1FB00, 0x1FBFF, "Symbols for Legacy Computing"),
    (0x20000, 0x2A6DF, "CJK Unified Ideographs Extension B"),
    (0x2A700, 0x2B73F, "CJK Unified Ideographs Extension C"),
    (0x2B740, 0x2B81F, "CJK Unified Ideographs Extension D"),
    (0x2B820, 0x2CEAF, "CJK Unified Ideographs Extension E"),
    (0x2CEB0, 0x2EBEF, "CJK Unified Ideographs Extension F"),
    (0x2F800, 0x2FA1F, "CJK Compatibility Ideographs Supplement"),
    (0x30000, 0x3134F, "CJK Unified Ideographs Extension G"),
    (0x31350, 0x323AF, "CJK Unified Ideographs Extension H"),
    (0xE0000, 0xE007F, "Tags"),
    (0xE0100, 0xE01EF, "Variation Selectors Supplement"),
    (0xF0000, 0xFFFFF, "Supplementary Private Use Area-A"),
    (0x100000, 0x10FFFF, "Supplementary Private Use Area-B"),
]


def safe_chr(codepoint):
    try:
        return chr(codepoint)
    except (ValueError, OverflowError):
        return ""


def unicode_glyph(codepoint):
    """Return a printable representation without passing unsafe code points to Streamlit/HTML."""
    character = safe_chr(codepoint)
    category = unicodedata.category(character) if character else "Cn"
    if category[0] == "C":
        return "\u25A1"
    if category[0] == "M":
        return "\u25CC" + character
    return character


def format_unicode_value(codepoint, value_format):
    if value_format == "Decimal":
        return str(codepoint)
    if value_format == "UC32":
        return f"U+{codepoint:06X}" if codepoint > 0xFFFF else f"U+{codepoint:04X}"
    if value_format == "UC16/Surrogate Pair":
        if codepoint <= 0xFFFF:
            return f"U+{codepoint:04X}"
        offset = codepoint - 0x10000
        high = 0xD800 + (offset >> 10)
        low = 0xDC00 + (offset & 0x3FF)
        return f"U+{high:04X} U+{low:04X} (surrogate pair)"
    return str(codepoint)


def select_unichar(codepoint):
    st.session_state.uni_selected_char = codepoint


def reset_unicode_offsets():
    st.session_state.uni_selected_char = UNICODE_BLOCKS[st.session_state.uni_category_idx][0]


def search_unicode_category():
    query = st.session_state.uni_search_text.strip().lower()
    if not query:
        st.session_state.uni_search_match_count = None
        return
    matches = [i for i, (_, _, name) in enumerate(UNICODE_BLOCKS) if query in name.lower()]
    st.session_state.uni_search_match_count = len(matches)
    if matches:
        st.session_state.uni_category_idx = matches[0]
        reset_unicode_offsets()

UNICODE_FONT_OPTIONS = {
    "Segoe UI Symbol — symbols and math": '"Segoe UI Symbol", "Segoe UI", sans-serif',
    "Segoe UI Emoji — emoji and pictographs": '"Segoe UI Emoji", "Segoe UI Symbol", sans-serif',
    "Noto Sans Symbols 2 — symbols and math": '"Noto Sans Symbols 2", "Noto Sans Symbols", sans-serif',
    "Noto Color Emoji — color emoji": '"Noto Color Emoji", "Segoe UI Emoji", sans-serif',
    "Noto Music — musical notation": '"Noto Music", "Noto Sans Symbols 2", sans-serif',
    "Symbola — broad Unicode coverage": '"Symbola", "Noto Sans Symbols 2", sans-serif',
    "DejaVu Sans — general Unicode": '"DejaVu Sans", sans-serif',
}


def generate_obj_text(vertices, faces, object_name=None, params=None):
    lines = ["# HexSphere Studio model"]
    if object_name:
        lines.append(f"# object_type: {object_name}")
    if params:
        lines.append(f"# metadata: {json.dumps(params)}")
    for x, y, z in vertices:
        lines.append(f"v {x} {y} {z}")
    for a, b, c in faces:
        lines.append(f"f {a+1} {b+1} {c+1}")
    return "\n".join(lines)


def rotate_vertices(vertices, angles, scale=1.0):
    result = []
    ax_pairs = [(0, 1, angles[0]), (1, 2, angles[1]), (2, 0, angles[2])]
    for p in vertices:
        coords = list(p)
        for a, b, n in ax_pairs:
            rad = math.radians(n)
            c, s = math.cos(rad), math.sin(rad)
            qa, qb = coords[a], coords[b]
            coords[a] = qa * c - qb * s
            coords[b] = qa * s + qb * c
        result.append((coords[0] * scale, coords[1] * scale, coords[2] * scale))
    return result


def build_plotly_figure(
    vertices,
    faces,
    edge_indices,
    thickness=3,
    angles=(20, 25, 0),
    scale=1.0,
    color="#F4B942",
    alpha=0.94,
    flatshading=True,
    show_grid=False,
    face_colors=None,
    label_mesh=None,
):
    v = rotate_vertices(vertices, angles, scale)
    x = [p[0] for p in v]
    y = [p[1] for p in v]
    z = [p[2] for p in v]
    i = [face[0] for face in faces]
    j = [face[1] for face in faces]
    k = [face[2] for face in faces]

    edge_x = []
    edge_y = []
    edge_z = []
    for a, b in edge_indices:
        if a < len(v) and b < len(v):
            edge_x.extend([v[a][0], v[b][0], None])
            edge_y.extend([v[a][1], v[b][1], None])
            edge_z.extend([v[a][2], v[b][2], None])

    mesh_kwargs = {"facecolor": face_colors} if face_colors is not None else {"color": color}
    # Painted/photo tile colors must render at full opacity: the client-side alpha slider
    # blends overlapping faces together and washes out the intended per-tile colors.
    mesh_opacity = 1.0 if face_colors is not None else alpha
    mesh_trace = go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        opacity=mesh_opacity,
        flatshading=flatshading,
        lighting=dict(ambient=0.7, diffuse=0.8, specular=0.5, roughness=0.5, fresnel=0.2),
        lightposition=dict(x=100, y=200, z=1000),
        hoverinfo="none",
        name="Surface",
        **mesh_kwargs,
    )

    traces = [mesh_trace]
    if edge_indices and thickness > 0:
        edge_trace = go.Scatter3d(
            x=edge_x,
            y=edge_y,
            z=edge_z,
            mode="lines",
            line=dict(color="#162a43", width=thickness),
            hoverinfo="none",
            name="Wireframe",
        )
        traces.append(edge_trace)

    if label_mesh and label_mesh[0] and label_mesh[1]:
        label_vertices, label_faces, label_colors = label_mesh
        rotated_labels = rotate_vertices(label_vertices, angles, scale)
        label_trace = go.Mesh3d(
            x=[p[0] for p in rotated_labels],
            y=[p[1] for p in rotated_labels],
            z=[p[2] for p in rotated_labels],
            i=[f[0] for f in label_faces],
            j=[f[1] for f in label_faces],
            k=[f[2] for f in label_faces],
            facecolor=label_colors,
            opacity=1.0,
            flatshading=True,
            lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0),
            hoverinfo="none",
            name="Tile Labels",
        )
        traces.append(label_trace)

    fig = go.Figure(data=traces)
    fig.update_layout(
        autosize=True,
        height=680,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#ffffff",
        showlegend=False,
        scene=dict(
            aspectmode="data",
            # Force Plotly to recompute the auto-range on every rotation instead of
            # keeping the viewport Streamlit preserves across reruns (which otherwise
            # clips long/thin shapes like Tube once they rotate out of the old frame).
            uirevision=f"angles:{angles}",
            xaxis=dict(
                visible=show_grid,
                showgrid=show_grid,
                zeroline=show_grid,
                showticklabels=show_grid,
                title="",
            ),
            yaxis=dict(
                visible=show_grid,
                showgrid=show_grid,
                zeroline=show_grid,
                showticklabels=show_grid,
                title="",
            ),
            zaxis=dict(
                visible=show_grid,
                showgrid=show_grid,
                zeroline=show_grid,
                showticklabels=show_grid,
                title="",
            ),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.25),
                projection=dict(type="perspective"),
            ),
        ),
    )
    return fig


def build_hex_sphere(radius=5.0, hex_subdivisions=3, hex_size_pct=95.0, *args, **kwargs):
    # Backward compatibility with legacy (radius, xy_res, yz_res, zx_res) calls
    if len(args) >= 1 and isinstance(args[0], (int, float)):
        hex_subdivisions = max(1, min(8, round(float(args[0]) / 6.0)))
    return build_advanced_hex_sphere(
        radius=radius,
        hex_subdivisions=hex_subdivisions,
        hex_size_pct=hex_size_pct,
        wall_angle=0.0,
        wall_height=0.0,
        wall_radius=100.0,
    )


def build_advanced_hex_sphere(
    radius=5.0,
    hex_subdivisions=3,
    hex_size_pct=95.0,
    wall_angle=0.0,
    wall_height=0.0,
    wall_radius=100.0,
):
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    base_vertices = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]

    def normalize(v):
        l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / l, v[1] / l, v[2] / l) if l > 0 else (0.0, 0.0, 1.0)

    base_vertices = [normalize(v) for v in base_vertices]
    base_triangles = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    point_map = {}

    def get_subdivided_vertex(p1, p2, p3, i, j, k, n):
        x = (i * p1[0] + j * p2[0] + k * p3[0]) / n
        y = (i * p1[1] + j * p2[1] + k * p3[1]) / n
        z = (i * p1[2] + j * p2[2] + k * p3[2]) / n
        norm = normalize((x, y, z))
        key = (round(norm[0], 6), round(norm[1], 6), round(norm[2], 6))
        if key not in point_map:
            point_map[key] = len(point_map)
        return point_map[key], norm

    triangles = []
    points = []
    n = max(1, min(8, int(hex_subdivisions)))
    for t in base_triangles:
        p1, p2, p3 = base_vertices[t[0]], base_vertices[t[1]], base_vertices[t[2]]
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1 - i):
                k = n - i - j
                idx, pt = get_subdivided_vertex(p1, p2, p3, i, j, k, n)
                grid[(i, j)] = idx
                while len(points) <= idx:
                    points.append(pt)
        for i in range(n):
            for j in range(n - i):
                triangles.append((grid[(i, j)], grid[(i + 1, j)], grid[(i, j + 1)]))
                if i + j < n - 1:
                    triangles.append((grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))

    vert_to_tri = [[] for _ in range(len(points))]
    for t_idx, tri in enumerate(triangles):
        for v in tri:
            vert_to_tri[v].append(t_idx)

    tri_centroids = []
    for tri in triangles:
        p0, p1, p2 = points[tri[0]], points[tri[1]], points[tri[2]]
        c = normalize(((p0[0] + p1[0] + p2[0]) / 3, (p0[1] + p1[1] + p2[1]) / 3, (p0[2] + p1[2] + p2[2]) / 3))
        tri_centroids.append(c)

    scale_factor = max(0.1, min(1.0, float(hex_size_pct) / 100.0))
    wall_rad_factor = max(0.1, min(1.0, float(wall_radius) / 100.0))
    h = radius * (float(wall_height) / 100.0)
    top_scale = max(0.0, min(1.0, math.sin(math.radians(float(wall_angle)))))

    final_vertices = []
    final_faces = []
    final_edges = []

    for v_idx, v_center in enumerate(points):
        adj_tris = vert_to_tri[v_idx]
        if not adj_tris:
            continue
        normal = v_center
        up = (0.0, 1.0, 0.0) if abs(normal[1]) < 0.9 else (1.0, 0.0, 0.0)
        ux = up[1] * normal[2] - up[2] * normal[1]
        uy = up[2] * normal[0] - up[0] * normal[2]
        uz = up[0] * normal[1] - up[1] * normal[0]
        l = math.sqrt(ux * ux + uy * uy + uz * uz)
        u = (ux / l, uy / l, uz / l)
        vx = normal[1] * u[2] - normal[2] * u[1]
        vy = normal[2] * u[0] - normal[0] * u[2]
        vz = normal[0] * u[1] - normal[1] * u[0]
        v = (vx, vy, vz)

        corners = []
        for t_idx in adj_tris:
            c = tri_centroids[t_idx]
            dx = c[0] - v_center[0]
            dy = c[1] - v_center[1]
            dz = c[2] - v_center[2]
            pu = dx * u[0] + dy * u[1] + dz * u[2]
            pv = dx * v[0] + dy * v[1] + dz * v[2]
            angle = math.atan2(pv, pu)
            corners.append((angle, c))
        corners.sort(key=lambda x: x[0])
        m = len(corners)

        outer_indices = []
        for _, c in corners:
            sx = v_center[0] + (c[0] - v_center[0]) * scale_factor
            sy = v_center[1] + (c[1] - v_center[1]) * scale_factor
            sz = v_center[2] + (c[2] - v_center[2]) * scale_factor
            sp = normalize((sx, sy, sz))
            idx = len(final_vertices)
            final_vertices.append((sp[0] * radius, sp[1] * radius, sp[2] * radius))
            outer_indices.append(idx)

        for k in range(m):
            final_edges.append((outer_indices[k], outer_indices[(k + 1) % m]))

        has_collar = wall_rad_factor < 0.999
        if has_collar:
            inner_base_indices = []
            inner_factor = scale_factor * wall_rad_factor
            for _, c in corners:
                sx = v_center[0] + (c[0] - v_center[0]) * inner_factor
                sy = v_center[1] + (c[1] - v_center[1]) * inner_factor
                sz = v_center[2] + (c[2] - v_center[2]) * inner_factor
                sp = normalize((sx, sy, sz))
                idx = len(final_vertices)
                final_vertices.append((sp[0] * radius, sp[1] * radius, sp[2] * radius))
                inner_base_indices.append(idx)

            for k in range(m):
                nxt = (k + 1) % m
                o_curr, o_nxt = outer_indices[k], outer_indices[nxt]
                i_curr, i_nxt = inner_base_indices[k], inner_base_indices[nxt]
                final_faces.extend(((o_curr, o_nxt, i_nxt), (o_curr, i_nxt, i_curr)))
                final_edges.append((i_curr, i_nxt))
            wall_base_indices = inner_base_indices
        else:
            wall_base_indices = outer_indices

        is_flat = math.isclose(h, 0.0, abs_tol=1e-5)
        if is_flat and math.isclose(top_scale, 0.0, abs_tol=1e-5):
            for k in range(1, m - 1):
                final_faces.append((wall_base_indices[0], wall_base_indices[k], wall_base_indices[k + 1]))
        elif top_scale <= 0.01:
            apex_pos = (
                v_center[0] * (radius + h),
                v_center[1] * (radius + h),
                v_center[2] * (radius + h),
            )
            apex_idx = len(final_vertices)
            final_vertices.append(apex_pos)
            for k in range(m):
                nxt = (k + 1) % m
                b_curr, b_nxt = wall_base_indices[k], wall_base_indices[nxt]
                if h >= 0:
                    final_faces.append((b_curr, b_nxt, apex_idx))
                else:
                    final_faces.append((b_curr, apex_idx, b_nxt))
                final_edges.append((b_curr, apex_idx))
        else:
            top_indices = []
            inner_factor = scale_factor * wall_rad_factor
            for _, c in corners:
                sx = v_center[0] + (c[0] - v_center[0]) * (inner_factor * top_scale)
                sy = v_center[1] + (c[1] - v_center[1]) * (inner_factor * top_scale)
                sz = v_center[2] + (c[2] - v_center[2]) * (inner_factor * top_scale)
                sp = normalize((sx, sy, sz))
                idx = len(final_vertices)
                final_vertices.append((sp[0] * (radius + h), sp[1] * (radius + h), sp[2] * (radius + h)))
                top_indices.append(idx)

            for k in range(m):
                nxt = (k + 1) % m
                b_curr, b_nxt = wall_base_indices[k], wall_base_indices[nxt]
                t_curr, t_nxt = top_indices[k], top_indices[nxt]
                if h >= 0:
                    final_faces.extend(((b_curr, b_nxt, t_nxt), (b_curr, t_nxt, t_curr)))
                else:
                    final_faces.extend(((b_curr, t_nxt, b_nxt), (b_curr, t_curr, t_nxt)))
                final_edges.append((t_curr, t_nxt))
                final_edges.append((b_curr, t_curr))

            for k in range(1, m - 1):
                if h >= 0:
                    final_faces.append((top_indices[0], top_indices[k], top_indices[k + 1]))
                else:
                    final_faces.append((top_indices[0], top_indices[k + 1], top_indices[k]))

    return final_vertices, final_faces, final_edges


def build_complex_hex_sphere(
    radius=5.0,
    hex_subdivisions=3,
    hex_size_pct=95.0,
    wall_angle=0.0,
    wall_height=0.0,
    wall_radius=100.0,
    manifold_pct=0.0,
    round_walls=False,
    wall_end_type="Empty",
):
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    base_vertices = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]

    def normalize(v):
        l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / l, v[1] / l, v[2] / l) if l > 0 else (0.0, 0.0, 1.0)

    base_vertices = [normalize(v) for v in base_vertices]
    base_triangles = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    point_map = {}

    def get_subdivided_vertex(p1, p2, p3, i, j, k, n):
        x = (i * p1[0] + j * p2[0] + k * p3[0]) / n
        y = (i * p1[1] + j * p2[1] + k * p3[1]) / n
        z = (i * p1[2] + j * p2[2] + k * p3[2]) / n
        norm = normalize((x, y, z))
        key = (round(norm[0], 6), round(norm[1], 6), round(norm[2], 6))
        if key not in point_map:
            point_map[key] = len(point_map)
        return point_map[key], norm

    triangles = []
    points = []
    n = max(1, min(8, int(hex_subdivisions)))
    for t in base_triangles:
        p1, p2, p3 = base_vertices[t[0]], base_vertices[t[1]], base_vertices[t[2]]
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1 - i):
                k = n - i - j
                idx, pt = get_subdivided_vertex(p1, p2, p3, i, j, k, n)
                grid[(i, j)] = idx
                while len(points) <= idx:
                    points.append(pt)
        for i in range(n):
            for j in range(n - i):
                triangles.append((grid[(i, j)], grid[(i + 1, j)], grid[(i, j + 1)]))
                if i + j < n - 1:
                    triangles.append((grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))

    vert_to_tri = [[] for _ in range(len(points))]
    for t_idx, tri in enumerate(triangles):
        for v in tri:
            vert_to_tri[v].append(t_idx)

    tri_centroids = []
    for tri in triangles:
        p0, p1, p2 = points[tri[0]], points[tri[1]], points[tri[2]]
        c = normalize(((p0[0] + p1[0] + p2[0]) / 3, (p0[1] + p1[1] + p2[1]) / 3, (p0[2] + p1[2] + p2[2]) / 3))
        tri_centroids.append(c)

    scale_factor = max(0.1, min(1.0, float(hex_size_pct) / 100.0))
    wall_rad_factor = max(0.1, min(1.0, float(wall_radius) / 100.0))
    h = radius * (float(wall_height) / 100.0)
    top_scale = max(0.0, min(1.0, math.sin(math.radians(float(wall_angle)))))
    manifold_ratio = max(0.0, min(0.75, float(manifold_pct) / 100.0))
    hole_active = manifold_ratio > 0.001 and wall_end_type != "Solid Magnet"
    round_segments = 4 if round_walls else 1

    final_vertices = []
    final_faces = []
    final_edges = []

    for v_idx, v_center in enumerate(points):
        adj_tris = vert_to_tri[v_idx]
        if not adj_tris:
            continue
        normal = v_center
        up = (0.0, 1.0, 0.0) if abs(normal[1]) < 0.9 else (1.0, 0.0, 0.0)
        ux = up[1] * normal[2] - up[2] * normal[1]
        uy = up[2] * normal[0] - up[0] * normal[2]
        uz = up[0] * normal[1] - up[1] * normal[0]
        l = math.sqrt(ux * ux + uy * uy + uz * uz)
        u = (ux / l, uy / l, uz / l)
        vx = normal[1] * u[2] - normal[2] * u[1]
        vy = normal[2] * u[0] - normal[0] * u[2]
        vz = normal[0] * u[1] - normal[1] * u[0]
        v = (vx, vy, vz)

        corners = []
        for t_idx in adj_tris:
            c = tri_centroids[t_idx]
            dx = c[0] - v_center[0]
            dy = c[1] - v_center[1]
            dz = c[2] - v_center[2]
            pu = dx * u[0] + dy * u[1] + dz * u[2]
            pv = dx * v[0] + dy * v[1] + dz * v[2]
            angle = math.atan2(pv, pu)
            corners.append((angle, c))
        corners.sort(key=lambda x: x[0])
        m = len(corners)

        def ring_at(scale, height):
            idxs = []
            for _, c in corners:
                sx = v_center[0] + (c[0] - v_center[0]) * scale
                sy = v_center[1] + (c[1] - v_center[1]) * scale
                sz = v_center[2] + (c[2] - v_center[2]) * scale
                sp = normalize((sx, sy, sz))
                idx = len(final_vertices)
                final_vertices.append((sp[0] * (radius + height), sp[1] * (radius + height), sp[2] * (radius + height)))
                idxs.append(idx)
            return idxs

        def connect_ring_pair(idx_a, idx_b, flipped):
            for k in range(len(idx_a)):
                nxt = (k + 1) % len(idx_a)
                a0, a1 = idx_a[k], idx_a[nxt]
                b0, b1 = idx_b[k], idx_b[nxt]
                if not flipped:
                    final_faces.extend(((a0, a1, b1), (a0, b1, b0)))
                else:
                    final_faces.extend(((a0, b1, a1), (a0, b0, b1)))
                final_edges.append((a0, b0))

        def cap_ring(idxs, flipped):
            for k in range(1, len(idxs) - 1):
                if not flipped:
                    final_faces.append((idxs[0], idxs[k], idxs[k + 1]))
                else:
                    final_faces.append((idxs[0], idxs[k + 1], idxs[k]))

        outer_indices = ring_at(scale_factor, 0.0)
        for k in range(m):
            final_edges.append((outer_indices[k], outer_indices[(k + 1) % m]))

        has_collar = wall_rad_factor < 0.999
        if has_collar:
            inner_factor = scale_factor * wall_rad_factor
            inner_base_indices = ring_at(inner_factor, 0.0)
            connect_ring_pair(outer_indices, inner_base_indices, flipped=False)
            for k in range(m):
                final_edges.append((inner_base_indices[k], inner_base_indices[(k + 1) % m]))
            wall_base_indices = inner_base_indices
        else:
            inner_factor = scale_factor
            wall_base_indices = outer_indices

        # Tip scale before any manifold hole is cut: a flat plateau (wall_angle) or a sharp point.
        plateau_scale = inner_factor * top_scale if top_scale > 0.01 else 0.0
        hole_scale = inner_factor * manifold_ratio if hole_active else 0.0
        tip_scale = max(plateau_scale, hole_scale)
        is_flat_top = math.isclose(h, 0.0, abs_tol=1e-5) and math.isclose(top_scale, 0.0, abs_tol=1e-5)

        if is_flat_top and not hole_active:
            cap_ring(wall_base_indices, flipped=False)
            continue

        # Build the (optionally rounded) side wall from the base ring up to the tip.
        prev_ring = wall_base_indices
        tip_ring = None
        for seg in range(1, round_segments + 1):
            t = seg / round_segments
            is_last = seg == round_segments
            if is_last and tip_scale <= 1e-6:
                apex_idx = len(final_vertices)
                final_vertices.append((v_center[0] * (radius + h), v_center[1] * (radius + h), v_center[2] * (radius + h)))
                for k in range(len(prev_ring)):
                    nxt = (k + 1) % len(prev_ring)
                    b_curr, b_nxt = prev_ring[k], prev_ring[nxt]
                    if h >= 0:
                        final_faces.append((b_curr, b_nxt, apex_idx))
                    else:
                        final_faces.append((b_curr, apex_idx, b_nxt))
                    final_edges.append((b_curr, apex_idx))
                prev_ring = None
                break
            seg_scale = inner_factor + (tip_scale - inner_factor) * t
            seg_height = h * t
            if round_walls and not is_last:
                seg_scale += 0.12 * inner_factor * math.sin(math.pi * t)
            seg_ring = ring_at(seg_scale, seg_height)
            connect_ring_pair(prev_ring, seg_ring, flipped=(h < 0))
            for k in range(len(seg_ring)):
                final_edges.append((seg_ring[k], seg_ring[(k + 1) % len(seg_ring)]))
            prev_ring = seg_ring
            tip_ring = seg_ring

        if prev_ring is None:
            continue

        if not hole_active:
            cap_ring(tip_ring, flipped=(h < 0))
            continue

        # A manifold hole stays open at the tip; how it's finished depends on the wall-end fitting.
        if wall_end_type in ("Empty", "Hollow Magnet"):
            continue
        elif wall_end_type == "Filter":
            recess = 0.08 * radius if h >= 0 else -0.08 * radius
            recessed_ring = ring_at(tip_scale * 0.9, h - recess)
            connect_ring_pair(tip_ring, recessed_ring, flipped=(h < 0))
            cap_ring(recessed_ring, flipped=(h < 0))
        elif wall_end_type == "Lense":
            bulge_height = h + (0.1 * radius if h >= 0 else -0.1 * radius)
            lens_apex_idx = len(final_vertices)
            final_vertices.append((
                v_center[0] * (radius + bulge_height),
                v_center[1] * (radius + bulge_height),
                v_center[2] * (radius + bulge_height),
            ))
            for k in range(len(tip_ring)):
                nxt = (k + 1) % len(tip_ring)
                b_curr, b_nxt = tip_ring[k], tip_ring[nxt]
                if h >= 0:
                    final_faces.append((b_curr, b_nxt, lens_apex_idx))
                else:
                    final_faces.append((b_curr, lens_apex_idx, b_nxt))

    return final_vertices, final_faces, final_edges


def generate_picture_sphere_geometry(s):
    tile_sig = (s["radius"], s["hex_subdivisions"], s["hex_size_pct"])
    if st.session_state.get("picture_sphere_tile_sig") != tile_sig:
        # Tile ids are meaningless across a geometry change (different subdivision/radius), so drop stale paint/anchor state.
        st.session_state.picture_sphere_tile_sig = tile_sig
        st.session_state.picture_sphere_tile_colors = {}
        st.session_state.picture_sphere_anchor_tile_id = 0
        st.session_state.picture_sphere_tile_labels = {}

    vertices, faces, edges, face_tile_ids, tile_centroids, tile_corner_ids, adjacency = picture_sphere.build_picture_sphere(
        s["radius"],
        s["hex_subdivisions"],
        s["hex_size_pct"],
    )
    anchor_tile_id = min(st.session_state.get("picture_sphere_anchor_tile_id", 0), len(tile_centroids) - 1)
    ring_of_tile, label_of_tile = picture_sphere.compute_tile_rings_and_labels(tile_centroids, adjacency, anchor_tile_id)

    tile_base_colors = None
    uploaded_image = st.session_state.get("picture_sphere_image_upload")
    if uploaded_image is not None:
        try:
            image = Image.open(io.BytesIO(uploaded_image.getvalue()))
            tile_base_colors = picture_sphere.sample_tile_colors_from_image(image, tile_centroids)
        except Exception:
            tile_base_colors = None

    paint_overrides = st.session_state.setdefault("picture_sphere_tile_colors", {})
    default_color = "#3568ad"
    tile_colors = [
        paint_overrides.get(tile_id, tile_base_colors[tile_id] if tile_base_colors else default_color)
        for tile_id in range(len(tile_centroids))
    ]

    # Sparse: only tiles with an assigned character get a decal, built as flat
    # pixel-quads tangent to that tile (not billboarded text), colored as the
    # inverse of the tile's own resolved color so it never blends into its background.
    tile_label_chars = st.session_state.setdefault("picture_sphere_tile_labels", {})
    num_label_layers = st.session_state.get("picture_sphere_label_layers", 3)
    label_mesh_vertices, label_mesh_faces, label_mesh_colors = picture_sphere.build_tile_label_decals(
        tile_label_chars, tile_centroids, adjacency, tile_colors, s["radius"], num_layers=num_label_layers,
    )

    # Stashed for later phases (viewer facecolor wiring).
    st.session_state.picture_sphere_tile_data = {
        "face_tile_ids": face_tile_ids,
        "tile_centroids": tile_centroids,
        "tile_corner_ids": tile_corner_ids,
        "adjacency": adjacency,
        "anchor_tile_id": anchor_tile_id,
        "ring_of_tile": ring_of_tile,
        "label_of_tile": label_of_tile,
        "tile_base_colors": tile_base_colors,
        "tile_colors": tile_colors,
        "label_mesh_vertices": label_mesh_vertices,
        "label_mesh_faces": label_mesh_faces,
        "label_mesh_colors": label_mesh_colors,
    }
    return vertices, faces, edges


def generate_picture_sphere_test_pattern():
    tile_data = st.session_state.get("picture_sphere_tile_data")
    if not tile_data:
        return
    num_tiles = len(tile_data["tile_centroids"])
    colors = picture_sphere.generate_test_tile_colors(num_tiles)
    st.session_state.picture_sphere_tile_colors = dict(enumerate(colors))
    label_mode = "random" if st.session_state.get("picture_sphere_test_label_mode") == "Random characters" else "alpha"
    labels = picture_sphere.generate_test_tile_labels(num_tiles, mode=label_mode)
    st.session_state.picture_sphere_tile_labels = dict(enumerate(labels))


def clear_picture_sphere_test_pattern():
    st.session_state.picture_sphere_tile_colors = {}
    st.session_state.picture_sphere_tile_labels = {}


def paint_selected_picture_sphere_tile():
    tile_data = st.session_state.get("picture_sphere_tile_data")
    if not tile_data:
        return
    label_to_tile_id = {label: tile_id for tile_id, label in tile_data["label_of_tile"].items()}
    tile_id = label_to_tile_id.get(st.session_state.get("picture_sphere_target_tile_label"))
    if tile_id is None:
        return
    st.session_state.setdefault("picture_sphere_tile_colors", {})[tile_id] = st.session_state.picture_sphere_paint_color
    char = st.session_state.get("picture_sphere_paint_character", "").strip().upper()
    tile_labels = st.session_state.setdefault("picture_sphere_tile_labels", {})
    if char:
        tile_labels[tile_id] = char[0]
    else:
        tile_labels.pop(tile_id, None)


def reset_picture_sphere_paint():
    st.session_state.picture_sphere_tile_colors = {}
    st.session_state.picture_sphere_tile_labels = {}


def build_cube(size):
    half = size / 2
    vertices = [(-half, -half, -half), (half, -half, -half), (half, half, -half), (-half, half, -half), (-half, -half, half), (half, -half, half), (half, half, half), (-half, half, half)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (4, 0, 3), (4, 3, 7)]
    return vertices, faces, [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def build_advanced_tube(length, top_inner_radius, bottom_inner_radius, tube_thickness, sides, top_angle, bottom_angle, cylinder_type, twist=0, stack_count=1):
    side_count = 48 if cylinder_type else int(sides)
    top_outer = top_inner_radius + tube_thickness
    bottom_outer = bottom_inner_radius + tube_thickness
    half = length / 2
    top_height = half + math.tan(math.radians(top_angle)) * tube_thickness
    bottom_height = -half + math.tan(math.radians(bottom_angle)) * tube_thickness
    vertices = []
    for stack in range(stack_count + 1):
        progress = stack / stack_count
        angle_offset = math.radians(stack * twist)
        inner = bottom_inner_radius + (top_inner_radius - bottom_inner_radius) * progress
        outer = bottom_outer + (top_outer - bottom_outer) * progress
        inner_height = -half + length * progress
        outer_height = bottom_height + (top_height - bottom_height) * progress
        for radius, height in ((inner, inner_height), (outer, outer_height)):
            for side in range(side_count):
                angle = 2 * math.pi * side / side_count + angle_offset
                vertices.append((radius * math.cos(angle), radius * math.sin(angle), height))
    ring_size = side_count * 2
    faces, edges = [], []
    index = lambda stack, outer, side: stack * ring_size + int(outer) * side_count + side
    for stack in range(stack_count):
        for side in range(side_count):
            nxt = (side + 1) % side_count
            a, b = index(stack, False, side), index(stack, False, nxt)
            c, d = index(stack + 1, False, side), index(stack + 1, False, nxt)
            e, f = index(stack, True, side), index(stack, True, nxt)
            g, h = index(stack + 1, True, side), index(stack + 1, True, nxt)
            faces.extend(((a, b, d), (a, d, c), (e, g, h), (e, h, f)))
            edges.extend(((a, b), (e, f), (a, c), (e, g)))
    for side in range(side_count):
        nxt = (side + 1) % side_count
        bi, bn, bo, bon = index(0, False, side), index(0, False, nxt), index(0, True, side), index(0, True, nxt)
        ti, tn, to, ton = index(stack_count, False, side), index(stack_count, False, nxt), index(stack_count, True, side), index(stack_count, True, nxt)
        faces.extend(((ti, tn, ton), (ti, ton, to), (bi, bo, bon), (bi, bon, bn)))
        edges.extend(((bi, bn), (bo, bon), (ti, tn), (to, ton), (bi, bo), (ti, to)))
    return vertices, faces, edges


def build_tube(length, inner_radius, thickness, sides, top_angle, bottom_angle, cylinder_type):
    return build_advanced_tube(length, inner_radius, inner_radius, thickness, sides, top_angle, bottom_angle, cylinder_type)


def build_complex_tube(length, top_inner, bottom_inner, thickness, sides, top_angle, bottom_angle, twist, stack_thickness):
    return build_advanced_tube(length, top_inner, bottom_inner, thickness, sides, top_angle, bottom_angle, False, twist, max(1, round(length / stack_thickness)))


def build_simple_torus(inner_radius, outer_radius, hollow_percent, xy_ratio, start_angle, sweep, sides, cylinder_type):
    closed = math.isclose(abs(sweep), 360.0)
    revolution_segments = 48 if cylinder_type else max(3, int(sides))
    profile_segments = 48 if cylinder_type else max(3, int(sides))
    ring_count = revolution_segments if closed else revolution_segments + 1
    path_radius = (inner_radius + outer_radius) / 2
    outer_tube_radius = max(0.001, (outer_radius - inner_radius) / 2)
    inner_tube_radius = outer_tube_radius * max(0.0, min(100.0, hollow_percent)) / 100
    profile = []
    profile_start_angle = math.pi
    for index in range(profile_segments):
        angle = profile_start_angle + 2 * math.pi * index / profile_segments
        profile.append((path_radius + outer_tube_radius * math.cos(angle), outer_tube_radius * math.sin(angle)))
    if inner_tube_radius > 0:
        for index in range(profile_segments - 1, -1, -1):
            angle = profile_start_angle + 2 * math.pi * index / profile_segments
            profile.append((path_radius + inner_tube_radius * math.cos(angle), inner_tube_radius * math.sin(angle)))
    else:
        profile.append((path_radius, 0.0))
    vertices = []
    for revolution in range(ring_count):
        angle = math.radians(start_angle + sweep * revolution / revolution_segments)
        cosine, sine = math.cos(angle), math.sin(angle)
        vertices.extend((radial * cosine, height * xy_ratio, radial * sine) for radial, height in profile)
    profile_size = len(profile)
    faces, edges = [], []
    for revolution in range(revolution_segments):
        next_revolution = (revolution + 1) % ring_count
        current, next_ring = revolution * profile_size, next_revolution * profile_size
        for index in range(profile_size):
            next_index = (index + 1) % profile_size
            a, b, c, d = current + index, next_ring + index, next_ring + next_index, current + next_index
            faces.extend(((a, b, c), (a, c, d)))
            edges.append((a, b))
        for index in range(profile_segments):
            edges.append((current + index, current + (index + 1) % profile_segments))
            if inner_tube_radius > 0:
                inner_index = profile_segments + index
                edges.append((current + inner_index, current + profile_segments + (index + 1) % profile_segments))
    if not closed:
        first, last = 0, (ring_count - 1) * profile_size
        if inner_tube_radius > 0:
            for index in range(profile_segments):
                nxt = (index + 1) % profile_segments
                inner = 2 * profile_segments - 1 - index
                inner_next = 2 * profile_segments - 1 - nxt
                faces.extend(((first + index, first + inner, first + inner_next), (first + index, first + inner_next, first + nxt), (last + index, last + nxt, last + inner_next), (last + index, last + inner_next, last + inner)))
        else:
            center = profile_segments
            for index in range(profile_segments):
                nxt = (index + 1) % profile_segments
                faces.extend(((first + center, first + nxt, first + index), (last + center, last + index, last + nxt)))
    return vertices, faces, edges


OBJECT_REGISTRY = {
    "SimpleHexShpere": {
        "label": "SimpleHexShpere",
        "generator": lambda s: build_hex_sphere(
            s["radius"],
            s["hex_subdivisions"],
            s["hex_size_pct"],
        ),
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "thickness": 3,
            },
        },
    },
    "PictureSphere": {
        "label": "PictureSphere",
        "generator": generate_picture_sphere_geometry,
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "thickness": 3,
            },
        },
    },
    "AdvancedHexSphere": {
        "label": "AdvancedHexSphere",
        "generator": lambda s: build_advanced_hex_sphere(
            s["radius"],
            s["hex_subdivisions"],
            s["hex_size_pct"],
            s["wall_angle"],
            s["wall_height"],
            s["wall_radius"],
        ),
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_angle": {
                "label": "Wall angle",
                "type": "slider",
                "min": 0,
                "max": 90,
                "default": 0,
                "step": 1,
            },
            "wall_height": {
                "label": "Wall height",
                "type": "slider",
                "min": -100.0,
                "max": 100.0,
                "default": 0.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_radius": {
                "label": "Wall radius",
                "type": "slider",
                "min": 50.0,
                "max": 100.0,
                "default": 100.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "thickness": 3,
            },
        },
    },
    "ComplexHexSphere": {
        "label": "ComplexHexSphere",
        "generator": lambda s: build_complex_hex_sphere(
            s["radius"],
            s["hex_subdivisions"],
            s["hex_size_pct"],
            s["wall_angle"],
            s["wall_height"],
            s["wall_radius"],
            s["manifold_pct"],
            s["round_walls"],
            s["wall_end_type"],
        ),
        "params": {
            "radius": {
                "label": "Sphere radius",
                "type": "slider",
                "min": 1.0,
                "max": 12.0,
                "default": 5.0,
                "step": 0.5,
            },
            "hex_subdivisions": {
                "label": "Hexagon density (subdivisions)",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
            "hex_size_pct": {
                "label": "Hexagon size percentage",
                "type": "slider",
                "min": 10.0,
                "max": 100.0,
                "default": 95.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_angle": {
                "label": "Wall angle",
                "type": "slider",
                "min": 0,
                "max": 90,
                "default": 0,
                "step": 1,
            },
            "wall_height": {
                "label": "Wall height",
                "type": "slider",
                "min": -100.0,
                "max": 100.0,
                "default": 0.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "wall_radius": {
                "label": "Wall radius",
                "type": "slider",
                "min": 50.0,
                "max": 100.0,
                "default": 100.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "manifold_pct": {
                "label": "Manifold (tip hole size)",
                "type": "slider",
                "min": 0.0,
                "max": 75.0,
                "default": 0.0,
                "step": 1.0,
                "format": "%.0f%%",
            },
            "round_walls": {
                "label": "Round walls",
                "type": "toggle",
                "default": False,
            },
            "wall_end_type": {
                "label": "Wall end fitting",
                "type": "select",
                "options": WALL_END_OPTIONS,
                "default": "Empty",
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "manifold_pct": 0.0,
                "round_walls": False,
                "wall_end_type": "Empty",
                "thickness": 3,
            },
            "Preset2": {
                "radius": 5.0,
                "hex_subdivisions": 3,
                "hex_size_pct": 95.0,
                "wall_angle": 0,
                "wall_height": 0.0,
                "wall_radius": 100.0,
                "manifold_pct": 0.0,
                "round_walls": False,
                "wall_end_type": "Empty",
                "thickness": 3,
            },
        },
    },
    "SimpleBlock": {
        "label": "SimpleBlock",
        "enabled": True,
        "generator": lambda s: build_cube(s["cube_size"]),
        "params": {
            "cube_size": {
                "label": "Size",
                "type": "slider",
                "min": 1.0,
                "max": 16.0,
                "default": 8.0,
                "step": 0.5,
            },
            "thickness": {
                "label": "Grid thickness",
                "type": "slider",
                "min": 1,
                "max": 8,
                "default": 3,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "cube_size": 8.0,
                "thickness": 3,
            },
            "Preset2": {
                "cube_size": 8.0,
                "thickness": 3,
            },
        },
    },
    "AdvancedBlock": {
        "label": "AdvancedBlock",
        "enabled": False,
        "generator": None,
        "params": {},
        "presets": {},
    },
    "ComplexBlock": {
        "label": "ComplexBlock",
        "enabled": False,
        "generator": None,
        "params": {},
        "presets": {},
    },
    "SimpleTube": {
        "label": "SimpleTube",
        "generator": lambda s: build_tube(
            s["tube_length"],
            s["tube_inner_radius"],
            s["tube_thickness"],
            s["tube_sides"],
            s["tube_top_angle"],
            s["tube_bottom_angle"],
            s["tube_cylinder"],
        ),
        "params": {
            "tube_cylinder": {
                "label": "Cylinder type",
                "type": "toggle",
                "default": False,
            },
            "tube_sides": {
                "label": "Sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
                "disabled_by": "tube_cylinder",
            },
            "tube_length": {
                "label": "Length",
                "type": "slider",
                "min": 1.0,
                "max": 20.0,
                "default": 16.0,
                "step": 0.5,
            },
            "tube_inner_radius": {
                "label": "Inner radius",
                "type": "slider",
                "min": 0.5,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_thickness": {
                "label": "Thickness",
                "type": "slider",
                "min": 0.5,
                "max": 8.0,
                "default": 2.0,
                "step": 0.5,
            },
            "tube_top_angle": {
                "label": "Top side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_bottom_angle": {
                "label": "Bottom side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
            "Preset2": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
        },
    },
    "AdvancedTube": {
        "label": "AdvancedTube",
        "generator": lambda s: build_advanced_tube(
            s["tube_length"],
            s["tube_top_inner_radius"],
            s["tube_bottom_inner_radius"],
            s["tube_thickness"],
            s["tube_sides"],
            s["tube_top_angle"],
            s["tube_bottom_angle"],
            s["tube_cylinder"],
        ),
        "params": {
            "tube_cylinder": {
                "label": "Cylinder type",
                "type": "toggle",
                "default": False,
            },
            "tube_sides": {
                "label": "Sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
                "disabled_by": "tube_cylinder",
            },
            "tube_length": {
                "label": "Length",
                "type": "slider",
                "min": 1.0,
                "max": 20.0,
                "default": 16.0,
                "step": 0.5,
            },
            "tube_top_inner_radius": {
                "label": "Top side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_bottom_inner_radius": {
                "label": "Bottom side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_thickness": {
                "label": "Thickness",
                "type": "slider",
                "min": 0.5,
                "max": 8.0,
                "default": 2.0,
                "step": 0.5,
            },
            "tube_top_angle": {
                "label": "Top side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_bottom_angle": {
                "label": "Bottom side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
        },
        "presets": {
            "Preset1": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
            "Preset2": {
                "tube_cylinder": False,
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
            },
        },
    },
    "ComplexTube": {
        "label": "ComplexTube",
        "generator": lambda s: build_complex_tube(
            s["tube_length"],
            s["tube_top_inner_radius"],
            s["tube_bottom_inner_radius"],
            s["tube_thickness"],
            s["tube_sides"],
            s["tube_top_angle"],
            s["tube_bottom_angle"],
            s["tube_twist"],
            s["tube_stack_thickness"],
        ),
        "params": {
            "tube_sides": {
                "label": "Sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
            },
            "tube_length": {
                "label": "Length",
                "type": "slider",
                "min": 1.0,
                "max": 20.0,
                "default": 16.0,
                "step": 0.5,
            },
            "tube_top_inner_radius": {
                "label": "Top side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_bottom_inner_radius": {
                "label": "Bottom side inner radius",
                "type": "slider",
                "min": 0.0,
                "max": 10.0,
                "default": 4.0,
                "step": 0.5,
            },
            "tube_thickness": {
                "label": "Thickness",
                "type": "slider",
                "min": 0.5,
                "max": 8.0,
                "default": 2.0,
                "step": 0.5,
            },
            "tube_top_angle": {
                "label": "Top side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_bottom_angle": {
                "label": "Bottom side angle",
                "type": "slider",
                "min": -60,
                "max": 60,
                "default": 0,
                "step": 1,
            },
            "tube_twist": {
                "label": "Twist per stack",
                "type": "slider",
                "min": -15,
                "max": 15,
                "default": 5,
                "step": 1,
            },
            "tube_stack_thickness": {
                "label": "Stack thickness",
                "type": "slider",
                "min": 1.0,
                "max": 10.0,
                "default": 1.0,
                "step": 1.0,
            },
        },
        "presets": {
            "Preset1": {
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
                "tube_twist": 5,
                "tube_stack_thickness": 1.0,
            },
            "Preset2": {
                "tube_sides": 8,
                "tube_length": 16.0,
                "tube_top_inner_radius": 4.0,
                "tube_bottom_inner_radius": 4.0,
                "tube_thickness": 2.0,
                "tube_top_angle": 0,
                "tube_bottom_angle": 0,
                "tube_twist": 5,
                "tube_stack_thickness": 1.0,
            },
        },
    },
    "SimpleTorus": {
        "label": "SimpleTorus",
        "enabled": True,
        "generator": lambda s: build_simple_torus(
            s["torus_inner_radius"],
            s["torus_outer_radius"],
            s["torus_hollow_percent"],
            s["torus_xy_ratio"],
            s["torus_start_angle"],
            s["torus_sweep"],
            s["torus_sides"],
            s["torus_cylinder"],
        ),
        "params": {
            "torus_inner_radius": {
                "label": "Inner radius",
                "type": "slider",
                "min": 0.5,
                "max": 20.0,
                "default": 4.0,
                "step": 0.5,
            },
            "torus_outer_radius": {
                "label": "Outer radius",
                "type": "slider",
                "min": 0.5,
                "max": 30.0,
                "default": 6.0,
                "step": 0.5,
            },
            "torus_hollow_percent": {
                "label": "Hollow from center",
                "type": "slider",
                "min": 0.0,
                "max": 100.0,
                "default": 50.0,
                "step": 5.0,
                "format": "%.0f%%",
            },
            "torus_xy_ratio": {
                "label": "X/Y ratio",
                "type": "slider",
                "min": 0.1,
                "max": 3.0,
                "default": 1.0,
                "step": 0.1,
            },
            "torus_start_angle": {
                "label": "Start angle",
                "type": "slider",
                "min": -360.0,
                "max": 360.0,
                "default": 0.0,
                "step": 1.0,
            },
            "torus_sweep": {
                "label": "Sweep",
                "type": "slider",
                "min": 1.0,
                "max": 360.0,
                "default": 360.0,
                "step": 1.0,
            },
            "torus_cylinder": {
                "label": "Cylinder",
                "type": "toggle",
                "default": False,
            },
            "torus_sides": {
                "label": "Polygon sides",
                "type": "slider",
                "min": 3,
                "max": 15,
                "default": 8,
                "step": 1,
                "disabled_by": "torus_cylinder",
            },
        },
        "presets": {
            "Preset1": {
                "torus_inner_radius": 4.0,
                "torus_outer_radius": 6.0,
                "torus_hollow_percent": 50.0,
                "torus_xy_ratio": 1.0,
                "torus_start_angle": 0.0,
                "torus_sweep": 360.0,
                "torus_cylinder": False,
                "torus_sides": 8,
            },
            "Preset2": {
                "torus_inner_radius": 4.0,
                "torus_outer_radius": 6.0,
                "torus_hollow_percent": 50.0,
                "torus_xy_ratio": 1.0,
                "torus_start_angle": 0.0,
                "torus_sweep": 360.0,
                "torus_cylinder": False,
                "torus_sides": 8,
            },
        },
    },
    "AdvancedTorus": {
        "label": "AdvancedTorus",
        "enabled": False,
        "generator": None,
        "params": {},
        "presets": {},
    },
    "ComplexTorus": {
        "label": "ComplexTorus",
        "enabled": False,
        "generator": None,
        "params": {},
        "presets": {},
    },
}

VIEWPORT_DEFAULTS = {
    "rotation_xy": 0,
    "rotation_yz": 0,
    "rotation_zx": 0,
    "attach_vis_controls": False,
    "attach_unicode_panel": False,
    "vis_auto_scale": True,
    "vis_scale": 1.0,
    "vis_color": "#FFFF00",
    "vis_alpha": 0.9,
    "vis_show_grid": False,
    "vis_flatshading": True,
    "vis_material": "Matte",
    "xy_spin": 0,
    "yz_spin": 0,
    "zx_spin": 0,
    "angle_resolution": 1.0,
    "anim_ticks_per_second": 10,
}

VIS_STATE_KEYS = (
    "rotation_xy",
    "rotation_yz",
    "rotation_zx",
    "vis_auto_scale",
    "vis_scale",
    "vis_color",
    "vis_material",
    "vis_alpha",
    "vis_show_grid",
    "vis_flatshading",
    "angle_resolution",
    "anim_ticks_per_second",
)

DEFAULTS = {"active_object": "SimpleHexShpere"}
for obj_meta in OBJECT_REGISTRY.values():
    for p_key, p_cfg in obj_meta["params"].items():
        DEFAULTS[p_key] = p_cfg["default"]
DEFAULTS.update(VIEWPORT_DEFAULTS)

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

st.session_state.setdefault("save_user_presets", True)

if "user_presets" not in st.session_state:
    st.session_state.user_presets = {}

for obj_name, obj_meta in OBJECT_REGISTRY.items():
    if obj_name not in st.session_state.user_presets:
        st.session_state.user_presets[obj_name] = {}
    for user_btn in ("User1", "User2", "User3"):
        if user_btn not in st.session_state.user_presets[obj_name]:
            st.session_state.user_presets[obj_name][user_btn] = {
                p_key: p_cfg["default"] for p_key, p_cfg in obj_meta["params"].items()
            }

st.session_state.setdefault("save_vis_states", True)

if "vis_user_states" not in st.session_state:
    st.session_state.vis_user_states = {}
for state_btn in ("State1", "State2"):
    if state_btn not in st.session_state.vis_user_states:
        st.session_state.vis_user_states[state_btn] = {key: VIEWPORT_DEFAULTS[key] for key in VIS_STATE_KEYS}


def sync_controls_to_object(active, previous):
    """Sync controls so widgets reflect the active object's real state, including cross-object shared fields and derived clamps."""
    if active != previous:
        if active == "SimpleTube" and previous in ("AdvancedTube", "ComplexTube"):
            st.session_state.tube_inner_radius = st.session_state.tube_top_inner_radius
        elif active in ("AdvancedTube", "ComplexTube") and previous == "SimpleTube":
            st.session_state.tube_top_inner_radius = st.session_state.tube_inner_radius
            st.session_state.tube_bottom_inner_radius = st.session_state.tube_inner_radius
    if active == "SimpleTorus" and st.session_state.torus_outer_radius < st.session_state.torus_inner_radius:
        st.session_state.torus_outer_radius = st.session_state.torus_inner_radius


def handle_active_object_change():
    sync_controls_to_object(st.session_state.active_object, st.session_state.previous_active_object)
    st.session_state.previous_active_object = st.session_state.active_object


def apply_object_preset(preset_name):
    active_cfg = OBJECT_REGISTRY[st.session_state.active_object]
    if not active_cfg.get("enabled", True):
        return
    if preset_name == "Defaults":
        for p_key, p_cfg in active_cfg["params"].items():
            st.session_state[p_key] = p_cfg["default"]
    else:
        preset_values = active_cfg.get("presets", {}).get(preset_name, {})
        for p_key, val in preset_values.items():
            st.session_state[p_key] = val


def apply_user_preset(preset_name):
    active_obj = st.session_state.active_object
    active_cfg = OBJECT_REGISTRY[active_obj]
    if not active_cfg.get("enabled", True):
        return
    is_save_mode = bool(st.session_state.get("save_user_presets", True))

    if is_save_mode:
        saved_params = {}
        for p_key, p_cfg in active_cfg["params"].items():
            saved_params[p_key] = st.session_state.get(p_key, p_cfg["default"])
        st.session_state.user_presets[active_obj][preset_name] = saved_params
        st.session_state["_preset_toast"] = f"Saved {active_obj} parameters to {preset_name}!"
    else:
        preset_values = st.session_state.user_presets[active_obj].get(preset_name, {})
        for p_key, val in preset_values.items():
            st.session_state[p_key] = val
        st.session_state["_preset_toast"] = f"Applied {preset_name} for {active_obj}!"


def generate_active_geometry():
    active = st.session_state.active_object
    active_cfg = OBJECT_REGISTRY[active]
    if not active_cfg.get("enabled", True) or active_cfg.get("generator") is None:
        return [], [], []
    generator = active_cfg["generator"]
    return generator(st.session_state)


def apply_material():
    preset = MATERIAL_PRESETS.get(st.session_state.vis_material)
    if preset:
        st.session_state.vis_alpha = preset["alpha"]
        st.session_state.vis_flatshading = preset["flatshading"]


def apply_vis_default():
    for key in VIS_STATE_KEYS:
        st.session_state[key] = VIEWPORT_DEFAULTS[key]
    st.session_state.xy_spin = 0
    st.session_state.yz_spin = 0
    st.session_state.zx_spin = 0


def set_spin(spin_key, direction):
    st.session_state[spin_key] = direction


def step_spin_angle(axis_key, spin_key):
    """Advance an axis angle by one animation tick if its spin direction is active."""
    direction = st.session_state.get(spin_key, 0)
    if direction:
        new_angle = st.session_state[axis_key] + direction * st.session_state.angle_resolution
        st.session_state[axis_key] = ((new_angle + 180) % 360) - 180


def apply_vis_state(state_name):
    is_save_mode = bool(st.session_state.get("save_vis_states", True))
    if is_save_mode:
        st.session_state.vis_user_states[state_name] = {
            key: st.session_state.get(key, VIEWPORT_DEFAULTS[key]) for key in VIS_STATE_KEYS
        }
        st.session_state["_preset_toast"] = f"Saved viewport controls to {state_name}!"
    else:
        state_values = st.session_state.vis_user_states.get(state_name, {})
        for key, val in state_values.items():
            st.session_state[key] = val
        st.session_state["_preset_toast"] = f"Applied {state_name} viewport controls!"


def build_recipe_dict():
    """Snapshot app version, object type, parameters, color, material and user presets for export."""
    active_obj = st.session_state.active_object
    active_cfg = OBJECT_REGISTRY[active_obj]
    parameters = {
        p_key: st.session_state.get(p_key, p_cfg["default"])
        for p_key, p_cfg in active_cfg["params"].items()
    }
    return {
        "app_version": APP_VERSION,
        "object_type": active_obj,
        "parameters": parameters,
        "color": st.session_state.vis_color,
        "material": st.session_state.vis_material,
        "user_presets": st.session_state.user_presets,
    }


def apply_recipe_dict(recipe):
    """Restore object type, parameters, color, material and user presets from an imported recipe."""
    object_type = recipe.get("object_type")
    if object_type in OBJECT_REGISTRY:
        st.session_state.active_object = object_type
        st.session_state.previous_active_object = object_type
        for p_key, val in recipe.get("parameters", {}).items():
            if p_key in OBJECT_REGISTRY[object_type]["params"]:
                st.session_state[p_key] = val
    if "color" in recipe:
        st.session_state.vis_color = recipe["color"]
    if recipe.get("material") in MATERIAL_PRESETS:
        st.session_state.vis_material = recipe["material"]
    imported_presets = recipe.get("user_presets")
    if isinstance(imported_presets, dict):
        for obj_name, presets in imported_presets.items():
            if obj_name in st.session_state.user_presets and isinstance(presets, dict):
                st.session_state.user_presets[obj_name].update(presets)
    st.session_state["_preset_toast"] = "Recipe imported successfully!"


st.session_state.setdefault("previous_active_object", st.session_state.active_object)
sync_controls_to_object(st.session_state.active_object, st.session_state.previous_active_object)

vertices, faces, edge_indices = generate_active_geometry()

if "_preset_toast" in st.session_state and st.session_state["_preset_toast"]:
    st.toast(st.session_state["_preset_toast"])
    st.session_state["_preset_toast"] = ""

st.markdown("<div class='eyebrow'>GEOMETRY LAB / 01</div>", unsafe_allow_html=True)
st.title("HexSphere Studio")
st.caption("Faceted 3D object generator with real-time viewport and Wavefront OBJ export.")

with st.sidebar:
    st.markdown("### 1. Server Control Panel")
    st.caption("Configure geometry parameters and apply changes to update the 3D model.")
    active_object = st.radio("Object type", tuple(OBJECT_REGISTRY.keys()), key="active_object", label_visibility="collapsed", on_change=handle_active_object_change)
    st.divider()
    with st.form("controls"):
        active_cfg = OBJECT_REGISTRY[st.session_state.active_object]
        st.markdown(f"#### {active_cfg['label']}")
        if not active_cfg.get("enabled", True):
            st.info("This object is a ToDo item for Server Controls and is not implemented or enabled yet.")
            submitted = st.form_submit_button("Apply object", width='stretch', type="primary", disabled=True)
        else:
            for p_key, p_cfg in active_cfg["params"].items():
                p_type = p_cfg.get("type", "slider")
                default_val = p_cfg["default"]
                is_disabled = (
                    bool(st.session_state.get(p_cfg["disabled_by"], False))
                    if "disabled_by" in p_cfg
                    else False
                )
                if p_type == "toggle":
                    st.toggle(
                        p_cfg["label"],
                        value=default_val,
                        key=p_key,
                        disabled=is_disabled,
                    )
                elif p_type == "slider":
                    slider_kwargs = {}
                    if "step" in p_cfg:
                        slider_kwargs["step"] = p_cfg["step"]
                    if "format" in p_cfg:
                        slider_kwargs["format"] = p_cfg["format"]
                    st.slider(
                        p_cfg["label"],
                        p_cfg["min"],
                        p_cfg["max"],
                        default_val,
                        key=p_key,
                        disabled=is_disabled,
                        **slider_kwargs,
                    )
                elif p_type == "select":
                    st.selectbox(
                        p_cfg["label"],
                        options=p_cfg["options"],
                        key=p_key,
                        disabled=is_disabled,
                    )
            submitted = st.form_submit_button("Apply object", width='stretch', type="primary")

    btn_col1, btn_col2, btn_col3 = st.sidebar.columns(3)
    btn_col1.button(
        "Defaults",
        width='stretch',
        disabled=not active_cfg.get("enabled", True),
        on_click=apply_object_preset,
        args=("Defaults",),
    )
    btn_col2.button(
        "Preset1",
        width='stretch',
        disabled=not active_cfg.get("enabled", True),
        on_click=apply_object_preset,
        args=("Preset1",),
    )
    btn_col3.button(
        "Preset2",
        width='stretch',
        disabled=not active_cfg.get("enabled", True),
        on_click=apply_object_preset,
        args=("Preset2",),
    )

    user_col1, user_col2, user_col3 = st.sidebar.columns(3)
    user_col1.button(
        "User1",
        width='stretch',
        disabled=not active_cfg.get("enabled", True),
        on_click=apply_user_preset,
        args=("User1",),
    )
    user_col2.button(
        "User2",
        width='stretch',
        disabled=not active_cfg.get("enabled", True),
        on_click=apply_user_preset,
        args=("User2",),
    )
    user_col3.button(
        "User3",
        width='stretch',
        disabled=not active_cfg.get("enabled", True),
        on_click=apply_user_preset,
        args=("User3",),
    )
    is_save_mode = st.sidebar.toggle("Save user presets", key="save_user_presets", value=True)
    if is_save_mode:
        st.sidebar.caption("Click to Save Presets")
    else:
        st.sidebar.caption("Click to apply the presets")

    st.divider()
    st.markdown("### Viewport Controls")
    st.toggle(
        "Attach visualization controls",
        key="attach_vis_controls",
        help="Attach or detach the 3D visualization controls panel (rotation, animation, color). Detached by default for a larger 3D viewer.",
    )
    st.toggle(
        "Attach Unicode panel",
        key="attach_unicode_panel",
        help="Attach or detach the Unicode character browser below the 3D viewer. Detached by default.",
    )

    if st.session_state.active_object == "PictureSphere":
        st.divider()
        st.markdown("### Picture Sphere Image")
        st.file_uploader(
            "Upload an image to map onto the sphere",
            type=["png", "jpg", "jpeg"],
            key="picture_sphere_image_upload",
            help="Sampled onto each hex/pentagon tile using an equirectangular projection.",
        )

        st.markdown("### Tile Inspection & Paintbrush")
        tile_data = st.session_state.get("picture_sphere_tile_data") or {}
        label_of_tile = tile_data.get("label_of_tile", {})
        num_tiles = len(tile_data.get("tile_centroids", []))
        if num_tiles:
            st.number_input(
                "Anchor tile ID",
                min_value=0,
                max_value=num_tiles - 1,
                key="picture_sphere_anchor_tile_id",
                help="Ring/Sequence addresses (R{ring}-S{seq}) are computed relative to this tile.",
            )
            sorted_labels = [label for _, label in sorted(
                label_of_tile.items(),
                key=lambda item: (0, 0) if item[1] == "Anchor-0" else (int(item[1].split("-")[0][1:]), int(item[1].split("-")[1][1:])),
            )]
            st.selectbox("Target tile (Ring-Sequence)", options=sorted_labels, key="picture_sphere_target_tile_label")
            st.color_picker("Paint color", value="#3568ad", key="picture_sphere_paint_color")
            st.text_input(
                "Character label (optional)",
                key="picture_sphere_paint_character",
                max_chars=1,
                help="Shown on the painted tile in the inverse of the paint color, so it always stays visible.",
            )
            st.number_input(
                "Label layers",
                min_value=1,
                max_value=10,
                value=3,
                key="picture_sphere_label_layers",
                help="Stacked flat layers each character decal is built from, just above the tile surface (groundwork for later solid extrusion).",
            )
            paint_col1, paint_col2 = st.columns(2)
            paint_col1.button("Paint Selected Tile", width='stretch', on_click=paint_selected_picture_sphere_tile)
            paint_col2.button("Reset Paint", width='stretch', on_click=reset_picture_sphere_paint)

            st.markdown("### Test Pattern")
            st.caption("Fills every tile with a distinct rainbow color and a letter, for visually verifying tile identity/adjacency.")
            st.selectbox(
                "Label characters",
                options=["A-Z (cycling)", "Random characters"],
                key="picture_sphere_test_label_mode",
            )
            test_col1, test_col2 = st.columns(2)
            test_col1.button("Generate Test Pattern", width='stretch', on_click=generate_picture_sphere_test_pattern)
            test_col2.button("Clear Test Pattern", width='stretch', on_click=clear_picture_sphere_test_pattern)

    st.divider()
    st.markdown("### Export OBJ")
    active_meta = {
        p_key: st.session_state.get(p_key, p_cfg["default"])
        for p_key, p_cfg in OBJECT_REGISTRY[st.session_state.active_object]["params"].items()
    }
    obj_data = generate_obj_text(
        vertices,
        faces,
        object_name=st.session_state.active_object,
        params=active_meta,
    )
    file_name = f"{st.session_state.active_object.lower().replace(' ', '_')}.obj"
    st.download_button(
        label="Download .OBJ (Native)",
        data=obj_data,
        file_name=file_name,
        mime="text/plain",
        width='stretch',
    )

    st.divider()
    st.markdown("### Recipe (Save/Load Config)")
    st.caption("A recipe stores app version, object type, parameters, color, material and User1/2/3 presets.")
    recipe_json = json.dumps(build_recipe_dict(), indent=2)
    st.download_button(
        label="Export Recipe",
        data=recipe_json,
        file_name="hexsphere_recipe.json",
        mime="application/json",
        width='stretch',
    )
    recipe_upload = st.file_uploader(
        "Import Recipe",
        type=["json"],
        key="recipe_uploader",
        label_visibility="collapsed",
    )
    if st.button("Import Recipe", width='stretch'):
        if recipe_upload is None:
            st.warning("Choose a recipe .json file first.")
        else:
            try:
                imported_recipe = json.loads(recipe_upload.getvalue().decode("utf-8"))
                apply_recipe_dict(imported_recipe)
                st.rerun()
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                st.error("Invalid recipe file. Please upload a valid HexSphere recipe .json.")


def resolve_active_face_colors(faces):
    """Per-face color list for PictureSphere (painted/image tile colors), else None for the default uniform color."""
    if st.session_state.active_object != "PictureSphere":
        return None
    tile_data = st.session_state.get("picture_sphere_tile_data")
    if not tile_data:
        return None
    tile_colors = tile_data.get("tile_colors")
    face_tile_ids = tile_data.get("face_tile_ids")
    if not tile_colors or not face_tile_ids or len(face_tile_ids) != len(faces):
        return None
    return [tile_colors[tile_id] for tile_id in face_tile_ids]


def resolve_active_label_mesh():
    """(vertices, faces, colors) for the PictureSphere tile-character decal mesh, else None."""
    if st.session_state.active_object != "PictureSphere":
        return None
    tile_data = st.session_state.get("picture_sphere_tile_data")
    if not tile_data:
        return None
    return (
        tile_data.get("label_mesh_vertices"),
        tile_data.get("label_mesh_faces"),
        tile_data.get("label_mesh_colors"),
    )


@st.fragment
def render_viewer_section(vertices, faces, edge_indices):
    """Isolated fragment so rotation controls and spin animation only re-render the viewer, not the whole page."""
    if st.session_state.attach_vis_controls:
        # Auto-rotate animation is disabled for now (perf tuning), so spin never advances.
        st.session_state.xy_spin = 0
        st.session_state.yz_spin = 0
        st.session_state.zx_spin = 0
        step_spin_angle("rotation_xy", "xy_spin")
        step_spin_angle("rotation_yz", "yz_spin")
        step_spin_angle("rotation_zx", "zx_spin")

        viewer_col, vis_col = st.columns([3, 1])
        with vis_col:
            st.subheader("3. Visualization Controls")
            st.markdown("#### Manual Rotation")
            xy_row = st.columns([7, 1, 1, 1])
            xy_row[0].slider("XY angle", -180.0, 180.0, key="rotation_xy")
            xy_row[1].button("⏪", key="xy_dec", width='stretch', disabled=True, on_click=set_spin, args=("xy_spin", -1))
            xy_row[2].button("⏹", key="xy_stop", width='stretch', disabled=True, on_click=set_spin, args=("xy_spin", 0))
            xy_row[3].button("⏩", key="xy_inc", width='stretch', disabled=True, on_click=set_spin, args=("xy_spin", 1))

            yz_row = st.columns([7, 1, 1, 1])
            yz_row[0].slider("YZ angle", -180.0, 180.0, key="rotation_yz")
            yz_row[1].button("⏪", key="yz_dec", width='stretch', disabled=True, on_click=set_spin, args=("yz_spin", -1))
            yz_row[2].button("⏹", key="yz_stop", width='stretch', disabled=True, on_click=set_spin, args=("yz_spin", 0))
            yz_row[3].button("⏩", key="yz_inc", width='stretch', disabled=True, on_click=set_spin, args=("yz_spin", 1))

            zx_row = st.columns([7, 1, 1, 1])
            zx_row[0].slider("ZX angle", -180.0, 180.0, key="rotation_zx")
            zx_row[1].button("⏪", key="zx_dec", width='stretch', disabled=True, on_click=set_spin, args=("zx_spin", -1))
            zx_row[2].button("⏹", key="zx_stop", width='stretch', disabled=True, on_click=set_spin, args=("zx_spin", 0))
            zx_row[3].button("⏩", key="zx_inc", width='stretch', disabled=True, on_click=set_spin, args=("zx_spin", 1))

            st.slider("Angle resolution (deg/tick)", 1.0, 15.0, step=0.5, key="angle_resolution", disabled=True)
            st.slider("Animation speed (ticks/sec)", 1, 30, step=1, key="anim_ticks_per_second", disabled=True)
            st.caption("Auto-rotate animation is temporarily disabled (performance tuning in progress). Drag the sliders above to rotate manually.")

            st.markdown("#### Scale & Appearance")
            st.toggle("Auto-scale", key="vis_auto_scale")
            st.slider("Scale", 0.1, 3.0, step=0.05, key="vis_scale", disabled=st.session_state.vis_auto_scale)
            is_picture_sphere = st.session_state.active_object == "PictureSphere"
            st.color_picker("Surface color", key="vis_color", disabled=is_picture_sphere)
            st.selectbox("Material", options=list(MATERIAL_PRESETS.keys()), key="vis_material", on_change=apply_material)
            st.slider("Alpha (opacity)", 0.0, 1.0, step=0.01, key="vis_alpha", disabled=is_picture_sphere)
            if is_picture_sphere:
                st.caption("Surface color and Alpha are driven by each tile's paint/photo color for PictureSphere and always render at full opacity.")
            st.toggle("Show grid", key="vis_show_grid")
            st.toggle("Flat shading", key="vis_flatshading")

            st.markdown("#### Viewport States")
            vis_btn_col1, vis_btn_col2, vis_btn_col3 = st.columns(3)
            vis_btn_col1.button("Default", width='stretch', on_click=apply_vis_default, key="vis_default_btn")
            vis_btn_col2.button("State1", width='stretch', on_click=apply_vis_state, args=("State1",), key="vis_state1_btn")
            vis_btn_col3.button("State2", width='stretch', on_click=apply_vis_state, args=("State2",), key="vis_state2_btn")
            is_vis_save_mode = st.toggle("Save viewport states", key="save_vis_states", value=True)
            if is_vis_save_mode:
                st.caption("Click State1/State2 to Save Viewport Controls")
            else:
                st.caption("Click State1/State2 to apply the saved viewport controls")

        with viewer_col:
            st.subheader("2. Viewer (3D Viewport)")
            scale = 1.0 if st.session_state.vis_auto_scale else st.session_state.vis_scale
            fig = build_plotly_figure(
                vertices,
                faces,
                edge_indices,
                thickness=st.session_state.thickness,
                angles=(st.session_state.rotation_xy, st.session_state.rotation_yz, st.session_state.rotation_zx),
                scale=scale,
                color=st.session_state.vis_color,
                alpha=st.session_state.vis_alpha,
                flatshading=st.session_state.vis_flatshading,
                show_grid=st.session_state.vis_show_grid,
                face_colors=resolve_active_face_colors(faces),
                label_mesh=resolve_active_label_mesh(),
            )
            st.plotly_chart(fig, width='stretch')

        if any(st.session_state.get(k, 0) for k in ("xy_spin", "yz_spin", "zx_spin")):
            time.sleep(1.0 / st.session_state.anim_ticks_per_second)
            st.rerun(scope="fragment")
    else:
        st.subheader("Viewer (3D Viewport) — Visualization Controls Detached")
        scale = 1.0 if st.session_state.vis_auto_scale else st.session_state.vis_scale
        fig = build_plotly_figure(
            vertices,
            faces,
            edge_indices,
            thickness=st.session_state.thickness,
            angles=(st.session_state.rotation_xy, st.session_state.rotation_yz, st.session_state.rotation_zx),
            scale=scale,
            color=st.session_state.vis_color,
            alpha=st.session_state.vis_alpha,
            flatshading=st.session_state.vis_flatshading,
            show_grid=st.session_state.vis_show_grid,
            face_colors=resolve_active_face_colors(faces),
            label_mesh=resolve_active_label_mesh(),
        )
        st.plotly_chart(fig, width='stretch')


@st.fragment
def render_unicode_panel():
    """Unicode browser kept in a fragment so character interactions stay local."""
    default_block_idx = next((i for i, (block_start, _, _) in enumerate(UNICODE_BLOCKS) if block_start == 0x2600), 0)
    st.session_state.setdefault("uni_category_idx", default_block_idx)
    st.session_state.setdefault("uni_selected_char", 0x2600)
    st.session_state.setdefault("uni_rotation", 0)
    st.session_state.setdefault("uni_flip_h", False)
    st.session_state.setdefault("uni_flip_v", False)
    st.session_state.setdefault("uni_axis_x", 0)
    st.session_state.setdefault("uni_font", "Segoe UI Symbol — symbols and math")
    st.session_state.setdefault("uni_search_text", "")
    st.session_state.setdefault("uni_search_match_count", None)

    start, end, block_name = UNICODE_BLOCKS[st.session_state.uni_category_idx]
    selected_cp = min(max(st.session_state.uni_selected_char, start), end)
    st.session_state.uni_selected_char = selected_cp
    block_size = end - start + 1
    block_rows = max(1, math.ceil(block_size / 16))

    st.markdown(
        """
        <style>
        .unicode-shell {
            background: #121b2b;
            border: 1px solid #2f3d54;
            border-radius: 10px;
            color: #ecf2ff;
            padding: 1.15rem;
        }
        .unicode-shell h2 { margin: 0; color: #f6f8fd; font-size: 1.65rem; }
        .unicode-subtitle { color: #9ba9bd; margin: .2rem 0 1rem; }
        .unicode-kicker { color: #78a8ff; font-size: .72rem; font-weight: 700; letter-spacing: .14em; }
        .unicode-section {
            background: #1a2638;
            border: 1px solid #314159;
            border-radius: 8px;
            padding: .8rem;
            margin-top: .8rem;
        }
        .unicode-section-title { color: #f4f7fb; font-weight: 700; margin-bottom: .55rem; }
        .unicode-meta { color: #9ba9bd; font-size: .83rem; }
        .unicode-preview {
            align-items: center; background: #101827; border: 1px solid #3c4b64;
            border-radius: 7px; display: flex; height: 174px; justify-content: center;
            margin-bottom: .65rem; overflow: hidden; position: relative;
        }
        .unicode-preview-glyph {
            color: #f7f9ff; position: relative; z-index: 2;
            font-size: 7rem; line-height: 1; transform-origin: center center;
        }
        .unicode-axis-h {
            position: absolute; left: 0; right: 0; top: 50%; height: 1px;
            background: rgba(120, 168, 255, .28); z-index: 1;
        }
        .unicode-axis-v {
            position: absolute; top: 0; bottom: 0; left: 50%; width: 1px;
            background: rgba(120, 168, 255, .28); z-index: 1;
        }
        .unicode-axis-rotation {
            position: absolute; top: 0; bottom: 0; width: 1px;
            background: rgba(255, 40, 40, .55); z-index: 1;
        }
        .unicode-info-grid { display: grid; gap: .5rem 1rem; grid-template-columns: 1fr 1fr; }
        .unicode-info-grid div { border-bottom: 1px solid #2d3a50; padding: .35rem 0; }
        .unicode-info-grid b { color: #f5f7fb; display: block; font-size: .82rem; }
        .unicode-info-grid span { color: #aebbd0; font-family: monospace; font-size: .8rem; }
        .st-key-unicode-grid [data-testid="stButton"] > button {
            background: #202d41; border: 1px solid #3b4a61; border-radius: 3px; color: #e9eff9;
            font-size: 1rem; min-height: 2.05rem; padding: 0;
        }
        .st-key-unicode-grid [data-testid="stButton"] > button:hover {
            background: #355b93; border-color: #78a8ff; color: #fff;
        }
        .st-key-unicode-grid [data-testid="stHorizontalBlock"] { gap: .12rem; }
        .st-key-unicode-grid [data-testid="stVerticalBlock"] { gap: .12rem; }
        .unicode-axis { color: #8d9cb2; font-family: monospace; font-size: .7rem; text-align: center; }
        .unicode-selected [data-testid="stButton"] > button { background: #3568ad; border-color: #8bb8ff; }
        @media (max-width: 900px) { .unicode-info-grid { grid-template-columns: 1fr; } }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="unicode-shell">', unsafe_allow_html=True)
    st.markdown('<div class="unicode-kicker">CHARACTER EXPLORER</div><h2>Unicode Panel</h2><div class="unicode-subtitle">Browse, search, and explore Unicode characters</div>', unsafe_allow_html=True)

    control_col, search_col, font_col = st.columns([1.1, .9, 1.15])
    with control_col:
        category_options = list(range(len(UNICODE_BLOCKS)))

        def format_category(i):
            s, _, name = UNICODE_BLOCKS[i]
            return f"{s:04X} : {name}"

        st.selectbox("Unicode Block", options=category_options, format_func=format_category,
                     key="uni_category_idx", on_change=reset_unicode_offsets)
    with search_col:
        st.text_input("Search blocks", key="uni_search_text", placeholder="Search block name...")
        st.button("Search", width="stretch", on_click=search_unicode_category)
        match_count = st.session_state.uni_search_match_count
        if match_count is not None and st.session_state.uni_search_text.strip():
            st.caption("No matching block." if match_count == 0 else f"{match_count} block(s) matched.")
    with font_col:
        st.selectbox("Character Font", options=list(UNICODE_FONT_OPTIONS), key="uni_font",
                     help="Choose a font installed on your system. Symbol and emoji fonts provide the best coverage for their named character sets.")

    selected_font_family = UNICODE_FONT_OPTIONS[st.session_state.uni_font]
    st.markdown(
        f'''<style>
        .st-key-unicode-grid [data-testid="stButton"] > button {{
            font-family: {selected_font_family};
        }}
        </style>
        <div class="unicode-meta" style="margin-top:-.5rem; margin-bottom:.4rem">Font preview: <span style="font-family:{selected_font_family}">Aa Ω ∑ ☀ 🎵</span> &nbsp; · &nbsp; {html.escape(st.session_state.uni_font.split(" — ")[0])}</div>''',
        unsafe_allow_html=True,
    )

    grid_col, info_col = st.columns([1.28, .92], gap="large")

    with grid_col:
        st.markdown('<div class="unicode-section">', unsafe_allow_html=True)
        st.markdown(f'<div class="unicode-section-title">{block_name}</div><div class="unicode-meta">U+{start:04X}–U+{end:04X} &nbsp; · &nbsp; {block_size} characters (16 × {block_rows})</div>', unsafe_allow_html=True)
        with st.container(key="unicode-grid"):
            header_cols = st.columns(17)
            header_cols[0].markdown('<div class="unicode-axis"> </div>', unsafe_allow_html=True)
            for col in range(16):
                header_cols[col + 1].markdown(f'<div class="unicode-axis">{col:X}</div>', unsafe_allow_html=True)
            for r in range(16):
                row_cols = st.columns(17)
                row_cols[0].markdown(f'<div class="unicode-axis">{r:X}</div>', unsafe_allow_html=True)
                for c in range(16):
                    cp = (start & ~0xFF) + r * 16 + c
                    if cp < start or cp > end or cp > 0x10FFFF:
                        row_cols[c + 1].button(" ", key=f"unichar_cell_{r}_{c}", disabled=True, width="stretch")
                    else:
                        row_cols[c + 1].button(
                            unicode_glyph(cp),
                            key=f"unichar_cell_{r}_{c}",
                            width="stretch",
                            help=f"U+{cp:04X}",
                            on_click=select_unichar,
                            args=(cp,),
                        )
        st.markdown('</div>', unsafe_allow_html=True)

    with info_col:
        character = safe_chr(selected_cp)
        selected_char = html.escape(unicode_glyph(selected_cp))
        char_name = unicodedata.name(character, "UNASSIGNED") if character else "UNASSIGNED"
        category_code = unicodedata.category(character) if character else "Cn"
        category_name = {"So": "Other Symbol", "Lu": "Uppercase Letter", "Ll": "Lowercase Letter", "Po": "Other Punctuation"}.get(category_code, "Unassigned" if category_code == "Cn" else "Unicode Character")
        utf16 = character.encode("utf-16-be", errors="surrogatepass").hex(" ").upper() if character else ""
        utf8 = character.encode("utf-8", errors="surrogatepass").hex(" ").upper() if character else ""

        st.markdown('<div class="unicode-section"><div class="unicode-section-title">Selected Character</div>', unsafe_allow_html=True)
        preview_font_size_rem = 7
        axis_limit_px = int(2 * preview_font_size_rem * 16)
        transform = (
            f"translateX({st.session_state.uni_axis_x}px) "
            f"rotate({st.session_state.uni_rotation}deg) "
            f"scaleX({-1 if st.session_state.uni_flip_h else 1}) "
            f"scaleY({-1 if st.session_state.uni_flip_v else 1})"
        )
        glyph_style = html.escape(f"font-family:{selected_font_family}; transform:{transform}", quote=True)
        st.markdown(
            f'<div class="unicode-preview">'
            f'<div class="unicode-axis-h"></div>'
            f'<div class="unicode-axis-v"></div>'
            f'<div class="unicode-axis-rotation" style="left:calc(50% + {st.session_state.uni_axis_x}px)"></div>'
            f'<div class="unicode-preview-glyph" style="{glyph_style}">{selected_char}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.slider("Rotation", -180, 180, key="uni_rotation")
        flip_col1, flip_col2 = st.columns(2)
        flip_col1.toggle("Horizontal Flip", key="uni_flip_h")
        flip_col2.toggle("Vertical Flip", key="uni_flip_v")
        st.slider("Rotation Axis Position", -axis_limit_px, axis_limit_px, key="uni_axis_x",
                   help="Horizontal placement of the red rotation-axis line, in pixels from center.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="unicode-section"><div class="unicode-section-title">Character Metadata</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="unicode-info-grid"><div><b>Name</b><span>{html.escape(char_name)}</span></div><div><b>Block</b><span>{html.escape(block_name)}</span></div><div><b>Index</b><span>U+{selected_cp:04X}</span></div><div><b>Category</b><span>{category_code} ({category_name})</span></div></div></div>', unsafe_allow_html=True)

        st.markdown('<div class="unicode-section"><div class="unicode-section-title">Character Value</div>', unsafe_allow_html=True)
        step_col, value_col, copy_col = st.columns([.55, 1.7, .55])
        if step_col.button("−", key="uni_prev", width="stretch"):
            st.session_state.uni_selected_char = max(start, selected_cp - 1)
            st.rerun(scope="fragment")
        value_col.code(f"U+{selected_cp:04X}")
        if copy_col.button("Copy", key="uni_copy", width="stretch"):
            st.toast(f"{unicode_glyph(selected_cp)}  U+{selected_cp:04X} ready to copy")
        if st.button("+", key="uni_next", width="stretch"):
            st.session_state.uni_selected_char = min(end, selected_cp + 1)
            st.rerun(scope="fragment")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="unicode-section"><div class="unicode-section-title">Character Info</div><div class="unicode-info-grid"><div><b>Decimal</b><span>{selected_cp}</span></div><div><b>Unicode (hex)</b><span>0x{selected_cp:X}</span></div><div><b>UTF-16</b><span>{utf16}</span></div><div><b>UTF-8</b><span>{utf8}</span></div></div></div></div>', unsafe_allow_html=True)


render_viewer_section(vertices, faces, edge_indices)
if st.session_state.attach_unicode_panel:
    render_unicode_panel()

