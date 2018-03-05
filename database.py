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
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=cl.Consts.promo_len()))


async def connect_to_db(app):
    connection = pymysql.connect(
        host='127.0.0.1',
        user='production',
        password='qH9JSqkEzjzntrAg',
        database='taxi',
        charset='utf8')
    connection.autocommit(True)
    app['db_connection'] = connection


async def close_connection(app):
    app['db_connection'].close()


async def check(conn):
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE device_id=1')
        cursor.fetchone()


async def store_event(conn, event):
    pass


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
        return

    sql = 'SELECT * FROM users WHERE promo=%s'
    with conn.cursor() as cursor:
        cursor.execute(sql, code)
        user = cursor.fetchone()
        if user.used_promo < cl.Consts.total_promo():
            user.used_promo += 1
            await update_user(conn, user)


async def get_ride(conn, begin_timestamp, device_id):
    sql = 'SELECT * FROM rides WHERE begin_timestamp=%s AND device_id=%s'
    with conn.cursor() as cursor:
        cursor.execute(sql, (begin_timestamp, device_id))
        return cursor.fetchone()


async def store_ride(conn, ride):
    if not ride:
        return None
    ride.begin_timestamp = datetime.now().timestamp()
    ride.duration = cl.Consts.search_duration()
    sql = 'INSERT INTO rides \
                (begin_timestamp, duration, device_id, mode, from_lat, from_lng, to_lat, to_lng)\
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
    with conn.cursor() as cursor:
        cursor.execute(sql, (str(ride.begin_timestamp),
                             str(ride.duration),
                             str(ride.user.device_id),
                             str(ride.mode),
                             str(ride.start.lat),
                             str(ride.start.lng),
                             str(ride.destination.lat),
                             str(ride.destination.lat)))
    raw_ride = await get_ride(conn=conn,
                              device_id=ride.user.device_id,
                              begin_timestamp=round(ride.begin_timestamp))
    return cl.Ride().unmarshall(raw_ride)


async def search_ride(conn, ride):
    if not ride:
        return None

    sql = 'SELECT * \
            FROM rides \
            WHERE device_id != {dev_id} \
            AND ABS(from_lat - {flat}) < {fr} \
            AND ABS (from_lng - {flng}) < {fr} \
            AND ABS(to_lat - {tlat}) < {tr} \
            AND ABS (to_lng - {tlng}) < {tr} \
            AND begin_timestamp + duration > {now}'.format(dev_id=ride.device_id,
                                                           flat=ride.start.lat,
                                                           flng=ride.start.lng,
                                                           tlat=ride.destination.lat,
                                                           tlng=ride.destination.lng,
                                                           fr=cl.Consts.start_radius_deg(),
                                                           tr=cl.Consts.dest_radius_deg(),
                                                           now=round(datetime.now().timestamp()))
    # TODO better time duration operation!!

    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone()


async def remove_ride(conn, ride):
    sql = "DELETE FROM rides WHERE ride_id=%"
    with conn.cursor() as cursor:
        cursor.execute(sql, ride.ride_id)
