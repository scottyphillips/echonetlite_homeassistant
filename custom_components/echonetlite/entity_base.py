"""Base entity class for ECHONETLite entities."""

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.fan import FanEntity
from homeassistant.components.cover import CoverEntity
from homeassistant.components.light import LightEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EOJX_CLASS


class EchonetBaseEntity(CoordinatorEntity):
    """Base class for all ECHONETLite entities.
    
    Provides standardized:
    - device_info property for consistent device identification
    - _handle_coordinator_update method for data updates
    - Utility methods for EPC value retrieval and type checking
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the entity.
        
        Args:
            coordinator: The data update coordinator
            epc_code: EPC code identifying this entity
            config_item: Configuration dictionary for this entity
            options: Optional set of user-configurable option keys
        """
        super().__init__(coordinator)
        self._code = epc_code
        self._config = config_item
        self._options = options or set()
        
        # Extract common attributes from coordinator
        self._device_name = self._get_device_name()
        self._eojgc = coordinator._eojgc
        self._eojcc = coordinator._eojcc
        self._manufacturer = coordinator._manufacturer
        self._version = coordinator._version
        self._product_model = coordinator._product_model
        
        # Generate unique ID based on coordinator type
        if hasattr(coordinator, '_uidi') and coordinator._uidi:
            self._attr_unique_id = f"{coordinator._uidi}-{self._code}"
        else:
            self._attr_unique_id = f"{coordinator._uid}-{self._code}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity.
        
        Standardized implementation across all ECHONETLite entities.
        """
        return {
            "identifiers": {(DOMAIN, self.coordinator._uid, self._eojgc, self._eojcc)},
            "name": self._device_name,
            "manufacturer": self._manufacturer + (" (ECHONET)" if self._manufacturer else ""),
            "model": self._product_model or EOJX_CLASS.get(self._eojgc, {}).get(self._eojcc, "Unknown"),
            "sw_version": self._version,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator data update.
        
        Standardized implementation that sets availability based on 
        last update success status. Override in subclasses for additional processing.
        """
        self._attr_available = self.coordinator.last_update_success
        self.async_write_ha_state()

    def _get_device_name(self) -> str:
        """Generate device name from coordinator data."""
        manufacturer = self._manufacturer or ""
        name = getattr(self.coordinator, '_name', 'Unknown')
        
        if manufacturer:
            return f"{manufacturer} {name}"
        return name

    def _get_epc_value(self, epc_code) -> any:
        """Safely retrieve EPC value from coordinator data.
        
        Args:
            epc_code: The EPC code to look up
            
        Returns:
            The value if found and available, None otherwise
        """
        if not self.coordinator.last_update_success:
            return None
        
        epdata = getattr(self.coordinator, 'data', {}).get(epc_code)
        if epdata is None:
            return None
            
        return epdata.get('val') if isinstance(epdata, dict) else epdata

    def _is_select_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a select-type entity.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a select type (has string/enum values), False otherwise
        """
        if not epc_function_data or not isinstance(epc_function_data, list):
            return False
        
        # Check for dict with multiple entries indicating selectable options
        if len(epc_function_data) > 1 and isinstance(epc_function_data[1], dict):
            return True
            
        return False

    def _is_switch_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a switch-type entity.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a switch type (0/1 or on/off), False otherwise
        """
        if not epc_function_data or not isinstance(epc_function_data, list):
            return False
        
        # Check for dict with exactly 2 entries indicating binary state
        if len(epc_function_data) > 1 and isinstance(epc_function_data[1], dict):
            values = epc_function_data[1]
            return len(values) == 2
            
        return False

    def _is_numeric_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a numeric-type entity.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a numeric type (integer or float), False otherwise
        """
        if not epc_function_data:
            return False
        
        # Check for integer function indicator (first element == 1)
        if isinstance(epc_function_data, list) and len(epc_function_data) > 0:
            return epc_function_data[0] == 1
            
        return False

    def _is_time_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a time-type entity.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a time type (HH:MM format), False otherwise
        """
        if not epc_function_data or not isinstance(epc_function_data, list):
            return False
        
        # Check for time function indicator (first element == 5)
        if len(epc_function_data) > 0:
            return epc_function_data[0] == 5
            
        return False

    def _is_sensor_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a sensor-type entity.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a sensor type (read-only value), False otherwise
        """
        if not epc_function_data or not isinstance(epc_function_data, list):
            return False
        
        # Check for sensor function indicator (first element == 2)
        if len(epc_function_data) > 0:
            return epc_function_data[0] == 2
            
        return False

    def _is_datetime_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a datetime-type entity.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a datetime type (date/time value), False otherwise
        """
        if not epc_function_data or not isinstance(epc_function_data, list):
            return False
        
        # Check for datetime function indicator (first element == 3)
        if len(epc_function_data) > 0:
            return epc_function_data[0] == 3
            
        return False

    def _is_binary_sensor_type(self, epc_function_data) -> bool:
        """Check if EPC function data represents a binary sensor type.
        
        Args:
            epc_function_data: The EPC function configuration to check
            
        Returns:
            True if this is a binary sensor type (on/off status), False otherwise
        """
        if not epc_function_data or not isinstance(epc_function_data, list):
            return False
        
        # Check for binary sensor function indicator (first element == 4)
        if len(epc_function_data) > 0:
            return epc_function_data[0] == 4
            
        return False

    def _get_entity_name(self) -> str:
        """Get the display name for this entity.
        
        Returns:
            Formatted entity name based on configuration
        """
        if hasattr(self.coordinator, '_name'):
            manufacturer = self._manufacturer or ""
            base_name = self.coordinator._name
            
            if manufacturer:
                return f"{manufacturer} {base_name}"
            return base_name
        
        return "Unknown Device"


