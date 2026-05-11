# Multiple Attachments Support

This document describes the complete implementation of multiple attachment support for the AI Forge Chat application.

## Overview

The application now supports uploading, managing, and processing multiple attachments in a single chat message. All attachments are validated, stored securely, and can be referenced by AI models during conversations.

## Architecture

### Database Schema

**One-to-Many Relationship**: `Message → Attachments`

```
Messages Table
├── id (UUID, PK)
├── thread_id (UUID, FK)
├── role (String: "user" | "assistant")
├── content (Text)
└── created_at (DateTime)

Attachments Table
├── id (UUID, PK)
├── thread_id (UUID, FK)
├── message_id (UUID, FK) ← Can reference ONE message (nullable)
├── file_name (String)
├── mime_type (String)
├── file_path (String)
└── created_at (DateTime)
```

**Key Points:**

- One attachment can belong to at most one message
- Multiple attachments can belong to the same message
- Attachments are associated with threads at upload time
- Attachments are linked to specific messages when chat is sent

### Backend Implementation

#### Configuration (`backend/app/core/config.py`)

New settings added:

```python
max_upload_bytes: int = 15 * 1024 * 1024        # 15MB per file
max_total_upload_bytes: int = 100 * 1024 * 1024 # 100MB total per request
max_files_per_upload: int = 20                   # Max files per upload request
```

#### File Storage Service (`backend/app/services/file_storage_service.py`)

**New Validation Methods:**

```python
def validate_batch_upload(files: list[UploadFile]) -> None
```

- Validates file count doesn't exceed `max_files_per_upload`
- Checks for duplicate filenames in batch
- Raises `FileStorageError` with descriptive messages

```python
async def validate_batch_sizes(files: list[UploadFile]) -> dict[str, int]
```

- Pre-checks total upload size before processing
- Returns file sizes for progress tracking
- Raises `FileSizeLimitExceededError` if total exceeds `max_total_upload_bytes`

**Supported File Types:**

- **Images**: PNG, JPEG, WebP, GIF, BMP, TIFF, SVG, HEIC, HEIF, AVIF
- **Videos**: MP4, WebM, QuickTime, AVI
- **Documents**: PDF, Word, PowerPoint, RTF
- **Data**: CSV, Excel (XLS/XLSX)
- **Code**: Python, JavaScript/TypeScript, JSON, SQL, and others
- **Text**: Plain text, Markdown, HTML, XML

**Security Features:**

1. **Payload Validation**: Blocks executable files (MZ, ELF signatures)
2. **Script Detection**: Rejects shebang scripts disguised as text
3. **Magic Number Detection**: Identifies file type by content, not extension
4. **Size Limits**: Per-file and per-request limits enforced
5. **Filename Sanitization**: Removes dangerous characters, limits length

#### API Routes (`backend/app/api/routes/attachments.py`)

**Upload Endpoint:**

```
POST /api/attachments/upload
```

**Request:**

- Form data with:
  - `thread_id` (UUID)
  - `files` (list[UploadFile]) - Multiple files supported

**Response:**

