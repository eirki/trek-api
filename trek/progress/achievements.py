import aiosql
from asyncpg import Connection
import pendulum

# queries = aiosql.from_path("sql/achievements.sql", driver_adapter="asyncpg")

# possible_achievements = [
#     {
#         "query": queries.most_steps_one_day,
#         "desc": "Flest skritt gått på en dag",
#         "unit": "skritt",
#     },
#     {
#         "query": queries.most_steps_one_week,
#         "desc": "Flest skritt gått på en uke",
#         "unit": "skritt",
#     },
#     {
#         "query": queries.longest_streak,
#         "desc": "Flest førsteplasser på rad",
#         "unit": "dager",
#     },
# ]


def get_new_achievement(db: Connection, trek_id: int, leg_id: int, date: pendulum.Date):
    for smt in (trek_id, leg_id):
        for possible_achv in possible_achievements:
            holder = possible_achv["query"](db, grouped_by=smt)
            if holder["date"] != date:
                continue
            return achievement


async def main(db: Connection, trek_id: int, leg_id: int, date: pendulum.Date) -> list:
    new = get_new_achievement(db, trek_id, leg_id, date)
    return new
