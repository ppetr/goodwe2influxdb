# How to build a Telegraf `execd` plugin in `async` Python 3

Telegraf's [`execd`] service plugin provides a convenient interface for
long-running custom input plugins.

[`execd`]: https://github.com/influxdata/telegraf/tree/master/plugins/inputs/execd

Taking advantage of that we build a small library
[`telegraf_plugin_main`](src/telegraf_plugin_main.py). The library takes an
`async` generator as an argument. The generator must `yield` a [`Point`] or
`List[Point]` in an infinite loop. It is paused by the library until Telegraf
asks for data, at which point the `yield` call is unblocked.

[`Point`]: https://influxdb-client.readthedocs.io/en/latest/api.html#influxdb_client.client.write.point.Point

The plugin must be configured with `signal = "STDIN"` and `data_format =
"influx"` in Telegraf's configuration.

Example:

```python
from influxdb_client import Point

async def query_data():
  # Do any initialization work.
  while True:
    temp = await my_get_temperature()
    yield influxdb_client.Point("my_measurement").field("temperature", temp)

def main():
  telegraf_plugin_main.main(query_data())

if __name__ == "__main__":
  main()
```

Assuming the plugin is saved in file `/opt/my_plugin.py`, Telegraf can be
configured as:

```ini
[[inputs.execd]]
command = ["/opt/my_plugin.py"]
signal = "STDIN"
data_format = "influx"
```
