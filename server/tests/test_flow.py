"""End-to-end flow against an in-memory fake of Supabase."""
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def mk_report(api, user, rtype, **over):
    body = dict(report_type=rtype, category="water_bottles", title="Blue Milton bottle",
                public_description="Blue Milton steel bottle with a dent", colour="Blue", brand="Milton",
                campus_location="Central Library", event_date="2026-09-10")
    body.update(over)
    r = api(user, "POST", "/api/reports", json=body)
    assert r.status_code == 201, r.text
    return r.json()["report"]


def owner_lost(api, user="u-owner"):
    """The claimant's own lost report — claims are only allowed against matching items."""
    return mk_report(api, user, "lost")


def found_with_secret(api):
    return mk_report(api, "u-finder", "found", private_detail="Sticker of a cat under the lid")


def test_new_report_creates_matches_and_notifications(api):
    lost = mk_report(api, "u-owner", "lost")
    found = found_with_secret(api)
    m = api("u-owner", "GET", f"/api/reports/{lost['report_code']}/matches").json()["matches"]
    assert len(m) == 1 and m[0]["tier"] == "high"
    assert "private_detail" not in m[0]["report"]
    assert api("u-finder", "GET", "/api/notifications").json()["unread_count"] == 1
    assert api("u-owner", "GET", "/api/notifications").json()["unread_count"] == 1
    # only the owner may see matches
    assert api("u-other", "GET", f"/api/reports/{found['report_code']}/matches").status_code == 403


def test_private_detail_visibility(api):
    found = found_with_secret(api)
    assert "private_detail" not in api("u-other", "GET", f"/api/reports/{found['report_code']}").json()["report"]
    assert api("u-finder", "GET", f"/api/reports/{found['report_code']}").json()["report"]["private_detail"]


def test_full_claim_to_return_flow(api, db):
    found = found_with_secret(api)
    code = found["report_code"]

    # cannot claim own item / cannot claim a lost report / cannot claim without a matching lost report
    assert api("u-finder", "POST", f"/api/reports/{code}/claims", json={"answers": "x" * 20}).status_code == 403
    lost = owner_lost(api)
    assert api("u-other", "POST", f"/api/reports/{lost['report_code']}/claims", json={"answers": "x" * 20}).status_code == 400
    assert api("u-other", "POST", f"/api/reports/{code}/claims", json={"answers": "x" * 20}).status_code == 403

    r = api("u-owner", "POST", f"/api/reports/{code}/claims", json={"answers": "There is a cat sticker under the lid"})
    assert r.status_code == 201
    cid = r.json()["claim"]["id"]
    assert api("u-owner", "POST", f"/api/reports/{code}/claims", json={"answers": "again again again"}).status_code == 409

    # a second claimant (who also has a matching lost report)
    owner_lost(api, "u-other")
    c2 = api("u-other", "POST", f"/api/reports/{code}/claims", json={"answers": "I think it was blue maybe"}).json()["claim"]["id"]

    # outsiders can't even see the claim
    assert api("u-admin", "GET", f"/api/claims/{cid}").status_code == 200   # admin allowed
    assert api("u-other", "GET", f"/api/claims/{cid}").status_code == 404

    # finder sees private detail, claimant does not; no contact before approval
    fin = api("u-finder", "GET", f"/api/claims/{cid}").json()
    assert fin["private_detail"] == "Sticker of a cat under the lid" and "contact" not in fin
    assert "private_detail" not in api("u-owner", "GET", f"/api/claims/{cid}").json()

    # claimant cannot review own claim; handover not available before approval
    assert api("u-owner", "PATCH", f"/api/claims/{cid}/status", json={"status": "approved"}).status_code == 403
    assert api("u-owner", "POST", f"/api/claims/{cid}/handover").status_code == 409

    assert api("u-finder", "PATCH", f"/api/claims/{cid}/status", json={"status": "under_review"}).status_code == 200
    ok = api("u-finder", "PATCH", f"/api/claims/{cid}/status", json={"status": "approved", "note": "matches"})
    assert ok.status_code == 200
    assert api("u-finder", "PATCH", f"/api/claims/{cid}/status", json={"status": "rejected"}).status_code == 409  # terminal

    # report now claimed; other claim auto-rejected
    assert api("u-finder", "GET", f"/api/reports/{code}").json()["report"]["status"] == "claimed"
    assert api("u-other", "GET", f"/api/claims/{c2}").json()["claim"]["status"] == "rejected"

    # contact is revealed to both sides after approval
    assert api("u-finder", "GET", f"/api/claims/{cid}").json()["contact"]["name"] == "Owner"
    assert api("u-owner", "GET", f"/api/claims/{cid}").json()["contact"]["name"] == "Finder"

    # handover code: returned once, only the hash is stored
    h = api("u-owner", "POST", f"/api/claims/{cid}/handover").json()
    assert len(h["code"]) == 6
    stored = db.tables["handovers"][0]
    assert h["code"] not in str(stored) and stored["code_hash"]
    assert api("u-finder", "POST", f"/api/claims/{cid}/handover").status_code == 403

    # wrong code, then right code
    bad = "000000" if h["code"] != "000000" else "111111"
    r = api("u-finder", "POST", f"/api/handovers/{h['handover_id']}/confirm", json={"code": bad})
    assert r.status_code == 400 and "4 attempt" in r.json()["detail"]
    assert api("u-owner", "POST", f"/api/handovers/{h['handover_id']}/confirm", json={"code": h["code"]}).status_code == 404  # not the finder
    done = api("u-finder", "POST", f"/api/handovers/{h['handover_id']}/confirm", json={"code": h["code"]})
    assert done.status_code == 200 and done.json()["status"] == "returned"
    assert api("u-finder", "GET", f"/api/reports/{code}").json()["report"]["status"] == "returned"

    # one-time: cannot be reused
    assert api("u-finder", "POST", f"/api/handovers/{h['handover_id']}/confirm", json={"code": h["code"]}).status_code == 409

    # audit trail exists
    actions = {a["action"] for a in db.tables["audit_log"]}
    assert {"claim.submitted", "claim.approved", "handover.created", "handover.confirmed", "handover.wrong_code"} <= actions


