# aquarea-logger

Log all values of a Panasonic Aquarea heatpump into sqlite, once per minute. No Clouds.

Successor of [LWZ303-RS232](https://github.com/wladimir-computin/LWZ303-RS232) for the new heatpump.
The protocol lives in the CIoT-ESP32-Aquarea firmware (based on [HeishaMon](https://github.com/Egyras/HeishaMon)),
this just polls its web interface (`http://<ip>/json`) and stores the answer.

## Install

```bash
pipx install git+https://github.com/wischbgr/aquarea-logger
pipx install 'git+https://github.com/wischbgr/aquarea-logger#egg=aquarea-logger[plot]'   # with plotting
```

## Usage

```bash
aquarea-logger --host 192.168.176.50 --once

2026-09-13 18:00:00,012 INFO using log/status_2026_09.db
HeatpumpState                             1       On
OperatingModeState                        4       Heat+DHW
MainInletTemp                          30.5 °C
MainOutletTemp                         35.0 °C
OutsideTemp                             8.0 °C
CompressorFreq                           42 Hz
DHWTemp                                47.5 °C
...
PowerConsumptionNow                     890 W
PowerProductionNow                     3400 W
COPNow                                 3.82       3.82
```

```bash
aquarea-logger --host 192.168.176.50        # log forever, one row per full minute into ./log
aquarea-logger --help
```

Values are the raw numbers of the protocol (`OperatingModeState` is `4`, not `Heat+DHW`).

## Database

One file per month, `log/status_YYYY_MM.db`.

* `status`: `id`, `timestamp` and one column per parameter (`MainInletTemp`, `DHWTemp`, `CompressorFreq`, ...)
* `meta`: `name`, `unit`, `writable` of every parameter

New parameters become new columns automatically.

```bash
sqlite3 log/status_2026_09.db "SELECT timestamp, OutsideTemp, DHWTemp FROM status ORDER BY timestamp DESC LIMIT 5"
```

## Plotting

```bash
aquarea-visualize --list
aquarea-visualize MainInletTemp MainOutletTemp OutsideTemp
aquarea-visualize DHWTemp DHWTargetTemp --from 2026-09-01 --to 2026-09-07
```

## Raspberry Pi

```bash
sudo apt install pipx
pipx install git+https://github.com/wischbgr/aquarea-logger
mkdir ~/aquarea
sudo cp aquarea-logger.service /etc/systemd/system/
sudo systemctl enable --now aquarea-logger
journalctl -u aquarea-logger -f
```

Runs as `pi` in `/home/pi/aquarea`, databases end up in `/home/pi/aquarea/log/`. Adjust the unit file if your paths differ.
