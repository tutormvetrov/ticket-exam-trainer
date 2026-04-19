"""i18n invariants: required keys present, no placeholders, all values non-empty."""

from __future__ import annotations


def test_text_has_required_keys():
    from ui_flet.i18n.ru import TEXT
    required = {
        # navigation + app
        "app_title", "app_subtitle",
        "nav.tickets", "nav.training", "nav.settings",
        # tickets view
        "tickets.title", "tickets.subtitle", "tickets.search",
        "tickets.filter.all", "tickets.filter.section", "tickets.filter.difficulty",
        "tickets.empty", "tickets.train", "tickets.no_selection",
        # training view
        "training.title", "training.back_to_list", "training.pick_mode",
        # six mode titles and hints
        "mode.reading.title", "mode.reading.hint",
        "mode.plan.title", "mode.plan.hint",
        "mode.cloze.title", "mode.cloze.hint",
        "mode.active_recall.title", "mode.active_recall.hint",
        "mode.state_exam_full.title", "mode.state_exam_full.hint",
        "mode.review.title", "mode.review.hint",
        # six answer blocks
        "block.intro", "block.theory", "block.practice",
        "block.skills", "block.conclusion", "block.extra",
        # result labels
        "result.score", "result.weak_points", "result.strengths",
        "result.recommendations", "result.per_thesis",
        "result.covered", "result.partial", "result.missing",
        "result.review_fallback",
        # timer
        "timer.start", "timer.pause", "timer.elapsed",
        # settings
        "settings.title", "settings.theme", "settings.theme.light", "settings.theme.dark",
        "settings.ollama.title", "settings.ollama.model", "settings.ollama.test",
        "settings.ollama.install_hint",
        "settings.about", "settings.version", "settings.seed",
        # ollama badge
        "ollama.ok", "ollama.offline",
    }
    missing = required - set(TEXT.keys())
    assert not missing, f"Missing i18n keys: {sorted(missing)}"


def test_all_values_nonempty():
    from ui_flet.i18n.ru import TEXT
    empty = [k for k, v in TEXT.items() if not v or not v.strip()]
    assert not empty, f"Empty values for: {empty}"


def test_no_obvious_placeholders():
    from ui_flet.i18n.ru import TEXT
    bad_tokens = ("TODO", "XXX", "FIXME", "<<<", ">>>")
    hits = [(k, v) for k, v in TEXT.items() if any(t in v for t in bad_tokens)]
    assert not hits, f"Placeholders left: {hits}"
