from __future__ import annotations

import pytest

from digi2pdf import concurrency


def test_recommend_workers_uses_one_worker_for_single_book(monkeypatch) -> None:
    monkeypatch.setattr(concurrency.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(concurrency, "_available_memory_gib", lambda: 16.0)

    recommendation = concurrency.recommend_workers(1)

    assert recommendation.recommended_workers == 1
    assert recommendation.max_workers == 1


def test_recommend_workers_uses_auto_parallel_for_multiple_books(monkeypatch) -> None:
    monkeypatch.setattr(concurrency.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(concurrency, "_available_memory_gib", lambda: 16.0)

    recommendation = concurrency.recommend_workers(10)

    assert recommendation.recommended_workers == 4
    assert recommendation.max_workers == 4


def test_recommend_workers_respects_memory_limit(monkeypatch) -> None:
    monkeypatch.setattr(concurrency.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(concurrency, "_available_memory_gib", lambda: 5.0)

    recommendation = concurrency.recommend_workers(4)

    assert recommendation.recommended_workers == 2


def test_recommend_workers_can_fall_back_to_serial_on_low_memory(monkeypatch) -> None:
    monkeypatch.setattr(concurrency.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(concurrency, "_available_memory_gib", lambda: 2.0)

    recommendation = concurrency.recommend_workers(4)

    assert recommendation.recommended_workers == 1


def test_parse_manual_worker_count_rejects_too_many_sessions() -> None:
    with pytest.raises(ValueError, match="selected books"):
        concurrency.parse_manual_worker_count("3", selected_books=2)


def test_parse_manual_worker_count_rejects_global_safe_limit() -> None:
    with pytest.raises(ValueError, match="safe limit"):
        concurrency.parse_manual_worker_count("5", selected_books=8)
