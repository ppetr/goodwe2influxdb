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

import aiohttp
import argparse
import asyncio
import logging
from numbers import Number
import os
from typing import Any, Iterator, Optional, Tuple
from urllib.parse import urlunsplit
import sys

import goodwe
from influxdb_client import Point

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


async def build_point(measurement_name: str, tags: dict[str, str],
                      json) -> Point:
  point = Point(measurement_name)
  for tag in tags:
    point.tag(tag, tags[tag])
  for key, value in unroll_json('', json):
    point.field(key, value)
  return point


async def print_sample(measurement_name: str, tags: dict[str, str], json):
  logging.info('Response data: %s', str(json))
  point = await build_point(measurement_name, tags, json)
  logging.info('In line format: %s', point.to_line_protocol())


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


async def query_data(measurement_name: str,
                     host: Optional[str] = _DEFAULT_HOST):
  async with aiohttp.ClientSession() as session:
    if os.isatty(sys.stdout.fileno()):
      logging.info('stdout is a tty, printing a single query result')
      status_json = await status(session, host)
      power_json = await power(session, host)
      await print_sample(measurement_name, {}, {**status_json, **power_json})
      return

    async for _ in stdin_lines():
      result = await status(session, host)
      point = await build_point(measurement_name, {}, result)
      line = point.to_line_protocol()
      logging.debug('Emitting data in the line format: %s', line)
      print(line, flush=True)


def main():
  logging.basicConfig(level=logging.INFO)
  parser = argparse.ArgumentParser(
      prog='azrouter2influxdb',
      description='On every new line received on stdin reads data from '
      'a local AZ-router device and outputs it to stdout in the '
      'InfluxDB line format.')
  parser.add_argument('--ip_address', default='azrouter.local')
  parser.add_argument('-m', '--measurement_name', default='azrouter')
  args = parser.parse_args()

  asyncio.run(query_data(args.measurement_name, args.ip_address))


if __name__ == '__main__':
  main()
