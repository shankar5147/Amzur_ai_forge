# Implementation & Usage Guide

## Quick Start

### For Users

1. **Select Files**
   - Click "Attach" button or drag & drop files
   - Select multiple files at once
   - Up to 20 files, 100MB total

2. **Review Before Sending**
   - See file names, sizes, and thumbnails
   - Progress bars show upload status
   - Remove files if needed

3. **Send Message**
   - All files upload in parallel
   - Type your message
   - Click "Send" when ready
   - Files included in conversation

### For Developers

#### Backend Setup

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Update config (optional)
# Edit backend/.env:
MAX_FILES_PER_UPLOAD=20
MAX_TOTAL_UPLOAD_BYTES=104857600

# 3. Run server
python -m uvicorn app.main:app --reload
```

#### Frontend Setup

```bash
# 1. Install dependencies
cd front-end
npm install

# 2. Run dev server
npm run dev
```

#### Testing

```bash
# Backend tests
cd backend
pytest tests/test_attachment_routes.py -v
pytest tests/test_auth_service.py -v

# Frontend tests
cd front-end
npm test
```

## File Structure

### Backend

```
backend/
├── app/
│   ├── api/routes/
│   │   └── attachments.py          # Upload, preview, list endpoints
│   ├── services/
│   │   ├── attachment_service.py   # Business logic
│   │   ├── file_storage_service.py # File validation & storage
│   │   └── attachment_ai_service.py # Context building
│   ├── models/
│   │   ├── db_models.py            # Message, Attachment, Thread models
│   │   └── schemas.py              # Request/response schemas
│   └── core/
│       └── config.py               # Configuration
└── uploads/                        # User uploaded files
    └── {thread-id}/
        └── {uuid}_{filename}
```

### Frontend

```
front-end/src/
├── components/
│   ├── AttachmentUploader.tsx       # Multi-file upload UI
│   ├── ChatComposer.tsx             # Chat input form
│   └── ChatMessageList.tsx          # Display messages with attachments
├── services/
│   └── chatApi.ts                   # API calls
├── types/
│   └── chat.ts                      # TypeScript interfaces
└── App.tsx                          # Main component
```

## API Reference

### Upload Attachments

```http
POST /api/attachments/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

Form Data:
- thread_id: {uuid}
- files: File1, File2, ...
```

**Success (201):**

```json
{
  "attachments": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "thread_id": "550e8400-e29b-41d4-a716-446655440001",
      "message_id": null,
      "file_name": "document.pdf",
      "mime_type": "application/pdf",
      "file_path": "550e8400-e29b-41d4-a716-446655440001/abc123_document.pdf",
      "created_at": "2025-01-09T12:00:00Z"
    }
  ]
}
```

**Errors:**

- `400`: Invalid files, duplicates, unsupported type
- `413`: Size limit exceeded
- `415`: Unsupported media type
- `404`: Thread not found

### Get Attachment Preview

```http
GET /api/attachments/{attachment_id}/preview
Authorization: Bearer {token}
```

**Response (200):**

```json
{
  "attachment_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "data.csv",
  "mime_type": "text/csv",
  "preview_type": "table",
  "columns": ["Name", "Age", "Email"],
  "rows": [
    ["Alice", "30", "alice@example.com"],
    ["Bob", "25", "bob@example.com"]
  ],
  "truncated": false
}
```

### List Thread Attachments

```http
GET /api/attachments/thread/{thread_id}
Authorization: Bearer {token}
```

**Response:**

```json
{
  "attachments": [
    { ... },
    { ... }
  ]
}
```

### Send Chat Message with Attachments

```http
POST /api/chat
Content-Type: application/json
Authorization: Bearer {token}

