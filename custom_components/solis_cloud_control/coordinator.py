import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.solis_cloud_control.api.solis_api import SolisCloudControlApiClient, SolisCloudControlApiError
from custom_components.solis_cloud_control.inverters.inverter import Inverter

_LOGGER = logging.getLogger(__name__)

_COORDINATOR_NAME = "Solis Cloud Control"

_DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)
# SolisCloud device telemetry is refreshed on a ~5 minute cadence. Polling Eimo
# every minute created 5x control-channel traffic without reliably newer data and
# overlapped with daytime write bursts. Keep periodic polling aligned with the
# cloud/device refresh cadence; explicit post-control refresh remains available.
_EIMO_UPDATE_INTERVAL = timedelta(minutes=5)

_DEFAULT_REQUEST_REFRESH_COOLDOWN_SECONDS = 10
# Eimo cloud is noticeably more fragile during daytime control activity. Multiple
# entity writes are issued as separate /control requests, so coalesce their
# confirmation read into one delayed refresh after the write burst has settled.
_EIMO_REQUEST_REFRESH_COOLDOWN_SECONDS = 30

_DEFAULT_UPDATE_BATCH_DATA_MAX_RETRY_TIME_SECONDS = 180
_DEFAULT_UPDATE_DATA_MAX_RETRY_TIME_SECONDS = 60
_EIMO_UPDATE_BATCH_DATA_MAX_RETRY_TIME_SECONDS = 30
_EIMO_UPDATE_DATA_MAX_RETRY_TIME_SECONDS = 30

_EIMO_INVERTER_SN = "1033300254190112"


class SolisCloudControlData(dict[int, str | None]):
    pass


class SolisCloudControlCoordinator(DataUpdateCoordinator[SolisCloudControlData]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: SolisCloudControlApiClient,
        inverter: Inverter,
    ) -> None:
        is_eimo = inverter.info.serial_number == _EIMO_INVERTER_SN

        super().__init__(
            hass,
            _LOGGER,
            name=_COORDINATOR_NAME,
            config_entry=config_entry,
            update_interval=_EIMO_UPDATE_INTERVAL if is_eimo else _DEFAULT_UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=(
                    _EIMO_REQUEST_REFRESH_COOLDOWN_SECONDS
                    if is_eimo
                    else _DEFAULT_REQUEST_REFRESH_COOLDOWN_SECONDS
                ),
                immediate=False,
            ),
        )
        self._api_client = api_client
        self._inverter = inverter
        self._batch_retry_seconds = (
            _EIMO_UPDATE_BATCH_DATA_MAX_RETRY_TIME_SECONDS
            if is_eimo
            else _DEFAULT_UPDATE_BATCH_DATA_MAX_RETRY_TIME_SECONDS
        )
        self._data_retry_seconds = (
            _EIMO_UPDATE_DATA_MAX_RETRY_TIME_SECONDS
            if is_eimo
            else _DEFAULT_UPDATE_DATA_MAX_RETRY_TIME_SECONDS
        )

    async def _async_update_data(self) -> SolisCloudControlData:
        inverter_sn = self._inverter.info.serial_number
        try:
            results = await self._api_client.read_batch(
                inverter_sn,
                self._inverter.read_batch_cids,
                max_retry_time=self._batch_retry_seconds,
            )

            for read_cid in self._inverter.read_cids:
                results[read_cid] = await self._api_client.read(
                    inverter_sn,
                    read_cid,
                    max_retry_time=self._data_retry_seconds,
                )

            data = SolisCloudControlData({cid: results.get(cid) for cid in self._inverter.all_cids})
            _LOGGER.debug("Data read from API: %s", data)
            return data
        except SolisCloudControlApiError as error:
            raise UpdateFailed(error) from error

    async def control(
        self,
        cid: int,
        value: str,
        old_value: str | None = None,
    ) -> None:
        inverter_sn = self._inverter.info.serial_number
        _LOGGER.info("SolisCloud control SN=%s CID=%s value=%s", inverter_sn, cid, value)

        try:
            # Do not publish the requested value before Solis confirms the
            # command. Previously a B0072/timeout could leave HA showing the
            # desired state even though the inverter never accepted it.
            await self._api_client.control(inverter_sn, cid, value, old_value)

            if self.data:
                new_data = SolisCloudControlData(self.data)
                new_data[cid] = value
                self.async_set_updated_data(new_data)
        except SolisCloudControlApiError:
            _LOGGER.warning(
                "SolisCloud control NOT confirmed SN=%s CID=%s value=%s; keeping last confirmed coordinator value",
                inverter_sn,
                cid,
                value,
            )
            raise
        finally:
            # Debounced. For Eimo this is intentionally delayed 30 s so a group
            # of related slot writes produces one confirmation read instead of
            # read-after-every-write traffic.
            await self.async_request_refresh()
