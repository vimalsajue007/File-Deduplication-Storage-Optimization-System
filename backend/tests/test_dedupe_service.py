"""Duplicate detection against a real (SQLite) database and real files on disk."""
from app.core.config import get_settings
from app.db.base import utcnow
from app.models import DuplicateGroup, File, User
from app.services import dedupe, file_service, storage
from app.services.hashing import hash_file


def make_user(db, name="u1") -> User:
    u = User(email=f"{name}@x.com", username=name, hashed_password="x")
    db.add(u)
    db.commit()
    return u


def add_file(db, owner: User, name: str, content: bytes, *, ts=None) -> File:
    key = storage.new_storage_key(owner.id)
    path = storage.resolve_storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    f = File(
        owner_id=owner.id, original_filename=name, storage_key=key, size_bytes=len(content),
        mime_type="text/plain", extension="txt", category="document", uploaded_at=ts or utcnow(),
    )
    db.add(f)
    db.commit()
    return f


def test_identical_content_is_detected_across_names(db):
    u = make_user(db)
    a = add_file(db, u, "report.txt", b"identical content")
    b = add_file(db, u, "totally-different-name.dat", b"identical content")
    c = add_file(db, u, "other.txt", b"something else")
    for f in (a, b, c):
        dedupe.process_file(db, f.id)
    db.expire_all()

    a, b, c = (db.get(File, i) for i in (a.id, b.id, c.id))
    assert a.status == b.status == c.status == "ready"
    assert a.duplicate_group_id == b.duplicate_group_id is not None
    assert not a.is_duplicate and b.is_duplicate          # earliest upload is the original
    assert c.duplicate_group_id is None and not c.is_duplicate

    group = db.get(DuplicateGroup, a.duplicate_group_id)
    assert group.original_file_id == a.id
    assert (group.file_count, group.file_size, group.total_storage, group.potential_savings) == (2, 17, 34, 17)


def test_third_copy_updates_existing_group(db):
    u = make_user(db)
    files = [add_file(db, u, f"copy{i}.txt", b"payload") for i in range(3)]
    for f in files:
        dedupe.process_file(db, f.id)
    groups = db.query(DuplicateGroup).all()
    assert len(groups) == 1
    assert groups[0].file_count == 3 and groups[0].potential_savings == 14


def test_reprocessing_is_idempotent(db):
    u = make_user(db)
    a, b = add_file(db, u, "a.txt", b"zzz"), add_file(db, u, "b.txt", b"zzz")
    for _ in range(3):
        dedupe.process_file(db, a.id)
        dedupe.process_file(db, b.id)
    assert db.query(DuplicateGroup).count() == 1
    assert db.query(DuplicateGroup).one().file_count == 2


def test_duplicates_are_never_matched_across_users(db):
    alice, bob = make_user(db, "alice"), make_user(db, "bob")
    a = add_file(db, alice, "x.txt", b"shared bytes")
    b = add_file(db, bob, "x.txt", b"shared bytes")
    dedupe.process_file(db, a.id)
    dedupe.process_file(db, b.id)
    assert db.query(DuplicateGroup).count() == 0


def test_hash_is_stored_with_sha256_of_content(db):
    u = make_user(db)
    f = add_file(db, u, "a.txt", b"abc")
    dedupe.process_file(db, f.id)
    db.expire_all()
    assert db.get(File, f.id).content_hash == hash_file(storage.resolve_storage_path(f.storage_key))


def test_missing_file_on_disk_is_marked_failed(db):
    u = make_user(db)
    f = add_file(db, u, "gone.txt", b"data")
    storage.resolve_storage_path(f.storage_key).unlink()
    result = dedupe.process_file(db, f.id)
    assert result.status == "failed"
    assert "missing" in db.get(File, f.id).status_message.lower()


def test_unknown_file_id_returns_none(db):
    assert dedupe.process_file(db, 99999) is None


def test_deleting_original_promotes_next_oldest(db):
    u = make_user(db)
    files = [add_file(db, u, f"f{i}.txt", b"same") for i in range(3)]
    for f in files:
        dedupe.process_file(db, f.id)
    file_service.delete_files(db, u, [files[0].id], confirm=True)
    db.expire_all()
    group = db.query(DuplicateGroup).one()
    assert group.file_count == 2 and group.original_file_id == files[1].id
    assert db.get(File, files[1].id).is_duplicate is False
    assert db.get(File, files[2].id).is_duplicate is True


def test_group_dissolves_when_one_copy_remains(db):
    u = make_user(db)
    a, b = add_file(db, u, "a.txt", b"same"), add_file(db, u, "b.txt", b"same")
    for f in (a, b):
        dedupe.process_file(db, f.id)
    file_service.delete_files(db, u, [b.id], confirm=True)
    db.expire_all()
    assert db.query(DuplicateGroup).count() == 0
    remaining = db.get(File, a.id)
    assert remaining.duplicate_group_id is None and remaining.is_duplicate is False


def test_full_rescan_rebuilds_groups(db):
    u = make_user(db)
    a, b = add_file(db, u, "a.txt", b"same"), add_file(db, u, "b.txt", b"same")
    for f in (a, b):
        dedupe.process_file(db, f.id)
    db.query(DuplicateGroup).delete()
    for f in db.query(File).all():
        f.duplicate_group_id, f.is_duplicate = None, False
    db.commit()
    stats = dedupe.rebuild_all_for_user(db, u.id)
    assert stats["duplicate_groups"] == 1
    assert db.query(File).filter(File.is_duplicate.is_(True)).count() == 1
