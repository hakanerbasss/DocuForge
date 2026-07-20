from typing import Iterable


class PipelineAwaitingUpload(Exception):
    """Raised by the media step when image_provider == "manual" and one or
    more scenes still need a hand-uploaded image.

    This is a cooperative *pause*, not a failure: the pipeline stops before
    the render step so the user can generate each scene's image (e.g. in
    ChatGPT, using the per-scene prompt the pipeline already produced) and
    upload it, then resume. It deliberately mirrors PipelineCancelled --
    both halt the run cleanly without marking a hard error.
    """

    def __init__(
        self,
        missing_scenes: Iterable[int],
        message: str | None = None,
    ) -> None:
        self.missing_scenes = [int(scene) for scene in missing_scenes]

        super().__init__(
            message
            or (
                "Elle yükleme bekleniyor: "
                f"{self.missing_scenes} numaralı sahne(ler) için görsel "
                "yüklenmedi."
            )
        )
