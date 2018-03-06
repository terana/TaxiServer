import random
import string
from datetime import datetime

import pymysql

import classes as cl

pymysql.install_as_MySQLdb()


def create_auth_token(user):
    return ''.join(random.choices(string.ascii_uppercase +
                                  string.ascii_lowercase +
                                  string.digits, k=cl.Consts.auth_token_len()))


def create_promo_code(user):
    return ''.join(random.choices(string.ascii_uppercase, k=cl.Consts.promo_len()))


async def connect_to_db(app):
    connection = pymysql.connect(
        host='127.0.0.1',
        user='split',
        password='taxisplit1927230',
        database='taxi',
        charset='utf8')
    connection.autocommit(True)
    app['db_connection'] = connection


async def close_connection(app):
    app['db_connection'].close()


async def check(conn):
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE device_id="1"')
        cursor.fetchone()


async def store_events(conn, events):
    if not events:
        return
    sql = "INSERT INTO events \
            (name, timestamp, parameters)\
          VALUES (%s, %s, %s)"

    with conn.cursor() as cursor:
        for ev in events:
            cursor.execute(sql, (ev.get('name', "undefined"), ev.get('time', 0), ev.get('parameters', "")))


async def get_user(conn, device_id):
    if not device_id:
        return None

    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE device_id=%s', device_id)
        raw_user = cursor.fetchone()
        if raw_user:
            return cl.User().unmarshall(raw_user)

    return None


async def update_user(conn, user):
    if not user.device_id:
        return None

    sql = 'UPDATE users \
            SET fcm_token=%s, name=%s, phone=%s, promo=%s, used_promo=%s, region=%s, \
            language=%s, os=%s, os_version=%s, app_version=%s\
            WHERE device_id = %s'
    with conn.cursor() as cursor:
        cursor.execute(sql, (str(user.fcm_token),
                             str(user.name),
                             str(user.phone),
                             str(user.promo),
                             str(user.used_promo),
                             str(user.region),
                             str(user.language),
                             str(user.os),
                             str(user.os_version),
                             str(user.app_version),
                             str(user.device_id)))

    return await get_user(conn, device_id=user.device_id)


async def put_user(conn, user):
    if not user.device_id:
        return None

    sql = 'INSERT INTO users \
            (device_id, fcm_token, name, phone, promo, used_promo, region, language, os, os_version, app_version, auth_token)\
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
    with conn.cursor() as cursor:
        cursor.execute(sql, (str(user.device_id),
                             str(user.fcm_token),
                             str(user.name),
                             str(user.phone),
                             str(user.promo),
                             str(user.used_promo),
                             str(user.region),
                             str(user.language),
                             str(user.os),
                             str(user.os_version),
                             str(user.app_version),
                             str(user.auth_token)))

    return await get_user(conn, device_id=user.device_id)


async def store_user(conn, user):
    existing = await get_user(conn, user.device_id)
    if existing:
        existing.update(user)
        user = await update_user(conn, existing)
    else:
        user.auth_token = create_auth_token(user)
        user.promo = create_promo_code(user)
        user.used_promo = 0
        user = await put_user(conn, user)

    if not user:
        raise Exception("No device id")
    return user


async def apply_promo(conn, code):
    if not code:
        raise cl.ClientError("Неверный промокод")

    sql = 'SELECT * FROM users WHERE promo=%s'
    with conn.cursor() as cursor:
        cursor.execute(sql, code)
        raw_user = cursor.fetchone()
        if not raw_user:
            raise cl.ClientError("Неверный промокод")
        user = cl.User().unmarshall(raw_user)
        if user.used_promo < cl.Consts.total_promo():
            user.used_promo += 1
            await update_user(conn, user)
            return
    raise cl.ClientError("Лимит активированных промокодов исчерпан")


async def get_ride(conn, begin_timestamp, device_id):
    sql = 'SELECT * FROM rides WHERE begin_timestamp=%s AND device_id=%s'
    with conn.cursor() as cursor:
        cursor.execute(sql, (begin_timestamp, device_id))
        return cursor.fetchone()


async def get_ride_by_id(conn, ride_id):
    if not ride_id:
        return None
    sql = 'SELECT * FROM rides WHERE ride_id=%s'
    with conn.cursor() as cursor:
        cursor.execute(sql, ride_id)
        raw_ride = cursor.fetchone()
        if raw_ride:
            return cl.Ride().unmarshall(raw_ride)
    return None


