from __future__ import annotations

from datetime import datetime
import re
import textwrap

import fitz


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_X = 42
MARGIN_BOTTOM = 42
CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)

NAVY = (0.06, 0.13, 0.25)
BLUE = (0.12, 0.32, 0.72)
TEAL = (0.03, 0.48, 0.43)
GREEN = (0.08, 0.48, 0.24)
RED = (0.72, 0.11, 0.11)
AMBER = (0.78, 0.44, 0.04)
SLATE = (0.2, 0.25, 0.33)
MUTED = (0.42, 0.48, 0.56)
BORDER = (0.83, 0.88, 0.94)
SOFT_BG = (0.97, 0.98, 1.0)
SOFT_TEAL = (0.9, 0.98, 0.96)
WHITE = (1, 1, 1)


SCORE_FIELDS = [
    ("ATS Score", ("ats_score", "atsScore")),
    ("Semantic Score", ("semantic_score", "semanticScore")),
    ("Skill Score", ("skill_score", "skillScore")),
    ("Education Score", ("education_score", "educationScore")),
    ("Experience Score", ("experience_score", "experienceScore")),
    ("Project Score", ("project_score", "projectScore")),
    ("Interview Score", ("interview_score", "interviewScore")),
]


def is_report_ready(application: dict) -> bool:
    status = str(application.get("interview_status") or application.get("interviewStatus") or "").lower()
    return (
        application.get("interview_completed") is True
        or application.get("interviewCompleted") is True
        or status in {"complete", "completed", "partial", "quit", "interrupted"}
    )


def report_filename(application: dict) -> str:
    return f"candidate_report_{_slug(_candidate_name(application))}.pdf"


def group_report_filename() -> str:
    return "novac_group_candidate_report.pdf"


def generate_candidate_report_pdf(application: dict) -> bytes:
    document = fitz.open()
    writer = _ReportWriter(document)
    _add_candidate_report(writer, application, section_number=None, compact=False)
    return _close_document(document)


def generate_candidate_reports_pdf(applications: list[dict]) -> bytes:
    document = fitz.open()
    writer = _ReportWriter(document)
    candidates = [application for application in applications if isinstance(application, dict)]

    _add_group_summary(writer, candidates)
    _add_group_index(writer, candidates)

    for index, application in enumerate(candidates, start=1):
        writer.new_page()
        _add_candidate_report(writer, application, section_number=index, compact=True)

    return _close_document(document)


