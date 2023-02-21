import base64
from itertools import tee
import json
import typing as t  # noqa
import urllib.parse
import uuid

from fastapi import Depends
from fastapi_jwt_auth import AuthJWT


def round_coords(coordinates: float) -> float:
    return round(coordinates, 7)


def protect_endpoint(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()


def pairwise(iterable):
    # pairwise('ABCDEFG') --> AB BC CD DE EF FG
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def encode_dict(data: dict) -> str:
    # print("data", data)
    message = json.dumps(data)
    base64_message = base64.urlsafe_b64encode(message.encode()).decode()
    # print("encode", base64_message)
    return base64_message


def decode_dict(data: str) -> dict:
    # print("data", data)
    data_out = base64.urlsafe_b64decode(data.encode()).decode()
    message_out = json.loads(data_out)
    # print("decode", message_out)
    return message_out


FRAGMENT_PLACEHOLDER = str(uuid.uuid4())


def add_params_to_url(url: str, params: dict) -> str:
    # urllib expects query params to come before '#'. Vue does not
    url = url.replace("#", FRAGMENT_PLACEHOLDER)
    url_parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(url_parts.query))
    query.update(params)
    new_url_parts = url_parts._replace(query=urllib.parse.urlencode(query))
    new_url = urllib.parse.urlunsplit(new_url_parts)
    new_url = new_url.replace(FRAGMENT_PLACEHOLDER, "#")
    return new_url
