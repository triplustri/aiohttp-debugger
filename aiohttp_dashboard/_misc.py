from aiohttp.web import WebSocketResponse
from asyncio import iscoroutine, isfuture, ensure_future, gather
from inspect import iscoroutinefunction, isfunction, ismethod, isclass
from enum import Enum
from time import time
from typing import List, Union, TypeVar, Sequence
from uuid import uuid4


_T = TypeVar('_T')


def uuid_() -> str:
    """ Used for generate id for documents.
    """
    return uuid4().hex


def timestamp():
    return time() * 1000


def ensure_list(value: Union[_T, Sequence[_T]]) -> List[_T]:
    if isinstance(value, (str, bytes)):  # special rule for string
        return [value]
    elif isinstance(value, Sequence):
        return list(value)
    else:
        return [value]


def is_subset_dict(subset_dict, superset_dict):
    for key, value in subset_dict.items():
        if key in superset_dict.keys():
            if value != superset_dict[key]:
                return False
        else:
            return False
    return True


class MsgDirection(Enum):
    OUTBOUND = 1
    INCOMING = 2
