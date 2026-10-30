"""Initialize the local database and seed the five example criteria."""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rfp_eval.database import DEFAULT_DB, load_criteria, seed_criteria


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file path")
    args = parser.parse_args()
    seed_criteria(args.db)
    print(f"Initialized {args.db} with {len(load_criteria(args.db))} criteria")


if __name__ == "__main__":
    main()
