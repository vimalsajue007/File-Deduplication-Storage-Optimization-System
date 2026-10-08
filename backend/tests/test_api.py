"""End-to-end API flow: upload -> background dedupe -> groups -> analytics -> safe delete."""
import io

from tests.conftest import register_and_login

API = "/api/v1"


def upload(client, auth, files):
    return client.post(f"{API}/files/upload", headers=auth, files=[("files", f) for f in files])


def f(name, content: bytes, mime="text/plain"):
    return (name, io.BytesIO(content), mime)


def test_requires_authentication(client):
    assert client.get(f"{API}/files").status_code == 401
    assert client.get(f"{API}/analytics/summary").status_code == 401


def test_register_validation_and_duplicates(client):
    bad = client.post(f"{API}/auth/register", json={"email": "a@b.com", "username": "al", "password": "short"})
    assert bad.status_code == 422
    register_and_login(client, "carol")
    again = client.post(f"{API}/auth/register", json={"email": "carol@example.com", "username": "carol2", "password": "Passw0rd123"})
    assert again.status_code == 409


def test_login_lockout_after_repeated_failures(client):
    register_and_login(client, "dave")
    for _ in range(5):
        assert client.post(f"{API}/auth/login", data={"username": "dave", "password": "wrong"}).status_code == 401
    assert client.post(f"{API}/auth/login", data={"username": "dave", "password": "Passw0rd123"}).status_code == 429


def test_upload_detects_duplicates_with_different_names(client, auth):
    r = upload(client, auth, [f("a.txt", b"same content"), f("renamed.dat", b"same content"), f("c.txt", b"unique")])
    assert r.status_code == 202, r.text
    assert len(r.json()["uploaded"]) == 3

    listing = client.get(f"{API}/files", headers=auth).json()
    assert listing["total"] == 3 and all(i["status"] == "ready" for i in listing["items"])

    groups = client.get(f"{API}/duplicates/groups", headers=auth).json()
    assert groups["total"] == 1
    g = groups["items"][0]
    assert g["original"]["original_filename"] == "a.txt"
    assert [d["original_filename"] for d in g["duplicates"]] == ["renamed.dat"]
    assert g["potential_savings"] == len(b"same content") and g["total_storage"] == 2 * len(b"same content")

    s = client.get(f"{API}/analytics/summary", headers=auth).json()
    assert s["total_files"] == 3 and s["duplicate_files"] == 1 and s["duplicate_groups"] == 1
    assert s["potential_savings"] == len(b"same content")
    assert s["total_storage"] == 2 * len(b"same content") + len(b"unique")
    assert len(s["uploads_timeline"]) == 14 and s["largest_files"] and s["recent_uploads"]


def test_rejects_dangerous_uploads_but_keeps_valid_ones(client, auth):
    r = upload(client, auth, [f("ok.txt", b"fine"), f("virus.exe", b"MZ....")])
    body = r.json()
    assert r.status_code == 202
    assert len(body["uploaded"]) == 1 and body["rejected"][0]["filename"] == "virus.exe"
    assert upload(client, auth, [f("bad.exe", b"x")]).status_code == 422


def test_empty_and_oversized_files_rejected(client, auth):
    assert upload(client, auth, [f("empty.txt", b"")]).status_code == 422
    assert upload(client, auth, [f("big.txt", b"a" * (6 * 1024 * 1024))]).status_code == 422  # limit is 5 MB in tests


def test_search_filter_sort_paginate(client, auth):
    upload(client, auth, [f("alpha.txt", b"1"), f("beta.txt", b"22"), f("gamma.json", b"333", "application/json")])
    q = lambda **p: client.get(f"{API}/files", headers=auth, params=p).json()
    assert q(q="ALP")["total"] == 1
    assert q(extension="json")["items"][0]["original_filename"] == "gamma.json"
    assert q(min_size=2)["total"] == 2
    assert q(max_size=1)["total"] == 1
    assert [i["original_filename"] for i in q(sort_by="size", sort_order="desc")["items"]][0] == "gamma.json"
    page = q(page=2, page_size=2, sort_by="name", sort_order="asc")
    assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 1
    assert q(duplicates="unique")["total"] == 3
    assert q(q="100%")["total"] == 0  # LIKE wildcards are escaped


