import re

try:
    from .kana_conv import to_katakana, to_hiragana
except ImportError:
    from kana_conv import to_katakana, to_hiragana

HIRAGANA_CONVERSION_DICT = {
    "か": ["が"],
    "き": ["ぎ"],
    "く": ["ぐ"],
    "け": ["げ"],
    "こ": ["ご"],
    "さ": ["ざ"],
    "し": ["じ"],
    "す": ["ず"],
    "せ": ["ぜ"],
    "そ": ["ぞ"],
    "た": ["だ"],
    "ち": ["ぢ"],
    "つ": ["づ"],
    "て": ["で"],
    "と": ["ど"],
    "は": ["ば", "ぱ"],
    "ひ": ["び", "ぴ"],
    "ふ": ["ぶ", "ぷ"],
    "へ": ["べ", "ぺ"],
    "ほ": ["ぼ", "ぽ"],
}
# Convert HIRAGANA_CONVERSION_DICT to katakana with to_katakana
KATAKANA_CONVERSION_DICT = {
    to_katakana(k): [to_katakana(v) for v in vs] if isinstance(vs, list) else to_katakana(vs)
    for k, vs in HIRAGANA_CONVERSION_DICT.items()
}

SMALL_TSU_POSSIBLE_KATAKANA = [to_katakana(k) for k in [
    "ぱ", "ぴ", "ぷ", "ぺ", "ぽ", "こ", "か", "く", "き"
]]

# Regex matching any kanji characters
# Include the kanji repeater puncuation as something that will be cleaned off
KANJI_RE = re.compile(r"([々\u4e00-\u9faf\u3400-\u4dbf]+)")

# Regex matching any furigana
FURIGANA_RE = re.compile(r" ?([^ >]+?)\[(.+?)\]")

# Regex matching any kanji and furigana
KANJI_AND_FURIGANA_RE = re.compile(r"([々\u4e00-\u9faf\u3400-\u4dbf]+)\[(.+?)\]")


def re_match_from_right(text):
    return re.compile(rf"(.+)({text})(.*?)$")


def re_match_from_left(text):
    return re.compile(rf"^(.*?)({text})(.+)$")


def re_match_from_middle(text):
    return re.compile(rf"^(.+?)({text})(.+?)$")


# Implementation of the basic Anki kana filter
# This is needed to clean up the text in cases where we know there's no matches to the kanji
# This works differently as it directly matches kanji characters instead of [^ >] as in the Anki
# built-in version. For whatever reason a python version using that doesn't work as expected.
def kana_filter(text):
    def bracket_replace(match):
        if match.group(1).startswith("sound:"):
            # [sound:...] should not be replaced
            return match.group(0)
        else:
            # Return the furigana inside the brackets
            return match.group(1)

    # First remove all brackets and then remove all kanji
    # Assuming every kanji had furigana, we'll be left with the correct kana
    return KANJI_RE.sub("", FURIGANA_RE.sub(bracket_replace, text.replace("&nbsp;", " ")))


