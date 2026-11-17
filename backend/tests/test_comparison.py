"""Saved-text comparison preserves technical values and bounds output work."""

from app.comparison import ComparisonCache, MAX_TEXT, compare_text


def test_spacing_and_identical_copies_do_not_report_text_changes():
    assert compare_text("Calidad: 40 N/mm2.", "Calidad: 40 N/mm2.")["classification"] == "unchanged"
    assert compare_text("Calidad:  40 N/mm2.\n", "Calidad: 40 N/mm2.")["classification"] == "spacing_only"
    assert compare_text("M\u00e9xico", "Me\u0301xico")["classification"] == "spacing_only"


def test_numeric_punctuation_and_case_changes_remain_visible():
    for before, after in [("Valor 2.5 kg.", "Valor 2,5 kg."), ("Límite 40 N/mm2.", "Límite 50 N/mm2."),
                          ("Producto A.", "Producto a.")]:
        result = compare_text(before, after)
        assert result["classification"] == "text_changed"
        row = next(row for row in result["rows"] if row["kind"] == "modified")
        assert "".join(mark["text"] for mark in row["before_marks"]) == row["before"]
        assert "".join(mark["text"] for mark in row["after_marks"]) == row["after"]
        assert any(mark["kind"] == "removed" for mark in row["before_marks"])
        assert any(mark["kind"] == "added" for mark in row["after_marks"])


def test_missing_text_is_not_classified_as_an_empty_official_amendment():
    assert compare_text("", "A new saved copy")["classification"] == "unavailable"


def test_large_or_fragmented_documents_return_a_clear_bounded_result():
    result = compare_text("A" * (MAX_TEXT + 1), "B")
    assert result["classification"] == "too_large" and result["rows"] == ()
    result = compare_text("A. " * 4000, "B. " * 4000)
    assert result["classification"] == "too_large"


def test_word_highlighting_remains_bounded_without_dropping_saved_text():
    before = "A " * 400
    after = "B " * 400
    result = compare_text(before, after)
    assert result["classification"] == "text_changed"
    row = result["rows"][0]
    assert len(row["before_marks"]) + len(row["after_marks"]) <= 160
    assert "".join(mark["text"] for mark in row["before_marks"]) == before.strip()
    assert "".join(mark["text"] for mark in row["after_marks"]) == after.strip()


def test_comparison_cache_is_bounded_and_scoped_to_the_database():
    cache = ComparisonCache()
    first_database, second_database = object(), object()
    cache.put((first_database, 1, 2), {"classification": "unchanged"})
    assert cache.get((second_database, 1, 2)) is None
    cache.put((first_database, 2, 3), {"classification": "text_changed"})
    cache.put((first_database, 3, 4), {"classification": "spacing_only"})
    assert cache.get((first_database, 1, 2)) is None
    assert cache.get((first_database, 3, 4))["classification"] == "spacing_only"
