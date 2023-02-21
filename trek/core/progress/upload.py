import logging
from pathlib import Path
import typing as t

from dropbox import Dropbox
import pendulum

from trek import config
from trek.models import Id

log = logging.getLogger(__name__)


class UploadFunc(t.Protocol):
    def __call__(
        self, data: bytes, trek_id: Id, leg_id: Id, date: pendulum.Date, name: str
    ) -> t.Optional[str]:
        raise NotImplementedError


def make_upload_f():
    dbx = Dropbox(config.dbx_token)

    def upload(
        data: bytes, trek_id: Id, leg_id: Id, date: pendulum.Date, name: str
    ) -> t.Optional[str]:
        path = (
            Path("/trek") / str(trek_id) / str(leg_id) / (name + str(date))
        ).with_suffix(".jpg")
        try:
            uploaded = dbx.files_upload(f=data, path=path.as_posix(), autorename=True)
        except Exception:
            log.error(f"Error uploading {name} image", exc_info=True)
            return None
        shared = dbx.sharing_create_shared_link(uploaded.path_display)
        url = shared.url.replace("?dl=0", "?raw=1")
        return url

    return upload
