#!/usr/bin/env python3
"""
Logs every value of a Panasonic Aquarea heatpump into sqlite, once per minute.

The heatpump is reached through the web interface of the CIoT-ESP32-Aquarea firmware:
GET http://<host>/json answers with every parameter as [{"n":name,"v":value,"t":text,"u":unit,"w":writable}, ...].

Like the old LWZ303 logger this writes one database per month, log/status_YYYY_MM.db, with a wide
`status` table holding a timestamp and one column per parameter. Columns are added as new
parameters show up, so a firmware update with new topics needs no migration. A `meta` table keeps
the unit and writability of every parameter for labelling plots.
"""
import argparse
import json
import logging
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

import dataset
import sqlalchemy.exc

from . import __version__

DEFAULT_HOST = "192.168.176.50"
DEFAULT_PORT = 80
DEFAULT_INTERVAL = 60
DEFAULT_TIMEOUT = 10
DEFAULT_LOGDIR = "log"

# parameter names are used as column names, so only accept what can go into a quoted identifier
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")

log = logging.getLogger("aquarea")


class Heatpump:
	def __init__(self, host, port=DEFAULT_PORT, timeout=DEFAULT_TIMEOUT):
		self.base = f"http://{host}:{port}"
		self.timeout = timeout

	def _get(self, path):
		with urllib.request.urlopen(self.base + path, timeout=self.timeout) as response:
			return json.load(response)

	def values(self):
		"""All readable parameters as a list of dicts with n, v, t, w and optionally u."""
		data = self._get("/json")
		if not isinstance(data, list):
			raise ValueError(f"unexpected answer from /json: {str(data)[:80]}")
		return data


class Store:
	"""Monthly sqlite files with a wide `status` table, one column per parameter.

	dataset adds columns as new parameters show up, so a firmware with new topics needs no migration.
	"""

	def __init__(self, directory):
		self.directory = directory
		self.path = None
		self.db = None

	def _open(self, now):
		path = os.path.join(self.directory, f"status_{now:%Y_%m}.db")
		if path == self.path and self.db is not None:
			return
		self.close()
		os.makedirs(self.directory, exist_ok=True)
		self.db = dataset.connect(f"sqlite:///{path}", sqlite_wal_mode=False)
		self.path = path
		log.info("using %s", path)

	def insert(self, now, entries):
		"""Writes one row from the /json list, returns the number of values stored."""
		self._open(now)
		row = {"timestamp": now}
		meta = []
		for entry in entries:
			name = entry.get("n")
			if not isinstance(name, str) or not NAME_RE.match(name) or name in ("id", "timestamp"):
				log.warning("skipping parameter with odd name %r", name)
				continue
			value = entry.get("v")
			# a null must not create the column: dataset would type it as text and sqlite would then
			# store every later number of that parameter as text as well
			if value is not None:
				row[name] = value
			meta.append({"name": name, "unit": entry.get("u"), "writable": bool(entry.get("w"))})

		if not meta:
			raise ValueError("heatpump answered without any values")

		self.db["status"].insert(row)
		# the table only exists after the first insert, create_index is a no-op once it is there
		self.db["status"].create_index(["timestamp"])
		self.db["meta"].upsert_many(meta, ["name"])
		return len(row) - 1

	def close(self):
		if self.db is not None:
			self.db.close()
			self.db = None
			self.path = None


class Logger:
	def __init__(self, heatpump, store, interval):
		self.heatpump = heatpump
		self.store = store
		self.interval = interval
		self.running = True

	def once(self):
		now = datetime.now().replace(microsecond=0)
		entries = self.heatpump.values()
		count = self.store.insert(now, entries)
		log.debug("%s: stored %d values", now, count)
		return entries

	def run(self):
		signal.signal(signal.SIGINT, self._stop)
		signal.signal(signal.SIGTERM, self._stop)
		while self.running:
			try:
				self.once()
			except (urllib.error.URLError, OSError, ValueError, dataset.util.DatasetError, sqlalchemy.exc.SQLAlchemyError) as e:
				log.error("%s", e)
			self._sleep_until_next_slot()
		self.store.close()

	def _stop(self, signum, frame):
		log.info("stopping")
		self.running = False

	def _sleep_until_next_slot(self):
		"""Waits until the next multiple of the interval, so rows land on full minutes."""
		target = (time.time() // self.interval + 1) * self.interval
		while self.running:
			remaining = target - time.time()
			if remaining <= 0:
				break
			time.sleep(min(remaining, 1))


def main():
	parser = argparse.ArgumentParser(description="Log all Aquarea heatpump values into monthly sqlite databases.")
	parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
	parser.add_argument("--host", default=DEFAULT_HOST, help=f"IP of the heatpump interface (default {DEFAULT_HOST})")
	parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port of the web interface (default {DEFAULT_PORT})")
	parser.add_argument("--dir", default=DEFAULT_LOGDIR, help="directory for the database files (default ./log in the working directory)")
	parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help=f"seconds between samples (default {DEFAULT_INTERVAL})")
	parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"http timeout in seconds (default {DEFAULT_TIMEOUT})")
	parser.add_argument("--once", action="store_true", help="fetch and store a single sample, print it and exit")
	parser.add_argument("-v", "--verbose", action="store_true", help="log every stored sample")
	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
	                    format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)

	logger = Logger(Heatpump(args.host, args.port, args.timeout), Store(args.dir), args.interval)
	if args.once:
		for entry in logger.once():
			unit = entry.get("u", "")
			print(f"{entry['n']:32} {str(entry.get('v')):>10} {unit:5} {entry.get('t', '')}")
		logger.store.close()
	else:
		log.info("logging %s every %d s into %s", logger.heatpump.base, args.interval, args.dir)
		logger.run()


if __name__ == "__main__":
	main()
