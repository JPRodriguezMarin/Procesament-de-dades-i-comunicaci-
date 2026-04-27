import functools
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from chapter_10.listing_10_4 import DB_KEY, create_database_pool, destroy_database_pool

routes = web.RouteTableDef()


@routes.get('/users/{id}/cart')
async def cart(request: Request) -> Response:
    try:
        user_id = int(request.match_info['id'])
        db = request.app[DB_KEY]
        query = 'SELECT product_id FROM user_cart WHERE user_id = $1'
        result = await db.fetch(query, user_id)
        if result is not None:
            return web.json_response([dict(record) for record in result])
        else:
            raise web.HTTPNotFound()
    except ValueError:
        raise web.HTTPBadRequest()


app = web.Application()
app.on_startup.append(functools.partial(
    create_database_pool,
    host='127.0.0.1',
    port=5432,
    user='postgres',
    password='password',
    database='cart'
))
app.on_cleanup.append(destroy_database_pool)
app.add_routes(routes)
web.run_app(app, port=8003)
