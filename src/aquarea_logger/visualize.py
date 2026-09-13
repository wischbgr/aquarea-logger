#!/usr/bin/env python3
"""
Plots columns of the databases written by aquarea-logger.

    aquarea-visualize MainInletTemp MainOutletTemp OutsideTemp
    aquarea-visualize DHWTemp DHWTargetTemp --from 2026-09-01 --to 2026-09-07
    aquarea-visualize --list

Every monthly file that overlaps the requested range is read, so a plot may span months.
"""
import argparse
import glob
import os
from datetime import datetime

import dataset
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

LOGDIR = "log"


def databases(directory, from_date, to_date):
	"""Monthly files between from_date and to_date, oldest first."""
	paths = []
	for path in sorted(glob.glob(os.path.join(directory, "status_????_??.db"))):
		year, month = os.path.basename(path)[7:14].split("_")
		first = datetime(int(year), int(month), 1)
		if first <= to_date and (first.year, first.month) >= (from_date.year, from_date.month):
			paths.append(path)
	return paths


def columns(paths):
	names = {}
	for path in paths:
		db = dataset.connect(f"sqlite:///{path}")
		if "meta" in db:
			for row in db["meta"].find(order_by="name"):
				names[row["name"]] = row["unit"]
		db.close()
	return names


def load(paths, names, from_date, to_date):
	timestamps = []
	series = {name: [] for name in names}
	for path in paths:
		db = dataset.connect(f"sqlite:///{path}")
		table = db["status"]
		missing = [n for n in names if n not in table.columns]
		if missing:
			print(f"{os.path.basename(path)}: no column {', '.join(missing)}")
		else:
			for row in table.find(timestamp={"between": [from_date, to_date]}, order_by="timestamp"):
				timestamps.append(row["timestamp"])
				for name in names:
					series[name].append(row[name])
		db.close()
	return timestamps, series


def plot(timestamps, series, units, title):
	for name, values in series.items():
		label = f"{name} ({units[name]})" if units.get(name) else name
		plt.plot(timestamps, values, label=label)
	plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y %H:%M"))
	plt.gcf().autofmt_xdate()
	plt.xlabel("Time")
	plt.title(title)
	plt.legend()
	plt.grid(True, alpha=0.3)
	plt.show()


def main():
	parser = argparse.ArgumentParser(description="Plot logged Aquarea values.")
	parser.add_argument("names", nargs="*", help="parameter names to plot, see --list")
	parser.add_argument("--dir", default=LOGDIR, help="directory with the database files (default ./log in the working directory)")
	parser.add_argument("--from", dest="from_date", type=datetime.fromisoformat, default=datetime(2000, 1, 1))
	parser.add_argument("--to", dest="to_date", type=datetime.fromisoformat, default=datetime.now())
	parser.add_argument("--list", action="store_true", help="list the available parameters and exit")
	parser.add_argument("--title", default=None)
	args = parser.parse_args()

	paths = databases(args.dir, args.from_date, args.to_date)
	if not paths:
		parser.exit(1, f"no databases in {args.dir} for that range\n")
	units = columns(paths)

	if args.list or not args.names:
		for name, unit in units.items():
			print(f"{name:32} {unit or ''}")
		return

	unknown = [n for n in args.names if n not in units]
	if unknown:
		parser.exit(1, f"unknown parameter: {', '.join(unknown)}\n")

	timestamps, series = load(paths, args.names, args.from_date, args.to_date)
	if not timestamps:
		parser.exit(1, "no rows in that range\n")
	plot(timestamps, series, units, args.title or ", ".join(args.names))


if __name__ == "__main__":
	main()
