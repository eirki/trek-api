import argparse
import asyncio

import schedule

from trek import database, progress


async def main():  # pragma: no cover
    print("starting")
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", "-m")
    args = parser.parse_args()
    if args.mode == "server":
        ...
    elif args.mode == "migrate":
        await database.migrate()
    else:
        raise Exception(f"Incorrect mode, {args.mode}")


def run_scheduler():
    schedule.every().hour.at(":00").do(progress.main.execute_all)


if __name__ == "__main__":
    asyncio.run(main())
