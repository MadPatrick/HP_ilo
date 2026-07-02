"""
HP Integrated Lights-Out (iLO) - Domoticz Python Plugin

Author: MadPatrick
Version: 1.2.0

<plugin key="hp_ilo" name="HP Integrated Lights-Out (iLO)" author="MadPatrick"
        version="1.2.0" wikilink="https://www.home-assistant.io/integrations/hp_ilo" externallink="https://github.com/MadPatrick/HP_ilo">
    <description>
        <br/><h2>HP Integrated Lights-Out (iLO)</h2>
        Reads sensor data from an HP iLO interface.
        <br/><br/>
        <h3>Parameters</h3>
        Enter the connection details for your HP iLO interface below.
    </description>
    <params>
        <param field="Address"  label="IP Address / Hostname" width="200px" required="true" default="192.168.1.1"/>
        <param field="Port"     label="Port"                  width="75px"  required="true" default="443"/>
        <param field="Username" label="Username"              width="150px" required="true" default="Administrator"/>
        <param field="Password" label="Password"              width="150px" required="true" default="" password="true"/>
        <param field="Mode1"    label="Poll interval (sec)"   width="75px"  required="true" default="300"/>
        <param field="Mode6"    label="Debug"                 width="100px">
            <options>
                <option label="Off" value="0" default="true"/>
                <option label="On"  value="1"/>
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz
import urllib3
import redfish
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Device Units ---

UNIT_SERVER_NAME = 1
UNIT_POWER_STATE = 2
UNIT_HEALTH      = 3
UNIT_LEGACY_FAN_SPEED = 4
UNIT_CPU_TEMP    = 5
UNIT_INLET_TEMP  = 6
UNIT_FIRMWARE    = 7
UNIT_STORAGE     = 8
UNIT_NETWORK     = 9
UNIT_SERIAL      = 10
UNIT_MODEL       = 11
UNIT_MIN_FAN_SPEED = 12
UNIT_THERMAL_CONFIG = 13
UNIT_POWER_REGULATOR = 14

THERMAL_CONFIG_SELECTOR_STYLE = "1"
POWER_REGULATOR_SELECTOR_STYLE = "1"

MIN_FAN_PERCENT = 10
MAX_FAN_PERCENT = 100

THERMAL_CONFIG_OPTIONS = [
    (10, "Optimal Cooling", ["OptimalCooling", "Optimal", "Optimal_Cooling"]),
    (20, "Enhanced CPU Cooling", ["EnhancedCPUCooling", "EnhancedCpuCooling", "EnhancedCooling", "Enhanced_CPU_Cooling"]),
    (30, "Increased Cooling", ["IncreasedCooling", "Increased", "Increased_Cooling"]),
    (40, "Maximum Cooling", ["MaximumCooling", "Maximum", "MaxCooling", "Maximum_Cooling"]),
    (50, "Smooth Cooling", ["SmoothCooling", "Smooth", "Smooth_Cooling"]),
]

POWER_REGULATOR_OPTIONS = [
    (10, "Dynamic Power Savings Mode", ["DynamicPowerSavings", "DynamicPowerSavingsMode", "DynamicPowerSavings_Mode"]),
    (20, "Static Low Power Mode", ["StaticLowPower", "StaticLowPowerMode", "StaticLowPower_Mode"]),
    (30, "Static High Performance Mode", ["StaticHighPerf", "StaticHighPerformance", "StaticHighPerformanceMode", "StaticHighPerformance_Mode"]),
    (40, "OS Control Mode", ["OSControl", "OsControl", "OSControlMode", "OSControl_Mode"]),
]

POWER_REGULATOR_KEYS = (
    "PowerRegulator",
    "PowerRegulatorMode",
    "PowerProfile",
)

MIN_FAN_SETTING_KEYS = (
    "FanPercentMinimum",
    "MinimumFanSpeedPercent",
    "MinimumFanSpeed",
    "MinFanSpeedPercent",
    "MinFanSpeed",
    "FanSpeedMinimum",
    "FanSpeedMin",
    "FanMinimumPercent",
)

THERMAL_CONFIG_KEYS = (
    "ThermalConfiguration",
    "ThermalConfig",
    "CoolingConfiguration",
    "CoolingMode",
    "FanConfiguration",
)

# --- Device Definitions ---

SENSOR_DEFINITIONS = [
    (UNIT_SERVER_NAME, "Server Name",       243, 19, {}),
    (UNIT_POWER_STATE, "Power State",       243, 19, {}),
    (UNIT_HEALTH,      "Health",            243, 22, {}),
    (UNIT_CPU_TEMP,    "CPU Temperature",    80,  5, {"Custom": "1;C"}),
    (UNIT_INLET_TEMP,  "Inlet Temperature",  80,  5, {"Custom": "1;C"}),
    (UNIT_FIRMWARE,    "iLO Firmware",      243, 19, {}),
    (UNIT_STORAGE,     "Storage",           243, 22, {}),
    (UNIT_NETWORK,     "Network",           243, 19, {}),
    (UNIT_SERIAL,      "Serial Number",     243, 19, {}),
    (UNIT_MODEL,       "Model",             243, 19, {}),
]

# --- Redfish Helper ---

class RedfishILO:
    def __init__(self, host, username, password, port=443):
        self.base_url = "https://{}:{}".format(host, port)
        self.client = redfish.redfish_client(
            base_url=self.base_url,
            username=username,
            password=password,
            default_prefix="/redfish/v1"
        )
        self.client.login(auth="session")

    def get(self, path):
        if path.startswith("http"):
            path = path.replace(self.base_url, "")
        response = self.client.get(path)
        if response.status not in [200, 201]:
            raise Exception("GET failed (HTTP {}): {}".format(response.status, path))
        return response.dict

    def patch(self, path, payload):
        if path.startswith("http"):
            path = path.replace(self.base_url, "")
        try:
            response = self.client.patch(path, body=payload)
        except TypeError:
            response = self.client.patch(path, payload)
        if response.status not in [200, 201, 202, 204]:
            detail = self._response_detail(response)
            if detail:
                raise Exception("PATCH failed (HTTP {}): {} -> {}".format(response.status, path, detail))
            raise Exception("PATCH failed (HTTP {}): {}".format(response.status, path))
        return getattr(response, "dict", {})

    def _response_detail(self, response):
        for attr in ("dict", "obj"):
            value = getattr(response, attr, None)
            if value:
                try:
                    return json.dumps(value)
                except Exception:
                    return str(value)
        for attr in ("text", "content"):
            value = getattr(response, attr, None)
            if value:
                try:
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", "replace")
                    return str(value)
                except Exception:
                    pass
        return ""

    def logout(self):
        try:
            self.client.logout()
        except Exception:
            pass

# --- Plugin ---

class BasePlugin:
    def __init__(self):
        self.debug               = False
        self.poll_interval       = 300
        self.heartbeat_count     = 0
        self.heartbeats_per_poll = 1
        self.min_fan_speed_supported = None
        self.thermal_config_supported = None
        self.power_regulator_supported = None

    def onStart(self):
        self.debug = Parameters["Mode6"] == "1"
        if self.debug:
            Domoticz.Debugging(1)
        try:
            self.poll_interval = int(Parameters["Mode1"])
        except Exception:
            self.poll_interval = 300
        heartbeat_sec = 10
        self.heartbeats_per_poll = max(1, self.poll_interval // heartbeat_sec)
        Domoticz.Heartbeat(heartbeat_sec)
        Domoticz.Log("HP iLO Redfish plugin started")
        if "hpilo" not in Images:
            Domoticz.Image("hpilo_icons.zip").Create()
            Domoticz.Log("Created custom icon: hpilo")
        self._delete_legacy_devices()
        self._create_devices()
        self._connect_and_update()

    def onStop(self):
        Domoticz.Log("Plugin stopped")

    def onHeartbeat(self):
        self.heartbeat_count += 1
        if self.heartbeat_count >= self.heartbeats_per_poll:
            self.heartbeat_count = 0
            self._connect_and_update()

    def onCommand(self, Unit, Command, Level, Color):
        if Unit == UNIT_MIN_FAN_SPEED:
            self._handle_min_fan_speed_command(Command, Level)
            return
        if Unit == UNIT_THERMAL_CONFIG:
            self._handle_thermal_config_command(Level)
            return
        if Unit == UNIT_POWER_REGULATOR:
            self._handle_power_regulator_command(Level)
            return

    def _delete_legacy_devices(self):
        if UNIT_LEGACY_FAN_SPEED in Devices:
            try:
                Devices[UNIT_LEGACY_FAN_SPEED].Delete()
                Domoticz.Log("Deleted legacy device: Fan Speed")
            except Exception as err:
                Domoticz.Error("Unable to delete legacy Fan Speed device: {}".format(err))

        if UNIT_THERMAL_CONFIG in Devices:
            try:
                options = getattr(Devices[UNIT_THERMAL_CONFIG], "Options", {})
                if options.get("SelectorStyle") != THERMAL_CONFIG_SELECTOR_STYLE:
                    Devices[UNIT_THERMAL_CONFIG].Delete()
                    Domoticz.Log("Recreated Thermal Configuration as selector menu")
            except Exception as err:
                Domoticz.Error("Unable to recreate Thermal Configuration selector: {}".format(err))
    def _create_devices(self):
        icon_id = Images["hpilo"].ID if "hpilo" in Images else 0
        for unit, name, type_num, subtype, options in SENSOR_DEFINITIONS:
            if unit not in Devices:
                Domoticz.Device(
                    Name=name,
                    Unit=unit,
                    Type=type_num,
                    Subtype=subtype,
                    Options=options,
                    Image=icon_id,
                    Used=1
                ).Create()
                Domoticz.Log("Created device: {}".format(name))


        if UNIT_MIN_FAN_SPEED not in Devices:
            Domoticz.Device(
                Name="Minimum Fan Speed",
                Unit=UNIT_MIN_FAN_SPEED,
                TypeName="Dimmer",
                Switchtype=7,
                Image=icon_id,
                Used=1
            ).Create()
            Domoticz.Log("Created device: Minimum Fan Speed")

        if UNIT_THERMAL_CONFIG not in Devices:
            Domoticz.Device(
                Name="Thermal Configuration",
                Unit=UNIT_THERMAL_CONFIG,
                TypeName="Selector Switch",
                Switchtype=18,
                Options={
                    "LevelActions": "|||||",
                    "LevelNames": "Off|Optimal Cooling|Enhanced CPU Cooling|Increased Cooling|Maximum Cooling|Smooth Cooling",
                    "LevelOffHidden": "true",
                    "SelectorStyle": THERMAL_CONFIG_SELECTOR_STYLE
                },
                Image=icon_id,
                Used=1
            ).Create()
            Domoticz.Log("Created device: Thermal Configuration")

        if UNIT_POWER_REGULATOR not in Devices:
            Domoticz.Device(
                Name="Power Regulator",
                Unit=UNIT_POWER_REGULATOR,
                TypeName="Selector Switch",
                Switchtype=18,
                Options={
                    "LevelActions": "|||",
                    "LevelNames": "Off|Dynamic Power Savings Mode|Static Low Power Mode|Static High Performance Mode|OS Control Mode",
                    "LevelOffHidden": "true",
                    "SelectorStyle": POWER_REGULATOR_SELECTOR_STYLE
                },
                Image=icon_id,
                Used=1
            ).Create()
            Domoticz.Log("Created device: Power Regulator")

    def _update_device(self, unit, value, nvalue=0):
        if unit not in Devices:
            return
        Devices[unit].Update(nValue=nvalue, sValue=str(value))
        if self.debug:
            Domoticz.Log("Updated unit {} = {}".format(unit, value))


    def _update_min_fan_speed(self, percent):
        if UNIT_MIN_FAN_SPEED not in Devices or percent is None:
            return
        level = self._clamp_fan_percent(percent)
        Devices[UNIT_MIN_FAN_SPEED].Update(nValue=2, sValue=str(level))
        if self.debug:
            Domoticz.Log("Updated minimum fan speed = {}%".format(level))

    def _update_thermal_config(self, config):
        if UNIT_THERMAL_CONFIG not in Devices or config is None:
            return
        level = self._thermal_config_to_level(config)
        if level is None:
            if self.debug:
                Domoticz.Log("Unknown thermal configuration value from iLO: {}".format(config))
            return
        Devices[UNIT_THERMAL_CONFIG].Update(nValue=1, sValue=str(level))
        if self.debug:
            Domoticz.Log("Updated thermal configuration = {}".format(config))

    def _update_power_regulator(self, value):
        if UNIT_POWER_REGULATOR not in Devices or value is None:
            return
        level = self._power_regulator_to_level(value)
        if level is None:
            if self.debug:
                Domoticz.Log("Unknown power regulator value from iLO: {}".format(value))
            return
        Devices[UNIT_POWER_REGULATOR].Update(nValue=1, sValue=str(level))
        if self.debug:
            Domoticz.Log("Updated power regulator = {}".format(value))

    def _restore_power_regulator_level(self, level):
        if UNIT_POWER_REGULATOR not in Devices or level is None:
            return
        Devices[UNIT_POWER_REGULATOR].Update(nValue=1, sValue=str(level))

    def _handle_min_fan_speed_command(self, Command, Level):
        previous_level = Devices[UNIT_MIN_FAN_SPEED].sValue if UNIT_MIN_FAN_SPEED in Devices else None
        if self.min_fan_speed_supported is False:
            Domoticz.Log("This iLO does not expose writable minimum fan speed via Redfish; restoring previous level")
            self._update_min_fan_speed(previous_level)
            self._connect_and_update()
            return

        percent = Level if Command == "Set Level" else previous_level
        percent = self._clamp_fan_percent(percent)
        Domoticz.Log("Setting iLO minimum fan speed to {}%".format(percent))

        try:
            rf = RedfishILO(
                host=Parameters["Address"],
                username=Parameters["Username"],
                password=Parameters["Password"],
                port=int(Parameters["Port"])
            )
            try:
                self._set_min_fan_speed_percent(rf, percent)
                self.min_fan_speed_supported = True
                self._update_min_fan_speed(percent)
                self._fetch_and_push(rf)
            finally:
                rf.logout()
        except Exception as err:
            if self._is_fan_control_not_writable(err):
                self.min_fan_speed_supported = False
                Domoticz.Error("iLO minimum fan speed is read-only or not exposed through this Redfish path")
            else:
                Domoticz.Error("Unable to set iLO minimum fan speed: {}".format(err))
            self._update_min_fan_speed(previous_level)
            self._connect_and_update()

    def _handle_thermal_config_command(self, Level):
        previous_level = Devices[UNIT_THERMAL_CONFIG].sValue if UNIT_THERMAL_CONFIG in Devices else None
        if self.thermal_config_supported is False:
            Domoticz.Log("This iLO does not expose writable thermal configuration via Redfish; restoring previous level")
            self._restore_thermal_config_level(previous_level)
            self._connect_and_update()
            return

        config = self._thermal_level_to_value(Level)
        if config is None:
            self._restore_thermal_config_level(previous_level)
            return

        Domoticz.Log("Setting iLO thermal configuration to {}".format(config))

        try:
            rf = RedfishILO(
                host=Parameters["Address"],
                username=Parameters["Username"],
                password=Parameters["Password"],
                port=int(Parameters["Port"])
            )
            try:
                self._set_thermal_configuration(rf, config)
                self.thermal_config_supported = True
                Devices[UNIT_THERMAL_CONFIG].Update(nValue=1, sValue=str(Level))
                Domoticz.Log("Thermal configuration accepted; skipping immediate refresh because iLO may restart")
                return
            finally:
                if not self.thermal_config_supported:
                    rf.logout()
        except Exception as err:
            if self._is_fan_control_not_writable(err):
                self.thermal_config_supported = False
                Domoticz.Error("iLO thermal configuration is read-only or not exposed through this Redfish path")
            else:
                Domoticz.Error("Unable to set iLO thermal configuration: {}".format(err))
            self._restore_thermal_config_level(previous_level)
            self._connect_and_update()

    def _handle_power_regulator_command(self, Level):
        previous_level = Devices[UNIT_POWER_REGULATOR].sValue if UNIT_POWER_REGULATOR in Devices else None
        if self.power_regulator_supported is False:
            Domoticz.Log("This iLO does not expose writable power regulator via Redfish; restoring previous level")
            self._restore_power_regulator_level(previous_level)
            self._connect_and_update()
            return

        value = self._power_level_to_value(Level)
        if value is None:
            self._restore_power_regulator_level(previous_level)
            return

        Domoticz.Log("Setting iLO power regulator to {}".format(value))

        try:
            rf = RedfishILO(
                host=Parameters["Address"],
                username=Parameters["Username"],
                password=Parameters["Password"],
                port=int(Parameters["Port"])
            )
            try:
                self._set_power_regulator(rf, value)
                self.power_regulator_supported = True
                Devices[UNIT_POWER_REGULATOR].Update(nValue=1, sValue=str(Level))
                Domoticz.Log("Power regulator accepted; a server reboot may be required before it becomes active")
            finally:
                rf.logout()
        except Exception as err:
            if self._is_fan_control_not_writable(err):
                self.power_regulator_supported = False
                Domoticz.Error("iLO power regulator is read-only or not exposed through this Redfish path")
            else:
                Domoticz.Error("Unable to set iLO power regulator: {}".format(err))
            self._restore_power_regulator_level(previous_level)
            self._connect_and_update()

    def _restore_thermal_config_level(self, level):
        if UNIT_THERMAL_CONFIG not in Devices or level is None:
            return
        Devices[UNIT_THERMAL_CONFIG].Update(nValue=1, sValue=str(level))
    def _clamp_fan_percent(self, value):
        try:
            percent = int(round(float(value)))
        except Exception:
            percent = MIN_FAN_PERCENT
        return max(MIN_FAN_PERCENT, min(MAX_FAN_PERCENT, percent))

    def _connect_and_update(self):
        try:
            rf = RedfishILO(
                host=Parameters["Address"],
                username=Parameters["Username"],
                password=Parameters["Password"],
                port=int(Parameters["Port"])
            )
            self._fetch_and_push(rf)
            rf.logout()
        except Exception as err:
            Domoticz.Error("Redfish connection error: {}".format(err))

    def _get_hpe_oem(self, data):
        oem = data.get("Oem", {})
        return oem.get("Hpe", oem.get("Hp", {}))

    def _get_thermal_setting_value(self, thermal, keys):
        hpe = self._get_hpe_oem(thermal)
        for source in (hpe, thermal):
            for key in keys:
                if source.get(key) is not None:
                    return source.get(key)
        return None

    def _power_level_to_value(self, level):
        try:
            level = int(level)
        except Exception:
            return None
        for item_level, label, aliases in POWER_REGULATOR_OPTIONS:
            if item_level == level:
                return aliases[0]
        return None

    def _power_regulator_to_level(self, value):
        normalized = str(value).replace(" ", "").replace("_", "").lower()
        for level, label, aliases in POWER_REGULATOR_OPTIONS:
            values = [label] + aliases
            for item in values:
                if normalized == str(item).replace(" ", "").replace("_", "").lower():
                    return level
        return None

    def _get_bios_attribute_value(self, bios, keys):
        attributes = bios.get("Attributes", {})
        for key in keys:
            if attributes.get(key) is not None:
                return attributes.get(key)
        for key in keys:
            if bios.get(key) is not None:
                return bios.get(key)
        return None

    def _thermal_level_to_value(self, level):
        try:
            level = int(level)
        except Exception:
            return None
        for item_level, label, aliases in THERMAL_CONFIG_OPTIONS:
            if item_level == level:
                return aliases[0]
        return None

    def _thermal_config_to_level(self, config):
        normalized = str(config).replace(" ", "").replace("_", "").lower()
        for level, label, aliases in THERMAL_CONFIG_OPTIONS:
            values = [label] + aliases
            for value in values:
                if normalized == str(value).replace(" ", "").replace("_", "").lower():
                    return level
        return None

    def _thermal_patch_targets(self, rf):
        root = rf.get("/redfish/v1/")
        chassis_path = root.get("Chassis", {}).get("@odata.id", "/redfish/v1/Chassis")
        chassis_uri = self._get_first_member_uri(rf, chassis_path)
        thermal_path = chassis_uri.rstrip("/") + "/Thermal"
        thermal = rf.get(thermal_path)
        settings_uri = thermal.get("@Redfish.Settings", {}).get("SettingsObject", {}).get("@odata.id")
        targets = []
        if settings_uri:
            targets.append(settings_uri)
        targets.append(thermal_path)
        if self.debug:
            Domoticz.Log("Thermal setting patch targets: {}".format(", ".join(targets)))
            Domoticz.Log("Thermal OEM HPE data: {}".format(self._json_for_log(self._get_hpe_oem(thermal))))
        return targets

    def _try_thermal_setting_payloads(self, rf, payloads):
        errors = []
        for path in self._thermal_patch_targets(rf):
            for payload in payloads:
                try:
                    rf.patch(path, payload)
                    Domoticz.Log("iLO accepted thermal setting update via {}".format(path))
                    return
                except Exception as err:
                    errors.append(str(err))
                    if self.debug:
                        Domoticz.Log("Thermal setting PATCH failed on {} with {}: {}".format(path, self._json_for_log(payload), err))
        raise Exception("thermal setting update not accepted by this iLO Redfish interface ({})".format("; ".join(errors)))

    def _set_min_fan_speed_percent(self, rf, percent):
        payloads = []
        for key in MIN_FAN_SETTING_KEYS:
            payloads.append({"Oem": {"Hpe": {key: percent}}})
            payloads.append({"Oem": {"Hp": {key: percent}}})
            payloads.append({key: percent})
        self._try_thermal_setting_payloads(rf, payloads)

    def _bios_settings_targets(self, rf):
        root = rf.get("/redfish/v1/")
        systems_path = root.get("Systems", {}).get("@odata.id", "/redfish/v1/Systems")
        system_uri = self._get_first_member_uri(rf, systems_path)
        bios_path = system_uri.rstrip("/") + "/Bios"
        bios = rf.get(bios_path)
        settings_uri = bios.get("@Redfish.Settings", {}).get("SettingsObject", {}).get("@odata.id")
        targets = []
        if settings_uri:
            targets.append(settings_uri)
        targets.append(bios_path + "/Settings")
        if self.debug:
            Domoticz.Log("BIOS setting patch targets: {}".format(", ".join(targets)))
            Domoticz.Log("BIOS attributes: {}".format(self._json_for_log(bios.get("Attributes", {}))))
        return targets

    def _try_bios_setting_payloads(self, rf, payloads):
        errors = []
        for path in self._bios_settings_targets(rf):
            for payload in payloads:
                try:
                    rf.patch(path, payload)
                    Domoticz.Log("iLO accepted BIOS setting update via {}".format(path))
                    return
                except Exception as err:
                    errors.append(str(err))
                    if self.debug:
                        Domoticz.Log("BIOS setting PATCH failed on {} with {}: {}".format(path, self._json_for_log(payload), err))
        raise Exception("BIOS setting update not accepted by this iLO Redfish interface ({})".format("; ".join(errors)))

    def _set_power_regulator(self, rf, value):
        payloads = []
        aliases = [value]
        for level, label, values in POWER_REGULATOR_OPTIONS:
            if value in values:
                aliases = values
                break
        for key in POWER_REGULATOR_KEYS:
            for item in aliases:
                payloads.append({"Attributes": {key: item}})
        self._try_bios_setting_payloads(rf, payloads)

    def _set_thermal_configuration(self, rf, config):
        payloads = []
        aliases = [config]
        for level, label, values in THERMAL_CONFIG_OPTIONS:
            if config in values:
                aliases = values
                break
        for key in THERMAL_CONFIG_KEYS:
            for value in aliases:
                payloads.append({"Oem": {"Hpe": {key: value}}})
                payloads.append({"Oem": {"Hp": {key: value}}})
                payloads.append({key: value})
        self._try_thermal_setting_payloads(rf, payloads)
    def _is_fan_control_not_writable(self, err):
        message = str(err)
        return (
            "PropertyNotWritableOrUnknown" in message or
            "HTTP 405" in message or
            "not accepted by this iLO Redfish interface" in message
        )

    def _get_first_member_uri(self, rf, collection_path):
        data    = rf.get(collection_path)
        members = data.get("Members", [])
        if not members:
            raise Exception("No members found in: {}".format(collection_path))
        uri = members[0].get("@odata.id")
        if not uri:
            raise Exception("No @odata.id in first member of: {}".format(collection_path))
        return uri


    def _json_for_log(self, value):
        try:
            text = json.dumps(value, sort_keys=True)
        except Exception:
            text = str(value)
        if len(text) > 900:
            return text[:900] + "..."
        return text


    def _fetch_and_push(self, rf):
        root = rf.get("/redfish/v1/")
        systems_path  = root.get("Systems",  {}).get("@odata.id", "/redfish/v1/Systems")
        chassis_path  = root.get("Chassis",  {}).get("@odata.id", "/redfish/v1/Chassis")
        managers_path = root.get("Managers", {}).get("@odata.id", "/redfish/v1/Managers")

        if self.debug:
            Domoticz.Log("Systems:  {}".format(systems_path))
            Domoticz.Log("Chassis:  {}".format(chassis_path))
            Domoticz.Log("Managers: {}".format(managers_path))

        # System
        try:
            system_uri  = self._get_first_member_uri(rf, systems_path)
            system      = rf.get(system_uri)
            model       = system.get("Model",        "Unknown")
            bios        = system.get("BiosVersion",  "")
            model_str   = "{} | BIOS: {}".format(model, bios) if bios else model
            health      = system.get("Status", {}).get("Health", "Unknown")

            self._update_device(UNIT_SERVER_NAME, system.get("HostName",     "Unknown"))
            self._update_device(UNIT_POWER_STATE, system.get("PowerState",   "Unknown"))
            self._update_device(UNIT_SERIAL,      system.get("SerialNumber", "Unknown"))
            self._update_device(UNIT_MODEL,       model_str)

            if str(health).upper() == "OK":
                Devices[UNIT_HEALTH].Update(nValue=1, sValue="All OK")
            else:
                Devices[UNIT_HEALTH].Update(nValue=4, sValue=str(health))
        except Exception as err:
            Domoticz.Error("System error: {}".format(err))

        # Power Regulator
        try:
            system_uri = self._get_first_member_uri(rf, systems_path)
            bios = rf.get(system_uri.rstrip("/") + "/Bios")
            self._update_power_regulator(self._get_bios_attribute_value(bios, POWER_REGULATOR_KEYS))
        except Exception as err:
            if self.debug:
                Domoticz.Log("Power regulator read error: {}".format(err))

        # Thermal
        try:
            thermal     = rf.get(self._get_first_member_uri(rf, chassis_path) + "/Thermal")
            self._update_min_fan_speed(self._get_thermal_setting_value(thermal, MIN_FAN_SETTING_KEYS))
            self._update_thermal_config(self._get_thermal_setting_value(thermal, THERMAL_CONFIG_KEYS))

            cpu_temp   = None
            inlet_temp = None
            for sensor in thermal.get("Temperatures", []):
                name    = sensor.get("Name", "").lower()
                reading = sensor.get("ReadingCelsius")
                if reading is None:
                    continue
                if "cpu" in name and cpu_temp is None:
                    cpu_temp = reading
                if "inlet ambient" in name or "ambient" in name:
                    inlet_temp = reading
                elif "inlet" in name and "board" not in name and inlet_temp is None:
                    inlet_temp = reading

            if cpu_temp is not None:
                self._update_device(UNIT_CPU_TEMP, cpu_temp)
            if inlet_temp is not None:
                self._update_device(UNIT_INLET_TEMP, inlet_temp)
        except Exception as err:
            Domoticz.Error("Thermal error: {}".format(err))

        # Firmware
        try:
            manager  = rf.get(self._get_first_member_uri(rf, managers_path))
            firmware = manager.get("FirmwareVersion", "Unknown")
            self._update_device(UNIT_FIRMWARE, firmware)
        except Exception as err:
            Domoticz.Error("Firmware error: {}".format(err))

        # Network
        try:
            manager_uri = self._get_first_member_uri(rf, managers_path)
            eth         = rf.get(self._get_first_member_uri(rf, manager_uri + "/EthernetInterfaces"))
            ipv4        = eth.get("IPv4Addresses", [])
            ip          = ipv4[0].get("Address", "N/A") if ipv4 else "N/A"
            mac         = eth.get("MACAddress", "N/A")
            self._update_device(UNIT_NETWORK, "IP: {} | MAC: {}".format(ip, mac))
        except Exception as err:
            Domoticz.Error("Network error: {}".format(err))

        # Storage
        try:
            system_uri   = self._get_first_member_uri(rf, systems_path)
            storage_path = system_uri.rstrip("/") + "/Storage"
            storage      = rf.get(storage_path)
            drives       = []
            any_bad      = False

            for member in storage.get("Members", []):
                uri = member.get("@odata.id")
                if not uri:
                    continue
                ctrl = rf.get(uri)
                for drive_ref in ctrl.get("Drives", []):
                    drive_uri = drive_ref.get("@odata.id")
                    if not drive_uri:
                        continue
                    try:
                        drive       = rf.get(drive_uri)
                        health      = drive.get("Status", {}).get("Health", "Unknown")
                        capacity    = drive.get("CapacityBytes", 0)
                        capacity_gb = round(capacity / 1e9, 1) if capacity else 0
                        media       = drive.get("MediaType", "Unknown")
                        drives.append({
                            "gb":     capacity_gb,
                            "media":  media,
                            "health": health
                        })
                        if str(health).upper() != "OK":
                            any_bad = True
                    except Exception:
                        pass

            if not drives:
                # iLO 4 fallback: no individual drive data, check controller health only
                bad, ok = [], []
                for member in storage.get("Members", []):
                    uri = member.get("@odata.id")
                    if not uri:
                        continue
                    try:
                        ctrl   = rf.get(uri)
                        name   = ctrl.get("Name", "Controller")
                        status = ctrl.get("Status", {}).get("Health", "Unknown")
                        if str(status).upper() != "OK":
                            bad.append("{}: {}".format(name, status))
                        else:
                            ok.append(name)
                    except Exception:
                        pass
                if bad:
                    Devices[UNIT_STORAGE].Update(nValue=4, sValue=" | ".join(bad))
                elif ok:
                    Devices[UNIT_STORAGE].Update(nValue=1, sValue="OK: {}".format(", ".join(ok)))
                else:
                    Devices[UNIT_STORAGE].Update(nValue=0, sValue="No storage data")
            else:
                parts = []
                for i, d in enumerate(drives, 1):
                    parts.append("Storage {}: {} | {} | {} GB".format(
                        i, d["health"], d["media"], d["gb"]
                    ))
                sValue = "\n".join(parts)
                nValue = 4 if any_bad else 1
                Devices[UNIT_STORAGE].Update(nValue=nValue, sValue=sValue)

        except Exception as err:
            if "404" in str(err):
                Devices[UNIT_STORAGE].Update(nValue=0, sValue="Not supported by this iLO version")
            else:
                Domoticz.Error("Storage error: {}".format(err))

#        Domoticz.Log("Redfish update completed")

# --- Domoticz Hooks ---

_plugin = BasePlugin()

def onStart():    _plugin.onStart()
def onStop():     _plugin.onStop()
def onHeartbeat(): _plugin.onHeartbeat()
def onCommand(Unit, Command, Level, Color): _plugin.onCommand(Unit, Command, Level, Color)









