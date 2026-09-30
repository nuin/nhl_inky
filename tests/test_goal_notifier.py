"""Tests for how goal_notifier resolves and uses its notification destinations."""

import sys
from pathlib import Path

import apprise
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import goal_notifier  # noqa: E402
from goal_notifier import (  # noqa: E402
    GoalNotifier,
    legacy_smtp_url,
    notify_urls_from_env,
    split_urls,
)

# Placeholder credentials only. The password has characters that must be escaped.
LEGACY_ENV = {
    "SMTP_SERVER": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "sender@example.com",
    "SMTP_PASSWORD": "p@ss/w:rd&x",
    "PHONE_NUMBER": "5550001111",
}


def test_split_urls_accepts_commas_and_whitespace():
    assert split_urls("ntfy://a, ntfy://b\n  ntfy://c") == ["ntfy://a", "ntfy://b", "ntfy://c"]
    assert split_urls("") == []
    assert split_urls(None) == []


@pytest.mark.parametrize("missing", sorted(LEGACY_ENV))
def test_legacy_smtp_url_needs_every_setting(missing):
    env = {k: v for k, v in LEGACY_ENV.items() if k != missing}
    assert legacy_smtp_url(env) is None


def test_legacy_smtp_url_targets_the_telus_gateway():
    a = apprise.Apprise()
    assert a.add(legacy_smtp_url(LEGACY_ENV))

    email = a[0]
    assert email.smtp_host == "smtp.example.com"
    assert email.port == 587
    assert email.user == "sender@example.com"
    # Special characters in the password survive the round trip through the URL.
    assert email.password == "p@ss/w:rd&x"
    assert [addr for _, addr in email.targets] == ["5550001111@msg.telus.com"]


def test_notify_urls_prefers_notify_urls_over_smtp():
    env = dict(LEGACY_ENV, NOTIFY_URLS="ntfy://ntfy.sh/flyers-goals")
    assert notify_urls_from_env(env) == ["ntfy://ntfy.sh/flyers-goals"]


def test_notify_urls_falls_back_to_smtp():
    urls = notify_urls_from_env(LEGACY_ENV)
    assert len(urls) == 1 and urls[0].startswith("mailtos://")


def test_notify_urls_empty_when_nothing_configured():
    assert notify_urls_from_env({}) == []


def test_notifier_refuses_to_start_without_a_destination(monkeypatch):
    for key in [*LEGACY_ENV, "NOTIFY_URLS"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="NOTIFY_URLS"):
        GoalNotifier()


def test_notifier_rejects_invalid_url_without_echoing_it():
    with pytest.raises(ValueError) as excinfo:
        GoalNotifier(["notaservice://secret-token"])
    assert "secret-token" not in str(excinfo.value)


def test_send_notification_goes_through_apprise(monkeypatch):
    sent = []

    def fake_notify(self, body, **kwargs):
        sent.append(body)
        return True

    monkeypatch.setattr(goal_notifier.apprise.Apprise, "notify", fake_notify)
    notifier = GoalNotifier(["ntfy://ntfy.sh/flyers-goals", "ntfy://ntfy.sh/other"])

    assert len(notifier.apprise) == 2
    assert notifier.send_notification("🚨 FLYERS GOAL!") is True
    assert sent == ["🚨 FLYERS GOAL!"]


def test_send_notification_reports_failure(monkeypatch):
    monkeypatch.setattr(goal_notifier.apprise.Apprise, "notify", lambda self, body, **kw: False)
    notifier = GoalNotifier(["ntfy://ntfy.sh/flyers-goals"])
    assert notifier.send_notification("goal") is False


def test_send_notification_never_raises(monkeypatch):
    def boom(self, body, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(goal_notifier.apprise.Apprise, "notify", boom)
    notifier = GoalNotifier(["ntfy://ntfy.sh/flyers-goals"])
    assert notifier.send_notification("goal") is False
