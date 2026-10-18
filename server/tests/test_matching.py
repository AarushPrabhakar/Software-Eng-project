from app.matching import description_similarity, is_candidate, keywords, rank_matches, score_pair, tier_for

LOST = dict(id="1", reporter_id="a", report_type="lost", category="water_bottles", brand="Milton", colour="Blue",
            campus_location="Central Library", event_date="2026-09-10", status="active",
            title="Blue Milton steel bottle", public_description="Blue Milton steel bottle with a dent near the base")
FOUND = dict(LOST, id="2", reporter_id="b", report_type="found", event_date="2026-09-11",
             title="Steel bottle found", public_description="Blue steel bottle Milton, dent at the bottom")


def test_keywords_strip_punctuation_and_stopwords():
    assert keywords("The Blue bottle, with a DENT!") == {"blue", "bottle", "dent"}


def test_similarity_is_share_of_shared_keywords():
    assert description_similarity("blue steel bottle", "blue steel bottle") == 1.0
    assert description_similarity("blue steel bottle", "red wallet") == 0.0
    assert description_similarity("", "red wallet") == 0.0


def test_perfect_attribute_match_is_high():
    r = score_pair(LOST, FOUND)
    assert r["breakdown"]["category"] == 30
    assert r["breakdown"]["brand"] == 15 and r["breakdown"]["colour"] == 15
    assert r["breakdown"]["location"] == 15 and r["breakdown"]["date"] == 15
    assert r["score"] >= 75 and r["tier"] == "high"


def test_date_outside_window_loses_points():
    far = dict(FOUND, event_date="2026-09-20")
    assert score_pair(LOST, far)["breakdown"]["date"] == 0


def test_missing_brand_does_not_count_as_match():
    r = score_pair(dict(LOST, brand=None), dict(FOUND, brand=None))
    assert r["breakdown"]["brand"] == 0


def test_tier_thresholds():
    assert tier_for(75) == "high" and tier_for(74) == "possible"
    assert tier_for(50) == "possible" and tier_for(49) == "weak"


def test_mandatory_filters():
    assert is_candidate(LOST, FOUND)
    assert not is_candidate(LOST, dict(FOUND, category="wallets_purses"))   # different category
    assert not is_candidate(LOST, dict(FOUND, report_type="lost"))           # same type
    assert not is_candidate(LOST, dict(FOUND, status="returned"))            # not active
    assert not is_candidate(LOST, dict(FOUND, reporter_id="a"))              # own report


def test_rank_orders_best_first():
    weaker = dict(FOUND, id="3", brand="Cello", colour="Red", campus_location="Hostel A", public_description="red bottle")
    ranked = rank_matches(LOST, [weaker, FOUND])
    assert [m["report"]["id"] for m in ranked] == ["2", "3"]
