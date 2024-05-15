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
"""
Provides helper code to easily implement Telegraf execd input plugins.

The implementer needs to provide an async generator that indefinitely yields an
`influxdb_client.Point` or an iterable of `Point`s. The generator is
automatically triggered whenever Telegraf requests new data.

In Telegraf the plugin needs to be configured with `signal = "STDIN"`.
See https://github.com/influxdata/telegraf/blob/master/plugins/inputs/execd/README.md

Example:

    async def query_data():
      # Do initialization work.
      while True:
        yield influxdb_client.Point("my_measurement").field("temperature", 25.3)


    def main():
      telegraf_plugin_main.main(query_data())
"""

import asyncio
import logging
import os
from typing import AsyncIterable, Iterable
import sys

from influxdb_client import Point


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


def _emit_points(points: Iterable[Point]):
  for point in points:
    line = point.to_line_protocol()
    logging.debug('Emitting data in the line format: %s', line)
    print(line)
  print(flush=True, end='')


async def _async_main(points_fn: AsyncIterable[Point]):
  if os.isatty(sys.stderr.fileno()):
    async for point in points_fn:
      print('stderr is a tty, logging just a single query result:',
            file=sys.stderr)
      print(point, file=sys.stderr)
      return

  it = points_fn.__aiter__()
  async for _ in stdin_lines():
    try:
      points = await it.__anext__()
    except StopAsyncIteration:
      logging.exception('The generator function stopped unexpectedly')
      sys.exit(1)
    if isinstance(points, Point):
      points = [points]
    # Unblock the event loop by writing to stdout asynchronously.
    await asyncio.to_thread(_emit_points, points)


def main(points_fn: AsyncIterable[Point]):
  """Runs `points_fn` and emits its output to stdout."""
  asyncio.run(_async_main(points_fn))
