import asyncio

from aiohttp import web

import classes as cl
import database as db
import search as sch

async def default(request):
    return web.json_response({})


def retrieve_user_and_geolocation(data):
    user = cl.User(name=data.get('name'),
                   phone=data.get('phone'),
                   fcm_token=data.get('fcmToken'),
                   device_id=data.get('deviceId'),
                   os=data.get('os'),
                   app_version=data.get('appVersion'),
                   region=data.get('region'),
                   language=data.get('language'),
                   os_version=data.get('osVersion'))

    geolocation = data.get('geolocation', {})
    geolocation = cl.Geolocation(lat=geolocation.get('lat'), lng=geolocation.get('lng'))
    if not geolocation.lat or not geolocation.lng:
        geolocation = None
    return user, geolocation


def retrieve_destination(data):
    destination = data.get('destination', {})
    if not destination:
        return None
    return cl.Geolocation(lat=destination.get('lat'),
                          lng=destination.get('lng'))


def default_response(user):
    if not user:
        return {}

    promo = None
    if user.promo:
        promo = {'code': user.promo,
                 'used': user.used_promo,
                 'total': cl.Consts.total_promo()}
    return {'promo': promo,
            'authToken': user.auth_token}


async def store_user(request):
    data = await request.json()
    print(data)
    conn = request.app['db_connection']
    user, _ = retrieve_user_and_geolocation(data)
    user = await db.store_user(conn, user)
    return web.json_response(default_response(user))


async def apply_promo(request):
    data = await request.json()
    conn = request.app['db_connection']
    db.apply_promo(conn, data.get('code'))
    user, _ = retrieve_user_and_geolocation(data)
    return web.json_response(default_response(user))


async def split(request):
    data = await request.json()
    conn = request.app['db_connection']
    loop = request.app.loop
    opt = request.match_info['option']
    if opt == "start":
        resp = await split_start(data=data, conn=conn, loop=loop)
    elif opt == "status":
        resp = await split_status(request)
    else:
        raise Exception("Invalid option")
    user, _ = retrieve_user_and_geolocation(data)
    resp.update(default_response(user))
    return web.json_response(resp)


async def split_start(data, conn, loop):
    user, start = retrieve_user_and_geolocation(data)
    ride = cl.Ride(user=user, start=start,
                   destination=retrieve_destination(data),
                   mode=data.get('mode'))
    if not start:
        raise Exception("No start point")
    if not ride.destination:
        raise Exception("No end point")
    if not user.device_id:
        raise Exception("No device id")
    ride = await db.store_ride(conn=conn, ride=ride)
    loop.create_task(asyncio.wait_for(fut=sch.search_ride_loop(conn=conn, ride=ride),
                                      loop=loop,
                                      timeout=ride.duration))
    return {'rideId': ride.ride_id, 'duration': ride.duration}


async def split_status(request):
    return web.Response(status=200)


async def split_cancel(request):
    return web.Response(status=200)


async def rate(request):
    return web.Response(status=200)


async def events(request):
    data = await request.json()

    return web.Response(status=200)
