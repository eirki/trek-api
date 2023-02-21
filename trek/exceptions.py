import typing as t

from pydantic import BaseModel, root_validator


class ServerExceptionModel(BaseModel):
    # Utility class that adds error_code and message to instance variables and schema output
    exception_models: t.ClassVar = []
    _message: t.ClassVar
    error_code: t.Optional[str] = None
    message: t.Optional[str] = None

    @root_validator()
    def validate(cls, values):
        values["error_code"] = cls.__name__  # type: ignore
        values["message"] = cls._message
        return values

    class Config:
        @staticmethod
        def schema_extra(
            schema: t.Dict[str, t.Any], model_class
        ) -> None:  # pragma: no cover
            schema["properties"]["error_code"] = {
                "title": "Error Code",
                "const": model_class.__name__,
                "enum": [model_class.__name__],
                "type": "integer",
            }
            schema["properties"]["message"] = {
                "title": "Message",
                "const": model_class._message,
                "enum": [model_class._message],
                "type": "string",
            }
            req = schema.get("required", [])
            req.insert(0, "message")
            req.insert(0, "error_code")
            schema["required"] = req

    @classmethod
    def __init_subclass__(cls):
        cls.exception_models.append(cls)


# 1 User related errors
class E101Error(ServerExceptionModel):
    _message = "Server error occured"
    status_code: int
    detail: str


# 2 Trek/crud related errors


# 3 search related errors
class E301SearchAPIError(ServerExceptionModel):
    _message = "Unexpected error from search API"
    description: str


class E302NoRouteFound(ServerExceptionModel):
    _message = "No route found for requested coordinates"


class E303RouteTooLong(ServerExceptionModel):
    _message = "Unable to find route shorter than length limit"
    route_length: t.Optional[int]
    max_length: int


# 9xx
class E901UnexpectedError(ServerExceptionModel):
    _message = "Unexpected error occured"
    traceback: str


class ServerException(Exception):
    def __init__(self, model: ServerExceptionModel):
        self.model = model


ServerExceptionType = t.Union[tuple(ServerExceptionModel.exception_models)]  # type: ignore
