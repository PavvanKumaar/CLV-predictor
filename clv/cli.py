import argparse
import importlib.util
import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from clv.data import ingest
from clv.db import session
from clv.features import snapshot
from clv.models import Customer, RawTransaction, Transaction
from clv.sample import generate

ROOT = Path(__file__).resolve().parent.parent


def migrate():
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description="CLV foundation and stage-one workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db")
    commands.add_parser("check")
    commands.add_parser("inspect")
    uci = commands.add_parser("convert-uci")
    uci.add_argument("paths", nargs="+", help="UCI Online Retail II CSV files")
    uci.add_argument("--output", default="data/uci_orders.csv")
    sample = commands.add_parser("sample")
    sample.add_argument("--output", default="data/sample.csv")
    sample.add_argument("--customers", type=int, default=350)
    load = commands.add_parser("ingest")
    load.add_argument("path")
    features = commands.add_parser("features")
    features.add_argument("--cutoff", required=True)
    features.add_argument("--observation-end", required=True)
    features.add_argument("--output", default="data/inspection")
    training = commands.add_parser("train")
    for name in ["train-cutoff", "validation-cutoff", "test-cutoff", "observation-end"]:
        training.add_argument(f"--{name}", required=True)
    full = commands.add_parser("train-all", help="Run classifier, count, value and combined CLV")
    for name in ["train-cutoff", "validation-cutoff", "test-cutoff", "observation-end"]:
        full.add_argument(f"--{name}", required=True)
    full.add_argument("--classifier-calibration", choices=["none", "sigmoid"], default="sigmoid")
    full.add_argument("--count-calibration", choices=["none", "scalar"], default="none")
    full.add_argument("--cold-prior-strength", type=float, default=50)
    full.add_argument("--cold-buckets", type=int, choices=[2, 4], default=2)
    full.add_argument("--calibration", choices=["none", "scalar", "isotonic"], default="none")
    full.add_argument("--cap-quantile", type=float, default=None, help="Validation revenue percentile for cap (0, 1]")
    full.add_argument("--no-revenue-cap", action="store_true")
    full.add_argument("--established-calibration", choices=["none", "scalar", "isotonic"], default="none")
    full.add_argument("--shared-calibration", action="store_true", help="Fit one validation calibrator instead of separate history cohorts")
    commands.add_parser("demo")
    args = parser.parse_args()
    if args.command == "init-db":
        migrate()
        result = {"database": "migrated to head"}
    elif args.command == "sample":
        result = generate(args.output, args.customers)
    elif args.command == "convert-uci":
        from clv.uci import convert
        result = convert(args.paths, args.output)
    elif args.command == "check":
        with session() as db:
            db.execute(text("SELECT 1"))
        result = {"database": "reachable", "packages": {name: importlib.util.find_spec(name) is not None for name in ["pandas", "numpy", "sklearn", "sqlalchemy", "fastapi", "lightgbm", "catboost", "xgboost", "statsmodels", "apscheduler", "psycopg"]}}
    elif args.command == "demo":
        from clv.ml import train
        migrate()
        generate("data/sample.csv")
        with session() as db:
            ingestion = ingest(db, "data/sample.csv")
            result = train(db, "2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01", os.getenv("ARTIFACT_DIR", "artifacts"))
            result["ingestion"] = ingestion
    else:
        with session() as db:
            if args.command == "ingest":
                result = ingest(db, args.path)
            elif args.command == "inspect":
                result = {"customers": db.scalar(select(func.count()).select_from(Customer)), "raw_rows": db.scalar(select(func.count()).select_from(RawTransaction)), "clean_orders": db.scalar(select(func.count()).select_from(Transaction)), "clean_revenue": str(db.scalar(select(func.sum(Transaction.amount))))}
            elif args.command == "features":
                identity, frame, labels = snapshot(db, args.cutoff, args.observation_end)
                target = Path(args.output)
                target.mkdir(parents=True, exist_ok=True)
                frame.to_csv(target / "features.csv", index=False)
                labels.to_csv(target / "labels.csv", index=False)
                result = {"snapshot_id": identity, "customers": len(frame), "output": str(target.resolve())}
            else:
                from clv.ml import train, train_full
                operation = train_full if args.command == "train-all" else train
                options = {} if args.command == "train" else {
                    "calibration_method": args.calibration,
                    "classifier_calibration": args.classifier_calibration,
                    "count_calibration": args.count_calibration,
                    "cold_prior_strength": args.cold_prior_strength, "cold_buckets": args.cold_buckets,
                    "established_calibration": args.established_calibration,
                    "cap_quantile": None if args.no_revenue_cap else args.cap_quantile,
                    "separate_cohorts": not args.shared_calibration}
                result = operation(db, args.train_cutoff, args.validation_cutoff, args.test_cutoff, args.observation_end, os.getenv("ARTIFACT_DIR", "artifacts"), **options)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