def kana_highlight(
        kanji_to_highlight: str,
        onyomi: str,
        kunyomi: str,
        text: str,
) -> str:
    """
    Function that replaces the furigana of a kanji with the furigana that corresponds to the kanji's
    onyomi or kunyomi reading. The furigana is then highlighted with <b> tags.
    Text received could be a sentence or a single word with furigana.
    :param kanji_to_highlight: should be a single kanji character
    :param onyomi: onyomi reading of the kanji, separated by commas if there are multiple readings
    :param kunyomi: kunyomi reading of the kanji, separated by commas if there are multiple readings
        okuri gana should be separated by a dot
    :param text: The text to process
    :return: The text cleaned from any previous <b> tags and with the furigana highlighted with <b> tags
        when the furigana corresponds to the kanji_to_highlight
    """
    debug_text = ""

    def debug_print(text):
        nonlocal debug_text
        debug_text += text + "\n"
        print(text)

    # Function that processess a furigana by checking all possible onyomi and kunyomi readings on it
    # Either returns the furigana as-is when there is no match or modifies the furigana by
    # adding <b> tags around the part that matches the reading
    def process_readings(furigana, right_edge=False, left_edge=False, middle=False,
                         show_error_message=print):
        # We'll loop through all onyomi and kunyomi readings and find the one that has a match in the furigana
        # If we find a match, we'll highlight that part of the furigana
        target_furigana_section = None
        if left_edge:
            # Leave out the last character of the furigana
            target_furigana_section = furigana[:-1]
        elif right_edge:
            # Leave out the first character of the furigana
            target_furigana_section = furigana[1:]
        elif middle:
            # Leave out both the first and last characters of the furigana
            target_furigana_section = furigana[1:-1]
        if target_furigana_section is None:
            show_error_message(
                "Error in kana_highlight[]: process_readings() called with no edge specified")
            return None

        # Check onyomi readings
        # If we find an onyomi match, we'll convert the furigana to katana to signify this is an
        # onyomi reading for the kanji
        def replace_onyomi_match(onyomi_that_matched):
            # def onyomi_replacer(match):
            #     return f'<b>{to_katakana(match.group(1))}</b>'

            nonlocal furigana
            return furigana.replace(onyomi_that_matched, f'<b>{to_katakana(onyomi_that_matched)}</b>')

        for onyomi_reading in onyomi.split("、"):
            # remove text in () in the reading
            onyomi_reading = re.sub(r"\(.*?\)", "", onyomi_reading).strip()
            # Convert the onyomi to hiragana since the furigana is in hiragana
            onyomi_reading = to_hiragana(onyomi_reading)
            if onyomi_reading in target_furigana_section:
                debug_print(f"\nonyomi_reading: {onyomi_reading}")
                return replace_onyomi_match(onyomi_reading)
            # The reading might have a match with a changed kana like シ->ジ, フ->プ, etc.
            # This only applies to the first kana in the reading
            if onyomi_reading[0] in HIRAGANA_CONVERSION_DICT:
                for kana in HIRAGANA_CONVERSION_DICT[onyomi_reading[0]]:
                    converted_onyomi = onyomi_reading.replace(onyomi_reading[0], kana, 1)
                    if converted_onyomi in target_furigana_section:
                        debug_print(f"\nconverted_onyomi: {converted_onyomi}")
                        return replace_onyomi_match(converted_onyomi)
        # Then also check for small tsu conversion of some consonants
        # this only happens in the last kana of the reading
        for kana in SMALL_TSU_POSSIBLE_KATAKANA:
            if onyomi[-1] == kana:
                converted_onyomi = onyomi[:-1] + "っ"
                if converted_onyomi in target_furigana_section:
                    debug_print(f"\nconverted_onyomi: {converted_onyomi}")
                    return replace_onyomi_match(converted_onyomi)

        def replace_kunyomi_match(kunyomi_that_matched):
            nonlocal furigana
            return furigana.replace(kunyomi_that_matched, f"<b>{kunyomi_that_matched}</b>")

        # Then check the kunyomi readings
        # We'll keep these as hiragana
        for kunyomi_reading in kunyomi.split("、"):
            # Remove the okurigana in the reading which are split by a dot
            kunyomi_stem = re.sub(r"\..+", "", kunyomi_reading).strip()
            # For kunyomi we just check for a match with the stem
            if kunyomi_stem in target_furigana_section:
                debug_print(f"\nkunyomi_stem: {kunyomi_stem}")
                return replace_kunyomi_match(kunyomi_stem)
            # Also check for changed kana
            if kunyomi_stem[0] in HIRAGANA_CONVERSION_DICT:
                for kana in HIRAGANA_CONVERSION_DICT[kunyomi_stem[0]]:
                    converted_kunyomi = kunyomi_stem.replace(kunyomi_stem[0], kana, 1)
                    if converted_kunyomi in target_furigana_section:
                        debug_print(f"\nconverted_kunyomi: {converted_kunyomi}")
                        return replace_kunyomi_match(converted_kunyomi)
        # No onyomi or kunyomi reading matched the furigana
        show_error_message(
            f"Error in kana_highlight[]: No reading found for furigana ({furigana}) among onyomi ({onyomi}) and kunyomi ({kunyomi})")
        return furigana

    # Regex sub replacer function.
    def furigana_replacer(match):
        word = match.group(1)
        furigana = match.group(2)
        if furigana.startswith("sound:"):
            # This was something like 漢字[sound:...], we shouldn't modify the text in the brackets as it'd
            # break the audio tag. But we know the text to the right is kanji (what is it doing there next
            # to a sound tag?) so we'll just leave it out anyway
            return furigana
        if word == kanji_to_highlight or word == f"{kanji_to_highlight}々":
            return f"<b>{furigana}</b>"
        kanji_pos = word.find(kanji_to_highlight)
        if kanji_pos == -1:
            return furigana
        # Take of note of which side of the word the kanji is found on
        # 1. left edge, the furigana replacement has to begin on the left edge and can't end on the right edge
        # 2. right edge, the furigana replacement has to end on the right edge and can't begin on the left edge
        # 3. both (the word is just the kanji or the kanji is repeated), we can just highlight the whole furigana
        # 4. or middle, the furigana replacement can't begin on the left or end on the right
        kanji_in_left_edge = kanji_pos == 0
        kanji_in_right_edge = kanji_pos == len(word) - 1
        # We've already ruled out case 3. so, the middle case
        # is 4. where the kanji is in the middle of the word
        kanji_in_middle = not kanji_in_left_edge and not kanji_in_right_edge
        if kanji_in_left_edge:
            return process_readings(furigana, left_edge=True)
        elif kanji_in_right_edge:
            return process_readings(furigana, right_edge=True)
        elif kanji_in_middle:
            return process_readings(furigana, middle=True)

    # First clean any existing <b> tags from the text, as we don't want to nest them
    clean_text = re.sub(r"<b>(.+?)</b>", r"\1", text)
    return KANJI_AND_FURIGANA_RE.sub(furigana_replacer, clean_text)


def test(test_name, expected_result, sentence, kanji, onyomi, kunyomi):
    result = kana_highlight(
        kanji,
        onyomi,
        kunyomi,
        sentence,
    )
    try:
        assert result == expected_result
    except AssertionError:
        print(test_name)
        print(f"Expected: {expected_result}")
        print(f"Got: {result}")
        raise


def main():
    test(
        test_name="Should not incorrectly match onyomi twice",
        expected_result="<b>シ</b>ちょうしゃ",
        # しちょうしゃ　has し in it twice but only the first one should be highlighted
        sentence="視聴者[しちょうしゃ]",
        kanji="視",
        onyomi="シ(漢)、ジ(呉)",
        kunyomi="み.る"
    )
    print("Ok.")


if __name__ == "__main__":
    main()
