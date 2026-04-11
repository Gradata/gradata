"""Tests for pub/sub event pipeline."""

from gradata.enhancements.pubsub_pipeline import PubSubPipeline


class TestPubSubPipeline:
    def test_subscribe_and_emit(self):
        pipe = PubSubPipeline()
        received = []
        pipe.subscribe("CORRECTION", lambda d: received.append(d))
        pipe.emit("CORRECTION", {"text": "hello"})
        assert len(received) == 1
        assert received[0]["text"] == "hello"

    def test_multiple_subscribers(self):
        pipe = PubSubPipeline()
        results = []
        pipe.subscribe("X", lambda d: results.append("a"))
        pipe.subscribe("X", lambda d: results.append("b"))
        pipe.emit("X")
        assert results == ["a", "b"]

    def test_stage_failure_doesnt_block(self):
        pipe = PubSubPipeline()
        results = []
        pipe.subscribe("X", lambda d: 1 / 0)  # will raise
        pipe.subscribe("X", lambda d: results.append("ok"))
        pipe.emit("X")
        assert results == ["ok"]

    def test_unsubscribed_event_noop(self):
        pipe = PubSubPipeline()
        results = pipe.emit("UNKNOWN")
        assert results == []

    def test_event_log_tracked(self):
        pipe = PubSubPipeline()
        pipe.emit("A", {"x": 1})
        pipe.emit("B", {"y": 2})
        assert len(pipe.event_log) == 2
        assert pipe.event_log[0]["type"] == "A"

    def test_ordering_preserved(self):
        pipe = PubSubPipeline()
        order = []
        pipe.subscribe("X", lambda d: order.append(1))
        pipe.subscribe("X", lambda d: order.append(2))
        pipe.subscribe("X", lambda d: order.append(3))
        pipe.emit("X")
        assert order == [1, 2, 3]
