from app.schemas.digitization_job import DigitizationJobRead


class DigitizerJobRead(DigitizationJobRead):
    """A DigitizationJob plus the safe filenames stored for it.

    `source_images` are server-generated filenames only (no directory
    components), never absolute filesystem paths.
    """

    source_images: list[str] = []
