#!/usr/bin/env python3

# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import asyncio
import logging
import os
from typing import Optional
import sys

import goodwe
from influxdb_client import Point

# Transformation of unit names to field name suffixes.
_UNIT_MAP = {"%": "pct", "1": None}
_IGNORED_FIELDS = {"timestamp"}


async def detect_ip_address():
  response = await goodwe.search_inverters()
  logging.info("Received UDP broadcast: %s", response)
  return response.split(b",", 1)[0].decode('ASCII')


async def read_point(inverter, measurement_name: str, tags):
  runtime_data = await inverter.read_runtime_data()
  point = Point(measurement_name)
  for tag in tags:
    point.tag(tag, tags[tag])
  for sensor in inverter.sensors():
    data = runtime_data.get(sensor.id_)
    if data is None or sensor.id_ in _IGNORED_FIELDS:
      continue
    field = sensor.id_
    unit = _UNIT_MAP.get(sensor.unit, sensor.unit)
    if unit:
      field = f"{field}_{unit}"
    point.field(field, data)
  return point


async def print_sample(inverter, measurement_name: str, tags):
  print("Tags:")
  for tag in tags:
    print(f"{tag}: \t\t {tags[tag]}")
  print("\nRuntime data:")
  runtime_data = await inverter.read_runtime_data()
  for sensor in inverter.sensors():
    if sensor.id_ in runtime_data:
      print(
          f"{sensor.id_}: \t\t {sensor.name} = {runtime_data[sensor.id_]} {sensor.unit}"
      )
  print("\nIn line format:")
  point = await read_point(inverter, measurement_name, tags)
  print(point.to_line_protocol())


async def stdin_lines():
  """An asychronous generator that returns lines read from stdin."""
  reader = asyncio.StreamReader()
  reader_protocol = asyncio.StreamReaderProtocol(reader)
  await asyncio.get_event_loop().connect_read_pipe(lambda: reader_protocol,
                                                   sys.stdin)
  while True:
    line = await reader.readline()
    if not line:
      break
    yield line


async def get_runtime_data(ip_address: Optional[str], measurement_name: str):
  if ip_address is None:
    ip_address = await detect_ip_address()
  inverter = await goodwe.connect(ip_address)

  tags = {"ip_address": ip_address}
  for attr in [
      "model_name", "serial_number", "dsp1_version", "dsp2_version",
      "arm_version", "firmware"
  ]:
    value = getattr(inverter, attr, None)
    if value:
      tags[attr] = value

  if os.isatty(sys.stdout.fileno()):
    logging.info("stdout is a tty, printing sensor values")
    await print_sample(inverter, measurement_name, tags)
    return

  async for _ in stdin_lines():
    point = await read_point(inverter, measurement_name, tags)
    line = point.to_line_protocol()
    logging.debug("Emitting data in the line format: %s", line)
    print(line, flush=True)


def main():
  logging.basicConfig(level=logging.WARNING)
  parser = argparse.ArgumentParser(
      prog="goodwe2influxdb",
      description=
      "On every new line received on stdin reads data from a local Goodwe device and outputs it to stdout in the InfluxDB line format."
  )
  parser.add_argument("--ip_address")  # option that takes a value
  parser.add_argument("-m", "--measurement_name",
                      default="photovoltaic")  # option that takes a value
  args = parser.parse_args()

  asyncio.run(get_runtime_data(args.ip_address, args.measurement_name))


if __name__ == "__main__":
  main()
