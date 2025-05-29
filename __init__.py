"""KEPCO Energy Meter custom integration."""
import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """통합 초기 설정. configuration.yaml에 정의된 설정을 읽어서 처리해요."""
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error("설정이 없습니다. configuration.yaml에 kepco_meter 설정을 확인하세요.")
        return False

    # 필요한 추가 초기화가 있으면 여기에 작성
    _LOGGER.info("KEPCO Meter 설정 로드 완료")
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """UI로부터 설정할 때(옵션 플로우) 호출되는 부분이에요.
    이번 예제에선 사용하지 않으니 바로 True를 반환해도 돼요."""
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """엔트리 제거 시 정리할 부분이 있으면 여기서 처리해요."""
    return True