{
  "message": "Please analyze these documents",
  "thread_id": "550e8400-e29b-41d4-a716-446655440001",
  "attachment_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

## Configuration

### Backend Environment Variables

```bash
# File Upload Settings
UPLOAD_DIR=./uploads
MAX_UPLOAD_BYTES=15728640              # 15MB per file
MAX_TOTAL_UPLOAD_BYTES=104857600       # 100MB total
MAX_FILES_PER_UPLOAD=20                # Files per upload
MAX_ATTACHMENT_CONTEXT_ITEMS=5         # Items in chat context

# Database
DATABASE_URL=postgresql+asyncpg://...

# JWT
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# CORS
FRONTEND_ORIGINS=http://localhost:5173
```

### Frontend Environment Variables

Create `.env.local`:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Limits & Constraints

| Limit                  | Value      | Reason                 |
| ---------------------- | ---------- | ---------------------- |
| Per-file size          | 15 MB      | Memory/processing      |
| Total per upload       | 100 MB     | Server resources       |
| Files per upload       | 20         | Database efficiency    |
| Files per message      | Unlimited  | (via multiple uploads) |
| Total files per thread | Unlimited  | (cleaned by retention) |
| Filename length        | 120 chars  | Database constraints   |
| Supported formats      | 30+ types  | See file type table    |
| Preview size           | 72 rows    | UI performance         |
| Storage location       | `/uploads` | Configurable           |

## Troubleshooting

### Issue: "Upload failed"

**Causes & Solutions:**

- Network error → Check connection
- Server down → Check backend service
- Auth token expired → Refresh login
- Thread not found → Try another thread

**Debug:**

```bash
# Check backend logs
docker logs backend

# Check network requests
# Open browser DevTools → Network tab → look for POST /api/attachments/upload
```

### Issue: "File type not supported"

**Solution:**
Files are validated by content, not extension. Supported types:

- Images: PNG, JPEG, WebP, GIF, BMP, TIFF, SVG, HEIC, HEIF, AVIF
- Videos: MP4, WebM, MOV, AVI
- Documents: PDF, DOCX, PPTX, XLS, XLSX, RTF
- Text: TXT, MD, JSON, CSV, HTML, XML
- Code: Python, JavaScript, TypeScript, SQL, etc.

If your file type should be supported, contact support.

### Issue: "File exceeds max upload size"

**Solution:**

- Per-file limit: 15MB max per file
- Total limit: 100MB max per upload request
- Solution: Upload in smaller batches, compress files

### Issue: "Multiple files with the same name"

**Solution:**
Rename files to be unique before uploading.

- `document.pdf` → `document_v1.pdf`
- `image.jpg` → `image_full.jpg` (instead of `image_thumb.jpg`)

### Issue: Attachments not showing in chat

**Debug Steps:**

1. Check upload completed (green status)
2. Verify chat sent (click Send)
3. Check message history (refresh page)
4. Check browser console for errors

## Best Practices

### For Users

1. **Organize Files**: Use descriptive names
2. **Check Size**: Large files take longer
3. **Monitor Upload**: Watch progress bars
4. **Send Message**: Don't close tab during upload
5. **Review After**: Check message includes files

### For Developers

1. **Handle Errors**: Show user-friendly messages
2. **Test Uploads**: Use variety of file types
3. **Monitor Logs**: Track upload activity
4. **Backup Files**: Regular filesystem backups
5. **Clean Storage**: Implement retention policies
6. **Monitor Disk**: Alert on high usage

### For Admins

1. **Set Quotas**: Define user storage limits
2. **Monitor Performance**: Track upload metrics
3. **Review Logs**: Audit file access
4. **Backup Strategy**: Regular incremental backups
5. **Security**: Regular security audits
6. **Retention**: Define cleanup policies

## Performance Tips

### Frontend

1. **Batch Upload**: Multiple files in one request
2. **Local Preview**: Show before upload
3. **Optimistic UI**: Update before confirmation
4. **Compression**: Compress large files locally
5. **Chunking**: Consider chunked upload for huge files (future)

### Backend

1. **Async I/O**: Non-blocking file operations
2. **Streaming**: Stream files during upload
3. **Indexing**: Database indexes on common queries
4. **Caching**: Cache metadata temporarily
5. **Queue**: Background processing for heavy files

### Database

1. **Connection Pool**: Reuse connections
2. **Batch Inserts**: Insert multiple records together
3. **Indexes**: On thread_id, message_id, attachment_id
4. **Partitioning**: By created_at if table grows large
5. **Archiving**: Move old files to cold storage

## Monitoring & Metrics

### Key Metrics

```python
# Track these for optimization
- Upload success rate %
- Average upload time (seconds)
- Average file size (MB)
- Peak concurrent uploads
- Storage usage (GB)
- Most common file types
- Failed upload reasons
```

### Example Monitoring

```python
# Add to attachment service
logger.info(
    f"Upload: user={user_id}, "
    f"files={len(files)}, "
    f"total_size={total_size}MB, "
    f"duration={elapsed}s"
)

logger.error(
    f"Upload failed: {reason}",
    extra={
        "user_id": user_id,
        "file_count": len(files),
        "attachment_ids": attachment_ids,
    }
)
```

## Maintenance Tasks

### Daily

- Monitor disk space
- Check for upload errors in logs
- Verify backup completion

### Weekly

- Analyze performance metrics
- Review failed uploads
- Check for security issues

### Monthly

- Archive old uploads
- Update virus definitions (if using scan)
- Review storage usage
- Performance optimization

### Quarterly

- Security audit
- Capacity planning
- Compliance check
- Feature assessment

## Upgrade Path

### From Single to Multiple Attachments

If upgrading from previous version:

1. **No Database Migration Needed**
   - Schema already supports multiple attachments
   - Messages.attachments is already a list

2. **Code Updates**
   - Update frontend batch upload
   - Enable batch validation
   - Add new endpoints

3. **Testing**
   - Test existing attachments load
   - Test new batch uploads
   - Test error scenarios

### Backward Compatibility

✅ All changes are backward compatible:

- Old single-file uploads still work
- Old message/attachment structure unchanged
- Old API endpoints still functional

## Documentation

### For End Users

- See [User Guide](./USER_GUIDE.md)
- View [FAQ](./FAQ.md)

### For Developers

- See [MULTIPLE_ATTACHMENTS.md](./MULTIPLE_ATTACHMENTS.md) - Architecture
- See [SECURITY_ATTACHMENTS.md](./SECURITY_ATTACHMENTS.md) - Security
- See [RAG_ENHANCEMENT.md](./RAG_ENHANCEMENT.md) - Future RAG

### For DevOps

- See [DEPLOYMENT.md](./DEPLOYMENT.md) - Production setup
- See [MONITORING.md](./MONITORING.md) - Observability

## Support & Contributing

### Report Issues

```bash
# Check existing issues
git issues -L attachment upload

# Report new issue
git issues new --title "Attachment upload issue"
```

### Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Add tests
5. Create pull request

### Contact

- Development: dev-team@ai-forge.local
- Support: support@ai-forge.local
- Security: security@ai-forge.local

---

**Version**: 1.0.0
**Last Updated**: 2025-01-09
**Maintained By**: Development Team
