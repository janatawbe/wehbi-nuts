from app.schemas.digitization_job import DigitizationJobRead
from app.schemas.digitized_product import DigitizedProductRead


class DigitizerJobRead(DigitizationJobRead):
    """A DigitizationJob plus the safe filenames stored for it and the
    product drafts the AI has produced so far (empty before processing).

    `source_images` are server-generated filenames only (no directory
    components), never absolute filesystem paths. Each `candidates` entry
    carries its own `source_image`/`crop_image` filenames -- combined with
    the safe media endpoint, that is enough for the frontend to build a
    displayable URL for both without exposing any filesystem path.
    """

    source_images: list[str] = []
    candidates: list[DigitizedProductRead] = []
