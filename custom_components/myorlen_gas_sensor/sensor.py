"""Platform for sensor integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA, SensorStateClass, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, UnitOfVolume, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


from .invoices import InvoicesList
from .myorlen_api import myORLENApi, AUTH_METHOD_ORLEN_ID
from .ppg_reading_for_meter import MeterReading

_LOGGER = logging.getLogger(__name__)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional("auth_method", default=AUTH_METHOD_ORLEN_ID): cv.string,
})
SCAN_INTERVAL = timedelta(hours=8)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities,
):
    user = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    auth_method = config_entry.data.get("auth_method", AUTH_METHOD_ORLEN_ID)
    api = myORLENApi(user, password, auth_method)
    try:
        pgps = await hass.async_add_executor_job(api.meterList)
    except Exception as e:
        _LOGGER.error("Failed to initialize myORLEN sensor: %s", e)
        raise ValueError

    for x in pgps.ppg_list:
        meter_id = x.meter_number
        async_add_entities(
            [myORLENSensor(hass, api, meter_id, x.id_local),
             myORLENInvoiceSensor(hass, api, meter_id, x.id_local),
             myORLENCostTrackingSensor(hass, api, meter_id, x.id_local),
             myORLENLastInvoiceWearM3Sensor(hass, api, meter_id, x.id_local),
             myORLENLastInvoiceWearKWhSensor(hass, api, meter_id, x.id_local),
             myORLENConversionFactorSensor(hass, api, meter_id, x.id_local)],
            update_before_add=True)


async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: Callable,
        discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    api = myORLENApi(config.get(CONF_USERNAME), config.get(CONF_PASSWORD), config.get("auth_method", AUTH_METHOD_ORLEN_ID))
    try:
        pgps = await hass.async_add_executor_job(api.meterList)
    except Exception:
        raise ValueError

    for x in pgps.ppg_list:
        async_add_entities(
            [myORLENSensor(hass, api, x.meter_number, x.id_local),
             myORLENInvoiceSensor(hass, api, x.meter_number, x.id_local),
             myORLENCostTrackingSensor(hass, api, x.meter_number, x.id_local),
             myORLENLastInvoiceWearM3Sensor(hass, api, x.meter_number, x.id_local),
             myORLENLastInvoiceWearKWhSensor(hass, api, x.meter_number, x.id_local),
             myORLENConversionFactorSensor(hass, api, x.meter_number, x.id_local)],
            update_before_add=True)


class myORLENBaseSensor(SensorEntity):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        self._state = None
        self.hass = hass
        self.api = api
        self.meter_id = meter_id
        self.id_local = id_local

    @property
    def device_info(self):
        return {
            "identifiers": {("myorlen_gas_sensor", self.meter_id)},
            "name": f"myORLEN GAS METER ID {self.meter_id}",
            "manufacturer": "myORLEN",
            "model": self.meter_id,
            "via_device": None,
        }

    @property
    def name(self) -> str:
        return self.entity_name


class myORLENSensor(myORLENBaseSensor):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        super().__init__(hass, api, meter_id, id_local)
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._state: MeterReading | None = None
        self.entity_name = f"myORLEN Gas Sensor {meter_id} {id_local}"

    @property
    def unique_id(self) -> str | None:
        return f"myorlen_sensor{self.meter_id}_{self.id_local}"

    @property
    def state(self):
        if self._state is None:
            return None
        return self._state.value

    @property
    def extra_state_attributes(self):
        attrs = dict()
        if self._state is not None:
            attrs["wear"] = self._state.wear
            attrs["wear_unit_of_measurment"] = UnitOfVolume.CUBIC_METERS
        return attrs

    async def async_update(self):
        latest_meter_reading: MeterReading = await self.hass.async_add_executor_job(self.latestMeterReading)
        self._state = latest_meter_reading

    def latestMeterReading(self):
        readings = self.api.readingForMeter(self.meter_id).meter_readings
        if not readings:
            return None
        return max(readings, key=lambda z: z.reading_date_utc)


class myORLENInvoiceSensor(myORLENBaseSensor):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        super().__init__(hass, api, meter_id, id_local)
        self._attr_native_unit_of_measurement = "PLN"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._state: dict | None = None
        self.entity_name = f"myORLEN Gas Invoice Sensor {meter_id} {id_local}"

    @property
    def unique_id(self) -> str | None:
        return f"myorlen_invoice_sensor{self.meter_id}_{self.id_local}"

    @property
    def state(self):
        if self._state is None:
            return None
        return self._state.get("sumOfUnpaidInvoices")

    @property
    def extra_state_attributes(self):
        attrs = dict()
        if self._state is not None:
            attrs["next_payment_date"] = self._state.get("nextPaymentDate")
            attrs["next_payment_amount_to_pay"] = self._state.get("nextPaymentAmountToPay")
            attrs["next_payment_wear"] = self._state.get("nextPaymentWear")
            attrs["next_payment_wear_KWH"] = self._state.get("nextPaymentWearKWH")
        return attrs

    async def async_update(self):
        self._state = await self.hass.async_add_executor_job(self.invoices_summary)

    def invoices_summary(self):
        id_local = self.id_local
        invoices = self.api.invoices().invoices_list

        def upcoming_payment_for_meter(x: InvoicesList):
            return str(id_local) == str(x.id_pp) and not x.is_paid and not x.is_credit_note

        def to_amount_to_pay(x: InvoicesList):
            return x.amount_to_pay

        unpaid_invoices = list(filter(upcoming_payment_for_meter, invoices))
        sum_of_unpaid_invoices = sum(map(to_amount_to_pay, unpaid_invoices))

        next_payment_item = min(unpaid_invoices, key=lambda z: z.date) if unpaid_invoices else None

        return {
            "sumOfUnpaidInvoices": sum_of_unpaid_invoices,
            "nextPaymentDate": next_payment_item.paying_deadline_date if next_payment_item else None,
            "nextPaymentWear": next_payment_item.wear_m3 or next_payment_item.wear if next_payment_item else None,
            "nextPaymentWearKWH": next_payment_item.wear_kwh if next_payment_item else None,
            "nextPaymentAmountToPay": next_payment_item.amount_to_pay if next_payment_item else None,
        }


class myORLENCostTrackingSensor(myORLENBaseSensor):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        super().__init__(hass, api, meter_id, id_local)
        self._attr_native_unit_of_measurement = "PLN/m³"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._state: InvoicesList | None = None
        self.entity_name = f"myORLEN Gas Cost Tracking Sensor {meter_id} {id_local}"

    @property
    def unique_id(self) -> str | None:
        return f"myorlen_cost_tracking_sensor{self.meter_id}_{self.id_local}"

    @property
    def state(self):
        if self._state is None:
            return None
        gas_m3 = self._state.wear_m3 or self._state.wear
        if self._state.gross_amount is None or gas_m3 is None or gas_m3 == 0:
            return None
        return self._state.gross_amount / gas_m3

    @property
    def extra_state_attributes(self):
        attrs = dict()
        if self._state is not None:
            attrs["last_invoice_date"] = self._state.paying_deadline_date
            attrs["last_invoice_gross_amount"] = self._state.gross_amount
            attrs["last_invoice_wear_m3"] = self._state.wear_m3
            attrs["last_invoice_wear_KWH"] = self._state.wear_kwh
            attrs["last_invoice_number"] = self._state.number
        return attrs

    async def async_update(self):
        self._state = await self.hass.async_add_executor_job(self.latest_price)

    def latest_price(self):
        id_local = self.id_local
        invoices = self.api.invoices().invoices_list

        def has_valid_consumption(x: InvoicesList) -> bool:
            gas_m3 = x.wear_m3 or x.wear
            return (
                str(id_local) == str(x.id_pp)
                and gas_m3 is not None
                and gas_m3 != 0
                and x.gross_amount is not None
                and x.gross_amount != 0
                and not x.is_credit_note
            )

        valid_invoices = list(filter(has_valid_consumption, invoices))
        return max(valid_invoices, key=lambda z: z.date) if valid_invoices else None


def _latest_invoice_with_wear(api, id_local):
    """Zwraca najnowszą fakturę z niepustym zużyciem m3 i kWh dla danego licznika."""
    invoices = api.invoices().invoices_list
    valid = [
        x for x in invoices
        if str(id_local) == str(x.id_pp)
        and (x.wear_m3 or x.wear)
        and x.wear_kwh
        and not x.is_credit_note
    ]
    return max(valid, key=lambda z: z.date) if valid else None


class myORLENLastInvoiceWearM3Sensor(myORLENBaseSensor):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        super().__init__(hass, api, meter_id, id_local)
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._state: InvoicesList | None = None
        self.entity_name = f"myORLEN Gas Last Invoice Wear M3 {meter_id} {id_local}"

    @property
    def unique_id(self) -> str | None:
        return f"myorlen_last_invoice_wear_m3_{self.meter_id}_{self.id_local}"

    @property
    def state(self):
        if self._state is None:
            return None
        return self._state.wear_m3 or self._state.wear

    @property
    def extra_state_attributes(self):
        if self._state is None:
            return {}
        return {
            "invoice_number": self._state.number,
            "invoice_date": self._state.date,
            "period_start": self._state.start_date,
            "period_end": self._state.end_date,
        }

    async def async_update(self):
        self._state = await self.hass.async_add_executor_job(
            _latest_invoice_with_wear, self.api, self.id_local)


class myORLENLastInvoiceWearKWhSensor(myORLENBaseSensor):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        super().__init__(hass, api, meter_id, id_local)
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._state: InvoicesList | None = None
        self.entity_name = f"myORLEN Gas Last Invoice Wear KWH {meter_id} {id_local}"

    @property
    def unique_id(self) -> str | None:
        return f"myorlen_last_invoice_wear_kwh_{self.meter_id}_{self.id_local}"

    @property
    def state(self):
        if self._state is None:
            return None
        return self._state.wear_kwh

    @property
    def extra_state_attributes(self):
        if self._state is None:
            return {}
        return {
            "invoice_number": self._state.number,
            "invoice_date": self._state.date,
            "period_start": self._state.start_date,
            "period_end": self._state.end_date,
        }

    async def async_update(self):
        self._state = await self.hass.async_add_executor_job(
            _latest_invoice_with_wear, self.api, self.id_local)


class myORLENConversionFactorSensor(myORLENBaseSensor):
    def __init__(self, hass, api: myORLENApi, meter_id: str, id_local: int) -> None:
        super().__init__(hass, api, meter_id, id_local)
        self._attr_native_unit_of_measurement = "kWh/m³"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._state: InvoicesList | None = None
        self.entity_name = f"myORLEN Gas Conversion Factor {meter_id} {id_local}"

    @property
    def unique_id(self) -> str | None:
        return f"myorlen_conversion_factor_{self.meter_id}_{self.id_local}"

    @property
    def state(self):
        if self._state is None:
            return None
        m3 = self._state.wear_m3 or self._state.wear
        if not m3 or not self._state.wear_kwh:
            return None
        return round(self._state.wear_kwh / m3, 4)

    @property
    def extra_state_attributes(self):
        if self._state is None:
            return {}
        return {
            "invoice_number": self._state.number,
            "invoice_date": self._state.date,
            "wear_m3": self._state.wear_m3 or self._state.wear,
            "wear_kwh": self._state.wear_kwh,
        }

    async def async_update(self):
        self._state = await self.hass.async_add_executor_job(
            _latest_invoice_with_wear, self.api, self.id_local)
