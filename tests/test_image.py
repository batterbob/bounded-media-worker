import struct
from collections.abc import Iterable

from bounded_media_worker import Outcome, WorkerPolicy, canonicalize_image, ocr_image


def png_header(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def png_chunk_types(data: bytes) -> Iterable[bytes]:
    position = 8
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        yield data[position + 4:position + 8]
        position += 12 + length


def test_extreme_header_is_rejected_before_decoder_import() -> None:
    result = canonicalize_image(png_header(100_000, 1), policy=WorkerPolicy())
    assert result.outcome is Outcome.OUTPUT_LIMIT


def test_invalid_image_is_a_safe_result() -> None:
    result = ocr_image(b"not image", policy=WorkerPolicy())
    assert result.outcome is Outcome.INVALID_INPUT


def test_generated_image_canonicalizes_to_png() -> None:
    import io

    from PIL import Image, PngImagePlugin

    source = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "metadata")
    Image.new("RGBA", (4, 4), "red").save(source, "PNG", pnginfo=metadata, icc_profile=b"profile")
    result = canonicalize_image(source.getvalue(), policy=WorkerPolicy())
    assert result.outcome is Outcome.SUCCESS
    assert result.media_type == "image/png"
    assert result.data is not None and result.data.startswith(b"\x89PNG")
    canonical = Image.open(io.BytesIO(result.data))
    assert canonical.mode == "RGB"
    assert not canonical.getexif()
    assert "private" not in canonical.info
    assert "icc_profile" not in canonical.info
    assert set(png_chunk_types(result.data)) <= {b"IHDR", b"IDAT", b"IEND"}
