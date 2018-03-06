import asyncio
import json

import aiohttp

import classes as cl
import database as db


async def find_ride(conn, ride):
    found_ride = await db.search_ride(conn=conn, ride=ride)
    if found_ride:
        await on_ride_found(conn=conn, search_ride=ride, found_ride=found_ride)
        return
    await asyncio.sleep(ride.duration)
    ride = await db.get_ride_by_id(conn, ride_id=ride.ride_id)
    if ride.found == 0 and ride.status != "cancelled":
        await send_timeout_push(ride)
        print("Timeout exceeded for ride {}".format(ride.ride_id))


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


async def on_ride_found(conn, search_ride, found_ride):
    await asyncio.gather(db.mark_as_found(conn=conn, ride1=search_ride, ride2=found_ride),
                         send_ride_found_push(ride_search=search_ride, phone=found_ride.user.phone),
                         send_ride_found_push(ride_search=found_ride, phone=search_ride.user.phone))
    print("Rides {} and {} found".format(search_ride.ride_id, found_ride.ride_id))


async def send_ride_found_push(ride_search, phone):
    if not ride_search.user or not ride_search.user.fcm_token:
        print("Error trying to push ride found: fcm token missing")
        return None

    body = json.dumps({'to': ride_search.user.fcm_token,
                       'notification': {'title': "SPLIT",
                                        'body': "Найден попутчик!"},
                       'data': {'rideId': ride_search.ride_id,
                                'found': 1,
                                'phone': phone}
                       })
    headers = {'content-type': 'application/json',
               'Authorization': 'key=' + cl.Consts.push_server_key()}

    async with aiohttp.ClientSession() as session:
        async with session.post(cl.Consts.push_url(), data=body, headers=headers) as resp:
            print(await resp.read())
