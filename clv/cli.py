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
                from clv.ml import train
                result = train(db, args.train_cutoff, args.validation_cutoff, args.test_cutoff, args.observation_end, os.getenv("ARTIFACT_DIR", "artifacts"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
