from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from database import db
from models import ChunkKnowledgeLink, DocumentChunk, KnowledgeDocument, KnowledgeLink
from services.ollama import OllamaClient


class KnowledgeLinkProposal(BaseModel):
    action_name: str
    document_id: int | None = Field(default=None, gt=0)
    chunk_id: int | None = Field(default=None, gt=0)
    target_type: str
    target_key: str = Field(min_length=1, max_length=340)
    reason: str = Field(default="", max_length=1000)


class MutationPlan(BaseModel):
    action_requests: list[KnowledgeLinkProposal] = Field(default_factory=list, max_length=3)


class AssistantActionError(ValueError):
    pass


MUTATION_ACTIONS = {
    "knowledge.link_document": "Propose linking one existing project document to one active table or field",
    "knowledge.link_chunk": "Propose linking one precise existing document chunk to one active table or field",
}


def plan_mutation_actions(*, question: str, evidence: list[dict], model, documents, ollama_url: str, ollama_model: str, client=None) -> MutationPlan:
    targets = ([{"target_type": "table", "target_key": table.name} for table in model.tables] +
               [{"target_type": "column", "target_key": f"{table.name}.{column.name}"} for table in model.tables for column in table.columns]) if model else []
    available_documents = [{"document_id": document.id, "title": document.title, "chunks": [{"chunk_id": chunk.id, "locator": chunk.locator} for chunk in document.chunks[:20]]} for document in documents]
    prompt = f"""Suggest zero to three useful actions. Suggestions are proposals only and require explicit user confirmation.
Return JSON only: {{"action_requests":[{{"action_name":"knowledge.link_document or knowledge.link_chunk","document_id":1,"chunk_id":null,"target_type":"table or column","target_key":"exact target","reason":"why"}}]}}.
For document links supply document_id and omit chunk_id. For chunk links supply chunk_id and omit document_id. Use only listed IDs and exact targets. Do not request deletion, shell, filesystem, network, SQL execution, catalogue changes or any unlisted action.
Allowed actions: {json.dumps(MUTATION_ACTIONS, sort_keys=True)}
Documents: {json.dumps(available_documents[:50], sort_keys=True)}
Targets: {json.dumps(targets[:500], sort_keys=True)}
Question: {question[:1000]}
Evidence labels: {json.dumps(evidence[:16], sort_keys=True)}
"""
    raw = (client or OllamaClient(ollama_url)).generate_json(ollama_model, prompt)
    try:
        plan = MutationPlan.model_validate(raw)
    except ValidationError as exc:
        raise AssistantActionError(f"Action plan has the wrong structure: {exc}") from exc
    for request in plan.action_requests:
        if request.action_name not in MUTATION_ACTIONS:
            raise AssistantActionError(f"Assistant requested non-permitted action '{request.action_name}'.")
        project_id = documents[0].project_id if documents else None
        if request.action_name == "knowledge.link_document": validate_knowledge_link(project_id=project_id, model=model, proposal=request)
        else: validate_chunk_link(project_id=project_id, model=model, proposal=request)
    return plan


def validate_knowledge_link(*, project_id: int | None, model, proposal: KnowledgeLinkProposal) -> KnowledgeDocument:
    if project_id is None or not model:
        raise AssistantActionError("An active model and project document are required for link proposals.")
    if proposal.document_id is None or proposal.chunk_id is not None:
        raise AssistantActionError("A document-link proposal must supply only document_id.")
    document = db.session.get(KnowledgeDocument, proposal.document_id)
    if not document or document.project_id != project_id:
        raise AssistantActionError("The proposed document does not belong to this project.")
    valid_targets = {("table", table.name) for table in model.tables}
    valid_targets.update(("column", f"{table.name}.{column.name}") for table in model.tables for column in table.columns)
    if (proposal.target_type, proposal.target_key) not in valid_targets:
        raise AssistantActionError("The proposed model target is not valid for the active revision.")
    return document


def validate_chunk_link(*, project_id: int | None, model, proposal: KnowledgeLinkProposal) -> DocumentChunk:
    if project_id is None or not model:
        raise AssistantActionError("An active model and project document chunk are required for chunk-link proposals.")
    if proposal.chunk_id is None or proposal.document_id is not None:
        raise AssistantActionError("A chunk-link proposal must supply only chunk_id.")
    chunk = db.session.get(DocumentChunk, proposal.chunk_id) if proposal.chunk_id else None
    if not chunk or chunk.document.project_id != project_id:
        raise AssistantActionError("The proposed document chunk does not belong to this project.")
    valid_targets = {("table", table.name) for table in model.tables}
    valid_targets.update(("column", f"{table.name}.{column.name}") for table in model.tables for column in table.columns)
    if (proposal.target_type, proposal.target_key) not in valid_targets:
        raise AssistantActionError("The proposed model target is not valid for the active revision.")
    return chunk


def apply_knowledge_link(*, project, model, revision_id: int, proposal: KnowledgeLinkProposal, created_by: str) -> KnowledgeLink:
    document = validate_knowledge_link(project_id=project.id, model=model, proposal=proposal)
    existing = KnowledgeLink.query.filter_by(document_id=document.id, revision_id=revision_id, target_type=proposal.target_type, target_key=proposal.target_key).first()
    if existing:
        raise AssistantActionError("That document link already exists.")
    link = KnowledgeLink(project_id=project.id, document_id=document.id, revision_id=revision_id, target_type=proposal.target_type, target_key=proposal.target_key, created_by=created_by)
    db.session.add(link)
    return link


def apply_chunk_link(*, project, model, revision_id: int, proposal: KnowledgeLinkProposal, created_by: str) -> ChunkKnowledgeLink:
    chunk = validate_chunk_link(project_id=project.id, model=model, proposal=proposal)
    existing = ChunkKnowledgeLink.query.filter_by(chunk_id=chunk.id, revision_id=revision_id, target_type=proposal.target_type, target_key=proposal.target_key).first()
    if existing:
        raise AssistantActionError("That document chunk link already exists.")
    link = ChunkKnowledgeLink(project_id=project.id, chunk_id=chunk.id, revision_id=revision_id, target_type=proposal.target_type, target_key=proposal.target_key, created_by=created_by)
    db.session.add(link)
    return link
