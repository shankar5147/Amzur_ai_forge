import { FormEvent } from "react";

interface ChatComposerProps {
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function ChatComposer({
  value,
  disabled,
  onChange,
  onSubmit,
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
      <div className="flex gap-3">
        <input
          type="text"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask anything..."
          className="flex-1 rounded-xl border border-black/15 bg-white px-4 py-3 text-sm outline-none transition focus:border-(--clay) focus:ring-2 focus:ring-(--clay)/20 sm:text-base"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-xl bg-(--clay) px-5 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60 sm:text-base"
        >
          Send
        </button>
      </div>
    </form>
  );
}
