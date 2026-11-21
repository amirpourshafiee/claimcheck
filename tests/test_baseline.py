from claimcheck.baseline import LexicalBaseline, content_tokens, numbers
from claimcheck.schema import Claim, Label

SOURCE = "The device was found in a shipwreck near Antikythera island. It had 35 meshing gears."


def _label(text, source=SOURCE, **kw):
    return LexicalBaseline(**kw).judge(Claim("c1", text), source)


def test_tokens_drop_stopwords_and_numbers_drop_thousands_commas():
    assert content_tokens("The Tower is a tall tower") == {"tower", "tall"}
    assert numbers("In 1,901 about 2.5 percent") == {"1901", "2.5"}


def test_paraphrase_with_full_word_overlap_is_supported():
    v = _label("The device was found in a shipwreck near Antikythera.")
    assert v.label is Label.SUPPORTED


def test_unrelated_claim_is_not_mentioned():
    assert _label("Voyager 1 left the heliosphere.").label is Label.NOT_MENTIONED


def test_wrong_number_blocks_support_even_with_high_word_overlap():
    # 4 of 5 content words overlap (0.8 >= 0.7), but 37 is not in the source.
    v = _label("The device had 37 meshing gears.")
    assert v.label is Label.NOT_MENTIONED and "37" in v.rationale


def test_thousands_separator_does_not_cause_a_false_number_mismatch():
    v = _label(
        "Found 1901 shipwreck Antikythera", source="Found in 1,901, a shipwreck at Antikythera"
    )
    assert v.label is Label.SUPPORTED


def test_threshold_is_adjustable():
    text = "The device was found near Rhodes."  # device, found, near, rhodes: 3 of 4 overlap
    assert _label(text, threshold=0.9).label is Label.NOT_MENTIONED
    assert _label(text, threshold=0.7).label is Label.SUPPORTED


def test_claim_made_only_of_stopwords_is_not_mentioned():
    assert _label("It was in the.").label is Label.NOT_MENTIONED


def test_baseline_never_predicts_contradicted():
    claims = ["It had 99 gears.", "The device was lost.", "Nothing here matches."]
    assert all(_label(c).label is not Label.CONTRADICTED for c in claims)
