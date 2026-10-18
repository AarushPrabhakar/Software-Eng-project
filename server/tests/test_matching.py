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
    assert r["breakdown"]["category"] == 15
    assert r["breakdown"]["brand"] == 20 and r["breakdown"]["colour"] == 20
    assert r["breakdown"]["location"] == 10 and r["breakdown"]["date"] == 10
    assert r["score"] >= 90 and r["tier"] == "high"


def test_date_fades_and_expires():
    near = score_pair(LOST, dict(FOUND, event_date="2026-09-12"))["breakdown"]["date"]
    far = score_pair(LOST, dict(FOUND, event_date="2026-09-20"))["breakdown"]["date"]
    gone = score_pair(LOST, dict(FOUND, event_date="2026-10-20"))["breakdown"]["date"]
    assert near > far > gone == 0


def test_found_before_lost_is_penalised():
    r = score_pair(LOST, dict(FOUND, event_date="2026-09-01"))
    assert r["breakdown"]["date"] == 0 and r["breakdown"]["penalty"] < 0


def test_missing_brand_is_neutral_not_a_match():
    r = score_pair(dict(LOST, brand=None), dict(FOUND, brand=None))
    assert 0 < r["breakdown"]["brand"] < 20 and r["breakdown"]["penalty"] == 0


def test_conflicting_brand_is_penalised():
    r = score_pair(LOST, dict(FOUND, brand="Cello"))
    assert r["breakdown"]["brand"] < 5 and r["breakdown"]["penalty"] < 0


def test_colour_families_and_synonyms():
    assert score_pair(LOST, dict(FOUND, colour="Navy"))["breakdown"]["colour"] == 20
    assert score_pair(LOST, dict(FOUND, colour="Red"))["breakdown"]["colour"] == 0
    assert description_similarity("steel flask", "steel bottle") == 1.0


def test_brand_tolerates_typos():
    assert score_pair(LOST, dict(FOUND, brand="Miltn"))["breakdown"]["brand"] > 14


def test_place_and_date_alone_cannot_unlock():
    other = dict(FOUND, brand="Cello", colour="Red", title="Thing", public_description="something different entirely")
    assert score_pair(LOST, other)["score"] < 60


def test_tier_thresholds():
    assert tier_for(75) == "high" and tier_for(74) == "possible"
    assert tier_for(60) == "possible" and tier_for(59) == "weak"


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
