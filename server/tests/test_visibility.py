"""Found items: everyone sees a generic title; details only for matched owners."""
from tests.test_flow import mk_report

DETAIL_FIELDS = ("public_description", "colour", "brand", "campus_location", "event_date", "image_url", "private_detail")


def found(api, **over):
    return mk_report(api, "u-finder", "found", private_detail="cat sticker under the lid",
                     image_url="https://x/y.jpg", **over)


def feed(api, user, query=""):
    return api(user, "GET", f"/api/reports{query}").json()


def test_unmatched_viewer_sees_only_generic_title(api):
    f = found(api, title="Blue Milton bottle with a cat sticker")   # a leaky stored title
    row = feed(api, "u-other")["reports"][0]
    assert row["redacted"] is True and row["access"] == "hidden"
    assert row["title"] == "Water bottle or tumbler found"          # stored title is NOT exposed
    assert row["category"] == "water_bottles" and row["report_code"] == f["report_code"]
    for k in DETAIL_FIELDS:
        assert k not in row
    one = api("u-other", "GET", f"/api/reports/{f['report_code']}").json()["report"]
    assert one["redacted"] is True and "public_description" not in one


def test_weak_lost_report_does_not_unlock(api):
    found(api)
    # same category only -> 30 points, below the 50 unlock threshold
    mk_report(api, "u-other", "lost", brand="Cello", colour="Red", campus_location="Hostel A",
              event_date="2026-01-01", public_description="red plastic thing", title="red thing")
    rows = {r["report_type"]: r for r in feed(api, "u-other")["reports"]}
    assert rows["found"]["redacted"] is True


def test_matching_lost_report_unlocks_details_but_not_private_detail(api):
    found(api)
    mk_report(api, "u-owner", "lost")
    rows = {r["report_type"]: r for r in feed(api, "u-owner")["reports"]}
    row = rows["found"]
    assert row["redacted"] is False and row["access"] == "matched" and row["match_score"] >= 50
    assert row["colour"] == "Blue" and row["campus_location"] == "Central Library"
    assert "private_detail" not in row
    # ...and the notification does not leak details either
    msg = api("u-owner", "GET", "/api/notifications").json()["notifications"][0]["message"]
    assert "could be yours" in msg and "Milton" not in msg and "Blue" not in msg


def test_owner_and_admin_see_details(api):
    f = found(api)
    mine = api("u-finder", "GET", f"/api/reports/{f['report_code']}").json()["report"]
    assert mine["access"] == "owner" and mine["private_detail"] == "cat sticker under the lid"
    adm = api("u-admin", "GET", f"/api/reports/{f['report_code']}").json()["report"]
    assert adm["access"] == "admin" and adm["colour"] == "Blue" and "private_detail" not in adm


def test_search_filters_cannot_be_used_as_an_oracle(api):
    found(api)
    for q in ("?colour=blue", "?brand=milton", "?campus_location=library", "?search=milton", "?date_from=2026-09-01"):
        r = feed(api, "u-other", q)
        assert r["reports"] == [] and r["pagination"]["total"] == 0, q
    # a matched viewer can still filter
    mk_report(api, "u-owner", "lost")
    r = feed(api, "u-owner", "?colour=blue")
    assert {x["report_type"] for x in r["reports"]} == {"lost", "found"}
    # the finder can filter their own
    assert len(feed(api, "u-finder", "?report_type=found&brand=milton")["reports"]) == 1


def test_claim_requires_a_matching_lost_report(api):
    f = found(api)
    body = {"answers": "cat sticker under the lid"}
    r = api("u-other", "POST", f"/api/reports/{f['report_code']}/claims", json=body)
    assert r.status_code == 403 and "lost report" in r.json()["detail"]
    mk_report(api, "u-other", "lost")
    assert api("u-other", "POST", f"/api/reports/{f['report_code']}/claims", json=body).status_code == 201