async def store_ride(conn, ride):
    if not ride:
        return None
    ride.begin_timestamp = datetime.now().timestamp()
    ride.duration = cl.Consts.search_duration()
    sql = 'INSERT INTO rides \
                (begin_timestamp, duration, device_id, mode, from_lat, from_lng, to_lat, to_lng, phone, fcm_token, found, found_id)\
                VALUES ({begin}, {duration}, "{dev_id}", "{mode}", {from_lat}, {from_lng}, {to_lat}, {to_lng}, \
                 "{phone}", "{fcm}", {found}, {found_id})'.format(begin=round(ride.begin_timestamp),
                                                                  duration=ride.duration,
                                                                  dev_id=ride.user.device_id,
                                                                  mode=ride.mode,
                                                                  from_lat=ride.start.lat,
                                                                  from_lng=ride.start.lng,
                                                                  to_lat=ride.destination.lat,
                                                                  to_lng=ride.destination.lng,
                                                                  phone=ride.user.phone,
                                                                  fcm=ride.user.fcm_token,
                                                                  found=ride.found,
                                                                  found_id=ride.found_ride_id)
    with conn.cursor() as cursor:
        cursor.execute(sql)
    raw_ride = await get_ride(conn=conn,
                              device_id=ride.user.device_id,
                              begin_timestamp=round(ride.begin_timestamp))
    return cl.Ride().unmarshall(raw_ride)


async def search_ride(conn, ride):
    if not ride:
        return None

    if ride.mode == "driver":
        search_mode = "'passenger'"
    elif ride.mode == "passenger":
        search_mode = "'driver'"
    else:
        search_mode = "'driver' , passenger"

    sql = 'SELECT * \
            FROM rides \
            WHERE device_id != "{dev_id}" \
            AND ABS(from_lat - {from_lat}) < {from_rad} \
            AND ABS (from_lng - {from_lng}) < {from_rad} \
            AND ABS(to_lat - {to_lat}) < {to_rad} \
            AND ABS (to_lng - {to_lng}) < {to_rad} \
            AND found != 1 \
            AND begin_timestamp + duration > {now} \
            AND mode in ({mode}) \
            AND status != "cancelled" \
            AND phone != "{phone}"'.format(dev_id=ride.user.device_id,
                                           from_lat=ride.start.lat,
                                           from_lng=ride.start.lng,
                                           to_lat=ride.destination.lat,
                                           to_lng=ride.destination.lng,
                                           from_rad=cl.Consts.start_radius_deg(),
                                           to_rad=cl.Consts.dest_radius_deg(),
                                           now=round(datetime.now().timestamp()),
                                           mode=search_mode,
                                           phone=ride.user.phone)

    with conn.cursor() as cursor:
        cursor.execute(sql)
        raw_ride = cursor.fetchone()
        if raw_ride:
            return cl.Ride().unmarshall(raw_ride)
    return None


async def mark_as_found(conn, ride1, ride2):
    if not ride1 or not ride2:
        return

    sql = 'UPDATE rides \
               SET found = 1, status="found", found_id = %s \
               WHERE ride_id = %s'
    with conn.cursor() as cursor:
        cursor.execute(sql, (ride1.ride_id, ride2.ride_id))
        cursor.execute(sql, (ride2.ride_id, ride1.ride_id))


async def update_status(conn, ride, status):
    if not ride or not ride.ride_id:
        return

    sql = 'UPDATE rides \
               SET status = "{}" \
               WHERE ride_id = %s'.format(status)
    with conn.cursor() as cursor:
        cursor.execute(sql, ride.ride_id)
    ride.status = status
    return ride


async def rate_ride(conn, ride_id, rate):
    if not ride_id:
        raise cl.ClientError("Нет номера поездки")

    if not rate:
        raise cl.ClientError("Нет оценки")

    sql = 'UPDATE rides \
               SET rate = {} \
               WHERE ride_id = %s'.format(rate)
    with conn.cursor() as cursor:
        cursor.execute(sql, ride_id)
    ride = await get_ride_by_id(conn, ride_id=ride_id)
    if not ride:
        raise cl.ClientError("Поездки не существует")