def test_users_cannot_access_each_others_files(client, auth, auth_bob):
    fid = upload(client, auth, [f("secret.txt", b"alice only")]).json()["uploaded"][0]["id"]
    assert client.get(f"{API}/files/{fid}", headers=auth_bob).status_code == 404
    assert client.get(f"{API}/files/{fid}/download", headers=auth_bob).status_code == 404
    assert client.delete(f"{API}/files/{fid}?confirm=true", headers=auth_bob).status_code == 404
    assert client.get(f"{API}/files", headers=auth_bob).json()["total"] == 0
    # same bytes uploaded by bob must not form a duplicate with alice's file
    upload(client, auth_bob, [f("mine.txt", b"alice only")])
    assert client.get(f"{API}/duplicates/groups", headers=auth_bob).json()["total"] == 0


def test_download_returns_original_bytes_as_attachment(client, auth):
    fid = upload(client, auth, [f("hello.txt", b"hello world")]).json()["uploaded"][0]["id"]
    r = client.get(f"{API}/files/{fid}/download", headers=auth)
    assert r.status_code == 200 and r.content == b"hello world"
    assert "attachment" in r.headers["content-disposition"]


def test_safe_delete_workflow(client, auth):
    ids = [i["id"] for i in upload(client, auth, [f("a.txt", b"dup!"), f("b.txt", b"dup!")]).json()["uploaded"]]
    original, copy = ids

    # confirmation is mandatory
    assert client.delete(f"{API}/files/{copy}", headers=auth).status_code == 400

    # preview shows storage impact
    prev = client.post(f"{API}/files/deletion-preview", headers=auth, json={"file_ids": [copy]}).json()
    assert prev["total_bytes"] == 4 and prev["redundant_bytes_removed"] == 4 and prev["can_delete"] is True

    # protected files cannot be deleted
    assert client.patch(f"{API}/files/{copy}/protection", headers=auth, json={"is_protected": True}).status_code == 200
    blocked = client.delete(f"{API}/files/{copy}?confirm=true", headers=auth)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "protected_file"
    assert client.post(f"{API}/files/deletion-preview", headers=auth, json={"file_ids": [copy]}).json()["can_delete"] is False

    client.patch(f"{API}/files/{copy}/protection", headers=auth, json={"is_protected": False})
    done = client.delete(f"{API}/files/{copy}?confirm=true&reason=cleanup", headers=auth)
    assert done.status_code == 200 and done.json()["freed_bytes"] == 4

    # history + group dissolved + remaining file is unique again
    hist = client.get(f"{API}/history/deletions", headers=auth).json()
    assert hist["total"] == 1 and hist["items"][0]["filename"] == "b.txt" and hist["items"][0]["reason"] == "cleanup"
    assert client.get(f"{API}/duplicates/groups", headers=auth).json()["total"] == 0
    assert client.get(f"{API}/files/{original}", headers=auth).json()["is_duplicate"] is False
    actions = [a["action"] for a in client.get(f"{API}/history/audit", headers=auth).json()["items"]]
    assert "file.delete" in actions and "file.upload" in actions


def test_group_cleanup_keeps_original_and_skips_protected(client, auth):
    ids = [i["id"] for i in upload(client, auth, [f(f"c{n}.txt", b"same") for n in range(4)]).json()["uploaded"]]
    client.patch(f"{API}/files/{ids[3]}/protection", headers=auth, json={"is_protected": True})
    gid = client.get(f"{API}/files/{ids[0]}", headers=auth).json()["duplicate_group_id"]

    assert client.post(f"{API}/duplicates/groups/{gid}/cleanup", headers=auth, json={}).status_code == 400
    r = client.post(f"{API}/duplicates/groups/{gid}/cleanup", headers=auth, json={"confirm": True}).json()
    assert r["deleted_count"] == 2 and r["skipped_protected_ids"] == [ids[3]]
    remaining = client.get(f"{API}/files", headers=auth).json()["items"]
    assert {i["id"] for i in remaining} == {ids[0], ids[3]}
