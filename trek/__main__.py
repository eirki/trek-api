import argparse
import asyncio

from trek import database


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


if __name__ == "__main__":
    asyncio.run(main())