def test_claimant_keeps_access_after_lost_report_closes(api):
    f = found(api)
    lost = mk_report(api, "u-owner", "lost")
    api("u-owner", "POST", f"/api/reports/{f['report_code']}/claims", json={"answers": "cat sticker under lid"})
    api("u-owner", "PATCH", f"/api/reports/{lost['report_code']}/status", json={"status": "closed"})
    assert api("u-owner", "GET", f"/api/reports/{f['report_code']}").json()["report"]["access"] == "claimant"


def test_lost_owner_match_list_hides_weak_found_items(api):
    mk_report(api, "u-finder", "found", brand="Cello", colour="Red", campus_location="Hostel A",
              event_date="2026-01-01", public_description="red plastic thing", title="x")
    lost = mk_report(api, "u-owner", "lost")
    assert api("u-owner", "GET", f"/api/reports/{lost['report_code']}/matches").json()["matches"] == []


# ---- lost reports are private too -------------------------------------------------------

def lost(api, user="u-owner", **over):
    return mk_report(api, user, "lost", private_detail="scratch shaped like an X", **over)


def test_other_peoples_lost_reports_are_hidden(api):
    rep = lost(api, title="Blue Milton bottle with an X scratch")
    row = feed(api, "u-other")["reports"][0]
    assert row["redacted"] is True and row["access"] == "hidden"
    assert row["title"] == "Water bottle or tumbler lost"              # stored title not exposed
    for k in DETAIL_FIELDS:
        assert k not in row
    one = api("u-other", "GET", f"/api/reports/{rep['report_code']}").json()["report"]
    assert one["redacted"] is True and "public_description" not in one and "private_detail" not in one


def test_lost_owner_and_admin_still_see_their_report(api):
    rep = lost(api)
    mine = api("u-owner", "GET", f"/api/reports/{rep['report_code']}").json()["report"]
    assert mine["access"] == "owner" and mine["colour"] == "Blue" and mine["private_detail"]
    adm = api("u-admin", "GET", f"/api/reports/{rep['report_code']}").json()["report"]
    assert adm["access"] == "admin" and adm["colour"] == "Blue" and "private_detail" not in adm


def test_cannot_copy_a_lost_report_to_unlock_a_found_item(api):
    """The attack: read someone's lost report, file a look-alike, unlock the found item."""
    victim = lost(api, "u-owner")
    found(api)
    seen = api("u-other", "GET", f"/api/reports/{victim['report_code']}").json()["report"]
    assert "colour" not in seen and "campus_location" not in seen and "brand" not in seen
    # the attacker has nothing to copy, so a blind report in a different place/colour/date stays locked
    mk_report(api, "u-other", "lost", brand="Cello", colour="Red", campus_location="Hostel A",
              event_date="2026-01-01", public_description="red plastic thing", title="red thing")
    rows = [r for r in feed(api, "u-other")["reports"] if r["report_type"] == "found"]
    assert rows and all(r["redacted"] for r in rows)


def test_filters_cannot_find_other_peoples_lost_reports(api):
    lost(api)
    for q in ("?colour=blue", "?brand=milton", "?campus_location=library", "?search=milton", "?report_type=lost&colour=blue"):
        rows = feed(api, "u-other", q)["reports"]
        assert rows == [], q
    # the owner can still filter their own report
    assert len(feed(api, "u-owner", "?colour=blue")["reports"]) == 1


def test_finder_never_sees_the_lost_report_behind_a_match(api):
    f = found(api)
    lost(api)
    res = api("u-finder", "GET", f"/api/reports/{f['report_code']}/matches").json()
    assert res["matches"] == [] and res["interested"] == 1
    assert "Blue" not in str(res) and "Library" not in str(res)


def test_report_creation_is_rate_limited(api):
    for _ in range(20):
        mk_report(api, "u-other", "lost")
    r = api("u-other", "POST", "/api/reports", json=dict(report_type="lost", category="water_bottles", title="x",
            public_description="x", colour="Blue", brand="Milton", campus_location="Central Library", event_date="2026-09-10"))
    assert r.status_code == 429
