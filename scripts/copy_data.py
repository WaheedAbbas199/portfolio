"""Copy your LOCAL content into the PRODUCTION database. Insert-only: it never updates or deletes anything in the target.

    # 1. look first (default = dry run, writes nothing)
    python -m scripts.copy_data --source sqlite:///./data/portfolio.db --target "<production DATABASE_URL>"
    # 2. then really copy
    python -m scripts.copy_data --source sqlite:///./data/portfolio.db --target "<production DATABASE_URL>" --apply

Copies: settings groups, skills, projects (draft/published state preserved), profile items, uploaded media (images/CV bytes).
Admin accounts are copied only with --include-admin (otherwise create one with scripts.create_admin).
Rows whose id already exists in the target, projects whose slug already exists, and settings that already exist are SKIPPED and reported.
The target must already be migrated (`alembic upgrade head`)."""

import argparse
import sys

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, undefer

from app.core.config import normalize_database_url
from app.models import AdminUser, MediaAsset, ProfileItem, Project, SiteSetting, Skill

META_KEY = "_meta"


def _row(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def copy_data(source_url: str, target_url: str, *, apply: bool, include_admin: bool = False, overwrite_settings: bool = False) -> dict:
    src_engine, dst_engine = create_engine(normalize_database_url(source_url)), create_engine(normalize_database_url(target_url))
    missing = {"projects", "skills", "site_settings", "media_assets", "profile_items", "admin_users"} - set(inspect(dst_engine).get_table_names())
    if missing:
        raise SystemExit(f"Target database is not migrated (missing tables: {sorted(missing)}). Run `alembic upgrade head` against it first.")
    report: dict[str, dict[str, int]] = {}
    with Session(src_engine) as src, Session(dst_engine) as dst:
        existing_slugs = set(dst.scalars(select(Project.slug)))
        existing_emails = set(dst.scalars(select(AdminUser.email)))
        copied_media = set(dst.scalars(select(MediaAsset.id)))

        def run(name, model, pk, query, skip_reason=None):
            stats = {"copied": 0, "skipped_exists": 0, "skipped_conflict": 0, "overwritten": 0}
            existing = set(dst.scalars(select(getattr(model, pk))))
            for obj in src.scalars(query):
                key = getattr(obj, pk)
                reason = skip_reason(obj) if skip_reason else None
                if key in existing:
                    if model is SiteSetting and overwrite_settings:
                        stats["overwritten"] += 1
                        if apply:
                            dst.get(SiteSetting, key).value = obj.value
                    else:
                        stats["skipped_exists"] += 1
                    continue
                if reason:
                    stats["skipped_conflict"] += 1
                    print(f"  skip {name} {key!r}: {reason}")
                    continue
                values = _row(obj)
                if model is Project and values.get("image_id") and values["image_id"] not in copied_media:
                    print(f"  note: project {obj.slug!r} references media {values['image_id']} that is not in the target; image link cleared")
                    values["image_id"] = None
                if apply:
                    dst.add(model(**values))
                stats["copied"] += 1
                if model is MediaAsset:
                    copied_media.add(key)
                if model is Project:
                    existing_slugs.add(obj.slug)
                if model is AdminUser:
                    existing_emails.add(obj.email)
            if apply:
                dst.commit()
            report[name] = stats

        run("media", MediaAsset, "id", select(MediaAsset).options(undefer(MediaAsset.data)))
        run("settings", SiteSetting, "key", select(SiteSetting).where(SiteSetting.key != META_KEY))
        run("skills", Skill, "id", select(Skill))
        run("projects", Project, "id", select(Project), lambda o: "slug already exists in target" if o.slug in existing_slugs else None)
        run("profile_items", ProfileItem, "id", select(ProfileItem))
        if include_admin:
            run("admins", AdminUser, "id", select(AdminUser), lambda o: "email already exists in target" if o.email in existing_emails else None)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="local database URL, e.g. sqlite:///./data/portfolio.db")
    ap.add_argument("--target", required=True, help="PRODUCTION database URL (keep it out of git and chat)")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--include-admin", action="store_true")
    ap.add_argument("--overwrite-settings", action="store_true", help="replace settings groups that already exist in the target")
    a = ap.parse_args()
    print("APPLYING changes" if a.apply else "DRY RUN (nothing will be written; add --apply to copy)")
    report = copy_data(a.source, a.target, apply=a.apply, include_admin=a.include_admin, overwrite_settings=a.overwrite_settings)
    for name, st in report.items():
        print(f"{name:14} " + "  ".join(f"{k}={v}" for k, v in st.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
