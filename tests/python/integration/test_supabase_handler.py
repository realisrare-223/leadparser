"""
Integration tests for exporters/supabase_handler.py (fully mocked).

The Supabase client is replaced with a MagicMock so no real network
calls are made. Tests verify:
  - SupabaseHandler raises EnvironmentError without credentials
  - _prepare_row() maps fields correctly
  - bulk_insert() calls upsert with correct arguments
  - bulk_insert() counts new vs duplicates correctly
  - bulk_insert() handles empty lead list
  - bulk_insert() handles upsert exceptions gracefully
  - get_all_leads() / get_unexported_leads() call select correctly
  - mark_exported() is a no-op
  - start_session() returns a non-empty string
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_env(monkeypatch):
    """Inject fake Supabase credentials into the environment."""
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-service-role-key")


@pytest.fixture
def mock_client():
    """A MagicMock that mimics the supabase-py client's chained API."""
    client = MagicMock()

    # Default: upsert returns 3 inserted rows
    upsert_response = MagicMock()
    upsert_response.data = [{"id": i} for i in range(3)]
    client.table.return_value.upsert.return_value.execute.return_value = upsert_response

    # Default: select returns an empty list
    select_response = MagicMock()
    select_response.data = []
    (client.table.return_value
           .select.return_value
           .gte.return_value
           .order.return_value
           .execute.return_value) = select_response

    return client


@pytest.fixture
def handler(mock_env, mock_client):
    """SupabaseHandler with a patched supabase.create_client."""
    with patch("exporters.supabase_handler.create_client", return_value=mock_client):
        from exporters.supabase_handler import SupabaseHandler
        h = SupabaseHandler()
        h.client = mock_client
        yield h


def _make_lead(**overrides):
    base = {
        "niche":          "plumbers",
        "name":           "Joe's Plumbing",
        "phone":          "(214) 555-0123",
        "secondary_phone": "",
        "address":        "123 Main St",
        "city":           "Dallas",
        "state":          "TX",
        "zip_code":       "75201",
        "hours":          "Mon-Fri 8am-6pm",
        "review_count":   45,
        "rating":         "3.8",
        "gmb_link":       "https://maps.google.com/?cid=1",
        "website":        "",
        "facebook":       "",
        "instagram":      "",
        "data_source":    "Google Maps",
        "lead_score":     18,
        "pitch_notes":    "Great lead",
        "additional_notes": "",
        "date_added":     "2026-01-01",
        "email":          "",
    }
    base.update(overrides)
    return base


# ── EnvironmentError without credentials ─────────────────────────────────────

