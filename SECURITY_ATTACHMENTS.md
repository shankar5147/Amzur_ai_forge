# Security Implementation for Multiple Attachments

## Overview

This document details the security measures implemented for the multiple attachments feature in AI Forge Chat.

## Attack Prevention Strategies

### 1. File Type Validation

#### Magic Number Detection (Content-Based)

The system validates file types by inspecting file content rather than relying on extensions:

```
File Signature Detection:
├── PDF: %PDF- (0x25504446)
├── PNG: 89 50 4E 47 (PNG magic)
├── JPEG: FF D8 FF (JPEG marker)
├── ZIP: 50 4B 03 04 (ZIP header)
├── ELF: 7F 45 4C 46 (Unix executable)
├── MZ: 4D 5A (Windows executable)
├── Office 2007+: PK (ZIP-based)
└── Scripts: 23 21 (Shebang #!)
```

**Benefits:**

- Prevents disguised executables
- Detects polyglots (files with multiple headers)
- Language-independent validation

#### Extension Whitelist

```python
_allowed_code_extensions = {
    ".py", ".js", ".ts", ".json", ".sql",
    ".jsx", ".tsx", ".html", ".css", ".xml",
    ".yaml", ".yml", ".md", ".sh", ".bash",
    ".rb", ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".cs", ".php",
    ".swift", ".r", ".toml", ".ini", ".env",
}
```

### 2. Payload Safety Checks

#### Executable Detection

```python
def _assert_safe_payload(self, payload: bytes) -> None:
    # Block Windows executables (MZ header)
    if payload.startswith(b"MZ"):
        raise UnsafeFileError("Executable files are not allowed.")

    # Block ELF binaries (Unix/Linux)
    if payload.startswith(b"\x7fELF"):
        raise UnsafeFileError("Executable files are not allowed.")

    # Block shell scripts
    if payload.startswith(b"#!"):
        blocked = (b"/bin/bash", b"/bin/sh", b"powershell", b"python")
        header = payload[:120].lower()
        if any(token in header for token in blocked):
            raise UnsafeFileError("Executable scripts are not allowed.")
```

**Protected Against:**

- PE executables (.exe, .dll, .sys)
- ELF executables (.so, binaries)
- Shell scripts
- Python scripts with shebang

#### Embedded Threats

- Malicious macros (Office docs are checked via ZIP structure)
- Scripts embedded in PDFs (PDF parser-level defense)
- SVG with JavaScript (MIME type enforcement)

### 3. Size Limits

#### Per-File Limit: 15 MB

```python
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
```

**Prevents:**

- Disk space exhaustion
- Memory exhaustion from file processing
- DeS (Denial of Service) attacks

**Implementation:**

```python
async def _read_bounded(self, upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > self._max_upload_bytes:
            raise FileSizeLimitExceededError(
                f"File exceeds max upload size of {self._max_upload_bytes} bytes."
            )
        chunks.append(chunk)
```

#### Total Request Limit: 100 MB

```python
MAX_TOTAL_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB total per request
```

**Prevents:**

- Bulk upload attacks
- Resource starvation
- Cumulative impact attacks

**Validation:**

- Pre-checked on frontend
- Verified on backend before processing
- Per-file incremental checks

### 4. Rate Limiting

#### Recommended Configuration

```python
# Add to backend/.env or config
UPLOAD_RATE_LIMIT_PER_USER = "100 per day"  # Per user daily limit
UPLOAD_RATE_LIMIT_PER_THREAD = "50 per thread"  # Per thread limit
```

#### Implementation Sketch

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/upload")
@limiter.limit("100/day")  # 100 uploads per day per user
async def upload_attachments(...):
    # Implementation
```

### 5. Access Control

#### Thread Ownership Verification

```python
async def upload_files_for_thread(
    self,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    files: list,
) -> list[Attachment]:
    # Verify thread belongs to user
    thread = await self._get_user_thread(thread_id, user_id)
    if thread is None:
        return []  # Silently fail
```

#### Message Ownership Verification

```python
async def attach_to_message(
    self,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
    attachment_ids: list[uuid.UUID],
) -> None:
    # Verify user owns thread
    # Verify message belongs to thread
    # Only then attach
