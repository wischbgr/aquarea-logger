# aquarea-logger

Logs every value of a Panasonic Aquarea heatpump into sqlite, once per minute. Successor of
[LWZ303-RS232](../LWZ303-RS232) for the new heatpump: the parsing lives in the
[CIoT-ESP32-Aquarea](../../../media/veracrypt1/Sources/C++/platformio/CIoT-ESP32-Aquarea) firmware,
this only asks its web interface (`GET http://<ip>/json`) and stores the answer.

## Install

```
pipx install .                      # logger only
pipx install '.[plot]'              # with matplotlib for aquarea-visualize
```

or straight from the repository, `pipx install git+<url>`. Without pipx, `pip install .` in a venv
does the same. This gives the two commands `aquarea-logger` and `aquarea-visualize`.

## Running

```
aquarea-logger --once            # one sample, printed and stored, to check the connection
aquarea-logger                   # log forever, aligned to full minutes
aquarea-logger --host 192.168.176.50 --dir /var/lib/aquarea --interval 60
```

The databases go to `./log` in the working directory unless `--dir` says otherwise. Errors
(heatpump unreachable, bad answer) are logged and the next minute is tried again, the process never
gives up.

## Database

One file per month, `log/status_YYYY_MM.db`, same layout as before:

| Table | Content |
| --- | --- |
| `status` | `id`, `timestamp` (datetime, local time) plus one column per parameter, e.g. `MainInletTemp`, `DHWTemp`, `CompressorFreq`, `OutsideTemp` |
| `meta` | `name`, `unit`, `writable` for every parameter |

Values are the raw numbers of the protocol as the firmware reports them (`OperatingModeState` is
`4`, not `Heat+DHW`, see `/params` on the device for the meaning). A few are text, e.g. `Error`.
Columns are added automatically (by `dataset`) when the firmware starts reporting a new parameter.

```
sqlite3 log/status_2026_09.db "SELECT timestamp, OutsideTemp, DHWTemp FROM status ORDER BY timestamp DESC LIMIT 5"
```

## Plotting

```
aquarea-visualize --list
aquarea-visualize MainInletTemp MainOutletTemp OutsideTemp
aquarea-visualize DHWTemp DHWTargetTemp --from 2026-09-01 --to 2026-09-07
```

Needs the `plot` extra, see Install.

## Raspberry Pi

```
sudo apt install pipx
git clone <url> aquarea-logger && cd aquarea-logger
pipx install .
mkdir -p ~/aquarea
sudo cp aquarea-logger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aquarea-logger
journalctl -u aquarea-logger -f
```

The unit runs as `pi` with `/home/pi/aquarea` as working directory, so the databases end up in
`/home/pi/aquarea/log/`. Adjust `User`, `WorkingDirectory`, the path of the command and `--host` if
they differ. After a `git pull`, `pipx install --force .` updates the installed version. To fetch
the logs back: `scp pi@raspi:aquarea/log/*.db log/`.
