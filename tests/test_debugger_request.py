from aiohttp import web
from aiohttp_debugger import Debugger
from pytest import fixture
import asyncio


@fixture
def application():

    async def index(request):
        return web.Response(text='Hello, world!')

    application = web.Application()
    application.router.add_get('/index', index)

    Debugger.setup(application)

    return application


async def test_debugger_requests_number(loop, test_client, application):
    number, client = 3, await test_client(application)
    
    await asyncio.gather(*(client.get('/index') for _ in range(number)))
    assert Debugger.instance.api.requests().__len__() == number


async def test_debugger_resonse_content(loop, test_client, application):
    client = await test_client(application)
    await client.get('/index')

    head, *tail = Debugger.instance.api.requests()
    assert 'Hello, world!' in head['body']
