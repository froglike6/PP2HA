from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the pp2ha integration from a config entry."""
    # Sensor 플랫폼 설정을 완료할 때까지 기다립니다.
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Sensor 플랫폼 언로드를 await하여 안전하게 처리합니다.
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
