from __future__ import annotations

import json
from io import BytesIO
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from app import create_app
from database import db
from models import DiagramRevision, DocumentVersion, KnowledgeDocument, SampleDataset, SampleRowDefinition, SandboxBuild, SystemProject
from services.er_language import parse_er_source
from services.knowledge import ingest_document
from services.revisions import create_revision
from services.sandbox import build_sandbox


SOURCE = '''erModel Procurement_Demo {
  dialect "sqlite"
  direction LR
  subjectArea Procurement {
    table SUPPLIER {
      integer supplier_id PK
      string supplier_name length=200 not_null
      string country_code length=2
      string assurance_status length=30
    }
    table PURCHASE_ORDER {
      integer purchase_order_id PK
      integer supplier_id FK not_null
      string order_date not_null
      decimal order_value precision=18 scale=2
      string status length=30
    }
    table INVOICE {
      integer invoice_id PK
      integer purchase_order_id FK not_null
      string invoice_date not_null
      decimal invoice_value precision=18 scale=2
      string status length=30
    }
    table PAYMENT {
      integer payment_id PK
      integer invoice_id FK not_null
      string payment_date
      decimal payment_value precision=18 scale=2
    }
    relationship PURCHASE_ORDER.supplier_id -> SUPPLIER.supplier_id {
      cardinality many-to-one
      label "placed with"
    }
    relationship INVOICE.purchase_order_id -> PURCHASE_ORDER.purchase_order_id {
      cardinality many-to-one
      label "bills"
    }
    relationship PAYMENT.invoice_id -> INVOICE.invoice_id {
      cardinality many-to-one
      label "settles"
    }
  }
}'''


ROWS = {
    "SUPPLIER": [
        {"supplier_id": 1, "supplier_name": "Northwind Components", "country_code": "GB", "assurance_status": "Approved"},
        {"supplier_id": 2, "supplier_name": "Contoso Industrial", "country_code": "DE", "assurance_status": "Review due"},
    ],
    "PURCHASE_ORDER": [
        {"purchase_order_id": 1001, "supplier_id": 1, "order_date": "2026-07-15", "order_value": 12500.0, "status": "Approved"},
        {"purchase_order_id": 1002, "supplier_id": 2, "order_date": "2026-07-22", "order_value": 8400.5, "status": "Open"},
    ],
    "INVOICE": [
        {"invoice_id": 5001, "purchase_order_id": 1001, "invoice_date": "2026-07-30", "invoice_value": 12500.0, "status": "Paid"},
        {"invoice_id": 5002, "purchase_order_id": 1002, "invoice_date": "2026-08-02", "invoice_value": 4200.25, "status": "Pending approval"},
    ],
    "PAYMENT": [
        {"payment_id": 9001, "invoice_id": 5001, "payment_date": "2026-08-05", "payment_value": 12500.0},
    ],
}


KNOWLEDGE = b'''# Procurement demo operating notes

Suppliers require an approved assurance status before purchase orders are released.
Invoices are matched to purchase orders. Payments are created only after invoice approval.
The review-due supplier should be reassessed before additional orders are approved.
'''


def seed() -> tuple[int, int, int, int]:
    app = create_app()
    with app.app_context():
        project = SystemProject.query.filter_by(slug="procurement-demo").first()
        if project is None:
            project = SystemProject(name="Procurement Demo", slug="procurement-demo", description="Example supplier-to-payment system with safe synthetic data.", dialect="sqlite")
            db.session.add(project); db.session.flush()
        if not project.revisions:
            revision = create_revision(project, SOURCE, parse_er_source(SOURCE), "Seeded procurement demonstration")
            revision.status = "approved"; revision.approved_at = revision.created_at; project.active_revision_id = revision.id
        dataset = SampleDataset.query.filter_by(project_id=project.id, name="Procurement demonstration rows").first()
        if dataset is None:
            dataset = SampleDataset(project_id=project.id, name="Procurement demonstration rows", description="Synthetic linked supplier, order, invoice and payment examples.", provenance="synthetic", classification="non-sensitive")
            db.session.add(dataset); db.session.flush()
            for table_name, rows in ROWS.items():
                for position, values in enumerate(rows, start=1):
                    db.session.add(SampleRowDefinition(dataset_id=dataset.id, table_name=table_name, position=position, values_json=json.dumps(values, sort_keys=True)))
        document = KnowledgeDocument.query.filter_by(project_id=project.id, title="Procurement demo operating notes").first()
        if document is None:
            upload = FileStorage(stream=BytesIO(KNOWLEDGE), filename="procurement-demo-notes.md", content_type="text/markdown")
            document = ingest_document(project_id=project.id, upload=upload, title="Procurement demo operating notes", provenance="authored", classification="non-sensitive", data_dir=app.config["DATA_DIR"])
            db.session.add(DocumentVersion(project_id=project.id, document_id=document.id, family_id=str(uuid4()), version_number=1))
        db.session.flush()
        sandbox = SandboxBuild.query.filter_by(
            project_id=project.id,
            dataset_id=dataset.id,
            revision_id=project.active_revision_id,
            status="completed",
        ).first()
        if sandbox is None:
            active_revision = db.session.get(DiagramRevision, project.active_revision_id)
            sandbox = build_sandbox(project, active_revision, dataset, app.config["DATA_DIR"])
            db.session.add(sandbox)
        db.session.commit()
        return project.id, dataset.id, document.id, sandbox.id


if __name__ == "__main__":
    project_id, dataset_id, document_id, sandbox_id = seed()
    print(f"Seeded Procurement Demo: project={project_id} dataset={dataset_id} document={document_id} sandbox={sandbox_id}")