def test_handover_locks_after_too_many_wrong_codes_and_expires(api, db):
    found = found_with_secret(api)
    owner_lost(api)
    cid = api("u-owner", "POST", f"/api/reports/{found['report_code']}/claims", json={"answers": "cat sticker under lid"}).json()["claim"]["id"]
    api("u-finder", "PATCH", f"/api/claims/{cid}/status", json={"status": "approved"})
    h = api("u-owner", "POST", f"/api/claims/{cid}/handover").json()
    bad = "000000" if h["code"] != "000000" else "111111"
    for _ in range(5):
        assert api("u-finder", "POST", f"/api/handovers/{h['handover_id']}/confirm", json={"code": bad}).status_code == 400
    assert api("u-finder", "POST", f"/api/handovers/{h['handover_id']}/confirm", json={"code": h["code"]}).status_code == 423

    # regenerating gives a fresh code
    h2 = api("u-owner", "POST", f"/api/claims/{cid}/handover").json()
    db.tables["handovers"][0]["expires_at"] = "2000-01-01T00:00:00+00:00"
    assert api("u-finder", "POST", f"/api/handovers/{h2['handover_id']}/confirm", json={"code": h2["code"]}).status_code == 410


def test_evidence_upload_rules(api, db):
    found = found_with_secret(api)
    owner_lost(api)
    cid = api("u-owner", "POST", f"/api/reports/{found['report_code']}/claims", json={"answers": "cat sticker under lid"}).json()["claim"]["id"]
    up = lambda user, name, data, ctype: api(user, "POST", f"/api/claims/{cid}/evidence", files={"file": (name, data, ctype)})
    assert up("u-owner", "x.exe", b"MZ" + b"0" * 50, "application/x-msdownload").status_code == 415
    assert up("u-owner", "x.png", b"MZ" + b"0" * 50, "image/png").status_code == 415            # lying content-type
    assert up("u-owner", "x.png", PNG + b"0" * (5 * 1024 * 1024), "image/png").status_code == 413
    assert up("u-finder", "x.png", PNG, "image/png").status_code == 403
    assert up("u-owner", "x.png", PNG, "image/png").status_code == 200
    ev = api("u-finder", "GET", f"/api/claims/{cid}").json()["claim"]
    assert ev["evidence_url"].startswith("https://signed.example/claim-evidence/") and "evidence_path" not in ev


