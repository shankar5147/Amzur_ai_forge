import { useRef, useState } from "react";

import type { PendingAttachment } from "../types/chat";

interface AttachmentUploaderProps {
  disabled: boolean;
  attachments: PendingAttachment[];
  onFilesAdded: (files: File[]) => void;
  onRemoveAttachment: (localId: string) => void;
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
        <div className="grid gap-2 sm:grid-cols-2">
          {attachments.map((item) => (
            <div
              key={item.local_id}
              className="rounded-lg border border-black/10 bg-white/70 p-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-(--ink) sm:text-sm">
                    {item.file_name}
                  </p>
                  <p className="truncate text-[11px] text-(--muted) sm:text-xs">
                    {item.mime_type || "Detecting type..."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveAttachment(item.local_id)}
                  className="rounded-md px-2 py-1 text-xs text-(--muted) transition hover:bg-black/5"
                >
                  Remove
                </button>
              </div>

              <div className="mt-2 h-1.5 rounded-full bg-black/10">
                <div
                  className={`h-full rounded-full transition-all ${item.status === "error" ? "bg-red-500" : "bg-(--clay)"}`}
                  style={{ width: `${Math.max(4, item.progress)}%` }}
                />
              </div>
              {item.error && (
                <p className="mt-1 text-[11px] text-red-600">{item.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
