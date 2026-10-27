"""The built-in model catalog, inserted at startup where missing (formerly seeded by database migrations 005 and 008).

Only missing entries are added: an operator's changes to a seeded model (for example withdrawing its approval) are
never undone. Ids are deterministic, so every installation names the same model the same way.
"""

import uuid
from datetime import datetime

from pymongo.errors import DuplicateKeyError

from app.core.database import Session, retry_transient
from app.core.timeutil import utcnow
from app.documents.model import Model, ModelArtifact


def model_id(tag: str) -> uuid.UUID:
    """Id of an Ollama catalog model."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"agentmesh:ollama:{tag}")


def artifact_id(model: uuid.UUID, runtime: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"agentmesh:artifact:{model}:{runtime}")


CATALOG = [
    # tag, name, publisher, family, params, quant, license, ctx, download_mb, ram_mb, disk_mb, cpu
    ("smollm2:135m", "SmolLM2 135M", "Hugging Face", "llama", "135M", "F16", "Apache-2.0", 8192, 271, 768, 512, 1),
    ("qwen2.5:0.5b", "Qwen2.5 0.5B", "Alibaba Qwen", "qwen2", "494M", "Q4_K_M", "Apache-2.0", 32768, 398, 1024, 768, 1),
    (
        "llama3.2:1b",
        "Llama 3.2 1B",
        "Meta",
        "llama",
        "1.2B",
        "Q8_0",
        "Llama 3.2 Community License",
        131072,
        1300,
        2048,
        1792,
        2,
    ),
    (
        "llama3.2:3b",
        "Llama 3.2 3B",
        "Meta",
        "llama",
        "3.2B",
        "Q4_K_M",
        "Llama 3.2 Community License",
        131072,
        2000,
        3072,
        2560,
        2,
    ),
    ("qwen2.5:7b", "Qwen2.5 7B", "Alibaba Qwen", "qwen2", "7.6B", "Q4_K_M", "Apache-2.0", 32768, 4700, 6144, 5632, 4),
    (
        "llama3.1:8b",
        "Llama 3.1 8B",
        "Meta",
        "llama",
        "8.0B",
        "Q4_K_M",
        "Llama 3.1 Community License",
        131072,
        4900,
        6656,
        5888,
        4,
    ),
]


QWEN15_MODEL_ID = uuid.uuid5(uuid.NAMESPACE_URL, "agentmesh:model:qwen2.5-1.5b-instruct")

NEW_MODELS = [
    {
        "id": QWEN15_MODEL_ID,
        "name": "Qwen2.5 1.5B Instruct",
        "version": "1.5b",
        "runtime": "vllm",
        "source": "huggingface",
        "model_tag": "Qwen/Qwen2.5-1.5B-Instruct",
        "publisher": "Alibaba Qwen",
        "family": "qwen2",
        "parameter_size": "1.5B",
        "quantization": "BF16",
        "format": "safetensors",
        "license": "Apache-2.0",
        "context_length": 32768,
        "download_size_mb": 2955,
        "min_ram_mb": 8192,
        "min_disk_mb": 4096,
        "min_vram_mb": 8192,
        "min_cpu_cores": 2,
        "gpu_required": True,
    },
]

# runtime, model id, reference, revision, file, sha256, size bytes, format, quant, ram, disk, vram, cpu, gpu
HF_ARTIFACTS = [
    (
        "llamacpp",
        model_id("smollm2:135m"),
        "bartowski/SmolLM2-135M-Instruct-GGUF",
        "09816acd5d99df7be770d85ea30822623dab342c",
        "SmolLM2-135M-Instruct-Q8_0.gguf",
        "5a1395716f7913741cc51d98581b9b1228d80987a9f7d3664106742eb06bba83",
        144811360,
        "gguf",
        "Q8_0",
        512,
        256,
        0,
        1,
        False,
    ),
    (
        "llamacpp",
        model_id("qwen2.5:0.5b"),
        "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "9217f5db79a29953eb74d5343926648285ec7e67",
        "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
        491400032,
        "gguf",
        "Q4_K_M",
        1024,
        640,
        0,
        1,
        False,
    ),
    (
        "vllm",
        model_id("qwen2.5:0.5b"),
        "Qwen/Qwen2.5-0.5B-Instruct",
        "7ae557604adf67be50417f59c2c2f167def9a775",
        None,
        None,
        953 * 2**20,
        "safetensors",
        "BF16",
        4096,
        2048,
        4096,
        2,
        True,
    ),
    (
        "vllm",
        QWEN15_MODEL_ID,
        "Qwen/Qwen2.5-1.5B-Instruct",
        "989aa7980e4cf806f80c7fef2b1adb7bc71aa306",
        None,
        None,
        2955 * 2**20,
        "safetensors",
        "BF16",
        8192,
        4096,
        8192,
        2,
        True,
    ),
]


def catalog_models() -> list[Model]:
    now = utcnow()
    ollama = [
        Model(
            id=model_id(tag),
            name=name,
            version=tag.split(":", 1)[1],
            runtime="ollama",
            source="ollama-registry",
            is_approved=True,
            created_at=now,
            model_tag=tag,
            publisher=publisher,
            family=family,
            parameter_size=params,
            quantization=quant,
            format="gguf",
            license=license_,
            context_length=ctx,
            download_size_mb=dl,
            min_ram_mb=ram,
            min_disk_mb=disk,
            min_vram_mb=0,
            min_cpu_cores=cpu,
            gpu_required=False,
            requirements_estimated=True,
        )
        for (tag, name, publisher, family, params, quant, license_, ctx, dl, ram, disk, cpu) in CATALOG
    ]
    others = [Model(**spec, requirements_estimated=True, is_approved=True, created_at=now) for spec in NEW_MODELS]
    return ollama + others


def catalog_artifacts(models: list[Model]) -> list[ModelArtifact]:
    """An Ollama artifact for every Ollama catalog model, plus the pinned Hugging Face artifacts."""
    out = [
        ModelArtifact(
            id=artifact_id(m.id, "ollama"),
            model_id=m.id,
            runtime="ollama",
            source_type="ollama",
            reference=m.model_tag,
            size_bytes=(m.download_size_mb or 0) * 2**20 or None,
            format="ollama",
            quantization=m.quantization,
            min_ram_mb=m.min_ram_mb,
            min_disk_mb=m.min_disk_mb,
            min_vram_mb=m.min_vram_mb or 0,
            min_cpu_cores=m.min_cpu_cores or 1,
            gpu_required=m.gpu_required,
        )
        for m in models
        if m.runtime == "ollama" and m.model_tag and m.min_ram_mb and m.min_disk_mb
    ]
    created = datetime(2026, 10, 20)
    out += [
        ModelArtifact(
            id=artifact_id(mid, rt),
            model_id=mid,
            runtime=rt,
            source_type="huggingface",
            reference=ref,
            revision=rev,
            file=file,
            sha256=sha,
            size_bytes=size,
            format=fmt,
            quantization=quant,
            min_ram_mb=ram,
            min_disk_mb=disk,
            min_vram_mb=vram,
            min_cpu_cores=cpu,
            gpu_required=gpu,
            created_at=created,
        )
        for (rt, mid, ref, rev, file, sha, size, fmt, quant, ram, disk, vram, cpu, gpu) in HF_ARTIFACTS
    ]
    return out


SEED_ATTEMPTS = 5


async def seed_catalog(db: Session) -> int:
    """Insert catalog models and artifacts that do not exist yet. Commits. Returns how many were added.

    Safe when several replicas start at once: a transaction aborted by a concurrent one, or an insert that lost the
    race to another replica's identical entry, is retried, and the retry finds the entries already present."""
    for _ in range(SEED_ATTEMPTS - 1):
        try:
            return await retry_transient(db, lambda: _seed_once(db))
        except DuplicateKeyError:
            await db.rollback()
    return await retry_transient(db, lambda: _seed_once(db))


async def _seed_once(db: Session) -> int:
    wanted = catalog_models()
    have = set(await db.distinct(Model, "_id", {"_id": {"$in": [m.id for m in wanted]}}))
    new_models = [m for m in wanted if m.id not in have]
    db.add_all(new_models)
    present = {
        (a.model_id, a.runtime) for a in await db.find(ModelArtifact, {"model_id": {"$in": [m.id for m in wanted]}})
    }
    new_artifacts = [a for a in catalog_artifacts(wanted) if (a.model_id, a.runtime) not in present]
    db.add_all(new_artifacts)
    await db.commit()
    return len(new_models) + len(new_artifacts)
