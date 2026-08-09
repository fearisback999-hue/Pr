"""Money guards. Every test here exists because the path it covers could spend
real money twice, spend it unbounded, or spend it and lose the receipt."""

import pytest

from tt_engine.creative import spend
from tt_engine.creative.mcp_client import HiggsfieldMCP, PartialBatch, recover_jobs
from tt_engine.creative.video_spec import AlreadyGenerated, create_spec, generate_from_spec
from tt_engine.db import Database, models


# ── size cap ──────────────────────────────────────────────────────────────────

def test_batch_size_is_capped():
    """`--variations 3000` is a typo, and without the cap it submits 3000 paid jobs."""
    with pytest.raises(spend.BatchTooLarge) as e:
        spend.clamp_variations(3000)
    assert "typo" in str(e.value)
    assert spend.clamp_variations(spend.MAX_BATCH) == spend.MAX_BATCH


def test_batch_size_rejects_zero_and_negative():
    for bad in (0, -1, -100):
        with pytest.raises(spend.BatchTooLarge):
            spend.clamp_variations(bad)


# ── cost estimate ─────────────────────────────────────────────────────────────

def test_cost_is_never_guessed_when_unpriced(monkeypatch):
    """An invented default price in the file whose job is preventing invented
    numbers would be worse than saying 'unpriced'."""
    monkeypatch.delenv("TT_GENERATION_UNIT_COST", raising=False)
    est = spend.estimate(30)
    assert est.total is None
    assert not est.priced
    assert "UNPRICED" in est.render()
    assert "TT_GENERATION_UNIT_COST" in est.render()


def test_priced_estimate_shows_dollars_and_cost_per_usable(monkeypatch):
    monkeypatch.setenv("TT_GENERATION_UNIT_COST", "0.40")
    monkeypatch.delenv("TT_MAX_BATCH_SPEND", raising=False)
    est = spend.estimate(30)
    assert est.total == 12.00
    text = est.render()
    assert "$12.00" in text
    assert "per USABLE clip" in text   # the honest unit, at the ~30% keep rate


def test_malformed_cost_env_is_ignored_not_crashed(monkeypatch):
    monkeypatch.setenv("TT_GENERATION_UNIT_COST", "not-a-number")
    assert spend.unit_cost() is None
    monkeypatch.setenv("TT_GENERATION_UNIT_COST", "-5")
    assert spend.unit_cost() is None


# ── spend ceiling ─────────────────────────────────────────────────────────────

def test_ceiling_refuses_the_batch_even_when_confirmed(monkeypatch):
    """The ceiling is for the moment you are tired and typing fast — confirm
    is not supposed to be able to override it."""
    monkeypatch.setenv("TT_GENERATION_UNIT_COST", "1.00")
    monkeypatch.setenv("TT_MAX_BATCH_SPEND", "25")
    with pytest.raises(spend.SpendCeilingExceeded) as e:
        spend.guard(40)                      # $40 > $25
    assert "Nothing was submitted" in str(e.value)
    spend.guard(20)                          # $20 under the ceiling — fine


def test_no_ceiling_configured_means_only_the_size_cap(monkeypatch):
    monkeypatch.delenv("TT_MAX_BATCH_SPEND", raising=False)
    monkeypatch.setenv("TT_GENERATION_UNIT_COST", "1000")
    spend.guard(50)                          # expensive, but no ceiling set → allowed
    with pytest.raises(spend.BatchTooLarge):
        spend.guard(500)                     # size cap still bites


# ── double-spend on a spec ────────────────────────────────────────────────────

def _product(db):
    p = models.Product(id="P1", name="Test Thing", category="home")
    db.upsert_product(p)
    return p


class _FakeMCP(HiggsfieldMCP):
    """Configured and wired — the only shape where real money moves."""
    def __init__(self, submissions=None, fail_at=None):
        super().__init__(api_key="k")
        self.submissions = submissions if submissions is not None else []
        self.fail_at = fail_at

    @property
    def available(self):
        return True

    def submit(self, kit, c):
        if self.fail_at is not None and len(self.submissions) >= self.fail_at:
            raise ConnectionError("network died mid-batch")
        self.submissions.append(c.id)
        return f"job-{len(self.submissions)}"

    def poll(self, job_id):
        return "ready", f"https://example.test/{job_id}.mp4"


