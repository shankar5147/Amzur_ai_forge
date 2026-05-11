# Quick Reference Card

## Multiple Attachments Features

### User Features ✨

**Upload**

- Select 1-20 files at once
- Drag & drop multiple files
- See progress for each file
- Max 100MB total per upload

**Preview**

- See file names and sizes
- Thumbnail preview for images/videos
- Remove files before sending
- Status indicators (Uploading/Uploaded/Failed)

**Send**

- Include files with chat message
- Files automatically attached
- Works with text or just files
- All files in conversation history

### Supported File Types

```
Images:    PNG, JPEG, WebP, GIF, BMP, TIFF, SVG, HEIC, HEIF, AVIF
Videos:    MP4, WebM, MOV, AVI
Docs:      PDF, DOCX, PPTX, RTF
Sheets:    CSV, XLS, XLSX
Code:      Python, JS, TS, SQL, JSON, HTML, CSS, YAML, etc.
Text:      Plain text, Markdown, HTML, XML
```

### Limits

| Limit             | Value     |
| ----------------- | --------- |
| Files per upload  | 20        |
| Per-file size     | 15 MB     |
| Total per request | 100 MB    |
| Filename length   | 120 chars |

## Developer API

### Upload Endpoint

```bash
curl -X POST http://localhost:8000/api/attachments/upload \
  -H "Authorization: Bearer {token}" \
  -F "thread_id={uuid}" \
  -F "files=@document.pdf" \
  -F "files=@image.jpg"
```

### Response

```json
{
  "attachments": [
    {
      "id": "uuid",
      "thread_id": "uuid",
      "message_id": null,
      "file_name": "document.pdf",
      "mime_type": "application/pdf",
      "file_path": "uuid/uuid_document.pdf",
      "created_at": "2025-01-09T12:00:00Z"
    }
  ]
}
```

### Error Codes

- `400` - Invalid files, unsupported type
- `413` - File too large
- `415` - Unsupported media type
- `404` - Thread not found

## Configuration

### Backend (.env)

```bash
MAX_UPLOAD_BYTES=15728640              # 15MB per file
MAX_TOTAL_UPLOAD_BYTES=104857600       # 100MB per batch
MAX_FILES_PER_UPLOAD=20                # Files per upload
```

### Frontend (.env.local)

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## File Structure

```
backend/
├── services/
│   ├── file_storage_service.py     # Validation & storage
│   └── attachment_service.py       # Business logic
└── api/routes/
    └── attachments.py             # Upload endpoints

front-end/src/
├── services/
│   └── chatApi.ts                 # API calls
├── types/
│   └── chat.ts                    # Interfaces
└── components/
    └── AttachmentUploader.tsx      # UI component
```

## Common Tasks

### Upload Multiple Files

```typescript
// Frontend
const files = [file1, file2, file3];
const attachments = await uploadAttachmentsBatch(
  threadId,
  files,
  (fileIndex, progress) => {
    console.log(`File ${fileIndex}: ${progress}%`);
  },
);
```

### Send Chat with Attachments

```typescript
await sendMessage({
  message: "Please review these documents",
  thread_id: threadId,
  attachment_ids: attachments.map((a) => a.id),
});
```

### Get Attachment Preview

```typescript
const preview = await getAttachmentPreview(attachmentId);
// Returns: { columns, rows, content, preview_type }
```

## Security

### What Gets Validated

✅ File type (by content, not extension)  
✅ File size (15MB per file)  
✅ Total batch size (100MB)  
✅ Executable detection  
✅ Filename safety  
✅ User access  
✅ Thread ownership

### What Gets Blocked

🚫 Executable files (.exe, .elf)  
🚫 Shell scripts (bash, powershell)  
🚫 Path traversal attempts  
🚫 Oversized files  
🚫 Unsupported types  
🚫 Unauthorized access

## Troubleshooting

| Problem               | Solution                                 |
| --------------------- | ---------------------------------------- |
| Upload fails          | Check: file type, size, network, auth    |
| File not showing      | Verify: upload complete, try refresh     |
| Slow upload           | Check: file size, internet speed         |
| Type not supported    | Contact support (30+ types supported)    |
| Can't upload 20 files | Batch upload limit reached (per request) |

## Performance

| Operation             | Time       |
| --------------------- | ---------- |
| Upload 1 file (5MB)   | ~2 seconds |
| Upload 5 files (20MB) | ~5 seconds |
| Upload batch request  | ~4 seconds |
| Preview generation    | ~1 second  |

## Endpoints Quick Reference

```
POST   /api/attachments/upload              # Upload files
GET    /api/attachments/thread/{id}         # List attachments
GET    /api/attachments/{id}/preview        # Get preview
POST   /api/chat                            # Send with attachments
GET    /api/chat/history/{id}               # Get chat history
```

## Code Examples

### Backend - Validate Files

```python
from app.services.file_storage_service import FileStorageService

storage = FileStorageService()
storage.validate_batch_upload(files)
await storage.validate_batch_sizes(files)
```

### Backend - Upload Files

```python
from app.services.attachment_service import AttachmentService

service = AttachmentService(db)
attachments = await service.upload_files_for_thread(
    thread_id=thread_id,
    user_id=user_id,
    files=files,
)
```

### Frontend - Track Progress

```typescript
const onProgress = (fileIndex: number, progress: number) => {
  setPendingAttachments((prev) =>
    prev.map((item, i) => (i === fileIndex ? { ...item, progress } : item)),
  );
};
```

### Frontend - Display Attachments

```typescript
{attachments.map(att => (
  <div key={att.id}>
    <img src={getAttachmentUrl(att.file_path)} />
    <p>{att.file_name} ({formatSize(att.file_size)})</p>
  </div>
))}
```

## Monitoring

### Key Metrics

```
Upload Success Rate:     > 99%
Average Upload Time:     < 5 seconds
Failed Uploads:          < 1%
Storage Usage:           < 80% disk
Most Common Types:       PDF, JPEG, DOCX
```

### Debug Commands

```bash
# Check backend logs
docker logs backend

# Browser console (frontend)
Open DevTools → Console

# Network requests
DevTools → Network → search "attachments"

# Database
SELECT COUNT(*) FROM attachments;
SELECT SUM(size) FROM attachment_metadata;
```

## Links to Full Documentation

- 📘 [MULTIPLE_ATTACHMENTS.md](./MULTIPLE_ATTACHMENTS.md) - Full architecture
- 🔒 [SECURITY_ATTACHMENTS.md](./SECURITY_ATTACHMENTS.md) - Security details
- 🤖 [RAG_ENHANCEMENT.md](./RAG_ENHANCEMENT.md) - Future RAG features
- 📖 [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) - Complete guide
- ✅ [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Summary

## Support

| Issue            | Contact                 |
| ---------------- | ----------------------- |
| Bug report       | dev-team@ai-forge.local |
| Feature request  | dev-team@ai-forge.local |
| Security issue   | security@ai-forge.local |
| Production issue | support@ai-forge.local  |

---

**Quick Reference v1.0** | Updated: 2025-01-09
