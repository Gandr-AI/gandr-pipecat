"""Unit tests for transcript splitting.

These import ``pipecat_gandr._text`` directly, which pulls in neither Pipecat
nor a network, so they run on a bare interpreter.
"""

import pytest

from pipecat_gandr._text import MAX_REQUEST_CHARS, split_for_request


def test_empty_input_yields_nothing():
    assert split_for_request("") == []
    assert split_for_request("   \n\t ") == []


def test_short_text_passes_through_stripped():
    assert split_for_request("Hello there.") == ["Hello there."]
    assert split_for_request("  Hello there.  ") == ["Hello there."]


def test_text_at_the_limit_is_not_split():
    text = "a" * MAX_REQUEST_CHARS
    assert split_for_request(text) == [text]


def test_every_piece_respects_the_limit():
    text = ("Sentence number one is here. " * 200).strip()
    pieces = split_for_request(text)
    assert len(pieces) > 1
    assert all(len(piece) <= MAX_REQUEST_CHARS for piece in pieces)


def test_split_is_lossless_ignoring_seam_whitespace():
    text = ("Sentence number one is here. " * 200).strip()
    pieces = split_for_request(text)
    joined = "".join(piece.replace(" ", "") for piece in pieces)
    assert joined == text.replace(" ", "")


def test_prefers_a_sentence_boundary_over_a_later_word_boundary():
    # The window is "A big one. Two thr". The sentence end is at 10 and the
    # last word boundary is at 14, so the two rules disagree and only the
    # sentence rule can produce this result.
    text = "A big one. Two three"
    pieces = split_for_request(text, limit=18)
    assert pieces[0] == "A big one."
    assert pieces[1] == "Two three"


def test_falls_back_to_a_word_boundary():
    # No sentence end anywhere, and the limit lands strictly inside "charlie",
    # so a hard cut at the limit would produce "alpha bravo ch".
    text = "alpha bravo charlie delta"
    pieces = split_for_request(text, limit=14)
    assert pieces == ["alpha bravo", "charlie delta"]


def test_never_cuts_mid_word_at_scale():
    # A seven-character cycle, so the limit does not land on a space and a
    # hard cut would slice a token in half.
    text = ("wordss " * 900).strip()
    assert MAX_REQUEST_CHARS % 7 != 0
    pieces = split_for_request(text)
    assert len(pieces) > 1
    assert all(len(piece) <= MAX_REQUEST_CHARS for piece in pieces)
    assert " ".join(pieces) == text
    # No piece may end mid-word.
    assert all(piece.endswith("wordss") for piece in pieces)


def test_cuts_inside_a_token_only_when_it_must():
    token = "a" * (MAX_REQUEST_CHARS * 2 + 500)
    pieces = split_for_request(token)
    assert all(len(piece) <= MAX_REQUEST_CHARS for piece in pieces)
    assert "".join(pieces) == token


def test_question_and_exclamation_are_sentence_boundaries():
    # Both windows contain a later word boundary than the sentence end, so a
    # word-boundary-only implementation gives a different first piece.
    assert split_for_request("Is it? Yes it", limit=12)[0] == "Is it?"
    assert split_for_request("Stop! Go now", limit=11)[0] == "Stop!"


def test_non_positive_limit_is_rejected():
    with pytest.raises(ValueError):
        split_for_request("anything", limit=0)
    with pytest.raises(ValueError):
        split_for_request("anything", limit=-5)
