from datetime import datetime

from aiohttp import web

import classes as cl
import database as db
import search as sch


async def default(request):
    return web.json_response({})


async def retrieve_user_and_geolocation(data, conn):
    user = cl.User(name=data.get('name'),
                   phone=data.get('phone'),
                   fcm_token=data.get('fcmToken'),
                   device_id=data.get('deviceId'),
                   os=data.get('os'),
                   app_version=data.get('appVersion'),
                   region=data.get('region'),
                   language=data.get('language'),
                   os_version=data.get('osVersion'))
    if user.device_id:
        db_user = await db.get_user(conn=conn, device_id=user.device_id)
        if db_user:
            user = db_user.update(user)

    geolocation = data.get('geolocation')
    if geolocation:
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


async def retrieve_ride(data, conn):
    user, start = await retrieve_user_and_geolocation(data, conn=conn)
    ride = cl.Ride(user=user, start=start,
                   destination=retrieve_destination(data),
                   mode=data.get('mode'))
    if not start:
        ride.start = cl.Consts.default_locaion()
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
    user, _ = await retrieve_user_and_geolocation(data, conn=conn)
    user = await db.store_user(conn, user)
    return web.json_response(default_response(user))


async def apply_promo(request):
    data = await request.json()
    conn = request.app['db_connection']
    await db.apply_promo(conn, data.get('code'))
    user, _ = await retrieve_user_and_geolocation(data, conn=conn)
    return web.json_response(default_response(user))


async def split(request):
    data = await request.json()
    conn = request.app['db_connection']
    loop = request.app.loop
    opt = request.match_info['option']
    if opt == "start":
        resp = await split_start(data=data, conn=conn, loop=loop)
    elif opt == "status":
        resp = await split_status(conn, data.get('rideId'))
    elif opt == "cancel":
        resp = await split_cancel(data=data, conn=conn)
    elif opt == "rate":
        resp = await split_rate(data=data, conn=conn)
    else:
        raise cl.ClientError("Неподдерживаемый метод")
    user, _ = await retrieve_user_and_geolocation(data, conn=conn)
    resp.update(default_response(user))
    return web.json_response(resp)


async def split_start(data, conn, loop):
    ride = await db.store_ride(conn=conn, ride=await retrieve_ride(data, conn=conn))
    loop.create_task(sch.find_ride(conn, ride))
    return {'rideId': ride.ride_id, 'duration': ride.duration}


async def split_status(conn, ride_id):
    ride = await db.get_ride_by_id(conn, ride_id)
    if not ride:
        raise cl.ClientError("Поездка не найдена")
    if ride.found:
        found_ride = await db.get_ride_by_id(conn, ride_id=ride.found_ride_id)
        return {'found': True, 'phone': found_ride.user.phone}
    return {'found': False, 'timeout': bool(ride.begin_timestamp + ride.duration < datetime.now().timestamp())}


async def split_cancel(data, conn):
    ride = await db.get_ride_by_id(conn, ride_id=data.get("rideId"))
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
    user, _ = await retrieve_user_and_geolocation(data, conn=conn)
    return web.json_response(default_response(user))
