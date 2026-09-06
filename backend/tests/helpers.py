from __future__ import annotations


def build_simple_pdf(text: str) -> bytes:
    """Minimal one-page PDF with Helvetica text (valid enough for pypdf)."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET\n"
    content_bytes = content.encode("latin-1", errors="replace")

    def obj(num: int, body: str) -> bytes:
        return f"{num} 0 obj\n{body}\nendobj\n".encode()

    objects = [
        obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(
            3,
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        ),
        b"4 0 obj\n<< /Length %d >>\nstream\n" % len(content_bytes)
        + content_bytes
        + b"\nendstream\nendobj\n",
        obj(5, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]

    header = b"%PDF-1.4\n"
    parts = [header]
    offsets = [0]
    pos = len(header)
    for item in objects:
        offsets.append(pos)
        parts.append(item)
        pos += len(item)

    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n"
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{pos}\n%%EOF\n"
    )
    return b"".join(parts) + xref.encode() + trailer.encode()
