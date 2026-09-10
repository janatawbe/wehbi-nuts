// These limits mirror the backend's DIGITIZER_* settings
// (see server/.env.example). They exist purely to give users fast
// client-side feedback -- the backend remains the authoritative source of
// truth and re-validates every upload regardless of what the client sends.
export const DIGITIZER_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const DIGITIZER_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB
export const DIGITIZER_MAX_FILES = 20
