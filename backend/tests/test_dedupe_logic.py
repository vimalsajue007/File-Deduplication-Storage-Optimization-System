"""Pure duplicate-detection rules (no database)."""
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from app.services.dedupe import calculate_group_stats, find_duplicate_groups, select_original

T0 = datetime(2026, 1, 1, 12, 0, 0)


@dataclass
class F:
    id: int
    uploaded_at: datetime
    name: str = ""
    sha: str = ""
    size: int = 0


def test_original_is_earliest_upload():
    files = [F(3, T0 + timedelta(days=2)), F(1, T0 + timedelta(days=1)), F(2, T0 + timedelta(days=3))]
    assert select_original(files).id == 1


def test_original_tie_broken_by_lowest_id():
    assert select_original([F(9, T0), F(4, T0), F(7, T0)]).id == 4


def test_original_of_empty_group_is_an_error():
    with pytest.raises(ValueError):
        select_original([])


def test_group_stats():
    s = calculate_group_stats(file_size=1000, file_count=4)
    assert (s.total_storage, s.duplicate_count, s.potential_savings) == (4000, 3, 3000)


def test_single_file_has_no_savings():
    assert calculate_group_stats(500, 1).potential_savings == 0


def test_negative_values_rejected():
    with pytest.raises(ValueError):
        calculate_group_stats(-1, 2)


def test_different_names_same_content_are_grouped():
    files = [
        F(1, T0, "invoice.pdf", "aaa", 10),
        F(2, T0, "invoice (copy).pdf", "aaa", 10),
        F(3, T0, "renamed-completely.bin", "aaa", 10),
        F(4, T0, "invoice.pdf", "bbb", 10),   # same name, different content
    ]
    groups = find_duplicate_groups(files, key=lambda f: (f.sha, f.size))
    assert list(groups) == [("aaa", 10)]
    assert {f.id for f in groups[("aaa", 10)]} == {1, 2, 3}


def test_unique_files_form_no_groups():
    files = [F(i, T0, f"f{i}", f"h{i}", 1) for i in range(5)]
    assert find_duplicate_groups(files, key=lambda f: (f.sha, f.size)) == {}


def test_same_hash_different_size_is_not_a_duplicate():
    files = [F(1, T0, "a", "x", 10), F(2, T0, "b", "x", 11)]
    assert find_duplicate_groups(files, key=lambda f: (f.sha, f.size)) == {}
