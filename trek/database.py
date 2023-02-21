from contextlib import contextmanager
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import tempfile
import typing as t  # noqa
import uuid

from filelock import FileLock
import pendulum
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from trek import config, models
from trek.models import Id

log = logging.getLogger(__name__)


type_map = {
    str: pa.string(),
    bool: pa.bool_(),
    Id: pa.string(),
    models.TrackerName: pa.string(),
    models.OutputName: pa.string(),
    pendulum.Date: pa.date32(),
    pendulum.DateTime: pa.timestamp("s"),
}


def _is_optional(type_) -> bool:
    return t.get_origin(type_) is t.Union and type(None) in t.get_args(type_)


def _field_for_annotation(name, annotation) -> pa.Field:
    if t.get_origin(annotation) is t.Annotated:
        py_type, arrow_type = t.get_args(annotation)
        field_is_optional = _is_optional(py_type)
    else:
        py_type = annotation
        field_is_optional = _is_optional(py_type)
        if field_is_optional:
            union_args = t.get_args(py_type)
            assert len(union_args) == 2
            py_type = union_args[0]
        arrow_type = type_map[py_type]
    return pa.field(name, arrow_type, nullable=field_is_optional)


def _make_schema(Type) -> pa.Schema:
    annotations = t.get_type_hints(Type, include_extras=True).items()
    return pa.schema([_field_for_annotation(name, hint) for name, hint in annotations])


class ValidationError(Exception):
    pass


def _validate(table: pa.Table, expression: pc.Expression):
    invalid = table.filter(~expression)
    if not invalid.num_rows == 0:
        raise ValidationError(expression, invalid)


R = t.TypeVar("R")


class Database:
    lock = FileLock("database.lock")

    @classmethod
    @contextmanager
    def get_db_mgr(cls):
        with cls.lock, tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            db = cls(save_dir=temp_dir, load_dir=config.tables_path)
            yield db
            db.commit()

    @classmethod
    def get_db(cls):
        with cls.get_db_mgr() as db:
            yield db

    def __init__(self, save_dir: Path, load_dir: Path):
        self.save_dir = save_dir
        self.load_dir = load_dir

    def load_table(
        self,
        Type: t.Type[R],
        filter: t.Optional[pc.Expression] = None,
        columns: t.Optional[list[str]] = None,
    ) -> pa.Table:
        metadata = table_metadatas[Type]
        path = self.save_dir / metadata.name
        if not path.exists():
            path = self.load_dir / metadata.name
        if not path.exists():
            table = pa.Table.from_pylist([], schema=metadata.schema)
        else:
            table = ds.dataset(
                path,
                schema=metadata.schema,
                format="parquet",
                partitioning=metadata.partitioning,
            ).to_table(filter=filter, columns=columns)

        return table

    def load_records(
        self,
        Type: t.Type[R],
        filter: t.Optional[pc.Expression] = None,
        columns: t.Optional[list[str]] = None,
    ) -> list[R]:
        return self.load_table(Type, filter, columns).to_pylist()

    def save_table(self, Type: t.Type[R], table: pa.Table) -> None:
        metadata = table_metadatas[Type]
        if metadata.validators is not None:
            for validator in metadata.validators:
                _validate(table, validator)
        if metadata.partitioning is None:
            ds.write_dataset(
                table,
                self.save_dir / metadata.name,
                format="parquet",
                existing_data_behavior="overwrite_or_ignore",
            )
        else:
            pq.write_to_dataset(
                table,
                root_path=self.save_dir / metadata.name,
                partitioning=metadata.partitioning,
                existing_data_behavior="overwrite_or_ignore",
            )

    def append_record(self, Type: t.Type[R], record: R) -> None:
        metadata = table_metadatas[Type]
        table = self.load_table(Type)
        record_table = pa.Table.from_pylist([record], schema=metadata.schema)
        merged_table = pa.concat_tables([table, record_table])
        # order is SOMETIMES non-deterministic if chunks not combined
        merged_table = merged_table.combine_chunks()
        self.save_table(Type, merged_table)

    def upsert_record(self, Type: t.Type[R], record: R, filter: pc.Expression):
        metadata = table_metadatas[Type]
        table = self.load_table(Type)
        is_in_table = table.filter(filter)
        if is_in_table.num_rows == 0:
            self.append_record(Type, record)
        else:
            table_without_new = table.filter(~filter)
            record_table = pa.Table.from_pylist([record], schema=metadata.schema)
            merged_table = pa.concat_tables([table_without_new, record_table])
            self.save_table(Type, merged_table)

    def delete_records(self, Type: t.Type[R], filter: pc.Expression):
        new_table = self.load_table(Type, filter=~filter)
        self.save_table(Type, new_table)

    def delete_partion(self, Type: t.Type[R], partition_id: Id):
        metadata = table_metadatas[Type]
        shutil.rmtree(
            str(self.save_dir / metadata.name / partition_id), ignore_errors=True
        )

    def commit(self):
        self.load_dir.mkdir(exist_ok=True)
        for metadata in self.save_dir.iterdir():
            to_path = self.load_dir / metadata.name
            shutil.copytree(metadata, to_path, dirs_exist_ok=True)

    def commit_table(self, Type: t.Type[R]):
        metadata = table_metadatas[Type]
        from_path = self.save_dir / metadata.name
        to_path = self.load_dir / metadata.name
        shutil.copytree(from_path, to_path, dirs_exist_ok=True)

    @staticmethod
    def make_id() -> Id:
        return Id(uuid.uuid4().hex)


@dataclass
class TableMetadata:
    name: str
    schema: pa.Schema
    partitioning: t.Optional[ds.Partitioning] = None
    validators: t.Optional[list[pc.Expression]] = None


user_schema = _make_schema(models.User)
user_token_schema = _make_schema(models.UserToken)
discord_channel_schema = _make_schema(models.DiscordChannel)
polar_cache_schema = _make_schema(models.PolarCache)
trek_schema = _make_schema(models.Trek)
leg_schema = _make_schema(models.Leg)
waypoint_schema = _make_schema(models.Waypoint)
location_schema = _make_schema(models.Location)
trek_user_schema = _make_schema(models.TrekUser)
step_schema = _make_schema(models.Step)
achievement_schema = _make_schema(models.Achievement)

table_metadatas: dict[t.Any, TableMetadata] = {
    models.User: TableMetadata(
        name="users",
        schema=user_schema,
    ),
    models.UserToken: TableMetadata(
        name="user_tokens",
        schema=user_token_schema,
    ),
    models.TrekUser: TableMetadata(
        name="trek_users",
        schema=trek_user_schema,
    ),
    models.DiscordChannel: TableMetadata(
        name="discord_channels",
        schema=discord_channel_schema,
    ),
    models.PolarCache: TableMetadata(
        name="polar_caches",
        schema=polar_cache_schema,
    ),
    models.Trek: TableMetadata(
        name="treks",
        schema=trek_schema,
        validators=models.trek_validators,
    ),
    models.Leg: TableMetadata(
        name="legs",
        schema=leg_schema,
    ),
    models.Waypoint: TableMetadata(
        name="waypoints",
        schema=waypoint_schema,
        partitioning=models.waypoints_partitioning,
    ),
    models.Location: TableMetadata(
        name="locations",
        schema=location_schema,
    ),
    models.Step: TableMetadata(
        name="steps",
        schema=step_schema,
    ),
    models.Achievement: TableMetadata(
        name="achievements",
        schema=achievement_schema,
    ),
}
