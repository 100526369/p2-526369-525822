#!/usr/bin/env python3
"""
Test battery for Part 1 (sol-1.py + the compiled sol-1 executable).

Usage (build first with `make`, then run from the directory that contains
vertices.csv and edges.csv):

    python3 parte-1/test_parte1.py -v

Optional environment variables:
    SOL1        path to sol-1.py              (default: next to this file)
    DATA_DIR    folder with the two CSV files (default: cwd, then this
                                               folder, then its parent)
    N_RANDOM    number of random airport pairs (default: 150)
    TIME_LIMIT  seconds allowed per run        (default: 30)

The reference answers come from an independent Dijkstra written here, which
uses the airport coordinates and the Earth radius stated in the dataset README
(6371.0088 km). The reference is itself checked against the haversine_km column
of edges.csv.
"""

import csv
import heapq
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOL = Path(os.environ.get("SOL1", HERE / "sol-1.py"))
EARTH_RADIUS_KM = 6371.0088          # mean radius used by the dataset README
TOL = 0.011                          # output is rounded to two decimals
N_RANDOM = int(os.environ.get("N_RANDOM", "150"))
TIME_LIMIT_S = float(os.environ.get("TIME_LIMIT", "30"))

DATA_DIR = None
REF = None


# --------------------------------------------------------------------------
# Independent reference implementation
# --------------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (inputs in degrees)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, a))))


