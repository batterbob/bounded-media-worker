import subprocess
import sys


def test_public_import_does_not_import_optional_parsers() -> None:
    command = "import sys; import bounded_media_worker; assert not {'PIL', 'pypdf', 'pytesseract'} & set(sys.modules)"
    subprocess.run([sys.executable, "-c", command], check=True)
