import { useRef, useState } from 'react'

interface FileDropzoneProps {
  onFilesSelected: (files: File[]) => void
  disabled?: boolean
}

export function FileDropzone({ onFilesSelected, disabled = false }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragActive, setIsDragActive] = useState(false)

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return
    onFilesSelected(Array.from(fileList))
  }

  return (
    <div
      data-testid="digitizer-dropzone"
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(event) => {
        if (!disabled && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault()
          inputRef.current?.click()
        }
      }}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setIsDragActive(true)
      }}
      onDragLeave={() => setIsDragActive(false)}
      onDrop={(event) => {
        event.preventDefault()
        setIsDragActive(false)
        if (!disabled) handleFiles(event.dataTransfer.files)
      }}
      className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
      } ${isDragActive ? 'border-emerald-500 bg-emerald-50' : 'border-stone-300'}`}
    >
      <p className="font-medium text-stone-700">Drag & drop shelf or product photos here</p>
      <p className="mt-1 text-sm text-stone-500">or click to browse</p>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        disabled={disabled}
        className="hidden"
        data-testid="digitizer-file-input"
        onChange={(event) => {
          handleFiles(event.target.files)
          event.target.value = ''
        }}
      />
    </div>
  )
}
