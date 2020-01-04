import logging
from typing import Tuple, List
import time
from os.path import join, normpath, isabs, dirname, abspath
from aiohttp_jinja2 import template, web
from aiohttp.web import WebSocketResponse, RouteTableDef, json_response
from voluptuous import Schema, Required, Coerce, Optional, All, ALLOW_EXTRA
from voluptuous.error import CoerceInvalid
from yarl import URL
from pathlib import Path
from json import loads

from ._subscriber import Subcriber
from ._state import DEBUGGER_KEY, JINJA_KEY
from ._setup import DEBUGGER_PREFIX_KEY
from ._misc import MsgDirection

logger = logging.getLogger(__name__)


_URL_POSTFIX_EVENT = '/api/event'
_PATH_STATIC = Path(__file__).resolve().parent / 'static'

_int_coerce = Coerce(int)


def _to_int(value, default=None):
    if value is None:
        return default

    return _int_coerce(value)


_subscribe_schema = Schema({
    Required('id'): str,
    Required('endpoint'): str,
    Required('data'): Schema({
        Required('event'): str,
        Optional('conditions', default=dict): Schema({
            Optional('request'): Coerce(int),
        }, extra=ALLOW_EXTRA),
    })
})

_unsubscribe_schema = Schema({
    Required('id'): str,
    Required('endpoint'): str,
    Required('data'): Schema({
        Optional('event'): str,
        Required('id'): str,
    })
})

_criteria_schema = Schema({
    Optional('statuscode'): Coerce(int),
    Optional('timestart'): Coerce(int),
    Optional('timestop'): Coerce(int),
    Optional('skip'): Coerce(int),
    Optional('limit'): Coerce(int),
}, extra=ALLOW_EXTRA)


def _build_event_endpoint(request):
    prefix = request.app[DEBUGGER_PREFIX_KEY]

    return URL.build(
        scheme='wss' if request.secure else 'ws',
        host=request.url.host,
        port=request.url.port,
        path=prefix + _URL_POSTFIX_EVENT,
    )


@template('index.html', app_key=JINJA_KEY)
async def _index(request):
    prefix = request.app[DEBUGGER_PREFIX_KEY]

    return {
        'timestamp': time.time(),
        'prefix': prefix,
        'endpoint': _build_event_endpoint(request),
    }


async def _event(request):
    state = request.app[DEBUGGER_KEY]
    websocket = WebSocketResponse()
    subscriber = Subcriber(websocket, state)

    await websocket.prepare(request)

    try:
        async for message in websocket:
            message_json = message.json()

            try:
                if message_json['endpoint'] == 'subscribe':
                    subscriber.subscribe(_subscribe_schema(message_json))
                elif message_json['endpoint'] == 'unsubscribe':
                    subscriber.unsubscribe(_unsubscribe_schema(message_json))
            except Exception:
                logger.exception(
                    'An error occurred while processing the message')
    finally:
        subscriber.cancel()

    return websocket


async def _messages(request):
    state = request.app[DEBUGGER_KEY]

    messages = await state.api_message.find({
        **request.query,
        'requestid': _to_int(request.query.get('request')),
        'skip': _to_int(request.query.get('skip'), 0),
        'limit': _to_int(request.query.get('limit'), 0),
    })

    return json_response(messages)


async def _message_status(request):
    state = request.app[DEBUGGER_KEY]
    id_ = _to_int(request.query.get('request', None))
    time_start = _to_int(request.query.get('datestart', None))
    time_stop = _to_int(request.query.get('datestop', None))

    response = {
        'websocket': {
            'countincoming': 0,
            'countoutcoming': 0,
        }
    }

    return json_response(response)


async def _requests(request):
    state = request.app[DEBUGGER_KEY]
    criteria = _criteria_schema({**request.query})

    return json_response({
        'records': await state.api_request.find(criteria),
    })


async def _requests_status(request):
    state = request.app[DEBUGGER_KEY]
    criteria = _criteria_schema({**request.query})

    return json_response({
        'count': await state.api_request.count(criteria),
    })


async def _request(request):
    state = request.app[DEBUGGER_KEY]
    request_id = _to_int(request.match_info['id'])

    return json_response(
        await state.api_request.find_one(request_id))


async def _request_error(request):
    state = request.app[DEBUGGER_KEY]
    request_id = _to_int(request.match_info['id'])

    return json_response(await state.api_error.find_one(request_id))


async def _request_errors_status(request):
    state = request.app[DEBUGGER_KEY]
    return json_response({
        'count': 0,
    })


async def _status(request):
    state = request.app[DEBUGGER_KEY]
    return json_response(await state.api_status.get())


def build_routes(prefix) -> Tuple[List[Tuple], List[Tuple]]:
    routes = [
        # index.html
        ('GET', prefix, _index),
        # websocket event bus connector
        ('GET', prefix + _URL_POSTFIX_EVENT, _event),
        # get data urls
        ('GET', prefix + '/api/request', _requests),
        ('GET', prefix + '/api/request/{id}', _request),
        ('GET', prefix + '/api/message', _messages),
        ('GET', prefix + '/api/error/request/{id}', _request_error),
        # get status data urls
        ('GET', prefix + '/api/status', _status),
        ('GET', prefix + '/api/status/message', _message_status),
        ('GET', prefix + '/api/status/request', _requests_status),
        ('GET', prefix + '/api/status/error/request', _request_errors_status),
    ]

    static_routes = [
        (prefix + '/static', _PATH_STATIC)
    ]

    return routes, static_routes


resource_paths = [_PATH_STATIC]