class Reference:
    def __init__(self, vertices_path, edges_path):
        self.coords = {}        # code -> (lat, lon)
        self.adj = {}           # origin -> {destination: km}
        self.dataset_cost = {}  # (origin, destination) -> haversine_km column

        with open(vertices_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row["acronym"].strip().upper()
                self.coords[code] = (float(row["latitude_deg"]),
                                     float(row["longitude_deg"]))

        with open(edges_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                o = row["origin"].strip().upper()
                d = row["destination"].strip().upper()
                if o == d or o not in self.coords or d not in self.coords:
                    continue
                if d not in self.adj.setdefault(o, {}):
                    self.adj[o][d] = haversine(*self.coords[o], *self.coords[d])
                    self.dataset_cost[(o, d)] = float(row["haversine_km"])

    def shortest(self, source, target):
        """Return (distance, route) or None when there is no route."""
        if source not in self.coords or target not in self.coords:
            return None
        dist, prev, done = {source: 0.0}, {}, set()
        heap = [(0.0, source)]
        while heap:
            g, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            if u == target:
                break
            for v, cost in self.adj.get(u, {}).items():
                if g + cost < dist.get(v, math.inf):
                    dist[v] = g + cost
                    prev[v] = u
                    heapq.heappush(heap, (g + cost, v))
        if target not in dist:
            return None
        route = [target]
        while route[-1] != source:
            route.append(prev[route[-1]])
        return dist[target], route[::-1]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def find_data_dir():
    candidates = []
    if os.environ.get("DATA_DIR"):
        candidates.append(Path(os.environ["DATA_DIR"]))
    candidates += [Path.cwd(), HERE, HERE.parent]
    for c in candidates:
        if (c / "vertices.csv").is_file() and (c / "edges.csv").is_file():
            return c.resolve()
    raise FileNotFoundError(
        "vertices.csv / edges.csv not found; run from their folder or set DATA_DIR")


def setUpModule():
    global DATA_DIR, REF
    DATA_DIR = find_data_dir()
    REF = Reference(DATA_DIR / "vertices.csv", DATA_DIR / "edges.csv")


def link_data(work):
    for name in ("vertices.csv", "edges.csv"):
        try:
            os.symlink(DATA_DIR / name, work / name)
        except OSError:
            shutil.copy(DATA_DIR / name, work / name)


def run_sol(cwd, *args):
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(SOL), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, timeout=TIME_LIMIT_S)
    return proc, time.perf_counter() - start


class Checks(unittest.TestCase):
    """Shared assertions (contains no tests itself)."""

    def parse_output(self, proc, out_file):
        """Check format and that stdout and the output file agree."""
        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(len(lines), 2,
                         f"stdout must have exactly two lines, got {lines!r}")
        self.assertRegex(lines[0], r"^\d+\.\d{2}$")
        self.assertRegex(lines[1], r"^[A-Z]{3}( - [A-Z]{3})*$")
        self.assertTrue(out_file.is_file(), "output file was not created")
        self.assertEqual(out_file.read_text().strip().splitlines(), lines,
                         "output file differs from standard output")
        return float(lines[0]), lines[1].split(" - ")

    def assert_fails_cleanly(self, proc, out_file):
        self.assertNotEqual(proc.returncode, 0, "expected a non-zero exit code")
        self.assertFalse(out_file.exists(), "no output file should be written")
        self.assertTrue(proc.stderr.strip(), "expected an error message on stderr")

    def assert_optimal(self, origin, destination, dist, route):
        ref = REF.shortest(origin, destination)
        self.assertIsNotNone(ref, "reference finds no route but the program did")
        self.assertAlmostEqual(
            dist, ref[0], delta=TOL,
            msg=f"{origin}->{destination}: got {dist}, optimum is {ref[0]:.3f}. "
                "A difference of about 1e-6 relative usually means the Earth "
                "radius is not 6371.0088")
        self.assertEqual(route[0], origin)
        self.assertEqual(route[-1], destination)
        self.assertEqual(len(set(route)), len(route), "route repeats an airport")
        total = 0.0
        for a, b in zip(route, route[1:]):
            self.assertIn(b, REF.adj.get(a, {}), f"no flight {a}->{b} in edges.csv")
            total += REF.adj[a][b]
        self.assertAlmostEqual(total, dist, delta=TOL,
                               msg="reported distance does not match the route")


class RealDataCase(Checks):
    """Each test gets a scratch folder with the CSVs linked in."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="p1_"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        link_data(self.work)

    def solve(self, origin, destination, name="case"):
        (self.work / f"{name}.in").write_text(f"{origin}\n{destination}\n")
        out = self.work / f"{name}.out"
        proc, _ = run_sol(self.work, f"{name}.in", out.name)
        return proc, out


# --------------------------------------------------------------------------
# 1. The reference itself and the data
# --------------------------------------------------------------------------

class TestReferenceData(unittest.TestCase):
    def test_haversine_matches_dataset_column(self):
        worst = max(abs(REF.adj[o][d] - c) for (o, d), c in REF.dataset_cost.items())
        self.assertLess(worst, 0.01,
                        f"reference differs from haversine_km by {worst:.4f} km")

    def test_statement_leg_values(self):
        self.assertAlmostEqual(REF.adj["MAD"]["VIE"], 1805.96, delta=0.01)


# --------------------------------------------------------------------------
# 2. Command line and files
# --------------------------------------------------------------------------

class TestCommandLine(RealDataCase):
    def test_script_is_directly_executable(self):
        head = SOL.read_bytes()[:30]
        self.assertTrue(head.startswith(b"#!/usr/bin/env python3\n"),
                        f"shebang must be the very first line, got {head!r}")
        self.assertTrue(os.access(SOL, os.X_OK), "sol-1.py is not executable")

    def test_runs_directly_with_shebang(self):
        (self.work / "case.in").write_text("MAD\nBTS\n")
        proc = subprocess.run([str(SOL), "case.in", "case.out"], cwd=self.work,
                              capture_output=True, text=True, timeout=TIME_LIMIT_S)
        dist, route = self.parse_output(proc, self.work / "case.out")
        self.assertEqual(route[0], "MAD")

    def test_wrong_number_of_arguments(self):
        for args in ([], ["a.in"], ["a.in", "a.out", "extra"]):
            with self.subTest(args=args):
                proc, _ = run_sol(self.work, *args)
                self.assertNotEqual(proc.returncode, 0)

    def test_missing_input_file(self):
        proc, _ = run_sol(self.work, "nope.in", "o.out")
        self.assert_fails_cleanly(proc, self.work / "o.out")

    def test_fails_without_csv_files_in_cwd(self):
        empty = Path(tempfile.mkdtemp(prefix="p1_empty_"))
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        (empty / "case.in").write_text("MAD\nBTS\n")
        proc, _ = run_sol(empty, "case.in", "case.out")
        self.assert_fails_cleanly(proc, empty / "case.out")

    def test_relative_subfolder_and_absolute_paths(self):
        sub = self.work / "sub"
        sub.mkdir()
        (sub / "in.txt").write_text("MAD\nBTS\n")
        proc, _ = run_sol(self.work, "sub/in.txt", "sub/out.txt")
        self.parse_output(proc, sub / "out.txt")
        proc, _ = run_sol(self.work, sub / "in.txt", sub / "abs.out")
        self.parse_output(proc, sub / "abs.out")

    def test_existing_output_is_overwritten(self):
        (self.work / "case.out").write_text("junk\n" * 20)
        proc, out = self.solve("MAD", "BTS")
        self.parse_output(proc, out)

    def test_deterministic(self):
        first = self.solve("MAD", "SYD", "a")
        second = self.solve("MAD", "SYD", "b")
        self.assertEqual(first[0].stdout, second[0].stdout)


# --------------------------------------------------------------------------
# 3. Input file variants
# --------------------------------------------------------------------------

class TestInputParsing(RealDataCase):
    EXPECTED = (1860.33, ["MAD", "TLS", "BTS"])

    def check_variant(self, content):
        (self.work / "v.in").write_bytes(content)
        proc, _ = run_sol(self.work, "v.in", "v.out")
        dist, route = self.parse_output(proc, self.work / "v.out")
        self.assertAlmostEqual(dist, self.EXPECTED[0], delta=0.005)
        self.assertEqual(route, self.EXPECTED[1])

    def test_variants(self):
        variants = {
            "plain": b"MAD\nBTS\n",
            "lowercase": b"mad\nbts\n",
            "mixed case": b"Mad\nbTs\n",
            "windows line endings": b"MAD\r\nBTS\r\n",
            "no trailing newline": b"MAD\nBTS",
            "surrounding spaces": b"  MAD  \n\tBTS \n",
            "extra trailing lines": b"MAD\nBTS\n\n\nignored\n",
        }
        for name, content in variants.items():
            with self.subTest(variant=name):
                self.check_variant(content)


# --------------------------------------------------------------------------
# 4. Known answers on the real data
# --------------------------------------------------------------------------

class TestKnownCases(RealDataCase):
    def test_known_answers(self):
        cases = [
            ("MAD", "BTS", 1860.33, "MAD - TLS - BTS"),
            ("MAD", "VIE", 1805.96, "MAD - VIE"),
            ("MAD", "JFK", 5762.19, "MAD - JFK"),
            ("MAD", "SYD", 17692.73, "MAD - DXB - SYD"),
            ("MAD", "MAD", 0.00, "MAD"),
        ]
        for o, d, dist, route in cases:
            with self.subTest(origin=o, destination=d):
                proc, out = self.solve(o, d)
                got_dist, got_route = self.parse_output(proc, out)
                self.assertAlmostEqual(got_dist, dist, delta=0.011)
                self.assertEqual(" - ".join(got_route), route)

    def test_not_symmetric_graph_is_respected(self):
        pairs = [(o, d) for o in ("MAD", "BTS", "KSC", "TLS") for d in ("MAD", "BTS", "KSC", "TLS")
                 if o != d]
        for o, d in pairs:
            with self.subTest(origin=o, destination=d):
                proc, out = self.solve(o, d)
                if REF.shortest(o, d) is None:
                    self.assertNotEqual(proc.returncode, 0)
                else:
                    dist, route = self.parse_output(proc, out)
                    self.assert_optimal(o, d, dist, route)


# --------------------------------------------------------------------------
# 5. Invalid input and unreachable destinations
# --------------------------------------------------------------------------

class TestErrors(RealDataCase):
    def run_input(self, text):
        (self.work / "bad.in").write_text(text)
        proc, _ = run_sol(self.work, "bad.in", "bad.out")
        return proc, self.work / "bad.out"

    def test_bad_inputs_fail_cleanly(self):
        cases = {
            "unknown destination": "MAD\nXXX\n",
            "unknown origin": "XXX\nMAD\n",
            "code too short": "MA\nBTS\n",
            "code too long": "MADR\nBTS\n",
            "digits": "123\nBTS\n",
            "only one line": "MAD\n",
            "empty file": "",
            "blank lines": "\n\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                proc, out = self.run_input(text)
                self.assert_fails_cleanly(proc, out)

    def test_unreachable_destination(self):
        # An airport with no outgoing flights cannot reach anything else
        sinks = sorted(c for c in REF.coords if c not in REF.adj and c != "MAD")
        self.assertTrue(sinks, "the data has no airport without outgoing flights")
        proc, out = self.run_input(f"{sinks[0]}\nMAD\n")
        self.assert_fails_cleanly(proc, out)

    def test_origin_equals_destination_without_outgoing_flights(self):
        sinks = sorted(c for c in REF.coords if c not in REF.adj)
        proc, out = self.run_input(f"{sinks[0]}\n{sinks[0]}\n")
        dist, route = self.parse_output(proc, out)
        self.assertEqual((dist, route), (0.0, [sinks[0]]))


# --------------------------------------------------------------------------
# 6. Optimality against the reference (real data)
# --------------------------------------------------------------------------

class TestOptimality(RealDataCase):
    def test_random_pairs_match_reference(self):
        rng = random.Random(12345)
        codes = sorted(REF.coords)
        reachable = slowest = 0
        for _ in range(N_RANDOM):
            o, d = rng.choice(codes), rng.choice(codes)
            with self.subTest(origin=o, destination=d):
                (self.work / "r.in").write_text(f"{o}\n{d}\n")
                out = self.work / "r.out"
                if out.exists():
                    out.unlink()
                proc, elapsed = run_sol(self.work, "r.in", "r.out")
                slowest = max(slowest, elapsed)
                if REF.shortest(o, d) is None:
                    self.assertNotEqual(proc.returncode, 0)
                    continue
                reachable += 1
                dist, route = self.parse_output(proc, out)
                self.assert_optimal(o, d, dist, route)
        self.assertGreater(reachable, 0, "no reachable pair was tested")
        print(f"\n[random pairs] reachable: {reachable}/{N_RANDOM}, "
              f"slowest run: {slowest:.2f}s")

    def test_every_airport_from_madrid(self):
        """One origin against every destination, in a single pass of runs."""
        for d in sorted(REF.coords):
            ref = REF.shortest("MAD", d)
            if ref is None:
                continue
            with self.subTest(destination=d):
                proc, out = self.solve("MAD", d, "all")
                dist, route = self.parse_output(proc, out)
                self.assert_optimal("MAD", d, dist, route)


# --------------------------------------------------------------------------
# 7. Small hand-made graphs (their own CSV files)
# --------------------------------------------------------------------------

def vtext(vertices, header="acronym,longitude_deg,latitude_deg", eol="\n"):
    rows = [header] + [f"{c},{lon},{lat}" for c, (lat, lon) in vertices.items()]
    return eol.join(rows) + eol


def etext(edges, header="origin,destination", eol="\n"):
    return eol.join([header] + [f"{o},{d}" for o, d in edges]) + eol


class TestSyntheticGraphs(Checks):
    def run_files(self, vtxt, etxt, origin, destination):
        work = Path(tempfile.mkdtemp(prefix="p1syn_"))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        if vtxt is not None:
            (work / "vertices.csv").write_bytes(vtxt.encode())
        if etxt is not None:
            (work / "edges.csv").write_bytes(etxt.encode())
        (work / "case.in").write_text(f"{origin}\n{destination}\n")
        proc, _ = run_sol(work, "case.in", "case.out")
        return proc, work / "case.out"

    def assert_route(self, vertices, proc, out, expected_route):
        dist, route = self.parse_output(proc, out)
        self.assertEqual(route, expected_route)
        expected = sum(haversine(*vertices[a], *vertices[b])
                       for a, b in zip(route, route[1:]))
        self.assertAlmostEqual(dist, expected, delta=TOL)

    # --- shortest-route logic -------------------------------------------
    V = {"AAA": (0, 0), "BBB": (3, 5), "CCC": (0, 10)}

    def test_route_through_intermediate_airport(self):
        proc, out = self.run_files(vtext(self.V), etext([("AAA", "BBB"), ("BBB", "CCC")]),
                                   "AAA", "CCC")
        self.assert_route(self.V, proc, out, ["AAA", "BBB", "CCC"])

    def test_direct_flight_beats_detour(self):
        edges = [("AAA", "BBB"), ("BBB", "CCC"), ("AAA", "CCC")]
        proc, out = self.run_files(vtext(self.V), etext(edges), "AAA", "CCC")
        self.assert_route(self.V, proc, out, ["AAA", "CCC"])

    def test_dead_end_and_tempting_detour(self):
        """A dead end next to the goal and a detour that reaches it by a long way."""
        v = {"AAA": (0, 0), "GGG": (0, 10), "TTT": (0, 9.5),
             "MMM": (0, 9), "NNN": (40, 9), "BBB": (2, 5)}
        edges = [("AAA", "TTT"),                       # dead end, looks great
                 ("AAA", "MMM"), ("MMM", "NNN"), ("NNN", "GGG"),   # long detour
                 ("AAA", "BBB"), ("BBB", "GGG")]       # the real optimum
        proc, out = self.run_files(vtext(v), etext(edges), "AAA", "GGG")
        self.assert_route(v, proc, out, ["AAA", "BBB", "GGG"])

    def test_duplicate_edges_and_self_loops(self):
        edges = [("AAA", "AAA"), ("AAA", "BBB"), ("AAA", "BBB"), ("AAA", "BBB"),
                 ("BBB", "BBB"), ("BBB", "CCC"), ("BBB", "CCC")]
        proc, out = self.run_files(vtext(self.V), etext(edges), "AAA", "CCC")
        self.assert_route(self.V, proc, out, ["AAA", "BBB", "CCC"])

    def test_cycles_do_not_loop_forever(self):
        edges = [("AAA", "BBB"), ("BBB", "AAA"), ("BBB", "CCC"), ("CCC", "BBB")]
        proc, out = self.run_files(vtext(self.V), etext(edges), "AAA", "CCC")
        self.assert_route(self.V, proc, out, ["AAA", "BBB", "CCC"])

    def test_edges_are_directed(self):
        v = {"AAA": (0, 0), "BBB": (3, 5)}
        proc, out = self.run_files(vtext(v), etext([("BBB", "AAA")]), "AAA", "BBB")
        self.assert_fails_cleanly(proc, out)
        proc, out = self.run_files(vtext(v), etext([("BBB", "AAA")]), "BBB", "AAA")
        self.assert_route(v, proc, out, ["BBB", "AAA"])

    def test_disconnected_components(self):
        v = {"AAA": (0, 0), "BBB": (1, 1), "CCC": (2, 2), "DDD": (3, 3)}
        edges = [("AAA", "BBB"), ("CCC", "DDD")]
        proc, out = self.run_files(vtext(v), etext(edges), "AAA", "DDD")
        self.assert_fails_cleanly(proc, out)

    def test_origin_equals_destination(self):
        v = {"AAA": (0, 0), "BBB": (3, 5)}
        proc, out = self.run_files(vtext(v), etext([("BBB", "AAA")]), "AAA", "AAA")
        dist, route = self.parse_output(proc, out)
        self.assertEqual((dist, route), (0.0, ["AAA"]))

    # --- geometry -----------------------------------------------------------
    def test_geometry_extremes(self):
        cases = {
            "across the antimeridian": ({"AAA": (0, 179), "BBB": (0, -179)}, 222.4),
            "antipodal points": ({"AAA": (0, 0), "BBB": (0, 180)}, 20015.1),
            "pole to pole": ({"AAA": (90, 0), "BBB": (-90, 0)}, 20015.1),
        }
        for name, (v, approx) in cases.items():
            with self.subTest(case=name):
                proc, out = self.run_files(vtext(v), etext([("AAA", "BBB")]), "AAA", "BBB")
                self.assert_route(v, proc, out, ["AAA", "BBB"])
                dist, _ = self.parse_output(proc, out)
                self.assertAlmostEqual(dist, approx, delta=0.5)

    # --- CSV details --------------------------------------------------------
    def test_lowercase_codes_in_csv(self):
        edges = etext([("aaa", "bbb"), ("bbb", "ccc")])
        proc, out = self.run_files(vtext(self.V), edges, "AAA", "CCC")
        self.assert_route(self.V, proc, out, ["AAA", "BBB", "CCC"])

    def test_windows_line_endings_in_csv(self):
        proc, out = self.run_files(vtext(self.V, eol="\r\n"),
                                   etext([("AAA", "BBB"), ("BBB", "CCC")], eol="\r\n"),
                                   "AAA", "CCC")
        self.assert_route(self.V, proc, out, ["AAA", "BBB", "CCC"])

    def test_extra_columns_are_ignored(self):
        vt = "acronym,longitude_deg,latitude_deg,airport_name\nAAA,0,0,A\nBBB,5,3,B\n"
        et = "origin,destination,flight_edge_id\nAAA,BBB,F1\n"
        proc, out = self.run_files(vt, et, "AAA", "BBB")
        self.assert_route({"AAA": (0, 0), "BBB": (3, 5)}, proc, out, ["AAA", "BBB"])

    # --- loader validation (these encode the current strict behavior) -------
    def test_invalid_csv_files_fail_cleanly(self):
        good_e = etext([("AAA", "BBB")])
        good_v = vtext({"AAA": (0, 0), "BBB": (3, 5)})
        cases = {
            "missing edges.csv": (good_v, None),
            "missing vertices.csv": (None, good_e),
            "wrong vertices header": (vtext({"AAA": (0, 0), "BBB": (3, 5)},
                                            header="code,lat,lon"), good_e),
            "wrong edges header": (good_v, etext([("AAA", "BBB")], header="from,to")),
            "non-numeric coordinate": ("acronym,longitude_deg,latitude_deg\nAAA,abc,0\nBBB,5,3\n", good_e),
            "latitude out of range": ("acronym,longitude_deg,latitude_deg\nAAA,0,95\nBBB,5,3\n", good_e),
            "longitude out of range": ("acronym,longitude_deg,latitude_deg\nAAA,200,0\nBBB,5,3\n", good_e),
            "code with four letters": ("acronym,longitude_deg,latitude_deg\nAAAA,0,0\nBBB,5,3\n", good_e),
            "edge to unknown airport": (good_v, etext([("AAA", "ZZZ")])),
            "no edges": (good_v, "origin,destination\n"),
            "empty vertices file": ("", good_e),
        }
        for name, (vt, et) in cases.items():
            with self.subTest(case=name):
                proc, out = self.run_files(vt, et, "AAA", "BBB")
                self.assert_fails_cleanly(proc, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
