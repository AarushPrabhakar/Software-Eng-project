"""
Matching accuracy benchmark on SYNTHETIC data (no real reports exist yet).

Run from the server folder:   python -m eval.run_eval

For each seed it invents N items. Every item gets a lost report and a found report written the way two
different people would describe it (typos, synonyms, blank fields, vague text, nearby places, days of delay).
Both reports are then mixed into a pool with many same-category distractors.

Reported:
  top1 / top3   how often the true partner ranks first / in the top three for its owner
  recall@50/75  share of true pairs scoring >= 50 (owner is told) / >= 75 (finder is told)
  false@50/75   share of WRONG pairs scoring >= 50 / >= 75 (these would wrongly unlock details or notify)

Caveat: the noise model is my assumption of real behaviour. Treat numbers as a regression benchmark and replace
the generator with real (anonymised) data once the pilot produces labelled matches.
"""
import random
import sys
from datetime import date, timedelta

from app import matching as v2
from eval import matching_v1 as v1

CATS = {
    "water_bottles": dict(nouns=["bottle", "flask", "tumbler", "sipper"], brands=["Milton", "Cello", "Borosil", "Tupperware", "Nike", "Decathlon"]),
    "bags_backpacks": dict(nouns=["backpack", "bag", "rucksack", "sling bag"], brands=["Wildcraft", "Skybags", "American Tourister", "Puma", "Adidas", "Safari"]),
    "earphones": dict(nouns=["earbuds", "earphones", "airpods", "headphones"], brands=["boAt", "Apple", "Realme", "Sony", "JBL", "Noise"]),
    "wallets_purses": dict(nouns=["wallet", "purse", "card holder"], brands=["Wildcraft", "Fastrack", "Hidesign", "Tommy", "Baggit"]),
    "keys": dict(nouns=["keys", "keychain", "key ring"], brands=["Yale", "Godrej", "None", "Hafele"]),
}
COLOURS = [("black", ["black", "jet black", "charcoal"]), ("blue", ["blue", "navy", "sky blue"]), ("red", ["red", "maroon"]),
           ("grey", ["grey", "silver", "steel"]), ("green", ["green", "olive"]), ("white", ["white", "cream"]),
           ("brown", ["brown", "tan"]), ("pink", ["pink"]), ("yellow", ["yellow"])]
FEATURES = ["dent near the base", "sticker of a cat", "scratch on the side", "broken strap", "initials AB written on it",
            "keychain attached", "cracked corner", "faded logo", "name tag inside", "zip is stuck", "gaming sticker",
            "red ribbon tied", "small tear", "coffee stain", "blue cap"]
PLACES = ["Central Library", "LT Complex", "Academic Block 2", "Hostel A", "Hostel J", "Sports Complex", "Cafeteria", "Main Gate", "Admin Block"]
NEAR = {"Central Library": ["LT Complex", "Academic Block 2"], "LT Complex": ["Central Library", "Academic Block 2"],
        "Academic Block 2": ["Central Library", "LT Complex"], "Hostel A": ["Hostel J"], "Hostel J": ["Hostel A"],
        "Sports Complex": ["Cafeteria"], "Cafeteria": ["Sports Complex"]}


def typo(s, rnd):
    if len(s) > 4 and rnd.random() < 0.5:
        i = rnd.randrange(1, len(s) - 1)
        return s[:i] + s[i + 1:]
    return s


def make_item(rnd, i):
    cat = rnd.choice(list(CATS))
    spec = CATS[cat]
    fam, names = rnd.choice(COLOURS)
    return dict(i=i, cat=cat, noun=rnd.choice(spec["nouns"]), brand=rnd.choice(spec["brands"]), fam=fam, names=names,
                feats=rnd.sample(FEATURES, 2), place=rnd.choice(PLACES), day=date(2026, 9, 1) + timedelta(days=rnd.randrange(0, 40)))


def describe(item, rnd, kind, uid):
    brand = item["brand"]
    if rnd.random() < 0.25: brand = None
    elif rnd.random() < 0.15: brand = typo(brand, rnd)
    colour = rnd.choice(item["names"]) if rnd.random() > 0.15 else None
    place = item["place"]
    if rnd.random() < 0.15: place = rnd.choice(NEAR.get(place, [place]))
    elif rnd.random() < 0.10: place = rnd.choice(PLACES)
    lag = rnd.choices([0, 1, 2, 4, 7, 11], [35, 25, 15, 12, 8, 5])[0]
    day = item["day"] if kind == "lost" else item["day"] + timedelta(days=lag)
    if kind == "found" and rnd.random() < 0.06: day = item["day"] - timedelta(days=1)
    feats = [f for f in item["feats"] if rnd.random() > 0.35]
    noun = item["noun"] if kind == "lost" else rnd.choice(CATS[item["cat"]]["nouns"])
    words = [colour or "", brand or "", noun] + feats
    text = " ".join(w for w in words if w)
    if rnd.random() < 0.2: text = noun            # lazy description
    title = f"{(colour or '').title()} {noun}".strip()
    return dict(id=f"{kind[0]}{item['i']}", reporter_id=f"{kind[0]}{uid}", report_type=kind, category=item["cat"], brand=brand,
                colour=colour, campus_location=place, event_date=day.isoformat(), status="active", title=title,
                public_description=text, truth=item["i"])


def evaluate(mod, lost, found, v2_mode, unlock):
    top1 = top3 = tp50 = tp75 = fp50 = fp75 = neg = 0
    for l in lost:
        cands = [f for f in found if f["category"] == l["category"] and f["reporter_id"] != l["reporter_id"]]
        if v2_mode:
            ranked = mod.rank_matches(l, cands)
            scored = [(m["report"], m["score"]) for m in ranked]
        else:
            scored = sorted(((f, mod.score_pair(l, f)["score"]) for f in cands), key=lambda x: -x[1])
        ids = [f["truth"] for f, _ in scored]
        if ids and ids[0] == l["truth"]: top1 += 1
        if l["truth"] in ids[:3]: top3 += 1
        for f, s in scored:
            if f["truth"] == l["truth"]:
                tp50 += s >= unlock; tp75 += s >= 75
            else:
                neg += 1; fp50 += s >= unlock; fp75 += s >= 75
    n = len(lost)
    return dict(top1=top1 / n, top3=top3 / n, recall50=tp50 / n, recall75=tp75 / n, false50=fp50 / max(neg, 1), false75=fp75 / max(neg, 1))


def main(seeds=5, n=150):
    agg = {"v1": [], "v2": []}
    for seed in range(seeds):
        rnd = random.Random(seed)
        items = [make_item(rnd, i) for i in range(n)]
        lost = [describe(it, rnd, "lost", it["i"]) for it in items]
        found = [describe(it, rnd, "found", it["i"] + 10_000) for it in items]
        agg["v1"].append(evaluate(v1, lost, found, False, 50))
        agg["v2"].append(evaluate(v2, lost, found, True, v2.POSSIBLE_THRESHOLD))
    keys = ["top1", "top3", "recall50", "recall75", "false50", "false75"]  # *50 = at the unlock threshold
    print(f"{seeds} seeds x {n} items, same-category distractors included (synthetic data)\n")
    print(f"{'metric':10s} {'v1':>8s} {'v2':>8s}")
    for k in keys:
        a = sum(r[k] for r in agg['v1']) / seeds
        b = sum(r[k] for r in agg['v2']) / seeds
        print(f"{k:10s} {a*100:7.1f}% {b*100:7.1f}%")


if __name__ == "__main__":
    main(*(int(x) for x in sys.argv[1:3]))
