#!/usr/bin/env python3

# Copyright 2024 Google LLC
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

"""Queries a local Goodwe inverter device and emits its status to stdout.

A query is triggered by receiving a newline in stdin (Telegraf execd input
module's 'STDIN' signalling protocol).

Data is emitted in the InfluxDB line format.
"""

import argparse
import logging
from typing import AsyncIterable

import goodwe
from influxdb_client import Point

import telegraf_plugin_main

# Transformation of unit names to field name suffixes.
_UNIT_MAP = {"%": "pct", "1": None}
_IGNORED_FIELDS = {"timestamp"}


async def detect_ip_address():
  response = await goodwe.search_inverters()
  logging.info("Received UDP broadcast: %s", response)
  return response.split(b",", 1)[0].decode("ASCII")


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


async def query_data() -> AsyncIterable[Point]:
  logging.basicConfig(level=logging.WARNING)
  parser = argparse.ArgumentParser(
      prog="goodwe2influxdb",
      description=__doc__)
  parser.add_argument("--ip_address")  # option that takes a value
  parser.add_argument("-m", "--measurement_name",
                      default="photovoltaic")  # option that takes a value
  args = parser.parse_args()

  if args.ip_address is None:
    args.ip_address = await detect_ip_address()
  inverter = await goodwe.connect(args.ip_address)

  tags = {"ip_address": args.ip_address}
  for attr in [
      "model_name", "serial_number", "dsp1_version", "dsp2_version",
      "arm_version", "firmware"
  ]:
    value = getattr(inverter, attr, None)
    if value:
      tags[attr] = value

  while True:
    yield await read_point(inverter, args.measurement_name, tags)


def main():
  telegraf_plugin_main.main(query_data())


if __name__ == "__main__":
  main()
