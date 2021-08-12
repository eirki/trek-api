import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".") / ".env.local")
load_dotenv(dotenv_path=Path(".") / ".env")

graphhopper_api_key: Final = os.environ["trek_graphhopper_api_key"]
graphopper_url: Final = os.environ["trek_graphopper_url"]

db_name: Final = os.environ["POSTGRES_DB"]
db_user: Final = os.environ["POSTGRES_USER"]
db_password: Final = os.environ["POSTGRES_PASSWORD"]
db_host: Final = os.environ["POSTGRES_HOST"]
db_port: Final = os.environ["POSTGRES_PORT"]
db_uri: Final = f"postgres://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