```json
{
  "attachments": [
    {
      "id": "uuid",
      "thread_id": "uuid",
      "message_id": null,
      "file_name": "example.pdf",
      "mime_type": "application/pdf",
      "file_path": "thread-id/uuid_example.pdf",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

**Error Handling:**

- `400`: Invalid files, unsupported types, safety check failures
- `413`: File size exceeds limits
- `415`: Unsupported media type
- `404`: Thread not found

#### Attachment Service (`backend/app/services/attachment_service.py`)

**Key Methods:**

```python
async def upload_files_for_thread(
    thread_id: UUID,
    user_id: UUID,
    files: list[UploadFile],
) -> list[Attachment]
```

- Handles batch file uploads
- Validates thread ownership
- Returns all saved attachments

```python
async def attach_to_message(
    thread_id: UUID,
    user_id: UUID,
    message_id: UUID,
    attachment_ids: list[UUID],
) -> None
```

- Associates previously uploaded attachments with a message
- Validates user ownership and thread membership

```python
async def get_message_with_attachments(message_id: UUID) -> Message | None
```

- Eager loads all attachments for a message
- Uses `selectinload` for efficient querying

### Frontend Implementation

#### Types (`front-end/src/types/chat.ts`)

**PendingAttachment Interface:**

```typescript
interface PendingAttachment {
  local_id: string; // Unique ID for tracking before upload
  file_name: string;
  mime_type: string;
  file_size: number; // Size in bytes
  progress: number; // 0-100
  status: "uploading" | "uploaded" | "error";
  error?: string; // Error message if failed
  preview_url?: string; // Blob URL for images/videos
  attachment_id?: string; // Server-assigned ID after upload
  local_preview?: string; // Local preview data URL
}
```

#### API Service (`front-end/src/services/chatApi.ts`)

**Batch Upload Function:**

```typescript
export async function uploadAttachmentsBatch(
  threadId: string,
  files: File[],
  onProgressUpdate?: (fileIndex: number, progress: number) => void,
): Promise<Attachment[]>;
```

**Features:**

- Uploads multiple files in single HTTP request
- Per-file progress tracking callback
- Returns array of uploaded attachment metadata
- Handles errors with descriptive messages

**Implementation Details:**

- Uses XMLHttpRequest for progress tracking
- FormData for multipart/form-data encoding
- Supports optional progress callback for each file

#### Components

**AttachmentUploader (`front-end/src/components/AttachmentUploader.tsx`)**

**Features:**

1. **Drag & Drop**: Drop multiple files at once
2. **File Browser**: Select multiple files from system
3. **Local Preview**: Shows image/video thumbnails before upload
4. **Progress Bars**: Per-file progress indicators
5. **Status Badges**: Visual indicators (Uploading, Uploaded, Failed)
6. **File Size Display**: Shows individual and total size
7. **Error Messages**: Displays upload errors per file
8. **Remove Option**: Remove files before sending

**Visual Enhancements:**

- Color-coded status (green for uploaded, red for failed, amber for uploading)
- File size formatting (B, KB, MB, GB)
- Summary counts at the top
- Responsive grid layout (1-2 columns)

**Main App (`front-end/src/App.tsx`)**

**Key Changes:**

1. Batch file upload instead of sequential uploads
2. Frontend size validation before upload (100MB total)
3. Batch error handling with same error for all files
4. Optimistic UI updates for better UX

```typescript
const handleFilesAdded = useCallback(
  async (files: File[]) => {
    // Validate total size
    // Create pending entries for all files
    // Upload all files in batch
    // Update status per-file
    // Handle errors
  },
  [ensureThreadForUpload],
);
```

## Chat Flow with Attachments

### User Perspective

1. **Select Files**: User drags/drops or selects multiple files
2. **Preview**: Attachments show with progress bars
3. **Upload**: Files upload in parallel (single HTTP request)
4. **Compose**: User types message while files upload
5. **Send**: Click "Send" to include uploaded attachments
6. **Display**: Message appears with all attachments

### Data Flow

```
User Uploads Files
    ↓
Frontend validates size, count
    ↓
Batch upload request to backend
    ↓
Backend validates each file
    ↓
Backend stores files in thread directory
    ↓
Backend returns attachment metadata
    ↓
Frontend marks as uploaded
    ↓
User sends chat message
    ↓
Backend links attachments to message
    ↓
