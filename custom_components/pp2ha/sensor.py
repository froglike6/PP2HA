import logging
import asyncio
import binascii
from datetime import timedelta, date

import requests
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator, UpdateFailed
)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN, INTRO_URL, LOGIN_URL, CHART_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up sensor platform from a config entry."""
    creds = entry.data
    username = creds[CONF_USERNAME]
    password = creds[CONF_PASSWORD]

    session = requests.Session()

    def login_and_fetch():
        # 1) 초기 페이지 호출
        r = session.get(INTRO_URL, timeout=10)
        sid = session.cookies.get("JSESSIONID")
        mod = session.cookies.get("cookieRsa")
        if not (sid and mod):
            raise UpdateFailed("로그인 쿠키 획득 실패")

        def rsa_encrypt(mod_hex: str, plaintext: str) -> str:
            pub = RSA.construct((int(mod_hex, 16), 0x10001))
            return binascii.hexlify(
                PKCS1_v1_5.new(pub).encrypt(plaintext.encode())
            ).decode()

        payload = {
            "USER_ID": f"{sid}_{rsa_encrypt(mod, username)}",
            "USER_PWD": f"{sid}_{rsa_encrypt(mod, password)}",
            "APT_YN": "N"
        }
        r2 = session.post(LOGIN_URL, data=payload, allow_redirects=False, timeout=10)
        if r2.status_code != 302:
            raise UpdateFailed("로그인 실패")

        today = date.today().strftime("%Y-%m-%d")
        body = {"SELECT_DT": today, "selectType": "all", "TIME_TYPE": "1"}
        data = session.post(CHART_URL, json=body, timeout=10).json()
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=lambda: hass.async_add_executor_job(login_and_fetch),
        update_interval=timedelta(minutes=10),
    )


class KEPCOSensor(Entity):
    """Representation of KEPCO energy usage sensor."""
    def __init__(self, coordinator: DataUpdateCoordinator, entry_id: str):
        self.coordinator = coordinator
        self._state = None
        self._entry_id = entry_id

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._entry_id}"

    @property
    def name(self):
        return "KEPCO Usage"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "KEPCO Meter",
            "manufacturer": "KEPCO",
            "model": "Power Planner",
        }

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None
        return float(data[-1]["F_AP_QT"])

    @property
    def unit_of_measurement(self):
        return "kWh"

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()