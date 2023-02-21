import argparse
import logging
import time

import schedule
import uvicorn

from trek.core.progress import progress

log = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )


def main():  # pragma: no cover
    setup_logging()
    log.info("starting")
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", "-m")
    args = parser.parse_args()
    if args.mode == "server":
        run_server()
    elif args.mode == "scheduler":
        run_scheduler()
    else:
        raise Exception(f"Incorrect mode, {args.mode}")


def run_server():
    uvicorn.run(
        "trek.server:make_app",
        host="0.0.0.0",
        port=5007,
        reload=True,
        debug=True,
        workers=1,
        factory=True,
    )


def run_scheduler():
    schedule.every().hour.at(":00").do(progress.run)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
