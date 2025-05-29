import asyncio
import binascii
from datetime import timedelta, date
import requests
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5
import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator, UpdateFailed
)

from .const import DOMAIN, INTRO_URL, LOGIN_URL, CHART_URL

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

def rsa_encrypt(mod_hex: str, plaintext: str) -> str:
    pub = RSA.construct((int(mod_hex, 16), 0x10001))
    return binascii.hexlify(PKCS1_v1_5.new(pub).encrypt(plaintext.encode())).decode()

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    credentials = config[DOMAIN]
    username = credentials[CONF_USERNAME]
    password = credentials[CONF_PASSWORD]

    session = requests.Session()
    # 로그인 로직은 동기 코드라 executor로 감싸줌
    async def login_and_fetch():
        # 1) 로그인
        r = session.get(INTRO_URL, timeout=10)
        sid, mod = session.cookies.get("JSESSIONID"), session.cookies.get("cookieRsa")
        if not (sid and mod):
            raise UpdateFailed("로그인 쿠키 획득 실패")
        payload = {
            "USER_ID": f"{sid}_{rsa_encrypt(mod, username)}",
            "USER_PWD": f"{sid}_{rsa_encrypt(mod, password)}",
            "APT_YN": "N"
        }
        r2 = session.post(LOGIN_URL, data=payload, allow_redirects=False, timeout=10)
        if r2.status_code != 302:
            raise UpdateFailed("로그인 실패")
        # 2) 차트 데이터 조회
        today = date.today().strftime("%Y-%m-%d")
        body = {"SELECT_DT": today, "selectType": "all", "TIME_TYPE": "1"}
        data = session.post(CHART_URL, json=body, timeout=10).json()
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=lambda: hass.async_add_executor_job(login_and_fetch),
        update_interval=timedelta(minutes=10),
    )

    # 최초 한 번 로드
    await coordinator.async_refresh()
    if coordinator.last_update_success:
        add_entities([KEPCOSensor(coordinator)], True)

class KEPCOSensor(Entity):
    def __init__(self, coordinator: DataUpdateCoordinator):
        self.coordinator = coordinator
        self._state = None

    @property
    def name(self):
        return f"{DOMAIN} Usage"

    @property
    def state(self):
        # 마지막 받은 리스트에서 원하는 값만 꺼내오기 (예: 마지막 시각의 kWh)
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
        # 수동 업데이트 시 coordinator에 위임
        await self.coordinator.async_request_refresh()
