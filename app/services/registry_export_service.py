"""National registry export -- generates an NCMEC-style XML document for a
case, and logs a "would have submitted" audit entry.

Important honesty note, also surfaced in the API docstring and the
frontend: this is a document-generation stub, not a live integration.
There's no publicly available, credential-free API to actually submit a
case to NCMEC (the real US National Center for Missing & Exploited
Children) or an equivalent national registry -- doing that requires a
formal partnership/MOU most deployments of an app like this wouldn't have.
What this DOES do honestly: produce a correctly-shaped export document in
a widely-recognized field layout, so a real integration later is "send this
existing XML to the real endpoint" rather than "design the export from
scratch." The "sync" action just records that a submission would have
happened here, for demo/workflow purposes -- it makes no network call.
"""
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.user import User
from app.services.geo_service import from_geography


def build_ncmec_style_xml(case: Case) -> str:
    """A simplified analog of NCMEC's case data-exchange fields: person
    details, last-known-contact details, physical description, and the
    reporting agency/case identifiers a real submission would need."""
    root = Element("MissingPersonCase", {"schemaVersion": "1.0", "source": "ReunificationNetwork"})

    case_el = SubElement(root, "CaseIdentifiers")
    SubElement(case_el, "LocalCaseNumber").text = str(case.id)
    SubElement(case_el, "CaseURL").text = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case.id}"
    SubElement(case_el, "ReportDate").text = case.created_at.isoformat()

    person = SubElement(root, "Person")
    SubElement(person, "FullName").text = case.name
    if case.age_at_disappearance is not None:
        SubElement(person, "AgeAtDisappearance").text = str(case.age_at_disappearance)
    if case.gender:
        SubElement(person, "Sex").text = case.gender
    SubElement(person, "PhysicalDescription").text = case.description

    contact = SubElement(root, "LastKnownContact")
    SubElement(contact, "DateTime").text = case.last_seen_at.isoformat()
    SubElement(contact, "Address").text = case.last_seen_address
    point = from_geography(case.last_seen_location)
    SubElement(contact, "Latitude").text = str(point.lat) if point else ""
    SubElement(contact, "Longitude").text = str(point.lng) if point else ""

    status = SubElement(root, "CaseStatus")
    SubElement(status, "Status").text = case.status.value
    SubElement(status, "LastUpdated").text = case.updated_at.isoformat()

    xml_bytes = tostring(root, encoding="utf-8")
    return minidom.parseString(xml_bytes).toprettyxml(indent="  ")


def record_registry_sync_stub(db: Session, case: Case, actor: User) -> dict:
    """Logs that a national-registry submission would have happened here --
    no network call is made (see module docstring for why). Returns a
    receipt-shaped dict for the API response, so the frontend has something
    concrete to show ("submission recorded") without implying a real
    external system was contacted."""
    timestamp = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.registry_sync_stub",
            target_type="case",
            target_id=case.id,
            log_metadata={"note": "Simulated national registry submission -- no external call made."},
        )
    )
    db.commit()
    return {
        "case_id": case.id,
        "submitted_at": timestamp,
        "note": (
            "This is a simulated submission for demonstration purposes -- no data left this "
            "server. A real integration would need a formal partnership with the receiving "
            "registry and would POST the XML export to their API."
        ),
    }
