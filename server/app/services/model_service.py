from fastapi import HTTPException

from app.core.database import Session
from app.core.ids import parse_uuid
from app.documents.model import Model, ModelArtifact
from app.schemas.model import ModelCreate
from app.services import audit_service
from app.services.catalog_service import load_artifacts


async def list_models(db: Session):
    models = await db.find(Model, {"is_approved": True}, sort=[("created_at", 1), ("_id", 1)])
    await load_artifacts(db, models)
    return models


async def get_model(db: Session, model_id: str):
    model = await db.get(Model, parse_uuid(model_id, "Model"))
    if not model or not model.is_approved:
        raise HTTPException(status_code=404, detail="Model not found")
    await load_artifacts(db, model)
    return model


async def create_model(db: Session, model_data: ModelCreate, actor_id=None):
    model = Model(**model_data.model_dump(), is_approved=False)
    db.add(model)
    await db.flush()
    if model.runtime == "ollama" and model.model_tag and model.min_ram_mb and model.min_disk_mb:
        # Older clients describe an Ollama model inline; keep that working by creating its artifact.
        db.add(
            ModelArtifact(
                model_id=model.id,
                runtime="ollama",
                source_type="ollama",
                reference=model.model_tag,
                format="ollama",
                quantization=model.quantization,
                min_ram_mb=model.min_ram_mb,
                min_disk_mb=model.min_disk_mb,
                min_vram_mb=model.min_vram_mb or 0,
                min_cpu_cores=model.min_cpu_cores or 1,
                gpu_required=model.gpu_required,
                requirements_estimated=model.requirements_estimated,
            )
        )
    audit_service.record(
        db,
        actor_id=actor_id,
        action="model.created",
        resource_type="model",
        resource_id=model.id,
        details={"name": model.name, "runtime": model.runtime, "model_tag": model.model_tag},
    )
    await db.commit()
    await db.refresh(model)
    await load_artifacts(db, model)
    return model


async def approve_model(db: Session, model_id: str, approved: bool, actor_id=None):
    model = await db.get(Model, parse_uuid(model_id, "Model"))
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    model.is_approved = approved
    audit_service.record(
        db,
        actor_id=actor_id,
        action="model.approved" if approved else "model.unapproved",
        resource_type="model",
        resource_id=model.id,
    )
    await db.commit()
    await db.refresh(model)
    await load_artifacts(db, model)
    return model


async def add_artifact(db: Session, model_id: str, data, actor_id=None) -> ModelArtifact:
    from app.services.catalog_service import artifact_problem

    model = await db.get(Model, parse_uuid(model_id, "Model"))
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    artifact = ModelArtifact(model_id=model.id, **data.model_dump())
    problem = artifact_problem(artifact)
    if problem:
        raise HTTPException(status_code=422, detail=f"Invalid artifact: {problem}")
    await load_artifacts(db, model)
    if any(a.runtime == artifact.runtime for a in model.artifacts):
        raise HTTPException(status_code=409, detail=f"Model already has a {artifact.runtime} artifact")
    db.add(artifact)
    await db.flush()
    audit_service.record(
        db,
        actor_id=actor_id,
        action="model.artifact_added",
        resource_type="model",
        resource_id=model.id,
        details={"runtime": artifact.runtime, "reference": artifact.reference, "revision": artifact.revision},
    )
    await db.commit()
    await db.refresh(artifact)
    return artifact


async def set_artifact_enabled(db: Session, model_id: str, artifact_id: str, enabled: bool, actor_id=None):
    artifact = await db.get(ModelArtifact, parse_uuid(artifact_id, "Artifact"))
    if artifact is None or str(artifact.model_id) != str(parse_uuid(model_id, "Model")):
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact.is_enabled = enabled
    audit_service.record(
        db,
        actor_id=actor_id,
        action="model.artifact_enabled" if enabled else "model.artifact_disabled",
        resource_type="model",
        resource_id=artifact.model_id,
        details={"runtime": artifact.runtime},
    )
    await db.commit()
    await db.refresh(artifact)
    return artifact
