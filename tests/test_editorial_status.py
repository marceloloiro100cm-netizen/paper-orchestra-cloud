"""M07: retratações, correções e avisos editoriais via Crossref, sem rede."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from editorial_status import editorial_status, notices_for, summarize

DOI = "10.1177/17588359231172420"


def fake_request(items=None, status="ok"):
    calls = []

    def request(session, url, params, headers):
        calls.append((url, params))
        return ({"message": {"items": items or []}} if status == "ok" else None), status
    request.calls = calls
    return request


# Formato documentado pela Crossref para registros do Retraction Watch:
# o "update-to" fica no próprio registro da obra.
RW_OWN_RECORD = {"DOI": DOI, "update-to": [{
    "updated": {"date-parts": [[2023, 4, 22]], "date-time": "2023-04-22T00:00:00Z"},
    "DOI": DOI, "type": "retraction", "source": "retraction-watch",
    "label": "Retraction", "record-id": 44124}]}


def publisher_notice(kind, notice="10.9999/notice.1", target=DOI):
    return {"DOI": notice, "update-to": [{
        "updated": {"date-parts": [[2025, 2, 3]]}, "DOI": target,
        "type": kind, "source": "publisher", "label": kind.title()}]}


class EditorialStatusTest(unittest.TestCase):
    def test_retraction_watch_self_record(self):
        result = editorial_status(DOI, None, fake_request(), own_record=RW_OWN_RECORD)
        self.assertEqual(result["editorial_status"], "retracted")
        notice = result["notices"][0]
        self.assertEqual(notice["source"], "retraction-watch")
        self.assertIsNone(notice["notice_doi"])
        self.assertEqual(notice["date"], "2023-04-22")

    def test_publisher_notice_found_by_updates_filter(self):
        request = fake_request([publisher_notice("expression_of_concern")])
        result = editorial_status("https://doi.org/" + DOI.upper(), None, request)
        self.assertEqual(request.calls[0][1]["filter"], f"updates:{DOI}")
        self.assertEqual(result["editorial_status"], "expression_of_concern")
        self.assertEqual(result["notices"][0]["notice_doi"], "10.9999/notice.1")
        self.assertEqual(result["notices"][0]["date"], "2025-02-03")

    def test_types_are_distinguished_and_most_severe_wins(self):
        self.assertEqual(editorial_status(DOI, None, fake_request([publisher_notice("correction")]))["editorial_status"], "corrected")
        self.assertEqual(editorial_status(DOI, None, fake_request([publisher_notice("erratum")]))["editorial_status"], "corrected")
        self.assertEqual(editorial_status(DOI, None, fake_request([publisher_notice("withdrawal")]))["editorial_status"], "withdrawn")
        both = [publisher_notice("correction", "10.9/a"), publisher_notice("retraction", "10.9/b")]
        self.assertEqual(editorial_status(DOI, None, fake_request(both))["editorial_status"], "retracted")

    def test_notice_for_other_doi_is_ignored(self):
        other = publisher_notice("retraction", target="10.5555/outra")
        self.assertEqual(notices_for(DOI, [other]), [])

    def test_absence_is_not_proof_and_failure_is_inconclusive(self):
        ok = editorial_status(DOI, None, fake_request([]))
        self.assertEqual(ok["editorial_status"], "no_notice_found")
        self.assertNotIn("nunca", ok["label"].lower())
        failed = editorial_status(DOI, None, fake_request(status="unavailable"))
        self.assertEqual(failed["editorial_status"], "inconclusive")

    def test_without_doi_nothing_is_queried(self):
        request = fake_request()
        self.assertEqual(editorial_status("", None, request)["editorial_status"], "not_checked")
        self.assertEqual(request.calls, [])

    def test_summary_counts_alerts(self):
        items = [{"editorial": {"editorial_status": "retracted"}},
                 {"editorial": {"editorial_status": "corrected"}},
                 {"editorial": {"editorial_status": "no_notice_found"}}, {}]
        summary = summarize(items)
        self.assertEqual(summary["alerts"], 1)
        self.assertEqual(summary["counts"]["corrected"], 1)


if __name__ == "__main__":
    unittest.main()
