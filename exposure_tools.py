from typing import Tuple, Union
import geopy.geocoders
import geopy.location
import datetime

USER_AGENT = "WA_Covid_Exposure_Locator"
TIMEOUT = 2

NOMINATIM = geopy.geocoders.Nominatim(user_agent=USER_AGENT, timeout=TIMEOUT)
PHOTON = geopy.geocoders.Photon(user_agent=USER_AGENT, timeout=TIMEOUT)
ARCGIS = geopy.geocoders.ArcGIS(user_agent=USER_AGENT, timeout=TIMEOUT)

GEOCODERS = [NOMINATIM, PHOTON, ARCGIS]
REVERSERS = [NOMINATIM, PHOTON, ARCGIS]

def geocode(street: str) -> geopy.location.Location:
    for geocoder in GEOCODERS:
        address = geocoder.geocode(street)
        if address: return address

def reverse_geocode(latitude: float, longitude: float) -> geopy.location.Location:
    coord_string = f"{latitude}, {longitude}"
    for geocoder in REVERSERS:
        address = geocoder.reverse(coord_string)
        if address: return address

class Exposure:
    def __init__(self, start_time: datetime.datetime, address: Union[geopy.location.Location, Tuple[float, float], str], location_descriptor: str=None, end_time: datetime.datetime=None, advice: str=None) -> None:
        self.start_time = start_time
        addr_type = type(address)
        if addr_type == geopy.location.Location:
            self.address = address
        elif addr_type == tuple:
            self.address = reverse_geocode(*address)
        else:
            self.address = geocode(address)
        self.location_descriptor = location_descriptor
        self.end_time = end_time
        self.advice = advice
    
    def __repr__(self) -> str:
        return f"{self.start_time.strftime('%H:%M %d/%m/%Y')} - {self.end_time.strftime('%H:%M %d/%m/%Y')} @ {self.address.address}"