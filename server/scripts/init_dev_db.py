"""Create the schema and seed the Ollama catalog in a local SQLite dev database.

Postgres environments must use `alembic upgrade head` instead. SQLite cannot run every migration (it cannot
alter constraints), so this script builds the schema from the ORM models and reuses the catalog seed data
from migration 005.

    DATABASE_URL=sqlite+aiosqlite:///./dev.db python scripts/init_dev_db.py
"""

import asyncio
import importlib.util
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models import Base, Model  # noqa: E402


def _catalog():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "005_worker_protocol_and_lifecycle.py"
    spec = importlib.util.spec_from_file_location("m005", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.CATALOG


async def main() -> None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        raise SystemExit("Refusing to run against a non-SQLite database. Use `alembic upgrade head`.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        for tag, name, publisher, family, params, quant, lic, ctx, dl, ram, disk, cpu in _catalog():
            model_id = uuid.uuid5(uuid.NAMESPACE_URL, f"agentmesh:ollama:{tag}")
            if (await db.execute(select(Model).where(Model.id == model_id))).scalar_one_or_none():
                continue
            db.add(
                Model(
                    id=model_id,
                    name=name,
                    version=tag.split(":", 1)[1],
                    runtime="ollama",
                    source="ollama-registry",
                    is_approved=True,
                    created_at=datetime.utcnow(),
                    model_tag=tag,
                    publisher=publisher,
                    family=family,
                    parameter_size=params,
                    quantization=quant,
                    format="gguf",
                    license=lic,
                    context_length=ctx,
                    download_size_mb=dl,
                    min_ram_mb=ram,
                    min_disk_mb=disk,
                    min_vram_mb=0,
                    min_cpu_cores=cpu,
                    gpu_required=False,
                    requirements_estimated=True,
                )
            )
        await db.commit()
    print(f"Initialised {settings.DATABASE_URL}")


if __name__ == "__main__":
    asyncio.run(main())
