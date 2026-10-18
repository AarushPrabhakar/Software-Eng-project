"""A tiny in-memory stand-in for the supabase-py client (only what the routers use)."""
import copy
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

DEFAULTS = {
    "item_reports": {"status": "active", "private_detail": None, "colour": None, "brand": None, "campus_location": None, "image_url": None},
    "claims": {"status": "submitted", "evidence_path": None, "review_note": None, "reviewed_by": None, "reviewed_at": None},
    "handovers": {"attempts": 0, "used_at": None, "confirmed_by": None},
    "notifications": {"is_read": False, "link": None},
    "flags": {"status": "open", "resolved_by": None, "resolved_at": None},
    "users": {"role": "student", "is_verified": False, "is_active": True},
}


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.op, self.payload, self.filters = "select", None, []
        self._order, self._limit, self._range, self._count, self._conflict = None, None, None, False, None

    def select(self, cols="*", count=None):
        self.op, self._count = "select", bool(count)
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows
        return self

    def upsert(self, rows, on_conflict=None):
        self.op, self.payload, self._conflict = "upsert", rows, on_conflict
        return self

    def update(self, values):
        self.op, self.payload = "update", values
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, c, v):
        self.filters.append((c, "eq", v)); return self

    def neq(self, c, v):
        self.filters.append((c, "neq", v)); return self

    def in_(self, c, vals):
        self.filters.append((c, "in", list(vals))); return self

    def ilike(self, c, v):
        self.filters.append((c, "ilike", v)); return self

    def gte(self, c, v):
        self.filters.append((c, "gte", v)); return self

    def lte(self, c, v):
        self.filters.append((c, "lte", v)); return self

    def or_(self, expr):
        # only supports "col.ilike.%x%,col2.ilike.%x%"
        parts = [p.split(".", 2) for p in expr.split(",")]
        self.filters.append((None, "or_ilike", [(c, v) for c, _, v in parts]))
        return self

    def order(self, c, desc=False):
        self._order = (c, desc); return self

    def limit(self, n):
        self._limit = n; return self

    def range(self, a, b):
        self._range = (a, b); return self

    def _match(self, row):
        for c, kind, v in self.filters:
            if kind == "or_ilike":
                if not any(val.strip("%").lower() in str(row.get(col) or "").lower() for col, val in v):
                    return False
                continue
            x = row.get(c)
            if kind == "eq" and x != v: return False
            if kind == "neq" and x == v: return False
            if kind == "in" and x not in v: return False
            if kind == "ilike" and v.strip("%").lower() not in str(x or "").lower(): return False
            if kind == "gte" and not (x is not None and str(x) >= v): return False
            if kind == "lte" and not (x is not None and str(x) <= v): return False
        return True

    def _prepare(self, row):
        row = {**DEFAULTS.get(self.table, {}), **row}
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if self.table == "item_reports":
            self.db.seq += 1
            row["report_code"] = f"LF-20260101-{self.db.seq:04d}"
            row["updated_at"] = row["created_at"]
        if self.table == "claims":
            live = ("submitted", "under_review", "approved")
            for r in self.db.tables["claims"]:
                if r["report_id"] == row["report_id"] and r["claimant_id"] == row["claimant_id"] and r["status"] in live:
                    raise Exception("duplicate key value violates unique constraint")
        return row

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            new = [self._prepare(copy.deepcopy(i)) for i in items]
            rows.extend(new)
            return SimpleNamespace(data=copy.deepcopy(new), count=None)
        if self.op == "upsert":
            keys = self._conflict.split(",")
            out = []
            for item in self.payload:
                hit = next((r for r in rows if all(r.get(k) == item[k] for k in keys)), None)
                if hit:
                    hit.update(item); out.append(hit)
                else:
                    r = self._prepare(copy.deepcopy(item)); rows.append(r); out.append(r)
            return SimpleNamespace(data=copy.deepcopy(out), count=None)
        hits = [r for r in rows if self._match(r)]
        if self.op == "update":
            for r in hits:
                r.update(copy.deepcopy(self.payload))
            return SimpleNamespace(data=copy.deepcopy(hits), count=None)
        if self.op == "delete":
            self.db.tables[self.table] = [r for r in rows if r not in hits]
            return SimpleNamespace(data=copy.deepcopy(hits), count=None)
        if self._order:
            c, desc = self._order
            hits.sort(key=lambda r: str(r.get(c)), reverse=desc)
        total = len(hits)
        if self._range:
            hits = hits[self._range[0]: self._range[1] + 1]
        if self._limit is not None:
            hits = hits[: self._limit]
        return SimpleNamespace(data=copy.deepcopy(hits), count=total if self._count else None)


class FakeBucket:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def upload(self, path, data, opts=None):
        self.store[(self.name, path)] = data

    def create_signed_url(self, path, seconds):
        return {"signedURL": f"https://signed.example/{self.name}/{path}?t=1"}


class FakeSupabase:
    def __init__(self):
        self.tables, self.seq, self.files = {}, 0, {}
        self.storage = SimpleNamespace(from_=lambda name: FakeBucket(self.files, name))

    def table(self, name):
        return Query(self, name)

    def add_user(self, uid, name, role="student"):
        self.tables.setdefault("users", []).append(
            {"id": uid, "name": name, "email": f"{name.lower()}@thapar.edu", "role": role, "is_verified": True, "is_active": True}
        )
