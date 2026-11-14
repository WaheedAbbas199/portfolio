import hashlib
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import Container, client_ip, get_container, get_db, ip_hash
from app.core.exceptions import ValidationFailed
from app.db.base import utcnow
from app.models import ContactMessage
from app.models.enums import EmailStatus
from app.schemas.admin import ChatIn, ContactIn
from app.services import chat_service, content_service, email_service
from app.services.audit_service import audit

router = APIRouter(prefix="/public", tags=["public"])


def _revalidate(request: Request, response: Response, db: Session, scope: str):
    """ETag from the content fingerprint. `max-age=0, must-revalidate` means every visit asks the server, which answers 304 when nothing
    changed. Saving or publishing in the admin changes the fingerprint, so edits are visible on the next page load: no stale copies."""
    etag = f'W/"{scope}-{content_service.content_version(db)}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=0, must-revalidate"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return None


@router.get("/site")
def site(request: Request, response: Response, db: Session = Depends(get_db)):
    if (not_modified := _revalidate(request, response, db, "site")) is not None:
        return not_modified
    return content_service.public_bundle(db)


@router.get("/projects/{slug}")
def project(slug: str, request: Request, response: Response, db: Session = Depends(get_db)):
    if (not_modified := _revalidate(request, response, db, f"p-{slug}")) is not None:
        return not_modified
    return content_service.public_project(db, slug)


@router.get("/chat/config")
def chat_config(c: Container = Depends(get_container), db: Session = Depends(get_db)) -> dict:
    cfg = content_service.get_group(db, "chatbot")
    return {**cfg, "ai_available": c.llm.name != "disabled"}


@router.post("/chat")
def chat(body: ChatIn, request: Request, c: Container = Depends(get_container), db: Session = Depends(get_db)) -> dict:
    c.chat_limiter.check_and_hit(ip_hash(c.settings, client_ip(request)))
    res = chat_service.answer(db, c.settings, c.llm, question=body.message, history=[t.model_dump() for t in body.history])
    return {"answer": res.answer, "mode": res.mode, "sources": res.sources}


def _notify_task(c: Container, message_id: str) -> None:
    with c.session_factory() as s:
        email_service.send_notification(s, c.settings, c.email, message_id)


@router.post("/contact", status_code=201)
def contact(body: ContactIn, request: Request, background: BackgroundTasks, c: Container = Depends(get_container), db: Session = Depends(get_db)) -> dict:
    iph = ip_hash(c.settings, client_ip(request))
    if body.website:  # honeypot tripped: pretend success, store nothing
        return {"status": "received", "id": "ignored", "notification": "not_applicable"}
    c.contact_limiter.check_and_hit(iph)
    cats = content_service.get_group(db, "contact")["categories"]
    if body.category not in cats:
        raise ValidationFailed("Please choose one of the listed inquiry categories.", details=[{"field": "category", "message": f"must be one of {cats}"}])
    if 0 < body.elapsed_ms < 2000:
        raise ValidationFailed("That was very fast. Please review your message and try again.")
    dedupe = hashlib.sha256(f"{body.email.lower()}|{body.message}".encode()).hexdigest()
    recent = db.scalar(select(ContactMessage).where(ContactMessage.dedupe_hash == dedupe, ContactMessage.created_at >= utcnow() - timedelta(minutes=10)))
    if recent:  # double-click / retry: same message, no duplicate row, no second notification
        return {"status": "received", "id": recent.id, "notification": recent.email_status.value}
    msg = ContactMessage(
        name=body.name,
        email=body.email.lower(),
        category=body.category,
        subject=body.subject,
        message=body.message,
        dedupe_hash=dedupe,
        ip_hash=iph,
        email_status=EmailStatus.PENDING if c.email else EmailStatus.DISABLED,
    )
    db.add(msg)
    audit(db, actor_id=None, action="contact.received", entity_type="contact_message", entity_id=msg.id, details={"category": body.category})
    db.commit()
    if c.email:
        if c.settings.email_inline:
            # Serverless: the function may be frozen right after replying, so send BEFORE responding and report the true outcome.
            email_service.send_notification(db, c.settings, c.email, msg.id)
            db.refresh(msg)
        else:
            background.add_task(_notify_task, c, msg.id)
    # The message is always saved first. `notification` reports the real email state (sent / failed / pending / disabled).
    return {"status": "received", "id": msg.id, "notification": msg.email_status.value}
