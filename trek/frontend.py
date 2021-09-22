import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

log = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def home():
    with open("frontend/home.html") as file:
        html = file.read()
    return html


@router.get("/login", response_class=HTMLResponse)
async def login():
    with open("frontend/login.html") as file:
        html = file.read()
    return html
