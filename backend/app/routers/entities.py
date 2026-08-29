"""
Entities Router.
CRUD operations for entities, entity resolution/merge.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.models import (
    User, Entity, Relationship, EntityType, CaseAssignment
)
from app.auth import get_current_user, RoleChecker, IO_ROLES
from app.services.entity_resolution import (
    find_potential_matches, merge_entities, split_entities
)
from app.utils import log_audit

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


class EntityCreate(BaseModel):
    case_id: str
    entity_type: str
    name: str
    aliases: Optional[list] = []
    attributes: Optional[dict] = {}


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    aliases: Optional[list] = None
    attributes: Optional[dict] = None
    is_reviewed: Optional[bool] = None


class EntityMerge(BaseModel):
    primary_entity_id: str
    secondary_entity_id: str


@router.get("")
def list_entities(
    case_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Entity).filter(Entity.is_merged_into.is_(None))

    if case_id:
        query = query.filter(Entity.case_id == case_id)
    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)
    if search:
        query = query.filter(
            Entity.name.ilike(f"%{search}%")
        )

    entities = query.limit(500).all()

    results = []
    for entity in entities:
        # Count relationships
        rel_count = db.query(Relationship).filter(
            (Relationship.source_entity_id == entity.id) |
            (Relationship.target_entity_id == entity.id)
        ).count()

        results.append({
            "id": entity.id,
            "name": entity.name,
            "entity_type": entity.entity_type.value,
            "case_id": entity.case_id,
            "confidence_score": entity.confidence_score,
            "is_ai_extracted": entity.is_ai_extracted,
            "is_reviewed": entity.is_reviewed,
            "aliases": entity.aliases or [],
            "attributes": entity.attributes or {},
            "relationship_count": rel_count,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
        })

    return results


@router.post("")
def create_entity(
    entity_data: EntityCreate,
    current_user: User = Depends(RoleChecker(IO_ROLES)),
    db: Session = Depends(get_db),
):
    entity = Entity(
        case_id=entity_data.case_id,
        entity_type=EntityType(entity_data.entity_type),
        name=entity_data.name,
        aliases=entity_data.aliases or [],
        attributes=entity_data.attributes or {},
        is_ai_extracted=False,
        is_reviewed=True,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    log_audit(db, current_user.id, "create_entity", "entity", entity.id,
              {"name": entity.name, "type": entity.entity_type.value})

    return {
        "id": entity.id,
        "name": entity.name,
        "entity_type": entity.entity_type.value,
    }


@router.get("/{entity_id}")
def get_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Get relationships
    source_rels = db.query(Relationship).filter(
        Relationship.source_entity_id == entity_id
    ).all()
    target_rels = db.query(Relationship).filter(
        Relationship.target_entity_id == entity_id
    ).all()

    relationships = []
    for rel in source_rels + target_rels:
        other_id = rel.target_entity_id if rel.source_entity_id == entity_id else rel.source_entity_id
        other = db.query(Entity).filter(Entity.id == other_id).first()
        if other:
            relationships.append({
                "id": rel.id,
                "other_entity_id": other_id,
                "other_entity_name": other.name,
                "other_entity_type": other.entity_type.value,
                "relationship_type": rel.relationship_type.value,
                "weight": rel.weight,
                "confidence_score": rel.confidence_score,
                "is_ai_generated": rel.is_ai_generated,
                "is_reviewed": rel.is_reviewed,
                "justification": rel.justification,
            })

    return {
        "id": entity.id,
        "name": entity.name,
        "entity_type": entity.entity_type.value,
        "case_id": entity.case_id,
        "confidence_score": entity.confidence_score,
        "is_ai_extracted": entity.is_ai_extracted,
        "is_reviewed": entity.is_reviewed,
        "aliases": entity.aliases or [],
        "attributes": entity.attributes or {},
        "relationships": relationships,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }


@router.put("/{entity_id}")
def update_entity(
    entity_id: str,
    update: EntityUpdate,
    current_user: User = Depends(RoleChecker(IO_ROLES)),
    db: Session = Depends(get_db),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    if update.name is not None:
        entity.name = update.name
    if update.aliases is not None:
        entity.aliases = update.aliases
    if update.attributes is not None:
        entity.attributes = update.attributes
    if update.is_reviewed is not None:
        entity.is_reviewed = update.is_reviewed

    db.commit()

    log_audit(db, current_user.id, "update_entity", "entity", entity_id)
    return {"message": "Entity updated", "id": entity.id}


@router.post("/merge")
def merge_entity_endpoint(
    merge_data: EntityMerge,
    current_user: User = Depends(RoleChecker(IO_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        result = merge_entities(
            db,
            merge_data.primary_entity_id,
            merge_data.secondary_entity_id,
            current_user.id,
        )
        log_audit(db, current_user.id, "merge_entities", "entity", result.id,
                  {"merged": merge_data.secondary_entity_id})
        return {
            "message": "Entities merged successfully",
            "primary_entity": {
                "id": result.id,
                "name": result.name,
                "aliases": result.aliases,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{entity_id}/split")
def split_entity_endpoint(
    entity_id: str,
    merge_data: EntityMerge,
    current_user: User = Depends(RoleChecker(IO_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        result = split_entities(
            db,
            merge_data.primary_entity_id,
            merge_data.secondary_entity_id,
            current_user.id,
        )
        log_audit(db, current_user.id, "split_entity", "entity", result.id)
        return {"message": "Entities split successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{entity_id}/matches")
def find_matches(
    entity_id: str,
    threshold: float = Query(0.6),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    matches = find_potential_matches(db, entity, threshold=threshold)
    return matches