class EchonetClimateEntity(EchonetBaseEntity, ClimateEntity):
    """Base class for ECHONET climate entities.
    
    Combines base entity functionality with Home Assistant's ClimateEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the climate entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetSelectEntity(EchonetBaseEntity, SelectEntity):
    """Base class for ECHONET select entities.
    
    Combines base entity functionality with Home Assistant's SelectEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the select entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetSwitchEntity(EchonetBaseEntity, SwitchEntity):
    """Base class for ECHONET switch entities.
    
    Combines base entity functionality with Home Assistant's SwitchEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the switch entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetFanEntity(EchonetBaseEntity, FanEntity):
    """Base class for ECHONET fan entities.
    
    Combines base entity functionality with Home Assistant's FanEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the fan entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetCoverEntity(EchonetBaseEntity, CoverEntity):
    """Base class for ECHONET cover entities.
    
    Combines base entity functionality with Home Assistant's CoverEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the cover entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetLightEntity(EchonetBaseEntity, LightEntity):
    """Base class for ECHONET light entities.
    
    Combines base entity functionality with Home Assistant's LightEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the light entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetNumberEntity(EchonetBaseEntity, NumberEntity):
    """Base class for ECHONET number entities.
    
    Combines base entity functionality with Home Assistant's NumberEntity.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the number entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchotimeEntity(EchonetBaseEntity):
    """Base class for ECHONET time entities.
    
    Combines base entity functionality with custom time handling.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the time entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetBinarySensorEntity(EchonetBaseEntity):
    """Base class for ECHONET binary sensor entities.
    
    Combines base entity functionality with custom binary sensor handling.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the binary sensor entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)


class EchonetSensorEntity(EchonetBaseEntity):
    """Base class for ECHONET sensor entities.
    
    Combines base entity functionality with custom sensor handling.
    """

    def __init__(self, coordinator, epc_code, config_item, options=None):
        """Initialize the sensor entity."""
        EchonetBaseEntity.__init__(self, coordinator, epc_code, config_item, options)