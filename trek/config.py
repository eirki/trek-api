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

schema_db_name: Final = "trek_schema_db"
schema_db_uri: Final = (
    f"postgres://{db_user}:{db_password}@{db_host}:{db_port}/{schema_db_name}"
)

fitbit_client_id = os.environ["trek_fitbit_client_id"]
fitbit_client_secret = os.environ["trek_fitbit_client_secret"]
fitbit_redirect_uri = os.environ["trek_fitbit_redirect_url"]

withings_client_id = os.environ["trek_withings_client_id"]
withings_consumer_secret = os.environ["trek_withings_consumer_secret"]
withings_redirect_uri = os.environ["trek_withings_redirect_uri"]

jwt_secret_key: Final = os.environ["trek_jwt_secret_key"]
fernet_key: Final = os.environ["trek_fernet_key"].encode()

ors_key: Final = os.environ["trek_ors_key"]
