import aiosql
from asyncpg import Connection

queries = aiosql.from_path("sql/activity.sql", "psycopg")


async def get_steps_data(db: Connection, trek_id: int, leg_id: int, user_info) -> list:
    # first from db
    # second from apis
    steps_data = ...
    await commit_steps_data(db, trek_id, leg_id, steps_data)
    return steps_data


async def commit_steps_data(
    db: Connection, trek_id: int, leg_id: int, steps_data: list
) -> None:
    as_dicts = [
        {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "user_id": user_id,
            "taken_at": taken_at,
            "amount": amount,
        }
        for user_id, taken_at, amount in steps_data
    ]
    async with db.transaction():
        await queries.add_steps(db, as_dicts)