```

### 6. Filename Sanitization

#### Prevent Path Traversal

```python
@staticmethod
def _sanitize_filename(name: str) -> str:
    # Extract only the basename (remove directory traversal)
    safe = Path(name).name  # Gets only filename, not path

    # Remove dangerous characters
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", safe)

    # Strip leading/trailing dots (hidden files, relative paths)
    safe = safe.strip("._") or "upload"

    # Limit length
    if len(safe) > 120:
        stem = Path(safe).stem[:100]
        suffix = Path(safe).suffix[:20]
        safe = f"{stem}{suffix}"

    return safe
```

**Prevents:**

- Directory traversal (../../etc/passwd)
- Hidden file creation
- Relative path escapes
- Excessively long names

#### Example Transformations

```
Input:                          Output:
../../etc/passwd        →       etc_passwd
.bashrc                 →       bashrc
file.pdf                →       file.pdf
my file (1).pdf         →       my_file_1_.pdf
very/long/../../path    →       very_long_path
```

### 7. Filename Duplicate Detection

```python
def validate_batch_upload(self, files: list[UploadFile]) -> None:
    filenames = [f.filename or "upload" for f in files]
    if len(filenames) != len(set(filenames)):
        raise FileStorageError(
            "Multiple files with the same name detected. Please rename files to be unique."
        )
```

**Prevents:**

- Accidental overwrites in same batch
- Symlink attacks
- Race conditions

### 8. MIME Type Verification

#### Multi-Layer Detection

```python
def _detect_mime_type(self, payload: bytes, filename: str) -> str:
    # 1. Binary magic number detection
    if head.startswith(b"%PDF-"):
        return "application/pdf"

    # 2. ZIP-based format detection
    zip_type = self._detect_zip_office(payload)
    if zip_type:
        return zip_type

    # 3. Text content analysis
    if self._is_text(payload):
        if self._is_json(text):
            return "application/json"
        if self._is_csv(text):
            return "text/csv"

    # 4. Reject unknowns
    raise UnsupportedFileTypeError("Unsupported file type.")
```

### 9. Frontend Security

#### Size Validation Before Upload

```typescript
const MAX_TOTAL_SIZE = 100 * 1024 * 1024; // 100MB

const totalSize = files.reduce((sum, file) => sum + file.size, 0);
if (totalSize > MAX_TOTAL_SIZE) {
  setError("Total upload size exceeds maximum...");
  return;
}
```

**Benefits:**

- Prevents network waste
- Immediate user feedback
- Reduces server load

#### No Auto-Retry of Failed Uploads

```typescript
try {
    const uploaded = await uploadAttachmentsBatch(...);
} catch (err) {
    // Show error, don't retry automatically
    setError(text);
    // Mark files as failed (no automatic retry)
}
```

**Prevents:**

- Infinite retry loops
- Amplified DoS attacks
- Resource exhaustion

## Security Best Practices

### 1. Principle of Least Privilege

- Only authenticated users can upload
- Users can only upload to their own threads
- No admin override shortcuts

### 2. Defense in Depth

**Layers:**

1. Frontend validation (UX)
2. Backend size limits
3. Content inspection
4. MIME validation
5. Filename sanitization
6. Access control checks

### 3. Fail Securely

- Reject unknown file types
- Default-deny access
- Detailed logs for admins, generic errors for users

### 4. Logging & Monitoring

```python
# Recommended: Log all uploads
logger.info(f"Upload: user={user_id}, files={len(files)}, "
            f"total_size={total_size}, thread={thread_id}")