def test_withdraw_and_reject_keep_report_open(api):
    found = found_with_secret(api)
    owner_lost(api)
    owner_lost(api, "u-other")
    code = found["report_code"]
    cid = api("u-owner", "POST", f"/api/reports/{code}/claims", json={"answers": "some guess at contents"}).json()["claim"]["id"]
    assert api("u-owner", "PATCH", f"/api/claims/{cid}/status", json={"status": "withdrawn"}).status_code == 200
    cid2 = api("u-other", "POST", f"/api/reports/{code}/claims", json={"answers": "another wrong guess"}).json()["claim"]["id"]
    assert api("u-finder", "PATCH", f"/api/claims/{cid2}/status", json={"status": "rejected"}).status_code == 200
    assert api("u-finder", "GET", f"/api/reports/{code}").json()["report"]["status"] == "active"
    assert len(api("u-finder", "GET", "/api/claims/received").json()["claims"]) == 2
    assert len(api("u-other", "GET", "/api/claims/mine").json()["claims"]) == 1


def test_owner_cannot_fake_returned_status(api):
    found = found_with_secret(api)
    r = api("u-finder", "PATCH", f"/api/reports/{found['report_code']}/status", json={"status": "returned"})
    assert r.status_code == 400


def test_claim_rate_limit(api):
    owner_lost(api)
    codes = [mk_report(api, "u-finder", "found")["report_code"] for _ in range(6)]
    results = [api("u-owner", "POST", f"/api/reports/{c}/claims", json={"answers": "some answer here"}).status_code for c in codes]
    assert results[:5] == [201] * 5 and results[5] == 429


def test_notifications_read(api):
    mk_report(api, "u-owner", "lost")
    found_with_secret(api)
    n = api("u-owner", "GET", "/api/notifications").json()["notifications"]
    assert api("u-other", "PATCH", f"/api/notifications/{n[0]['id']}/read").status_code == 404
    assert api("u-owner", "PATCH", f"/api/notifications/{n[0]['id']}/read").status_code == 200
    assert api("u-owner", "GET", "/api/notifications").json()["unread_count"] == 0


def test_flags_autohide_and_admin_moderation(api, db):
    found = found_with_secret(api)
    code = found["report_code"]
    db.add_user("u-x", "X"); db.add_user("u-y", "Y")
    assert api("u-finder", "POST", "/api/flags", json={"report_ref": code, "reason": "spam"*3}).status_code == 403
    for u in ("u-owner", "u-other"):
        assert api(u, "POST", "/api/flags", json={"report_ref": code, "reason": "looks fake"}).json()["report_hidden"] is False
    assert api("u-other", "POST", "/api/flags", json={"report_ref": code, "reason": "looks fake"}).status_code == 409
    assert api("u-x", "POST", "/api/flags", json={"report_ref": code, "reason": "looks fake"}).json()["report_hidden"] is True
    assert api("u-owner", "GET", "/api/reports").json()["reports"] == []   # hidden from feed

    # admin only
    assert api("u-owner", "GET", "/api/admin/flags").status_code == 403
    flags = api("u-admin", "GET", "/api/admin/flags").json()["flags"]
    assert len(flags) == 3
    for f in flags[:2]:
        api("u-admin", "PATCH", f"/api/admin/flags/{f['id']}", json={"action": "dismiss"})
    assert api("u-admin", "GET", f"/api/reports/{code}").json()["report"]["status"] == "flagged"  # one flag still open
    api("u-admin", "PATCH", f"/api/admin/flags/{flags[2]['id']}", json={"action": "dismiss"})
    assert api("u-admin", "GET", f"/api/reports/{code}").json()["report"]["status"] == "active"   # restored

    f = api("u-y", "POST", "/api/flags", json={"report_ref": code, "reason": "abusive text"}).json()["flag"]
    api("u-admin", "PATCH", f"/api/admin/flags/{f['id']}", json={"action": "remove"})
    assert api("u-admin", "GET", f"/api/reports/{code}").json()["report"]["status"] == "closed"
    assert api("u-admin", "GET", "/api/admin/stats").json()["reports"]["total"] == 1
    assert len(api("u-admin", "GET", "/api/admin/audit").json()["entries"]) > 0
