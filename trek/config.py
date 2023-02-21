import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".") / ".env.local")
load_dotenv(dotenv_path=Path(".") / ".env")

app_name: Final = "trek"

max_route_distance: Final = 1_000_000

tables_path: Final = Path(os.environ.get("trek_tables_path", "/var/lib/trekapi/data"))
frontend_url: Final = os.environ["trek_frontend_url"]
dbx_token: Final = os.environ["trek_dbx_token"]


fitbit_client_id: Final = os.environ["trek_fitbit_client_id"]
fitbit_client_secret: Final = os.environ["trek_fitbit_client_secret"]
fitbit_redirect_uri: Final = os.environ["trek_fitbit_redirect_url"]

discord_client_id: Final = os.environ["trek_discord_client_id"]
discord_client_secret: Final = os.environ["trek_discord_client_secret"]
discord_bot_token: Final = os.environ["trek_discord_bot_token"]

withings_client_id: Final = os.environ["trek_withings_client_id"]
withings_consumer_secret: Final = os.environ["trek_withings_consumer_secret"]
withings_redirect_uri: Final = os.environ["trek_withings_redirect_uri"]

googlefit_client_id: Final = os.environ["trek_googlefit_client_id"]
googlefit_project_id: Final = os.environ["trek_googlefit_project_id"]
googlefit_client_secret: Final = os.environ["trek_googlefit_client_secret"]
googlefit_redirect_uri: Final = os.environ["trek_googlefit_redirect_uri"]
googlefit_auth_uri: Final = os.environ["trek_googlefit_auth_uri"]
googlefit_token_uri: Final = os.environ["trek_googlefit_token_uri"]
googlefit_auth_provider_x509_cert_url: Final = os.environ[
    "trek_googlefit_auth_provider_x509_cert_url"
]

polar_client_id: Final = os.environ["trek_polar_client_id"]
polar_client_secret: Final = os.environ["trek_polar_client_secret"]
polar_redirect_uri: Final = os.environ["trek_polar_redirect_uri"]

jwt_secret_key: Final = os.environ["trek_jwt_secret_key"]
fernet_key: Final = os.environ["trek_fernet_key"].encode()

ors_key: Final = os.environ["trek_ors_key"]

google_api_key: Final = os.environ["trek_google_api_key"]
google_api_secret: Final = os.environ["trek_google_api_secret"]