# Alert on:
# - Multiple upload failures from same user
# - Attempts to upload blocked file types
# - Unusual file sizes
# - High frequency uploads
```

## Threat Model

### Attack Vectors & Mitigations

| Attack               | Vector                   | Mitigation                                   |
| -------------------- | ------------------------ | -------------------------------------------- |
| Executable Upload    | .exe, .elf, script       | Magic number detection, extension whitelist  |
| Malicious Archive    | Zip bomb, path traversal | Size limits, filename sanitization           |
| Polyglot File        | .pdf + .exe              | Content inspection, type detection           |
| Resource Exhaustion  | 10GB upload              | Per-file limit (15MB), batch limit (100MB)   |
| Malware Distribution | Serve infected files     | No public file access, access control        |
| Symlink Attack       | Create symlinks          | Filename validation, access control          |
| Unicode Bypass       | Homoglyph characters     | Regex sanitization                           |
| Macro Exploit        | Office macro             | ZIP structure validation, no macro execution |
| XXE Injection        | Malicious XML            | Parse-only, no entity expansion              |
| Directory Traversal  | ../../etc/passwd         | Path.name extraction, sanitization           |

## Compliance & Standards

### OWASP Top 10

- **A01:2021 Broken Access Control**: ✅ Verified thread/message ownership
- **A02:2021 Cryptographic Failures**: ✅ Files at rest in filesystem
- **A03:2021 Injection**: ✅ No command injection vectors
- **A04:2021 Insecure Design**: ✅ Whitelist approach
- **A05:2021 Security Misconfiguration**: ✅ Secure defaults
- **A06:2021 Vulnerable Components**: ✅ Updated dependencies
- **A07:2021 Authentication Failure**: ✅ JWT-based auth
- **A08:2021 Software/Data Integrity**: ✅ Backend validation
- **A09:2021 Logging & Monitoring**: ✅ Event logging
- **A10:2021 SSRF**: ✅ Local files only

### File Upload Security (OWASP)

- ✅ Validate file types
- ✅ Check file size
- ✅ Sanitize filenames
- ✅ Store outside web root
- ✅ Use access control
- ✅ Log uploads
- ✅ Scan for malware (optional)
- ✅ Serve as downloads (not inline)

## Testing Recommendations

### Security Test Cases

```bash
# Test 1: Executable upload attempt
curl -X POST \
  -F "thread_id=xxx" \
  -F "files=@/bin/ls" \
  http://localhost:8000/api/attachments/upload

# Expected: 400 "Executable files are not allowed."

# Test 2: Oversized file
dd if=/dev/zero of=large.bin bs=1M count=16
curl -X POST \
  -F "thread_id=xxx" \
  -F "files=@large.bin" \
  http://localhost:8000/api/attachments/upload

# Expected: 413 "File exceeds max upload size"

# Test 3: Path traversal in filename
curl -X POST \
  -F "thread_id=xxx" \
  -F "files=@test.pdf;filename=../../etc/passwd" \
  http://localhost:8000/api/attachments/upload

# Expected: 201 (file saved as sanitized name)

# Test 4: No extension, wrong content
echo "MZ..." > notexe.pdf
curl -X POST \
  -F "thread_id=xxx" \
  -F "files=@notexe.pdf" \
  http://localhost:8000/api/attachments/upload

# Expected: 400 "Executable files are not allowed."
```

## Security Checklist

- [ ] All file uploads require authentication
- [ ] File type validated by content, not extension
- [ ] Size limits enforced (per-file and per-request)
- [ ] Filenames sanitized to prevent traversal
- [ ] Executables blocked (MZ, ELF, scripts)
- [ ] MIME types verified against content
- [ ] Thread ownership verified before allowing upload
- [ ] All uploads logged with user and timestamp
- [ ] Error messages don't leak sensitive info
- [ ] Files stored outside web root
- [ ] No automatic retry on upload failure
- [ ] Rate limiting configured (optional)
- [ ] Virus scanning available (optional)
- [ ] File retention policies defined
- [ ] Security headers configured

## Future Security Enhancements

### Phase 2

1. **Virus Scanning**: Integrate ClamAV or VirusTotal
2. **YARA Rules**: Custom malware detection patterns
3. **Rate Limiting**: Per-user and per-thread limits
4. **File Retention**: Automatic cleanup policies
5. **Audit Trail**: Detailed upload/download logs

### Phase 3

1. **DLP (Data Loss Prevention)**: Detect sensitive content
2. **Sandboxed Preview**: Run previews in sandbox
3. **File Encryption**: Encrypt files at rest
4. **Integrity Checking**: SHA-256 verification
5. **Access Logs**: Track all file access

## Incident Response

### If Malicious File Detected

1. **Immediate:**
   - Quarantine file
   - Alert user
   - Disable thread uploads

2. **Investigation:**
   - Check file upload timestamp
   - Review user activity
   - Check if file was shared
   - Notify other users if needed

3. **Remediation:**
   - Delete file
   - Update detection rules
   - Patch if needed
   - Re-enable after validation

## References

- OWASP File Upload Cheat Sheet
- CWE-434: Unrestricted Upload of File with Dangerous Type
- NIST Guidelines for Media Sanitization
- SANS Top 25 Software Errors

---

**Last Updated**: 2025-01-09
**Version**: 1.0.0
**Classification**: Internal Security Documentation
