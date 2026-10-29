import pytest

from bounded_media_worker import protocol
from bounded_media_worker.protocol import ProtocolError, _walk, decode_frame, encode_frame


def test_rejects_duplicate_keys() -> None:
    with pytest.raises(ProtocolError):
        decode_frame(b'{"a":1,"a":2}', maximum=100)


def test_rejects_nonfinite_and_trailing_garbage() -> None:
    for raw in (b'{"x":NaN}', b'{"x":1} trailing'):
        with pytest.raises(ProtocolError):
            decode_frame(raw, maximum=100)


def test_round_trip_and_size_bound() -> None:
    assert decode_frame(encode_frame({"text": "h\u00e9"}, maximum=100), maximum=100) == {"text": "h\u00e9"}
    with pytest.raises(ProtocolError):
        encode_frame({"x": "x" * 100}, maximum=10)


def test_deeply_nested_frame_uses_iterative_finite_value_traversal() -> None:
    raw = b'{"nested":' + (b"[" * 2_000) + b"0" + (b"]" * 2_000) + b"}"

    assert decode_frame(raw, maximum=len(raw))["nested"]


def test_recursion_error_during_json_decode_becomes_protocol_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def recursive_parse(*_args: object, **_kwargs: object) -> None:
        raise RecursionError

    monkeypatch.setattr(protocol.json, "loads", recursive_parse)
    with pytest.raises(ProtocolError):
        decode_frame(b'{"safe":true}', maximum=100)


def test_finite_value_walk_handles_deep_python_nesting_iteratively() -> None:
    value: object = float("inf")
    for _ in range(2_000):
        value = [value]

    assert any(item == float("inf") for item in _walk(value))
