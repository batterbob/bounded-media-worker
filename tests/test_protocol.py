import pytest

from bounded_media_worker.protocol import ProtocolError, decode_frame, encode_frame


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
