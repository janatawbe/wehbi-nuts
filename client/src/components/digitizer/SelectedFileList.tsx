interface SelectedFileListProps {
  files: File[]
  onRemove: (index: number) => void
  disabled?: boolean
}

export function SelectedFileList({ files, onRemove, disabled = false }: SelectedFileListProps) {
  if (files.length === 0) return null

  return (
    <ul className="mt-4 space-y-2" data-testid="selected-file-list">
      {files.map((file, index) => (
        <li
          key={`${file.name}-${index}`}
          className="flex items-center justify-between rounded border border-stone-200 bg-white px-3 py-2 text-sm"
        >
          <span className="truncate">{file.name}</span>
          <button
            type="button"
            onClick={() => onRemove(index)}
            disabled={disabled}
            aria-label={`Remove ${file.name}`}
            className="text-red-600 hover:text-red-800 disabled:opacity-50"
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  )
}
