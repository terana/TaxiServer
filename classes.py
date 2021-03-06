import settings


class Consts:
    @staticmethod
    def total_promo():
        return 5

    @staticmethod
    def promo_len():
        return 5

    @staticmethod
    def auth_token_len():
        return 15

    @staticmethod
    def search_duration():
        return settings.search_duration

    @staticmethod
    def start_radius_deg():
        r = settings.start_radius
        return r / 6400. * 180 / 3.14

    @staticmethod
    def dest_radius_deg():
        r = settings.destination_radius
        return r / 6400. * 180 / 3.14

    @staticmethod
    def start_radius_km():
        return settings.start_radius

    @staticmethod
    def dest_radius_km():
        return settings.destination_radius

    @staticmethod
    def push_server_key():
        return 'AAAAgIqW_1U:APA91bHG2hR8ta4hLLsfTEkuKttyWx-ZKLZIM5hpMKgNAwuSdMw9im4ZXkOEppZo2jjXYfBUVDXGURXOzLW8soIj8riTdPC1gEFSa37YyMRbyTg6Ug-jT16bMNmS98GdetxWf70KwVlB'

    @staticmethod
    def push_url():
        return 'https://fcm.googleapis.com/fcm/send'

    @staticmethod
    def default_locaion():
        return Geolocation(lat=55.755826, lng=37.617299900000035)


class ClientError(Exception):
    pass


class Marshallable:
    def marshall(self):
        raise NotImplementedError("Method marshall() should be implemented in child class")

    def unmarshall(self, db_tuple):
        raise NotImplementedError("Method unmarshall() should be implemented in child class")

    def __str__(self):
        data = self.marshall()
        return data.__str__()


class User(Marshallable):
    def __init__(self,
                 device_id=None,
                 fcm_token=None,
                 name=None,
                 phone=None,
                 promo=None,
                 used_promo=None,
                 region=None,
                 language=None,
                 os=None,
                 os_version=None,
                 app_version=None,
                 auth_token=None):
        self.device_id = device_id
        self.fcm_token = fcm_token
        self.name = name
        self.phone = phone
        self.promo = promo
        self.used_promo = used_promo
        self.region = region
        self.language = language
        self.os = os
        self.os_version = os_version
        self.app_version = app_version
        self.auth_token = auth_token

    def marshall(self):
        return {'device_id': self.device_id,
                'fcm_token': self.fcm_token,
                'name': self.name,
                'phone': self.phone,
                'promo': self.promo,
                'used_promo': self.used_promo,
                'region': self.region,
                'language': self.language,
                'os': self.os,
                'os_version': self.os_version,
                'app_version': self.app_version,
                'auth_token': self.auth_token}

    def unmarshall(self, db_tuple):
        if not db_tuple or len(db_tuple) < 12:
            return None
        self.device_id = db_tuple[0]
        self.fcm_token = db_tuple[1]
        self.name = db_tuple[2]
        self.phone = db_tuple[3]
        self.promo = db_tuple[4]
        self.used_promo = db_tuple[5]
        self.region = db_tuple[6]
        self.language = db_tuple[7]
        self.os = db_tuple[8]
        self.os_version = db_tuple[9]
        self.app_version = db_tuple[10]
        self.auth_token = db_tuple[11]
        return self

    def update(self, new_user):
        if new_user.device_id:
            self.device_id = new_user.device_id
        if new_user.fcm_token:
            self.fcm_token = new_user.fcm_token
        if new_user.name:
            self.name = new_user.name
        if new_user.phone:
            self.phone = new_user.phone
        if new_user.promo:
            self.promo = new_user.promo
        if new_user.used_promo:
            self.used_promo = new_user.used_promo
        if new_user.region:
            self.region = new_user.region
        if new_user.language:
            self.language = new_user.language
        if new_user.os:
            self.os = new_user.os
        if new_user.os_version:
            self.os_version = new_user.os_version
        if new_user.app_version:
            self.app_version = new_user.app_version
        return self


class Geolocation:
    def __init__(self, lat=None, lng=None):
        self.lat = lat
        self.lng = lng


class Ride(Marshallable):
    def __init__(self, ride_id=None,
                 begin_timestamp=None,
                 duration=None,
                 user=None,
                 mode=None,
                 start=None,
                 destination=None,
                 found_ride_id=0,
                 status=None,
                 rate=None):
        self.ride_id = ride_id
        self.begin_timestamp = begin_timestamp
        self.duration = duration
        self.user = user
        self.mode = mode
        self.start = start
        self.destination = destination
        self.found_ride_id = found_ride_id
        self.status = status
        self.rate = rate

    def marshall(self):
        return ({'ride_id': self.ride_id,
                 'begin_timestamp': self.begin_timestamp,
                 'duration': self.duration,
                 'user': self.user,
                 'mode': self.mode,
                 'start': self.start,
                 'destination': self.destination,
                 'found_ride_id': self.found_ride_id,
                 'status': self.status,
                 'rate': self.rate})

    def unmarshall(self, db_tuple):
        if not db_tuple or len(db_tuple) < 14:
            return None
        self.ride_id = db_tuple[0]
        self.begin_timestamp = db_tuple[1]
        self.duration = db_tuple[2]
        self.user = User(device_id=db_tuple[3],
                         phone=db_tuple[9],
                         fcm_token=db_tuple[10])
        self.mode = db_tuple[4]
        self.start = Geolocation(lat=db_tuple[5], lng=db_tuple[6])
        self.destination = Geolocation(lat=db_tuple[7], lng=db_tuple[8])
        self.found_ride_id = db_tuple[11]
        self.status = db_tuple[12]
        self.rate = db_tuple[13]
        return self
