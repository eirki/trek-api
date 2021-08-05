import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".") / ".env.local")
load_dotenv(dotenv_path=Path(".") / ".env")

graphhopper_api_key: Final = os.environ["trek_graphhopper_api_key"]
graphopper_url: Final = os.environ["trek_graphopper_url"]