def test_regenerating_a_spec_is_refused(tmp_path):
    """SPEC-<id> is a fixed creative id, so a second generate overwrites the first
    job id — paying twice AND destroying the receipt needed to recover run one."""
    db = Database(str(tmp_path / "t.db"))
    _product(db)
    sid = create_spec(db, "P1", actor_slug="", prompt="hold it up")
    db.update_video_spec(sid, status="approved")

    mcp = _FakeMCP()
    generate_from_spec(db, sid, confirm=True, mcp=mcp)
    assert len(mcp.submissions) == 1

    with pytest.raises(AlreadyGenerated) as e:
        generate_from_spec(db, sid, confirm=True, mcp=mcp)
    assert len(mcp.submissions) == 1, "second generate must not submit a paid job"
    assert "pay a second time" in str(e.value)
    db.close()


def test_spec_generation_respects_the_ceiling(tmp_path, monkeypatch):
    monkeypatch.setenv("TT_GENERATION_UNIT_COST", "50")
    monkeypatch.setenv("TT_MAX_BATCH_SPEND", "10")
    db = Database(str(tmp_path / "t.db"))
    _product(db)
    sid = create_spec(db, "P1", actor_slug="", prompt="hold it up")
    db.update_video_spec(sid, status="approved")

    mcp = _FakeMCP()
    with pytest.raises(spend.SpendCeilingExceeded):
        generate_from_spec(db, sid, confirm=True, mcp=mcp)
    assert mcp.submissions == [], "ceiling must fire before anything is submitted"
    db.close()


# ── orphaned paid jobs ────────────────────────────────────────────────────────

def test_recover_collects_jobs_that_were_paid_for_but_never_landed(tmp_path):
    """Generation is charged at submit. A crash between submit and poll means money
    spent for an asset the engine never saved — recovery is how you get it back."""
    db = Database(str(tmp_path / "t.db"))
    _product(db)
    orphan = models.Creative(
        id="C1", product_id="P1", format="UGC", hook="h", hook_type="t",
        soul_id="s", asset_url=None, status="generating",
        meta={"aigc_disclosure": "AI-generated", "job_id": "job-abc"},
    )
    db.upsert_creative(orphan)

    out = recover_jobs(db, mcp=_FakeMCP())
    assert "recovered 1 of 1" in out
    got = next(c for c in db.all_creatives() if c.id == "C1")
    assert got.status == "ready"
    assert got.asset_url                       # the thing the money already bought
    db.close()


def test_recover_without_a_key_says_do_not_regenerate(tmp_path):
    """The dangerous instinct when an asset is missing is to generate it again.
    Unrecoverable-from-here must never read as 'gone, start over'."""
    db = Database(str(tmp_path / "t.db"))
    _product(db)
    db.upsert_creative(models.Creative(
        id="C1", product_id="P1", format="UGC", hook="h", hook_type="t",
        soul_id="s", asset_url=None, status="generating",
        meta={"aigc_disclosure": "AI-generated", "job_id": "job-abc"}))

    class _Unconfigured(HiggsfieldMCP):
        def __init__(self): super().__init__(api_key="")
        @property
        def available(self): return False

    out = recover_jobs(db, mcp=_Unconfigured())
    assert "job-abc" in out                    # the receipt is surfaced, not lost
    assert "pays twice" in out
    db.close()


def test_recover_is_a_noop_when_nothing_is_outstanding(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    assert "nothing to recover" in recover_jobs(db, mcp=_FakeMCP())
    db.close()


# ── partial batch ─────────────────────────────────────────────────────────────

def test_partial_batch_stops_spending_and_points_at_recovery(tmp_path):
    """A mid-batch failure used to propagate uncaught, stranding already-paid jobs
    with no instruction for getting them back."""
    from tt_engine.creative.brief import build_kit
    from tt_engine.psychology import analyze
    db = Database(str(tmp_path / "t.db"))
    p = _product(db)
    kit = build_kit(p, analyze(p.name, ["love it"], p.category), variations=6,
                    soul_id="SOUL-1")
    mcp = _FakeMCP(fail_at=3)                  # dies after 3 paid submissions

    from tt_engine.creative.mcp_client import generate_batch
    with pytest.raises(PartialBatch) as e:
        generate_batch(db, kit, confirm=True, mcp=mcp)
    msg = str(e.value)
    assert "3 job(s) were already submitted and PAID FOR" in msg
    assert "creative-recover" in msg
    assert len(mcp.submissions) == 3, "must stop, not keep burning money"
    db.close()
