import asyncio
import json
from datetime import datetime
from time import sleep

import pymysql
from aiohttp import web
from aiohttp.web import middleware

import classes as cl
import database as db
import handlers as hd
from database import connect_to_db, close_connection


@middleware
async def log_middleware(request, handler):
    print("{}   {}".format(datetime.now(), request))
    resp = await handler(request)
    print("{}   {}".format(datetime.now(), resp))
    return resp


@middleware
async def error_middleware(request, handler):
    try:
        resp = await handler(request)
        return resp
    except (BrokenPipeError, ConnectionError, pymysql.err.Error, pymysql.err.IntegrityError) as err:
        await db.close_connection(request.app)
        sleep(1)
        await db.connect_to_db(request.app)
        resp = await handler(request)
        return resp
    except (cl.ClientError, json.JSONDecodeError, web.HTTPClientError) as err:
        print("Caught client error in error moddleware: {}\n".format(err))
        return web.json_response({'error': 1, 'alert_text': "{}".format(err)})
    except Exception as err:
        print("Caught exception in error moddleware: {}\n".format(err))
        return web.json_response({'error': 1, 'alert_text': "Server error"})
    except:
        print("Caught error in error middleware")
        return web.json_response({'error': 1, 'alert_text': "Server error"})


async def check_db(app):
    try:
        while 1:
            await db.check(app['db_connection'])
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        pass


async def start_background_tasks(app):
    app['db_checker'] = app.loop.create_task(check_db(app))


async def cleanup_background_tasks(app):
    app['db_checker'].cancel()
    await app['db_checker']


def launch_server(host, port):
    app = web.Application(middlewares=[error_middleware, log_middleware])

    app.on_startup.append(connect_to_db)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    app.on_cleanup.append(close_connection)

    app.router.add_get('/ping', hd.ping)
    app.router.add_post('/api/v1/user', hd.store_user)
    app.router.add_post('/api/v1/events', hd.events)
    app.router.add_post('/api/v1/promo/apply', hd.apply_promo)

    split_resource = app.router.add_resource('/api/v1/split/{option}')
    split_resource.add_route('POST', hd.split)

    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    try:
        launch_server("78.140.221.64", 80)
    except:
        sleep(2)
        launch_server("78.140.221.64", 80)
