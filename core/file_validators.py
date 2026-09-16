"""
VVITU Portal — File Upload Security & Integrity Validators
Protects against unrestricted file uploads, MIME spoofing, stored XSS, and storage exhaustion.
"""

import os
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename

ALLOWED_DOC_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}

# File signatures (magic bytes)
SIGNATURES = {
    '.pdf':  [b'%PDF-'],
    '.jpg':  [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png':  [b'\x89PNG\r\n\x1a\n'],
}


def validate_document_upload(uploaded_file, allowed_extensions=None, max_size_mb=5):
    """
    Validates an uploaded file:
    1. Ensures a file was actually provided and is not empty.
    2. Enforces maximum file size limit in megabytes.
    3. Checks extension against strict whitelist (blocking HTML, SVG, scripts, executables).
    4. Inspects binary magic bytes / file signature to prevent MIME spoofing.
    5. Returns sanitized filename.
    """
    if not uploaded_file:
        return None

    if allowed_extensions is None:
        allowed_extensions = ALLOWED_DOC_EXTENSIONS
    else:
        allowed_extensions = {ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in allowed_extensions}

    # 1. Size check
    max_size_bytes = max_size_mb * 1024 * 1024
    if uploaded_file.size > max_size_bytes:
        raise ValidationError(f"File size ({uploaded_file.size / (1024*1024):.1f} MB) exceeds maximum allowed limit of {max_size_mb} MB.")

    if uploaded_file.size == 0:
        raise ValidationError("Uploaded file is empty (0 bytes).")

    # 2. Extension check
    orig_name = uploaded_file.name or ''
    _, ext = os.path.splitext(orig_name)
    ext = ext.lower()

    if ext not in allowed_extensions:
        allowed_str = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"Invalid file extension '{ext}'. Only {allowed_str} documents are permitted.")

    # 3. Magic Bytes / Header Signature Verification
    expected_signatures = SIGNATURES.get(ext)
    if expected_signatures:
        current_pos = uploaded_file.tell() if hasattr(uploaded_file, 'tell') else 0
        uploaded_file.seek(0)
        header = uploaded_file.read(16)
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(current_pos)

        matched = any(header.startswith(sig) for sig in expected_signatures)
        if not matched:
            raise ValidationError(
                f"File content does not match its '{ext}' extension. Uploading disguised or malicious files is prohibited."
            )

    # 4. Return sanitized filename
    sanitized = get_valid_filename(orig_name)
    return sanitized
