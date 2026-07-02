# HP Integrated Lights-Out (iLO) - Domoticz Plugin

A Domoticz Python plugin to read HP iLO sensor data via Redfish and manage supported HPE thermal settings.

---

## Requirements

- Domoticz with Python plugin support (version 2020.2 or newer recommended)
- Python 3
- The `redfish` Python library

### Install the Python library

```bash
pip3 install redfish
```

---

## Installation

1. Navigate to the Domoticz plugins directory:

   ```bash
   cd /home/<user>/domoticz/plugins
   ```

2. Clone the repository into a subdirectory:

   ```bash
   git clone https://github.com/MadPatrick/Domoticz_HP_ilo.git HP_ilo
   ```

3. Restart Domoticz:

   ```bash
   sudo systemctl restart domoticz
   ```

---

## Configuration

In Domoticz, go to **Settings -> Hardware** and add a new hardware device of type **HP Integrated Lights-Out (iLO)**.

| Parameter | Description | Default |
|-----------|-------------|---------|
| IP Address / Hostname | The IP address or hostname of the iLO interface | `192.168.1.1` |
| Port | TCP port of the iLO interface | `443` |
| Username | iLO login username | `Administrator` |
| Password | iLO login password | *(empty)* |
| Poll interval (sec) | How often data is retrieved, in seconds | `300` |
| Debug | Enable or disable verbose logging | `Off` |

---

## Created Devices

After the first start, the following Domoticz devices are created automatically:

| Unit | Name | Type | Description |
|------|------|------|-------------|
| 1 | `Server Name` | Text | Hostname of the server |
| 2 | `Power State` | Text | Power status |
| 3 | `Health` | Alert | Overall hardware health |
| 5 | `CPU Temperature` | Custom sensor | CPU temperature in Celsius |
| 6 | `Inlet Temperature` | Custom sensor | Inlet or ambient temperature in Celsius |
| 7 | `iLO Firmware` | Text | iLO firmware version |
| 8 | `Storage` | Alert | Storage or RAID health status |
| 9 | `Network` | Text | IP address and MAC address of the iLO interface |
| 10 | `Serial Number` | Text | Server serial number |
| 11 | `Model` | Text | Server model and BIOS version |
| 12 | `Minimum Fan Speed` | Dimmer | Sets the HPE `Oem/Hpe/FanPercentMinimum` value |
| 13 | `Thermal Configuration` | Selector menu | Sets the HPE `Oem/Hpe/ThermalConfiguration` value |
| 14 | `Power Regulator` | Selector menu | Sets the BIOS `PowerRegulator` attribute |

Unit `4` was previously used for fan RPM and is now removed automatically on plugin start. Fan control is handled through unit `12` (`Minimum Fan Speed`), which writes the supported HPE `FanPercentMinimum` setting.

---

## Fan Settings

### Minimum Fan Speed

The `Minimum Fan Speed` dimmer updates this Redfish field:

```http
PATCH /redfish/v1/Chassis/1/Thermal
```

```json
{
  "Oem": {
    "Hpe": {
      "FanPercentMinimum": 25
    }
  }
}
```

The plugin also reads the same value from `Oem/Hpe/FanPercentMinimum` and updates the Domoticz dimmer.

### Thermal Configuration

The `Thermal Configuration` device is a selector menu with these options:

- `Optimal Cooling`
- `Enhanced CPU Cooling`
- `Increased Cooling`
- `Maximum Cooling`
- `Smooth Cooling`

It updates this Redfish field:

```json
{
  "Oem": {
    "Hpe": {
      "ThermalConfiguration": "OptimalCooling"
    }
  }
}
```

After changing `Thermal Configuration`, iLO may restart or temporarily stop responding. The plugin therefore skips the immediate refresh after a successful change. The next normal poll will update the device state again.

### Power Regulator

The `Power Regulator` device is a selector menu with these options:

- `Dynamic Power Savings Mode`
- `Static Low Power Mode`
- `Static High Performance Mode`
- `OS Control Mode`

It updates the Redfish BIOS settings resource, usually through:

```http
PATCH /redfish/v1/Systems/1/Bios/Settings
```

```json
{
  "Attributes": {
    "PowerRegulator": "OSControl"
  }
}
```

Depending on the server model and firmware, this setting may be staged by iLO and may require a server reboot before it becomes active. The plugin updates the Domoticz selector immediately after iLO accepts the setting.

---

## Troubleshooting

- **iLO login failed** - Verify the username and password.
- **iLO communication error** - Check the IP address, port, and whether iLO is reachable from the Domoticz server.
- **Thermal Configuration changed, then iLO is briefly unreachable** - This can happen because iLO applies the setting and restarts or reloads its management interface. Wait for the next poll interval.
- **Power Regulator changed, but the server behavior does not change immediately** - BIOS power regulator changes may require a server reboot before becoming active.
- Enable **Debug** in the hardware settings for detailed Redfish request and response logging.

---

## License

This project was ported from the [Home Assistant HP iLO integration](https://www.home-assistant.io/integrations/hp_ilo).

