from datetime import datetime

from aiohttp import web

import classes as cl
import database as db
import search as sch


async def ping(request):
    return web.Response(text="I'm OK")


async def retrieve_user(data, conn):
    user = cl.User(name=data.get('name'),
                   phone=data.get('phone'),
                   fcm_token=data.get('fcmToken'),
                   device_id=data.get('deviceId'),
                   os=data.get('os'),
                   app_version=data.get('appVersion'),
                   region=data.get('region'),
                   language=data.get('language'),
                   os_version=data.get('osVersion'))

    db_user = await db.get_user(conn=conn, device_id=user.device_id)
    if db_user:
        user = db_user.update(user)
    return user


def retrieve_geolocation(data):
    geolocation = data.get('geolocation', {})
    if geolocation is None:
        geolocation = {}
    geolocation = cl.Geolocation(lat=geolocation.get('lat', cl.Consts.default_locaion().lat),
                                 lng=geolocation.get('lng', cl.Consts.default_locaion().lng))
    return geolocation


def retrieve_destination(data):
    destination = data.get('destination', {})
    if not destination:
        return None
    return cl.Geolocation(lat=destination.get('lat', cl.Consts.default_locaion().lat),
                          lng=destination.get('lng', cl.Consts.default_locaion().lng))


async def retrieve_ride(data, conn):
    user = await retrieve_user(data, conn=conn)

    ride = cl.Ride(user=user, start=retrieve_geolocation(data),
                   destination=retrieve_destination(data),
                   mode=data.get('mode'))
    if not ride.destination:
        raise cl.ClientError("Нет точки назначения")
    if not user.device_id:
        raise cl.ClientError("Нет айди устройства")
    return ride


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
    user = await retrieve_user(data, conn=conn)
    user = await db.store_user(conn, user)
    return web.json_response(default_response(user))


async def apply_promo(request):
    data = await request.json()
    conn = request.app['db_connection']
    user = await retrieve_user(data, conn=conn)
    await db.apply_promo(conn, code=data.get('code'), dev_id=user.device_id)

    return web.json_response(default_response(user))


async def split(request):
    data = await request.json()
    print(data)
    conn = request.app['db_connection']
    loop = request.app.loop
    opt = request.match_info['option']
    if opt == "start":
        resp = await split_start(data=data, conn=conn, loop=loop)
    elif opt == "status":
        resp = await split_status(conn, data.get('rideId'))
    elif opt == "cancel":
        resp = await split_cancel(ride_id=data.get("rideId"), conn=conn)
    elif opt == "rate":
        resp = await split_rate(data=data, conn=conn)
    else:
        raise cl.ClientError("Неподдерживаемый метод")
    user = await retrieve_user(data, conn=conn)
    resp.update(default_response(user))
    return web.json_response(resp)


async def split_start(data, conn, loop):
    ride = await retrieve_ride(data, conn=conn)
    ride.status = "search"
    ride = await db.store_ride(conn=conn, ride=ride)
    loop.create_task(sch.find_ride(conn, ride))
    return {'rideId': str(ride.ride_id), 'duration': ride.duration}


async def split_status(conn, ride_id):
    ride = await db.get_ride_by_id(conn, ride_id)
    if not ride:
        raise cl.ClientError("Поездка не найдена")
    if ride.status == "found":
        found_ride = await db.get_ride_by_id(conn, ride_id=ride.found_ride_id)
        return {'found': True, 'phone': found_ride.user.phone}
    return {'found': False, 'timeout': bool(ride.begin_timestamp + ride.duration < datetime.now().timestamp())}


async def split_cancel(ride_id, conn):
    ride = await db.get_ride_by_id(conn, ride_id=ride_id)
    if ride:
        await db.update_status(conn=conn, status="cancelled", ride=ride)
    return {}


async def split_rate(data, conn):
    await db.rate_ride(conn, ride_id=data.get('rideId'), rate=data.get('rating'))
    return {}


async def events(request):
    data = await request.json()
    conn = request.app['db_connection']
    await db.store_events(conn, data.get('events'))
    user = await retrieve_user(data, conn=conn)
    return web.json_response(default_response(user))
