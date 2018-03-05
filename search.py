import asyncio
import json

import aiohttp

import classes as cl
import database as db


async def search_ride_loop(conn, ride):
    while True:
        raw_ride = await db.search_ride(conn, ride)
        if raw_ride:
            return cl.Ride().unmarshall(raw_ride)


async def on_search_timeout(conn, ride):
    await asyncio.gather(db.remove_ride(conn, ride),
                         send_timeout_push(ride))
    print("Ride {} timeout".format(ride.ride_id))


async def send_timeout_push(ride):
    if not ride.user or not ride.user.fcm_token:
        print("Error trying to push ride timeout: fcm token missing")
        return None

    body = json.dumps({'to': ride.user.fcm_token,
                       'notification': {'title': "SPLIT",
                                        'body': "Попутчик не найден"},
                       'data': {'rideId': ride.ride_id,
                                'found': 0,
                                'timeout': 1}
                       })
    headers = {'content-type': 'application/json',
               'Authorization': 'key=' + cl.Consts.push_server_key()}

    async with aiohttp.ClientSession() as session:
        async with session.post(cl.Consts.push_url(), data=body, headers=headers) as resp:
            print(await resp.read())


async def on_ride_found(conn, ride_search, ride_found):
    await asyncio.gather(db.remove_ride(conn, ride_search),
                         send_ride_found_push(ride_search=ride_search, ride_found=ride_found))
    print("Ride {} timeout".format(ride_search.ride_id))


async def send_ride_found_push(ride_search, ride_found):
    if not ride_search.user or not ride_search.user.fcm_token:
        print("Error trying to push ride found: fcm token missing")
        return None

    body = json.dumps({'to': ride_search.user.fcm_token,
                       'notification': {'title': "SPLIT",
                                        'body': "Найден попутчик"},
                       'data': {'rideId': ride_search.ride_id,
                                'found': 1,
                                'phone': ride_found.user.phone}
                       })
    headers = {'content-type': 'application/json',
               'Authorization': 'key=' + cl.Consts.push_server_key()}

    async with aiohttp.ClientSession() as session:
        async with session.post(cl.Consts.push_url(), data=body, headers=headers) as resp:
            print(await resp.read())
