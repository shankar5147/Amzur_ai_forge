import { useRef, useState } from "react";

import type { PendingAttachment } from "../types/chat";

interface AttachmentUploaderProps {
  disabled: boolean;
  attachments: PendingAttachment[];
  onFilesAdded: (files: File[]) => void;
  onRemoveAttachment: (localId: string) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function getStatusColor(status: PendingAttachment["status"]): string {
  switch (status) {
    case "uploaded":
      return "bg-green-500";
    case "error":
      return "bg-red-500";
    case "uploading":
      return "bg-(--clay)";
    default:
      return "bg-(--clay)";
  }
}

function getStatusText(status: PendingAttachment["status"]): string {
  switch (status) {
    case "uploaded":
      return "Uploaded";
    case "error":
      return "Failed";
    case "uploading":
      return "Uploading";
    default:
      return "Pending";
  }
}

export function AttachmentUploader({
  disabled,
  attachments,
  onFilesAdded,
  onRemoveAttachment,
}: AttachmentUploaderProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0 || disabled) {
      return;
    }
    onFilesAdded(Array.from(fileList));
  };

  const totalSize = attachments.reduce((sum, item) => sum + item.file_size, 0);
  const uploadedCount = attachments.filter(
    (item) => item.status === "uploaded",
  ).length;
  const failedCount = attachments.filter(
    (item) => item.status === "error",
  ).length;

  return (
    <div className="space-y-2">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) {
            setDragActive(true);
          }
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          handleFiles(event.dataTransfer.files);
        }}
        className={`rounded-xl border border-dashed px-3 py-2 text-xs transition sm:text-sm ${
          dragActive
            ? "border-(--clay) bg-(--mist)"
            : "border-black/20 bg-white/60"
        } ${disabled ? "opacity-60" : ""}`}
      >
        <div className="flex items-center justify-between gap-3">
          <p className="text-(--muted)">
            Drag files here or choose from your device.
          </p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
            className="rounded-lg border border-black/15 px-3 py-1.5 font-semibold text-(--ink) transition hover:bg-black/5 disabled:cursor-not-allowed"
          >
            Attach
          </button>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          disabled={disabled}
          onChange={(event) => {
            handleFiles(event.target.files);
            event.currentTarget.value = "";
          }}
          className="hidden"
        />
      </div>

      {attachments.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-(--muted)">
            <span>
              {attachments.length} file{attachments.length !== 1 ? "s" : ""} (
              {formatFileSize(totalSize)})
            </span>
            {uploadedCount > 0 && (
              <span className="text-green-600">{uploadedCount} uploaded</span>
            )}
            {failedCount > 0 && (
              <span className="text-red-600">{failedCount} failed</span>
            )}
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            {attachments.map((item) => (
              <div
                key={item.local_id}
                className={`rounded-lg border px-3 py-2 ${
                  item.status === "error"
                    ? "border-red-300 bg-red-50"
                    : "border-black/10 bg-white/70"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-(--ink) sm:text-sm">
                      {item.file_name}
                    </p>
                    <div className="flex items-center gap-2">
                      <p className="truncate text-[11px] text-(--muted) sm:text-xs">
                        {formatFileSize(item.file_size)}
                      </p>
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          item.status === "uploaded"
                            ? "bg-green-100 text-green-700"
                            : item.status === "error"
                              ? "bg-red-100 text-red-700"
                              : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {getStatusText(item.status)}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemoveAttachment(item.local_id)}
                    className="rounded-md px-2 py-1 text-xs text-(--muted) transition hover:bg-black/5"
                  >
                    ✕
                  </button>
                </div>

                {item.preview_url && (
                  <div className="mt-2 rounded-md overflow-hidden bg-black/5 max-h-20">
                    {item.mime_type.startsWith("image/") ? (
                      <img
                        src={item.preview_url}
                        alt={item.file_name}
                        className="max-w-full max-h-20 object-contain mx-auto"
                      />
                    ) : item.mime_type.startsWith("video/") ? (
                      <video
                        src={item.preview_url}
                        className="max-w-full max-h-20 object-contain mx-auto"
                      />
                    ) : null}
                  </div>
                )}

                <div className="mt-2 h-1.5 rounded-full bg-black/10">
                  <div
                    className={`h-full rounded-full transition-all ${getStatusColor(item.status)}`}
                    style={{ width: `${Math.max(4, item.progress)}%` }}
                  />
                </div>

                {item.error && (
                  <p className="mt-1 text-[11px] text-red-600 line-clamp-2">
                    {item.error}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
