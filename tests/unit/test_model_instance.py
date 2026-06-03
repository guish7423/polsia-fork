"""Tests for model_instance.py — ModelProvider, ModelInstance, ModelManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.model_instance import (
    ChatResult,
    ModelUsageTracker,
    StreamChunk,
    UsageRecord,
    estimate_cost,
)


class TestEstimateCost:
    """Cost estimation for known and unknown models."""

    def test_deepseek_cost(self):
        cost = estimate_cost("deepseek-chat", 1000, 500)
        assert cost > 0

    def test_unknown_model_fallback_cost(self):
        cost = estimate_cost("nonexistent-model", 1000, 500)
        # Unknown models fall back to a default rate
        assert cost >= 0

    def test_zero_tokens_no_cost(self):
        cost = estimate_cost("deepseek-chat", 0, 0)
        assert cost == 0.0

    def test_volc_engine_cost(self):
        cost = estimate_cost("doubao-pro-32k", 2000, 1000)
        assert cost > 0


class TestStreamChunk:
    """StreamChunk dataclass behavior."""

    def test_default_construction(self):
        chunk = StreamChunk(content="hello")
        assert chunk.content == "hello"
        assert chunk.finish_reason is None

    def test_finish_chunk(self):
        chunk = StreamChunk(content="", finish_reason="stop")
        assert chunk.finish_reason == "stop"
        assert chunk.content == ""


class TestChatResult:
    """ChatResult dataclass behavior."""

    def test_default_construction(self):
        result = ChatResult(content="response", model="test-model")
        assert result.content == "response"
        assert result.model == "test-model"
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0

    def test_with_usage(self):
        result = ChatResult(
            content="response",
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.002,
            duration_ms=1500,
        )
        assert result.input_tokens == 100
        assert result.cost_usd == 0.002


class TestUsageRecord:
    """UsageRecord dataclass."""

    def test_minimal_record(self):
        record = UsageRecord(
            provider="openai",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.005,
            duration_ms=500,
            success=True,
            task_category="analysis",
        )
        assert record.provider == "openai"
        assert record.task_category == "analysis"
        assert record.error is None

    def test_with_error(self):
        record = UsageRecord(
            provider="openai",
            model="gpt-4",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            duration_ms=100,
            success=False,
            task_category="analysis",
            error="timeout",
        )
        assert record.success is False
        assert record.error == "timeout"


class TestModelUsageTracker:
    """ModelUsageTracker recording and querying."""

    @pytest.fixture
    def tracker(self):
        return ModelUsageTracker(max_records=100)

    def _make_record(self, model="test-model", tokens=100, cost=0.001, success=True):
        return UsageRecord(
            provider="openai",
            model=model,
            input_tokens=tokens,
            output_tokens=tokens // 2,
            cost_usd=cost,
            duration_ms=200,
            success=success,
            task_category="analysis",
        )

    def test_record_increments_count(self, tracker):
        tracker.record(self._make_record())
        assert len(list(tracker.recent(100))) == 1

    def test_multiple_records(self, tracker):
        tracker.record(self._make_record("model-a", 100, 0.001))
        tracker.record(self._make_record("model-b", 200, 0.002))
        assert len(list(tracker.recent(100))) == 2
        assert tracker.total_cost_usd > 0

    def test_failure_cost_is_zero(self, tracker):
        tracker.record(self._make_record(success=False, cost=0.0))
        assert tracker.total_cost_usd == 0.0

    def test_total_cost_usd(self, tracker):
        tracker.record(self._make_record(cost=0.001))
        tracker.record(self._make_record(cost=0.002))
        assert tracker.total_cost_usd == pytest.approx(0.003, rel=1e-6)

    def test_recent_returns_newest_last(self, tracker):
        for i in range(5):
            tracker.record(self._make_record(f"model-{i}", cost=0.001))
        recent = list(tracker.recent(3))
        assert len(recent) == 3
        assert recent[-1].model == "model-4"  # Newest is last
        assert recent[0].model == "model-2"  # Oldest in window

    def test_ring_buffer_purges_oldest(self, tracker):
        tracker = ModelUsageTracker(max_records=3)
        for i in range(5):
            tracker.record(self._make_record(f"model-{i}", cost=0.001))
        assert len(list(tracker.recent(100))) == 3

    def test_stats_by_model(self, tracker):
        tracker.record(self._make_record("model-a", 100, 0.001))
        tracker.record(self._make_record("model-a", 200, 0.002))
        tracker.record(self._make_record("model-b", 50, 0.0005))
        stats = tracker.stats_by_model()
        # Keys use "provider/model" format
        assert "openai/model-a" in stats
        assert "openai/model-b" in stats
        assert stats["openai/model-a"]["calls"] == 2
