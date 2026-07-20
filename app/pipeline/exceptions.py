from typing import Iterable


class PipelineAwaitingUpload(Exception):
    """Pause the pipeline for an optional manual-media decision.

    This is not a failure and does not mean every scene requires an upload.
    The user may upload only selected scenes; all remaining scenes continue
    through the configured automatic stock or AI provider after resume.
    """

    def __init__(
        self,
        missing_scenes: Iterable[int],
        message: str | None = None,
    ) -> None:
        self.missing_scenes = [
            int(scene)
            for scene in missing_scenes
        ]

        super().__init__(
            message
            or (
                "İsteğe bağlı sahne görselleri için kullanıcı kararı "
                "bekleniyor. Yüklenmeyen sahneler otomatik sağlayıcıyla "
                "tamamlanacaktır."
            )
        )
