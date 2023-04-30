# goodwe2influxdb - collect data from a GoodWe inverter to InfluxDB

*Disclaimer: This is not an official Google product.*

## Installation

Required Python version: >=3.7

In a cloned project directory run

```sh
sudo pip3 install .
```

Then set up [Telegraf] to run the script. For example create
`/etc/telegraf/telegraf.d/goodwe2influxdb.conf` with content:

```ini
[[inputs.execd]]
interval = "60s"
tags = {}
command = ["/usr/bin/env", "python3", "/mnt/ext/p/projects/goodwe/main.py"]
signal = "STDIN"
restart_delay = "60s"
data_format = "influx"
```

This automatically detects the IP address of a GoodWe module in your LAN (can
be overriden with `--ip_address`) and stores collected data in table
`photovoltaic` in the database (can be overriden with `--measurement_name`).

[Telegraf]: https://www.influxdata.com/time-series-platform/telegraf/
