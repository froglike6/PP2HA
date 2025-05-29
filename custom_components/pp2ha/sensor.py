import logging
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

    # 동기 로그인/데이터 조회 함수
    def login_and_fetch():
        # 1) 홈 페이지에서 쿠키 획득
        r = session.get(INTRO_URL, timeout=10)
        sid = session.cookies.get("JSESSIONID")
        mod = session.cookies.get("cookieRsa")
        if not (sid and mod):
            raise UpdateFailed("로그인 쿠키 획득 실패")

        # 2) RSA 암호화 함수
        def rsa_encrypt(mod_hex: str, plaintext: str) -> str:
            pub = RSA.construct((int(mod_hex, 16), 0x10001))
            return binascii.hexlify(
                PKCS1_v1_5.new(pub).encrypt(plaintext.encode())
            ).decode()

        # 3) 로그인 요청
        payload = {
            "USER_ID": f"{sid}_{rsa_encrypt(mod, username)}",
            "USER_PWD": f"{sid}_{rsa_encrypt(mod, password)}",
            "APT_YN": "N"
        }
        r2 = session.post(LOGIN_URL, data=payload, allow_redirects=False, timeout=10)
        if r2.status_code != 302:
            raise UpdateFailed("로그인 실패")

        # 4) 차트 데이터 요청 & JSON 파싱
        today = date.today().strftime("%Y-%m-%d")
        body = {"SELECT_DT": today, "selectType": "all", "TIME_TYPE": "1"}
        response = session.post(CHART_URL, json=body, timeout=10)
        try:
            data = response.json()
        except ValueError as exc:
            raise UpdateFailed(f"JSON 디코딩 실패: {exc}")

        # 5) 데이터 유효성 검사
        if not isinstance(data, list) or not data:
            raise UpdateFailed("차트 데이터가 비어 있습니다")
        last = data[-1]
        if "F_AP_QT" not in last:
            raise UpdateFailed("예상 키(F_AP_QT)가 없습니다")

        return data

    # 비동기 래퍼
    async def _async_update_data():
        return await hass.async_add_executor_job(login_and_fetch)

    # 코디네이터 생성
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=_async_update_data,
        update_interval=timedelta(minutes=10),
    )

    # 초기 업데이트
    await coordinator.async_refresh()
    if coordinator.last_update_success:
        async_add_entities([KEPCOSensor(coordinator, entry.entry_id)], True)

    return True


class KEPCOSensor(Entity):
    """Representation of KEPCO energy usage sensor."""
    def __init__(self, coordinator: DataUpdateCoordinator, entry_id: str):
        self.coordinator = coordinator
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
        try:
            return float(data[-1]["F_AP_QT"])
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.error("센서 상태 변환 실패: %s", err)
            return None

    @property
    def unit_of_measurement(self):
        return "kWh"

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()