class TestMissingCredentials:
    def test_raises_without_url(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        with patch("exporters.supabase_handler.create_client"):
            from exporters.supabase_handler import SupabaseHandler
            with pytest.raises(EnvironmentError):
                SupabaseHandler()

    def test_raises_with_only_url(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        with patch("exporters.supabase_handler.create_client"):
            from exporters.supabase_handler import SupabaseHandler
            with pytest.raises(EnvironmentError):
                SupabaseHandler()


# ── _prepare_row() field mapping ─────────────────────────────────────────────

class TestPrepareRow:
    def test_required_fields_present(self, handler):
        row = handler._prepare_row(_make_lead())
        required = {
            "dedup_key", "niche", "name", "phone", "city", "state",
            "lead_score", "email", "date_added"
        }
        assert required.issubset(row.keys())

    def test_dedup_key_is_md5_hex(self, handler):
        row = handler._prepare_row(_make_lead())
        assert len(row["dedup_key"]) == 32  # MD5 hex

    def test_dedup_key_case_insensitive(self, handler):
        row1 = handler._prepare_row(_make_lead(name="Joe's Plumbing", city="Dallas"))
        row2 = handler._prepare_row(_make_lead(name="JOE'S PLUMBING", city="DALLAS"))
        assert row1["dedup_key"] == row2["dedup_key"]

    def test_none_fields_default_to_empty_string(self, handler):
        row = handler._prepare_row(_make_lead(website=None, facebook=None))
        assert row["website"]  == ""
        assert row["facebook"] == ""

    def test_review_count_coerced_to_int(self, handler):
        row = handler._prepare_row(_make_lead(review_count="42"))
        assert isinstance(row["review_count"], int)
        assert row["review_count"] == 42

    def test_raises_when_name_missing(self, handler):
        with pytest.raises(ValueError):
            handler._prepare_row(_make_lead(name=""))

    def test_raises_when_niche_missing(self, handler):
        with pytest.raises(ValueError):
            handler._prepare_row(_make_lead(niche=""))

    def test_email_field_present(self, handler):
        row = handler._prepare_row(_make_lead(email="test@example.com"))
        assert row["email"] == "test@example.com"


# ── bulk_insert() ─────────────────────────────────────────────────────────────

class TestBulkInsert:
    def test_empty_leads_returns_zero_stats(self, handler):
        stats = handler.bulk_insert([])
        assert stats == {"new": 0, "duplicates": 0, "errors": 0}

    def test_counts_inserted_rows(self, handler, mock_client):
        # Mock returns 2 inserted rows for a chunk of 3
        response = MagicMock()
        response.data = [{"id": 1}, {"id": 2}]
        mock_client.table.return_value.upsert.return_value.execute.return_value = response

        leads = [_make_lead(name=f"Business {i}", city="Dallas") for i in range(3)]
        stats = handler.bulk_insert(leads)
        assert stats["new"] == 2
        assert stats["duplicates"] == 1
        assert stats["errors"] == 0

    def test_counts_all_duplicates_when_nothing_inserted(self, handler, mock_client):
        response = MagicMock()
        response.data = []
        mock_client.table.return_value.upsert.return_value.execute.return_value = response

        leads = [_make_lead(name="Biz", city="Dallas")]
        stats = handler.bulk_insert(leads)
        assert stats["duplicates"] == 1
        assert stats["new"] == 0

    def test_upsert_called_with_on_conflict(self, handler, mock_client):
        leads = [_make_lead()]
        handler.bulk_insert(leads)
        call_kwargs = mock_client.table.return_value.upsert.call_args
        assert call_kwargs is not None
        assert "on_conflict" in call_kwargs.kwargs or "dedup_key" in str(call_kwargs)

    def test_bad_lead_counted_as_error(self, handler):
        bad_lead = {"name": "", "niche": ""}
        stats = handler.bulk_insert([bad_lead])
        assert stats["errors"] == 1

    def test_exception_in_upsert_counted_as_errors(self, handler, mock_client):
        mock_client.table.return_value.upsert.return_value.execute.side_effect = Exception("DB down")
        leads = [_make_lead()]
        stats = handler.bulk_insert(leads)
        assert stats["errors"] >= 1


# ── get_all_leads() ───────────────────────────────────────────────────────────

class TestGetAllLeads:
    def test_returns_list(self, handler, mock_client):
        response = MagicMock()
        response.data = [{"id": "1", "name": "Joe"}]
        (mock_client.table.return_value
                    .select.return_value
                    .gte.return_value
                    .order.return_value
                    .execute.return_value) = response

        result = handler.get_all_leads()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_empty_on_exception(self, handler, mock_client):
        mock_client.table.return_value.select.side_effect = Exception("fail")
        result = handler.get_all_leads()
        assert result == []


# ── get_unexported_leads() ────────────────────────────────────────────────────

class TestGetUnexportedLeads:
    def test_returns_list(self, handler, mock_client):
        response = MagicMock()
        response.data = []
        (mock_client.table.return_value
                    .select.return_value
                    .gte.return_value
                    .is_.return_value
                    .order.return_value
                    .execute.return_value) = response

        result = handler.get_unexported_leads()
        assert isinstance(result, list)


# ── mark_exported() ───────────────────────────────────────────────────────────

class TestMarkExported:
    def test_is_noop(self, handler):
        """mark_exported should not raise and return None."""
        result = handler.mark_exported(["id1", "id2"])
        assert result is None


# ── start_session() ───────────────────────────────────────────────────────────

class TestStartSession:
    def test_returns_non_empty_string(self, handler, sample_config):
        session_id = handler.start_session(["plumbers"], sample_config)
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_session_id_format(self, handler, sample_config):
        """Session ID should be a timestamp-like string."""
        session_id = handler.start_session(["plumbers"], sample_config)
        assert "_" in session_id  # e.g. 20260303_123456


# ── Context manager ───────────────────────────────────────────────────────────

class TestContextManager:
    def test_context_manager_works(self, mock_env, mock_client):
        with patch("exporters.supabase_handler.create_client", return_value=mock_client):
            from exporters.supabase_handler import SupabaseHandler
            with SupabaseHandler() as db:
                assert db is not None
