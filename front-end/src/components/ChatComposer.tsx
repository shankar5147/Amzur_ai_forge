import { FormEvent } from "react";

import { AttachmentUploader } from "./AttachmentUploader";
import type { PendingAttachment } from "../types/chat";

interface ChatComposerProps {
  value: string;
  disabled: boolean;
  canSend: boolean;
  canGenerateImage: boolean;
  generatingImage: boolean;
  attachments: PendingAttachment[];
  onChange: (value: string) => void;
  onFilesAdded: (files: File[]) => void;
  onRemoveAttachment: (localId: string) => void;
  onSubmit: () => void;
  onGenerateImage: () => void;
}

export function ChatComposer({
  value,
  disabled,
  canSend,
  canGenerateImage,
  generatingImage,
  attachments,
  onChange,
  onFilesAdded,
  onRemoveAttachment,
  onSubmit,
  onGenerateImage,
}: ChatComposerProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-black/10 bg-white/70 p-4 backdrop-blur sm:p-5"
    >
      <AttachmentUploader
        disabled={disabled}
        attachments={attachments}
        onFilesAdded={onFilesAdded}
        onRemoveAttachment={onRemoveAttachment}
      />
      <div className="flex gap-3">
        <input
          type="text"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask anything or describe an image to generate..."
          className="flex-1 rounded-xl border border-black/15 bg-white px-4 py-3 text-sm outline-none transition focus:border-(--clay) focus:ring-2 focus:ring-(--clay)/20 sm:text-base"
        />
        <button
          type="button"
          disabled={disabled || !canGenerateImage}
          onClick={onGenerateImage}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-(--clay) px-4 py-3 text-sm font-semibold text-(--clay) transition hover:bg-(--clay)/10 disabled:cursor-not-allowed disabled:opacity-60 sm:text-base"
        >
          {generatingImage && (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-(--clay)/35 border-t-(--clay)" />
          )}
          Generate
        </button>
        <button
          type="submit"
          disabled={disabled || !canSend}
          className="rounded-xl bg-(--clay) px-5 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60 sm:text-base"
        >
          Send
        </button>
      </div>
    </form>
  );
}