def _add_candidate_report(
    writer: "_ReportWriter",
    application: dict,
    *,
    section_number: int | None,
    compact: bool,
) -> None:
    name = _candidate_name(application)
    title = f"Section {section_number}: {name}" if section_number else name

    writer.document_header(
        "NOVAC AI Hiring Platform",
        "Candidate Interview Report",
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    writer.title(title, _safe_text(application.get("email") or "N/A"))

    writer.section("Candidate Summary")
    writer.info_cards(
        [
            ("Candidate", name),
            ("Email", application.get("email") or "N/A"),
            ("Application ID", application.get("application_id") or application.get("_id") or "N/A"),
            ("Job", _job_title(application)),
            ("ATS Status", _format_status(application.get("ats_status") or application.get("ats_decision") or "N/A")),
            ("Verification", _verification_label(application)),
            ("Interview Status", _interview_status_label(application)),
            ("Completed At", application.get("interview_completed_at") or application.get("completedAt") or "N/A"),
        ],
        columns=2 if compact else 2,
    )

    writer.section("Score Overview")
    writer.score_cards(_score_cards(application), columns=4 if compact else 3)

    matched_skills = (
        application.get("matched_skills")
        or application.get("matchedSkills")
        or _safe_get(application, ["ats_result", "matched_skills"])
        or []
    )
    missing_skills = (
        application.get("missing_skills")
        or application.get("missingSkills")
        or _safe_get(application, ["ats_result", "missing_skills"])
        or []
    )
    writer.section("Skill Snapshot")
    writer.text_card(
        "Matched Skills",
        _format_list(matched_skills),
        accent=GREEN,
    )
    writer.text_card(
        "Missing Skills",
        _format_list(missing_skills),
        accent=AMBER,
    )

    writer.section("Liveness / Identity Verification")
    liveness = _liveness_summary(application)
    writer.text_card(
        "Liveness Status",
        _format_liveness_status(liveness["status"]),
        accent=_liveness_color(liveness["status"]),
    )
    writer.score_cards(
        [
            ("Warnings", str(liveness["total_warnings"])),
            ("No Face", str(liveness["no_face_count"])),
            ("Multiple Faces", str(liveness["multiple_face_count"])),
            ("Identity Mismatch", str(liveness["identity_mismatch_count"])),
            ("Last Similarity", _format_similarity(liveness["last_similarity"])),
        ],
        columns=3,
    )

    if liveness["events"]:
        recent = [
            f"{event.get('timestamp', 'N/A')} - {event.get('type', 'N/A')} - {event.get('message', 'N/A')}"
            for event in liveness["events"][-5:]
            if isinstance(event, dict)
        ]
        writer.text_card("Recent Liveness Events", _format_list(recent), accent=_liveness_color(liveness["status"]))
    else:
        writer.text_card("Liveness Events", "No liveness warnings recorded.", accent=GREEN)

    writer.section("Interview Answers")
    answers = _answer_records(application)

    if not answers:
        writer.text_card("No Answers", "No graded interview answers are available.", accent=MUTED)
        return

    for index, answer in enumerate(answers, start=1):
        writer.question_card(index, answer)


def _add_group_summary(writer: "_ReportWriter", applications: list[dict]) -> None:
    writer.document_header(
        "NOVAC AI Hiring Platform",
        "Consolidated Candidate Report",
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    writer.title("Overall Summary", "Candidate report pack")

    completed = [application for application in applications if is_report_ready(application)]
    completed_only = [application for application in applications if _interview_status_label(application) == "Complete"]
    partial_or_quit = [
        application
        for application in applications
        if str(application.get("interview_status") or application.get("interviewStatus") or "").lower() in {"partial", "quit", "interrupted"}
    ]
    passed = [
        application
        for application in applications
        if str(application.get("ats_status") or application.get("ats_decision") or "").lower() in {"passed", "shortlisted"}
    ]
    ranking = sorted(
        applications,
        key=lambda application: _score_value(application, ("interview_score", "interviewScore")),
        reverse=True,
    )
    highest = ranking[0] if ranking else None
    lowest = ranking[-1] if ranking else None

    writer.info_cards(
        [
            ("Total Candidates", str(len(applications))),
            ("Completed", str(len(completed_only))),
            ("Partial", str(len(partial_or_quit))),
            ("Passed / Shortlisted", str(len(passed))),
            ("Liveness Passed", str(sum(1 for application in applications if _liveness_summary(application)["status"] == "passed"))),
            ("Liveness Warnings", str(sum(1 for application in applications if _liveness_summary(application)["status"] == "warning"))),
            ("Suspicious", str(sum(1 for application in applications if _liveness_summary(application)["status"] == "suspicious"))),
            ("Highest Scoring", _candidate_name(highest) if highest else "N/A"),
            ("Lowest Scoring", _candidate_name(lowest) if lowest else "N/A"),
            ("Report Type", "Candidate Group"),
        ],
        columns=3,
    )

    writer.section("Average Scores")
    writer.score_cards(
        [
            (label.replace(" Score", ""), _format_score(_average_score(applications, keys)))
            for label, keys in SCORE_FIELDS
        ],
        columns=4,
    )

    writer.section("Top Candidates")
    top_rows = [
        [
            str(index),
            _candidate_name(application),
            _safe_text(application.get("email") or "N/A"),
            _format_score(_score_value(application, ("interview_score", "interviewScore"))),
            _format_status(application.get("ats_status") or "N/A"),
        ]
        for index, application in enumerate(ranking[:5], start=1)
    ]
    writer.table(["#", "Candidate", "Email", "Interview", "ATS"], top_rows or [["-", "N/A", "N/A", "0.0/10", "N/A"]])


def _add_group_index(writer: "_ReportWriter", applications: list[dict]) -> None:
    writer.new_page()
    writer.document_header(
        "NOVAC AI Hiring Platform",
        "Report Index",
        "Candidate sections follow this index",
    )
    writer.title("Index / Table of Contents", "Each candidate section starts on a new page")

    rows = [
        [
            str(index),
            _candidate_name(application),
            _safe_text(application.get("email") or "N/A"),
            _interview_status_label(application),
            _format_score(_score_value(application, ("interview_score", "interviewScore"))),
            f"Section {index}",
        ]
        for index, application in enumerate(applications, start=1)
    ]
    writer.table(
        ["#", "Candidate", "Email", "Status", "Score", "Reference"],
        rows or [["-", "N/A", "N/A", "N/A", "0.0/10", "N/A"]],
        font_size=8.4,
    )


class _ReportWriter:
    def __init__(self, document: fitz.Document):
        self.document = document
        self.page = None
        self.y = 0
        self.page_number = 0
        self.new_page()

    def new_page(self) -> None:
        self.page = self.document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        self.page_number += 1
        self.y = 36
        self._footer()

    def document_header(self, product: str, report_title: str, generated: str) -> None:
        self._ensure_space(96)
        rect = fitz.Rect(MARGIN_X, self.y, PAGE_WIDTH - MARGIN_X, self.y + 76)
        self.page.draw_rect(rect, color=NAVY, fill=NAVY)
        self.page.draw_rect(fitz.Rect(rect.x0, rect.y1 - 8, rect.x1, rect.y1), color=TEAL, fill=TEAL)
        self.page.insert_text(fitz.Point(rect.x0 + 18, rect.y0 + 25), product, fontsize=16, fontname="helv", color=WHITE)
        self.page.insert_text(fitz.Point(rect.x0 + 18.4, rect.y0 + 25), product, fontsize=16, fontname="helv", color=WHITE)
        self.page.insert_text(fitz.Point(rect.x0 + 18, rect.y0 + 49), report_title, fontsize=11.5, fontname="helv", color=(0.86, 0.92, 1.0))
        self.page.insert_text(fitz.Point(rect.x1 - 158, rect.y0 + 49), generated, fontsize=8.5, fontname="helv", color=(0.86, 0.92, 1.0))
        self.y = rect.y1 + 18

    def title(self, title: str, subtitle: str = "") -> None:
        self._ensure_space(42)
        self.page.insert_text(fitz.Point(MARGIN_X, self.y), _safe_text(title), fontsize=17, fontname="helv", color=NAVY)
        self.page.insert_text(fitz.Point(MARGIN_X + 0.35, self.y), _safe_text(title), fontsize=17, fontname="helv", color=NAVY)
        self.y += 18
        if subtitle:
            self._wrapped_text(_safe_text(subtitle), MARGIN_X, self.y, CONTENT_WIDTH, fontsize=9.3, color=MUTED)
            self.y += 17

    def section(self, title: str) -> None:
        self._ensure_space(30)
        self.y += 8
        self.page.insert_text(fitz.Point(MARGIN_X, self.y), _safe_text(title), fontsize=12.4, fontname="helv", color=TEAL)
        self.page.insert_text(fitz.Point(MARGIN_X + 0.3, self.y), _safe_text(title), fontsize=12.4, fontname="helv", color=TEAL)
        self.y += 8
        self.page.draw_line(
            fitz.Point(MARGIN_X, self.y),
            fitz.Point(PAGE_WIDTH - MARGIN_X, self.y),
            color=BORDER,
            width=0.8,
        )
        self.y += 12

    def info_cards(self, items: list[tuple[str, object]], *, columns: int) -> None:
        gap = 10
        width = (CONTENT_WIDTH - (gap * (columns - 1))) / columns
        height = 54

        for index, (label, value) in enumerate(items):
            if index % columns == 0:
                self._ensure_space(height + 10)
                row_y = self.y

            col = index % columns
            x = MARGIN_X + col * (width + gap)
            rect = fitz.Rect(x, row_y, x + width, row_y + height)
            self.page.draw_rect(rect, color=BORDER, fill=SOFT_BG)
            self.page.insert_text(fitz.Point(x + 10, row_y + 17), _safe_text(label).upper(), fontsize=7.5, fontname="helv", color=MUTED)
            self._wrapped_text(_safe_text(value), x + 10, row_y + 35, width - 20, fontsize=9.2, color=NAVY, max_lines=2)

            if col == columns - 1 or index == len(items) - 1:
                self.y = row_y + height + 10

    def score_cards(self, items: list[tuple[str, str]], *, columns: int) -> None:
        gap = 10
        width = (CONTENT_WIDTH - (gap * (columns - 1))) / columns
        height = 58

        for index, (label, score) in enumerate(items):
            if index % columns == 0:
                self._ensure_space(height + 10)
                row_y = self.y

            col = index % columns
            x = MARGIN_X + col * (width + gap)
            score_number = _number(score)
            accent = _score_color(score_number)
            rect = fitz.Rect(x, row_y, x + width, row_y + height)
            self.page.draw_rect(rect, color=BORDER, fill=WHITE)
            self.page.draw_rect(fitz.Rect(x, row_y, x + 5, row_y + height), color=accent, fill=accent)
            self.page.insert_text(fitz.Point(x + 12, row_y + 18), _safe_text(label).upper(), fontsize=7.2, fontname="helv", color=MUTED)
            self.page.insert_text(fitz.Point(x + 12, row_y + 43), _safe_text(score or "0.0/10"), fontsize=15, fontname="helv", color=accent)
            self.page.insert_text(fitz.Point(x + 12.3, row_y + 43), _safe_text(score or "0.0/10"), fontsize=15, fontname="helv", color=accent)

            if col == columns - 1 or index == len(items) - 1:
                self.y = row_y + height + 10

    def text_card(self, label: str, value: object, *, accent: tuple[float, float, float] = TEAL) -> None:
        lines = self._wrap(_safe_text(value), chars=98)
        height = max(46, 28 + len(lines) * 11)
        self._ensure_space(height + 8)
        rect = fitz.Rect(MARGIN_X, self.y, PAGE_WIDTH - MARGIN_X, self.y + height)
        self.page.draw_rect(rect, color=BORDER, fill=SOFT_BG)
        self.page.draw_rect(fitz.Rect(rect.x0, rect.y0, rect.x0 + 4, rect.y1), color=accent, fill=accent)
        self.page.insert_text(fitz.Point(rect.x0 + 12, rect.y0 + 18), _safe_text(label).upper(), fontsize=7.5, fontname="helv", color=MUTED)
        self._draw_lines(lines, rect.x0 + 12, rect.y0 + 34, fontsize=9.2, color=SLATE, line_height=11)
        self.y = rect.y1 + 8

    def question_card(self, index: int, answer: dict) -> None:
        score = _format_score(_answer_score(answer))
        self._ensure_space(70)
        rect = fitz.Rect(MARGIN_X, self.y, PAGE_WIDTH - MARGIN_X, self.y + 46)
        self.page.draw_rect(rect, color=BORDER, fill=SOFT_TEAL)
        self.page.insert_text(fitz.Point(rect.x0 + 12, rect.y0 + 19), f"Question {index}", fontsize=11.3, fontname="helv", color=NAVY)
        self.page.insert_text(fitz.Point(rect.x0 + 12.3, rect.y0 + 19), f"Question {index}", fontsize=11.3, fontname="helv", color=NAVY)
        self._badge(rect.x1 - 82, rect.y0 + 10, score, _score_color(_number(score)))
        self.y = rect.y1 + 8
        self.field("Question Text", answer.get("question") or "N/A")
        self.field("Difficulty", _format_status(answer.get("difficulty") or "N/A"))
        self.field("Area of Interest", answer.get("area_of_interest") or answer.get("areaOfInterest") or answer.get("category") or "N/A")
        self.field("Expected Answer", answer.get("expectedAnswer") or answer.get("expected_answer") or "N/A")
        self.field(
            "Candidate Transcript / Answer",
            answer.get("transcript") or answer.get("answerText") or answer.get("answer_text") or "Not answered",
        )
        self.field("Answer Status", _format_status(answer.get("status") or answer.get("answer_status") or answer.get("gradingStatus") or "Submitted"))
        self.field(
            "Feedback / Evaluation",
            answer.get("feedback")
            or _safe_get(answer, ["grading", "feedback"])
            or _safe_get(answer, ["evaluation", "feedback"])
            or "N/A",
        )
        metrics = [
            ("Relevance", _format_score(_answer_metric(answer, "relevance"))),
            ("Technical", _format_score(_answer_metric(answer, "technical"))),
            ("Depth", _format_score(_answer_metric(answer, "depth"))),
            ("Clarity", _format_score(_answer_metric(answer, "clarity"))),
        ]
        self.inline_metrics(metrics)
        self.field(
            "Missing Points",
            _format_list(
                answer.get("missingPoints")
                or answer.get("missing_points")
                or _safe_get(answer, ["grading", "missingPoints"])
                or _safe_get(answer, ["evaluation", "missingPoints"])
                or []
            ),
        )

    def field(self, label: str, value: object) -> None:
        self._ensure_space(28)
        self.page.insert_text(fitz.Point(MARGIN_X, self.y), _safe_text(label).upper(), fontsize=7.4, fontname="helv", color=MUTED)
        self.y += 12
        lines = self._wrap(_safe_text(value), chars=102)
        for line in lines:
            self._ensure_space(12)
            self.page.insert_text(fitz.Point(MARGIN_X, self.y), line, fontsize=9, fontname="helv", color=SLATE)
            self.y += 11.5
        self.y += 5

    def inline_metrics(self, metrics: list[tuple[str, str]]) -> None:
        self._ensure_space(34)
        gap = 8
        width = (CONTENT_WIDTH - gap * (len(metrics) - 1)) / len(metrics)
        row_y = self.y
        for index, (label, value) in enumerate(metrics):
            x = MARGIN_X + index * (width + gap)
            rect = fitz.Rect(x, row_y, x + width, row_y + 30)
            self.page.draw_rect(rect, color=BORDER, fill=WHITE)
            self.page.insert_text(fitz.Point(x + 7, row_y + 12), _safe_text(label).upper(), fontsize=6.6, fontname="helv", color=MUTED)
            self.page.insert_text(fitz.Point(x + 7, row_y + 24), _safe_text(value), fontsize=8.6, fontname="helv", color=SLATE)
        self.y = row_y + 38

    def table(self, headers: list[str], rows: list[list[str]], *, font_size: float = 8.0) -> None:
        col_count = len(headers)
        widths = _table_widths(headers)
        row_height = 28
        self._ensure_space(row_height * 2)
        self._draw_table_row(headers, widths, row_height, fill=NAVY, color=WHITE, font_size=font_size, bold=True)

        for row in rows:
            self._ensure_space(row_height + 4)
            self._draw_table_row(row[:col_count], widths, row_height, fill=WHITE, color=SLATE, font_size=font_size)

        self.y += 6

    def _draw_table_row(
        self,
        values: list[str],
        widths: list[float],
        height: int,
        *,
        fill: tuple[float, float, float],
        color: tuple[float, float, float],
        font_size: float,
        bold: bool = False,
    ) -> None:
        x = MARGIN_X
        for value, width in zip(values, widths):
            rect = fitz.Rect(x, self.y, x + width, self.y + height)
            self.page.draw_rect(rect, color=BORDER, fill=fill)
            lines = self._wrap(_safe_text(value), chars=max(8, int(width / 5.2)))[:2]
            self._draw_lines(lines, x + 5, self.y + 11, fontsize=font_size, color=color, line_height=9.5, bold=bold)
            x += width
        self.y += height

    def _badge(self, x: float, y: float, text: str, color: tuple[float, float, float]) -> None:
        rect = fitz.Rect(x, y, x + 68, y + 22)
        self.page.draw_rect(rect, color=color, fill=color)
        self.page.insert_text(fitz.Point(x + 9, y + 15), _safe_text(text), fontsize=8.5, fontname="helv", color=WHITE)

    def _footer(self) -> None:
        self.page.insert_text(
            fitz.Point(MARGIN_X, PAGE_HEIGHT - 22),
            f"NOVAC AI Hiring Platform | Page {self.page_number}",
            fontsize=7.5,
            fontname="helv",
            color=MUTED,
        )

    def _ensure_space(self, height: float) -> None:
        if self.y + height > PAGE_HEIGHT - MARGIN_BOTTOM:
            self.new_page()

    def _wrap(self, text: str, *, chars: int) -> list[str]:
        return textwrap.wrap(_safe_text(text), width=chars) or ["N/A"]

    def _wrapped_text(
        self,
        text: str,
        x: float,
        y: float,
        width: float,
        *,
        fontsize: float,
        color: tuple[float, float, float],
        max_lines: int | None = None,
    ) -> None:
        chars = max(12, int(width / (fontsize * 0.55)))
        lines = self._wrap(text, chars=chars)
        if max_lines:
            lines = lines[:max_lines]
        self._draw_lines(lines, x, y, fontsize=fontsize, color=color, line_height=fontsize + 2)

    def _draw_lines(
        self,
        lines: list[str],
        x: float,
        y: float,
        *,
        fontsize: float,
        color: tuple[float, float, float],
        line_height: float,
        bold: bool = False,
    ) -> None:
        for line in lines:
            self.page.insert_text(fitz.Point(x, y), line, fontsize=fontsize, fontname="helv", color=color)
            if bold:
                self.page.insert_text(fitz.Point(x + 0.25, y), line, fontsize=fontsize, fontname="helv", color=color)
            y += line_height


def _close_document(document: fitz.Document) -> bytes:
    pdf_bytes = document.write()
    document.close()
    return pdf_bytes


def _score_cards(application: dict) -> list[tuple[str, str]]:
    return [
        (label.replace(" Score", ""), _format_score(_score_value(application, keys)))
        for label, keys in SCORE_FIELDS
    ]


def _average_score(applications: list[dict], keys: tuple[str, ...]) -> float:
    values = [
        _score_value(application, keys) if _score_value(application, keys) is not None else 0.0
        for application in applications
    ]
    return round(sum(values) / len(values), 1) if values else 0.0


def _score_value(application: dict, keys: tuple[str, ...]):
    for key in keys:
        score = _number(application.get(key))
        if score is not None:
            return score
    return None


def _score_color(score) -> tuple[float, float, float]:
    number = _number(score)
    if number is None:
        return MUTED
    if number >= 8:
        return GREEN
    if number >= 6:
        return TEAL
    if number >= 4:
        return AMBER
    return RED


def _liveness_summary(application: dict) -> dict:
    liveness = application.get("liveness") if isinstance(application, dict) else {}

    if not isinstance(liveness, dict):
        liveness = {}

    events = liveness.get("events") if isinstance(liveness.get("events"), list) else []
    total_warnings = int(liveness.get("total_warnings") or len(events) or 0)
    status = str(liveness.get("status") or "").lower()

    if status not in {"passed", "warning", "suspicious"}:
        if total_warnings >= 3:
            status = "suspicious"
        elif total_warnings >= 1:
            status = "warning"
        else:
            status = "passed"

    return {
        "status": status,
        "total_warnings": total_warnings,
        "no_face_count": int(liveness.get("no_face_count") or 0),
        "multiple_face_count": int(liveness.get("multiple_face_count") or 0),
        "identity_mismatch_count": int(liveness.get("identity_mismatch_count") or 0),
        "last_similarity": liveness.get("last_similarity"),
        "events": events,
    }


def _format_liveness_status(status: str) -> str:
    normalized = str(status or "passed").lower()

    if normalized == "suspicious":
        return "Suspicious"

    if normalized == "warning":
        return "Warning"

    return "Passed"


def _liveness_color(status: str) -> tuple[float, float, float]:
    normalized = str(status or "passed").lower()

    if normalized == "suspicious":
        return RED

    if normalized == "warning":
        return AMBER

    return GREEN


def _table_widths(headers: list[str]) -> list[float]:
    if len(headers) == 6:
        return [28, 118, 142, 78, 58, 76]
    if len(headers) == 5:
        return [28, 130, 165, 82, 94]
    return [CONTENT_WIDTH / len(headers)] * len(headers)


def _answer_records(application: dict) -> list[dict]:
    answers = application.get("interview_answers") or application.get("interviewAnswers") or {}

    if isinstance(answers, dict):
        records_by_id = {
            str(key): answer
            for key, answer in answers.items()
            if isinstance(answer, dict)
        }
        records = list(records_by_id.values())
    elif isinstance(answers, list):
        records_by_id = {
            str(answer.get("questionId") or answer.get("question_id") or f"q{index + 1}"): answer
            for index, answer in enumerate(answers)
            if isinstance(answer, dict)
        }
        records = [answer for answer in answers if isinstance(answer, dict)]
    else:
        records_by_id = {}
        records = []

    question_payload = application.get("interview_questions") if isinstance(application, dict) else {}
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    if not isinstance(questions, list) or not questions:
        return sorted(records, key=_answer_sort_key)

    normalized = []

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue

        question_id = str(question.get("id") or question.get("question_id") or f"q{index}")
        existing = records_by_id.get(question_id)

        if existing:
            normalized.append(
                {
                    **existing,
                    "question": question.get("question") or existing.get("question") or "",
                    "expectedAnswer": question.get("expectedAnswer") or question.get("expected_answer") or existing.get("expectedAnswer") or existing.get("expected_answer") or "",
                    "expected_answer": question.get("expected_answer") or question.get("expectedAnswer") or existing.get("expected_answer") or existing.get("expectedAnswer") or "",
                    "difficulty": question.get("difficulty") or existing.get("difficulty") or "N/A",
                    "area_of_interest": question.get("area_of_interest") or question.get("areaOfInterest") or existing.get("area_of_interest") or existing.get("areaOfInterest") or "N/A",
                    "areaOfInterest": question.get("area_of_interest") or question.get("areaOfInterest") or existing.get("areaOfInterest") or existing.get("area_of_interest") or "N/A",
                    "question_index": existing.get("question_index") or index,
                }
            )
            continue

        normalized.append(
            {
                "questionId": question_id,
                "question_id": question_id,
                "question_index": index,
                "question": question.get("question") or "",
                "expectedAnswer": question.get("expectedAnswer") or question.get("expected_answer") or "",
                "expected_answer": question.get("expected_answer") or question.get("expectedAnswer") or "",
                "difficulty": question.get("difficulty") or "N/A",
                "area_of_interest": question.get("area_of_interest") or question.get("areaOfInterest") or "N/A",
                "areaOfInterest": question.get("area_of_interest") or question.get("areaOfInterest") or "N/A",
                "transcript": "Not answered",
                "answerText": "Not answered",
                "answer_text": "Not answered",
                "score": 0,
                "finalScore": 0,
                "final_score": 0,
                "status": "unanswered",
                "answer_status": "unanswered",
                "feedback": "Candidate did not answer this question.",
            }
        )

    return normalized


def _answer_sort_key(answer: dict):
    index = _number(answer.get("question_index"))

    if index is not None:
        return (0, index)

    return (1, str(answer.get("questionId") or answer.get("question_id") or ""))


def _answer_metric(answer: dict, metric: str):
    aliases = {
        "relevance": ("relevance", "relevanceScore", "relevance_score"),
        "technical": ("technical", "technicalScore", "technical_score", "technicalAccuracy", "technical_accuracy"),
        "depth": ("depth", "depthScore", "depth_score"),
        "clarity": ("clarity", "clarityScore", "clarity_score"),
    }
    return _first_number(answer, aliases.get(metric, (metric,)))


def _answer_score(answer: dict):
    return _first_number(answer, ("finalScore", "final_score", "score", "overallScore", "overall_score"))


def _first_number(answer: dict, keys: tuple[str, ...]):
    sources = [answer, answer.get("grading"), answer.get("evaluation")]

    for source in sources:
        if not isinstance(source, dict):
            continue

        for key in keys:
            value = _number(source.get(key))
            if value is not None:
                return value

    return None


def _number(value):
    if value is None or value == "" or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return max(0, min(10, float(value)))

    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return None

    return max(0, min(10, float(match.group(0))))


def _format_score(value) -> str:
    number = _number(value)
    return "0.0/10" if number is None else f"{number:.1f}/10"


def _format_similarity(value) -> str:
    if value is None or value == "":
        return "N/A"

    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return _safe_text(value)


def _format_status(value) -> str:
    text = _safe_text(value or "N/A").replace("_", " ")
    return text.title() if text != "N/A" else text


def _interview_status_label(application: dict) -> str:
    status = str(application.get("interview_status") or application.get("interviewStatus") or "").strip()

    if (
        application.get("interview_completed") is True
        or application.get("interviewCompleted") is True
        or status.lower() in {"complete", "completed"}
    ):
        return "Complete"

    return _format_status(status or "Incomplete")


def _verification_label(application: dict) -> str:
    if (
        application.get("verification_completed") is True
        or application.get("faceVerified") is True
        or application.get("face_verified") is True
        or str(application.get("verification_status") or "").lower() == "verified"
        or str(application.get("verificationStatus") or "").lower() == "verified"
    ):
        return "Verified"

    return "Not Verified"


def _candidate_name(application: dict | None) -> str:
    if not isinstance(application, dict):
        return "N/A"
    return _safe_text(
        application.get("candidate_name")
        or _safe_get(application, ["resume", "candidate_name"])
        or application.get("resume_name")
        or application.get("file_name")
        or "Candidate"
    )


def _job_title(application: dict) -> str:
    return _safe_text(
        application.get("job_title")
        or application.get("job_role")
        or application.get("title")
        or "N/A"
    )


def _format_list(value) -> str:
    if isinstance(value, list):
        cleaned = [_safe_text(item) for item in value if _safe_text(item) != "N/A"]
        return ", ".join(cleaned) if cleaned else "None"

    if isinstance(value, tuple):
        return _format_list(list(value))

    return _safe_text(value or "None")


def _safe_get(mapping: dict, keys: list[str]):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def _safe_text(value) -> str:
    if value is None:
        return "N/A"

    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text or "N/A"


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", _safe_text(value)).strip("_").lower() or "candidate"
