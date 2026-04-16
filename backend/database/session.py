from collections.abc import Generator
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

try:
    from .config import get_settings, normalize_database_url
except ImportError:  # pragma: no cover - supports running from backend/ as main:app
    from database.config import get_settings, normalize_database_url

settings = get_settings()
database_url = normalize_database_url(settings.database_url)
SQLITE_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "test_smoke.db"


def ensure_sqlite_parent_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return

    parsed = urlparse(url)
    db_path_value = unquote(parsed.path)
    if len(db_path_value) >= 4 and db_path_value[0] == "/" and db_path_value[2] == ":":
        db_path_value = db_path_value[1:]
    db_path = Path(db_path_value)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def sqlite_file_path(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None

    parsed = urlparse(url)
    db_path_value = unquote(parsed.path)
    if len(db_path_value) >= 4 and db_path_value[0] == "/" and db_path_value[2] == ":":
        db_path_value = db_path_value[1:]
    return Path(db_path_value)


def bootstrap_sqlite_database(url: str) -> None:
    db_path = sqlite_file_path(url)
    if db_path is None or db_path.exists():
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if SQLITE_TEMPLATE_PATH.exists():
        shutil.copyfile(SQLITE_TEMPLATE_PATH, db_path)
        return

    db_path.touch()


class Base(DeclarativeBase):
    pass


connect_args = {}
engine_options = {
    "future": True,
    "echo": False,
    "connect_args": connect_args,
}

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if ":memory:" in database_url:
        engine_options["poolclass"] = StaticPool
    else:
        ensure_sqlite_parent_dir(database_url)
        bootstrap_sqlite_database(database_url)
else:
    engine_options["pool_pre_ping"] = True

engine = create_engine(database_url, **engine_options)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reconcile_recipe_schema() -> None:
    inspector = inspect(engine)
    if "recipes" not in inspector.get_table_names():
        return

    existing_columns = {column["name"]: column for column in inspector.get_columns("recipes")}
    servings_column = next(
        (column for column in existing_columns.values() if column["name"] == "servings"),
        None,
    )
    if servings_column is None:
        return

    column_type = str(servings_column["type"]).lower()
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql" and ("integer" in column_type or "int" in column_type):
            connection.execute(
                text("ALTER TABLE recipes ALTER COLUMN servings TYPE TEXT USING servings::text")
            )

        column_patches = {
            "summary": "TEXT",
            "image_url": "TEXT",
            "source_domain": "TEXT",
        }
        for column_name, column_definition in column_patches.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE recipes ADD COLUMN {column_name} {column_definition}")
                )

        if engine.dialect.name == "postgresql":
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS recipes_source_domain_idx ON recipes (source_domain)")
            )


def init_db() -> None:
    try:
        from ..models.recipe import Recipe  # noqa: F401
    except ImportError:  # pragma: no cover - supports running from backend/ as main:app
        from models.recipe import Recipe  # noqa: F401

    Base.metadata.create_all(bind=engine)
    reconcile_recipe_schema()
