from abc import ABCMeta
import typing as t

from trek.core.progress.progress_utils import UserProgress
from trek.database import Database
from trek.models import Achievement, Location, Trek, User


class Outputter(metaclass=ABCMeta):
    @staticmethod
    def post_leg_reminder(db: Database, trek: Trek, next_adder: User):
        return NotImplemented

    @staticmethod
    def post_update(
        db: Database,
        trek: Trek,
        users_progress: list[UserProgress],
        location: Location,
        achievements: t.Optional[list[Achievement]],
        next_adder: t.Optional[User],
    ):
        return NotImplemented
