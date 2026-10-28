# Private-source provenance

The implementation began after a read-only check of the following files at source revision `425c1f8acc8615b8d243ac763b13006cf005e48b`. This document only records paths and hashes; no private content was transferred.

| Path | SHA-256 |
| --- | --- |
| `lib/pdfparse.py` | `51ea67aeb4d08d499025b404d0b25b53d4045eb5d555ccd518fd018f182135dc` |
| `lib/imagesandbox.py` | `71e5087703f2633269ad1686656734861a9d35df938cc7c5e2dddfa0063a9e07` |
| `lib/photos.py` | `2bbadf0743bd99ba68537284986ee57364753dcfe813ff0acbc708018fc9f6b2` |
| `tests/test_pdfparse.py` | `0d95fc552efbf64f507e4ae50b60d4a9dc38d58f8fc1258879fc3b429a5710e0` |
| `tests/test_pdf_real_parser.py` | `c2140df00289df07650dd231db80520dc8710f07bc64136f5ebc86957f27a6ac` |
| `tests/test_pdf_advisory_corpus.py` | `455d65dbae2b44d296e9afd006dc91cdaec255e13fd1ff383ea1ff2d32039ac6` |
| `tests/test_imagesandbox.py` | `fc041f8b20a070b27be06cca59077104eead072c5e436f80584177f5ab78e264` |

Allowed concepts: bounded input; child-only parser imports; minimal environment; process-group teardown; resource limits; bounded protocol; conservative outcomes; and image header/dimension validation.

Excluded material: names, domains, paths, logging/product terminology, configuration keys, fixtures, comments, error text, and deployment defaults.

Compatibility was independently inventoried as pypdf 6.19.0, Pillow 12.3.0, and pytesseract 0.3.13. This project specifies bounded compatible ranges rather than copying a private requirements file.
