"""
Sales Profile — Behavioral metrics for sales domain brains.
============================================================
Layer 1 Enhancement: pure logic, stdlib only.

Tracks what top-performing AEs do differently (Gong Labs, RAIN Group research):
- Outreach timing patterns (when do successful emails get sent?)
- Follow-up cadence compliance (3-7-7 vs actual)
- Multi-threading depth (contacts per deal)
- Question density per call stage
- Deal velocity by segment

These metrics complement the core correction pipeline. Corrections tell
you what the AI gets wrong. Sales metrics tell you what patterns predict
deal closure.

Usage:
    profile = SalesProfile()
    profile.log_outreach("email", "2026-03-25T10:30:00", prospect="Hassan")
    profile.log_followup("Hassan", touch_number=3, days_since_last=7)
    profile.log_deal_contact("Acme Corp", "CFO")
    profile.log_deal_contact("Acme Corp", "VP Sales")
    report = profile.compute()
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OutreachEvent:
    """A single outreach attempt."""

    channel: str  # email, call, linkedin, etc.
    timestamp: str  # ISO 8601
    prospect: str = ""
    replied: bool = False
    reply_sentiment: str = ""  # positive, neutral, negative


@dataclass
class FollowupEvent:
    """A follow-up in a sequence."""

    prospect: str
    touch_number: int
    days_since_last: int
    channel: str = "email"
    replied: bool = False


@dataclass
class SalesProfileReport:
    """Aggregated sales behavioral metrics."""

    # Timing
    best_send_hours: list[int]  # Hours (0-23) with highest reply rates
    best_send_days: list[str]  # Days of week with highest reply rates
    avg_response_time_hours: float  # Average time to reply after outreach

    # Cadence
    avg_days_between_touches: float
    cadence_compliance: float  # 0-1, how close to optimal cadence
    touches_before_reply: float  # Average touches before first reply
    drop_off_touch: int  # Touch number where most sequences die

    # Multi-threading
    avg_contacts_per_deal: float  # Gong: 2x contacts = higher win rate
    deals_with_single_contact: int  # Risk indicator
    deals_with_multithread: int

    # Volume
    total_outreach: int
    reply_rate: float
    positive_reply_rate: float


class SalesProfile:
    """Tracks sales behavioral patterns for domain-specific learning."""

    def __init__(self) -> None:
        self._outreach: list[OutreachEvent] = []
        self._followups: list[FollowupEvent] = []
        self._deal_contacts: dict[str, set[str]] = defaultdict(set)

    def log_outreach(
        self,
        channel: str,
        timestamp: str,
        prospect: str = "",
        replied: bool = False,
        reply_sentiment: str = "",
    ) -> None:
        """Log an outreach attempt."""
        self._outreach.append(
            OutreachEvent(
                channel=channel,
                timestamp=timestamp,
                prospect=prospect,
                replied=replied,
                reply_sentiment=reply_sentiment,
            )
        )

    def log_followup(
        self,
        prospect: str,
        touch_number: int,
        days_since_last: int,
        channel: str = "email",
        replied: bool = False,
    ) -> None:
        """Log a follow-up touch in a sequence."""
        self._followups.append(
            FollowupEvent(
                prospect=prospect,
                touch_number=touch_number,
                days_since_last=days_since_last,
                channel=channel,
                replied=replied,
            )
        )

    def log_deal_contact(self, deal: str, contact_role: str) -> None:
        """Log a contact associated with a deal (multi-threading tracking)."""
        self._deal_contacts[deal].add(contact_role)

    def compute(self) -> SalesProfileReport:
        """Compute aggregated sales metrics."""
        # Timing analysis
        reply_hours: dict[int, list[bool]] = defaultdict(list)
        reply_days: dict[str, list[bool]] = defaultdict(list)

        for o in self._outreach:
            try:
                dt = datetime.fromisoformat(o.timestamp.replace("Z", "+00:00"))
                hour = dt.hour
                day = dt.strftime("%A")
                reply_hours[hour].append(o.replied)
                reply_days[day].append(o.replied)
            except (ValueError, AttributeError):
                continue

        # Best hours by reply rate
        hour_rates = {
            h: sum(replies) / len(replies)
            for h, replies in reply_hours.items()
            if len(replies) >= 3  # minimum sample
        }
        best_hours = sorted(hour_rates, key=hour_rates.get, reverse=True)[:3]

        # Best days by reply rate
        day_rates = {
            d: sum(replies) / len(replies) for d, replies in reply_days.items() if len(replies) >= 3
        }
        best_days = sorted(day_rates, key=day_rates.get, reverse=True)[:3]

        # Cadence analysis (grouped by prospect to avoid cross-contamination)
        if self._followups:
            avg_gap = sum(f.days_since_last for f in self._followups) / len(self._followups)
            replied_followups = [f for f in self._followups if f.replied]
            touches_before = (
                sum(f.touch_number for f in replied_followups) / len(replied_followups)
                if replied_followups
                else 0.0
            )
            # Find drop-off: touch number with most non-replied sequences
            touch_counts: dict[int, int] = defaultdict(int)
            for f in self._followups:
                if not f.replied:
                    touch_counts[f.touch_number] += 1
            drop_off = max(touch_counts, key=lambda k: touch_counts[k]) if touch_counts else 0

            # Cadence compliance: compare per-prospect to 3-7-7 optimal (Belkins)
            optimal_gaps = [3, 7, 7, 14, 14]
            by_prospect: dict[str, list[int]] = defaultdict(list)
            for f in self._followups:
                by_prospect[f.prospect].append(f.days_since_last)
            compliances: list[float] = []
            for _prospect, gaps in by_prospect.items():
                if gaps:
                    deviations = [
                        abs(a - o) / max(o, 1)
                        for a, o in zip(gaps[:5], optimal_gaps[: len(gaps)], strict=False)
                    ]
                    compliances.append(max(0.0, 1.0 - sum(deviations) / len(deviations)))
            compliance = sum(compliances) / len(compliances) if compliances else 0.0
        else:
            avg_gap = 0.0
            touches_before = 0.0
            drop_off = 0
            compliance = 0.0

        # Multi-threading
        deal_count = len(self._deal_contacts)
        single = sum(1 for contacts in self._deal_contacts.values() if len(contacts) <= 1)
        multi = sum(1 for contacts in self._deal_contacts.values() if len(contacts) > 1)
        avg_contacts = (
            sum(len(c) for c in self._deal_contacts.values()) / deal_count
            if deal_count > 0
            else 0.0
        )

        # Reply rates
        total = len(self._outreach)
        replies = sum(1 for o in self._outreach if o.replied)
        positive = sum(1 for o in self._outreach if o.replied and o.reply_sentiment == "positive")

        return SalesProfileReport(
            best_send_hours=best_hours,
            best_send_days=best_days,
            avg_response_time_hours=0.0,  # Needs response timestamps to compute
            avg_days_between_touches=round(avg_gap, 1),
            cadence_compliance=round(compliance, 2),
            touches_before_reply=round(touches_before, 1),
            drop_off_touch=drop_off,
            avg_contacts_per_deal=round(avg_contacts, 1),
            deals_with_single_contact=single,
            deals_with_multithread=multi,
            total_outreach=total,
            reply_rate=round(replies / total, 3) if total > 0 else 0.0,
            positive_reply_rate=round(positive / replies, 3) if replies > 0 else 0.0,
        )