Conversation history displays with attachments
```

## Security & Validation

### Frontend Validation

1. **Total Size Check**: Validates before upload
   - Max 100MB total per upload
   - Prevents network waste

2. **File Type Detection**: Shows mime type from File API
   - May differ from actual content
   - Backend performs actual validation

3. **UI Feedback**: Shows errors immediately

### Backend Validation (Primary)

1. **Batch Validation**

   ```python
   # Check file count
   # Check for duplicate names
   # Check total size
   ```

2. **Per-File Validation**

   ```python
   # Size limit (15MB)
   # Content inspection (magic numbers)
   # Type whitelist checking
   # Script/executable detection
   # Filename sanitization
   ```

3. **Access Control**
   ```python
   # User authentication required
   # Thread ownership verification
   # Message access checks
   ```

### Supported Limits

| Limit             | Value     | Configurable             |
| ----------------- | --------- | ------------------------ |
| Per-file size     | 15 MB     | `MAX_UPLOAD_BYTES`       |
| Total per request | 100 MB    | `MAX_TOTAL_UPLOAD_BYTES` |
| Files per request | 20        | `MAX_FILES_PER_UPLOAD`   |
| Filename length   | 120 chars | (sanitized)              |

## Error Handling

### Common Errors

**Frontend:**

- Network error → "Network error during upload."
- Size exceeded → "Total upload size (X MB) exceeds maximum (100 MB)..."
- File type unsupported → From backend response

**Backend:**

- Too many files → "Cannot upload more than 20 files at once..."
- Duplicate names → "Multiple files with the same name detected..."
- File too large → "File exceeds max upload size of 15 MB..."
- Unsafe file → "Executable files are not allowed."
- Unsupported type → "This file type is not supported..."

### Error Recovery

1. **Failed Uploads**: Show error message per file
2. **User Can**:
   - Remove failed files and retry
   - Fix file and re-upload
   - Continue without problematic files

3. **No Automatic Retry**: Prevent infinite loops

## Performance Considerations

### Optimizations

1. **Batch Uploads**: Single HTTP request instead of N requests
   - Reduced overhead
   - Faster for users with latency
   - More efficient network usage

2. **Progress Tracking**: Single progress event for all files
   - Lower CPU usage
   - Smoother UI updates

3. **Lazy Loading**: Attachment previews loaded on demand
   - Faster chat history load
   - Preview only when displayed

4. **Local Preview**: Instant image/video thumbnails
   - No network latency
   - Better UX

### Scalability

- Database: Indexes on `thread_id`, `message_id` for fast queries
- File Storage: Organized by thread ID for efficient directory structure
- Processing: Async file I/O with `anyio`

## Future Enhancements

### Phase 2

1. **Advanced RAG**
   - Generate embeddings for PDFs and documents
   - Store vectors per attachment
   - Multi-file context retrieval
   - Cross-file semantic search

2. **Better Previews**
   - PDF thumbnail generation
   - Document formatting preservation
   - Syntax highlighting for code

3. **File Management**
   - Bulk delete operations
   - Archive old attachments
   - Storage usage tracking

### Phase 3

1. **Collaboration**
   - Share file links with download tracking
   - Granular permission controls

2. **Processing**
   - Automatic OCR for scanned PDFs
   - Video transcription
   - Audio transcription

3. **Integration**
   - Google Drive integration
   - OneDrive integration
   - AWS S3 support for large files

## Testing

### Test Coverage

**Backend:**

- File validation tests (`test_attachment_routes.py`)
- Size limit tests
- File type detection tests
- Security/safety tests
- Database relationship tests

**Frontend:**

- Upload component tests
- Progress tracking tests
- Error handling tests
- Batch upload tests

### Manual Testing Checklist

- [ ] Single file upload
- [ ] Multiple file upload (batch)
- [ ] Large file upload (near limits)
- [ ] File size limit exceeded
- [ ] File count limit exceeded
- [ ] Invalid file types
- [ ] Duplicate filenames
- [ ] Drag & drop multiple files
- [ ] Progress bar updates smoothly
- [ ] Error messages display correctly
- [ ] Remove file before upload
- [ ] Preview shows for images/videos
- [ ] Chat message includes all attachments
- [ ] Attachments appear in chat history

## Environment Configuration

### Backend `.env` Variables

```bash
# File upload settings
UPLOAD_DIR=./uploads                    # Directory for file storage
MAX_UPLOAD_BYTES=15728640              # 15MB per file
MAX_TOTAL_UPLOAD_BYTES=104857600       # 100MB total per request
MAX_FILES_PER_UPLOAD=20                # Max files per upload
```

### Frontend Constants

```typescript
// Frontend validation limits (should match backend)
const MAX_TOTAL_SIZE = 100 * 1024 * 1024; // 100MB
```

## File Organization

### Upload Directory Structure

```
uploads/
├── {thread-id-1}/
│   ├── {uuid}_document.pdf
│   ├── {uuid}_image.jpg
│   └── {uuid}_code.py
├── {thread-id-2}/
│   └── {uuid}_spreadsheet.xlsx
└── ...
```

**Benefits:**

- Easy cleanup by thread
- Prevents filename collisions
- Organized by conversation context

## Troubleshooting

### Issue: Upload fails with "Unsupported file type"

**Causes:**

- File extension not in whitelist
- File content doesn't match declared type
- Corrupted file

**Solution:**

- Verify file is genuine
- Try converting to standard format
- Contact support if file should be allowed

### Issue: Progress bar doesn't update

**Causes:**

- Large files take time to compress
- Network latency
- Browser limiting progress events

**Solution:**

- This is normal for large files
- Check network tab in browser dev tools
- Try with smaller file

### Issue: Batch upload partially fails

**Causes:**

- One or more files invalid
- Total size exceeds limit
- Server-side error

**Solution:**

- Check error messages
- Remove problematic files
- Retry remaining files

---

## API Reference

### Upload Endpoint

```http
POST /api/attachments/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

thread_id: {uuid}
files: File1, File2, File3, ...
```

### Response

```json
{
  "attachments": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "thread_id": "550e8400-e29b-41d4-a716-446655440001",
      "message_id": null,
      "file_name": "document.pdf",
      "mime_type": "application/pdf",
      "file_path": "550e8400-e29b-41d4-a716-446655440001/a1b2c3d4_document.pdf",
      "created_at": "2025-01-01T12:00:00Z"
    },
    ...
  ]
}
```

### Error Responses

```json
{
  "detail": "Cannot upload more than 20 files at once. You tried to upload 25 files."
}
```

Status codes:

- `201`: Success
- `400`: Bad request / validation failed
- `413`: Payload too large
- `415`: Unsupported media type
- `404`: Thread not found

---

**Last Updated**: 2025-01-09
**Version**: 1.0.0
**Status**: Production Ready
