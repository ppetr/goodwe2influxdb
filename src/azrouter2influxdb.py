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
"""Queries a local AZ-router device and emits its status to stdout.

A query is triggered by receiving a newline in stdin (Telegraf execd input
module's 'STDIN' signalling protocol).

Data is emitted in the InfluxDB line format.
"""

import aiohttp
import argparse
import logging
from numbers import Number
from typing import Any, Iterator, Tuple
from urllib.parse import urlunsplit

from influxdb_client import Point

import telegraf_plugin_main

_DEFAULT_HOST = 'azrouter.local'


async def status(session: aiohttp.ClientSession, host: str):
  url = urlunsplit(('http', host, '/api/v1/status', '', ''))
  async with session.get(url) as response:
    result = await response.json()
    logging.debug('AZrouter status response: %s', result)
    return result


async def power(session: aiohttp.ClientSession, host: str):
  url = urlunsplit(('http', host, '/api/v1/power', '', ''))
  async with session.get(url) as response:
    result = await response.json()
    logging.debug('AZrouter status response: %s', result)
    return result


def unroll_json(prefix: str, json) -> Iterator[Tuple[str, Any]]:
  if isinstance(json, str) or isinstance(json, Number) or isinstance(
      json, bool) or json is None:
    yield (prefix, json)
    return
  if prefix:
    prefix += '_'
  if isinstance(json, dict):
    for key, value in json.items():
      for pair in unroll_json(prefix + key, value):
        yield pair
  elif isinstance(json, list):
    try:
      for entry in json:
        yield (prefix + str(entry['id']), str(entry['value']))
    except KeyError as ex:
      raise KeyError('Expecting lists to contain just dictionaries just `id` '
                     'and `value` items.') from ex
  else:
    raise ValueError('Unknown type `{}`: {}'.format(
        type(json).__qualname__, json))


def build_point(measurement_name: str, tags: dict[str, str], json) -> Point:
  point = Point(measurement_name)
  for tag in tags:
    point.tag(tag, tags[tag])
  for key, value in unroll_json('', json):
    point.field(key, value)
  return point


async def query_data():
  logging.basicConfig(level=logging.INFO)
  parser = argparse.ArgumentParser(prog='azrouter2influxdb',
                                   description=__doc__)
  parser.add_argument('--ip_address', default=_DEFAULT_HOST)
  parser.add_argument('-m', '--measurement_name', default='azrouter')
  args = parser.parse_args()

  async with aiohttp.ClientSession() as session:
    while True:
      status_json = await status(session, args.ip_address)
      power_json = await power(session, args.ip_address)
      yield build_point(args.measurement_name, {}, {
          **status_json,
          **power_json
      })


def main():
  telegraf_plugin_main.main(query_data())


if __name__ == '__main__':
  main()
