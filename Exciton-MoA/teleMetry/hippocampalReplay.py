# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np


class HippocampalReplay:
    def __init__(self, working_dir: Path | None = None):
        self.working_dir = (
            Path(working_dir)
            if working_dir is not None
            else Path(__file__).resolve().parents[1] / "working_data"
        )

    def list_burst_files(self) -> list[Path]:
        return sorted(self.working_dir.glob("**/hippocampal_burst_*.json"))

    def list_long_term_archives(self) -> list[Path]:
        return sorted(self.working_dir.glob("**/hippocampal_long_term.jsonl"))

    def load_burst(self, path: Path | None = None) -> list[dict[str, object]]:
        burst_path = Path(path) if path is not None else self._latest_burst_path()
        return json.loads(burst_path.read_text(encoding="utf-8"))

    def load_long_term_records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for archive_path in self.list_long_term_archives():
            for line in archive_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                records.append(json.loads(line))
        return records

    def load_pair_telemetry_records(self, pair_id: str | None = None) -> list[dict[str, object]]:
        history_path = self.working_dir / "adaptive_tau_history.jsonl"
        if not history_path.exists():
            return []

        records: list[dict[str, object]] = []
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("record_type") != "pair" and "pair_id" not in entry:
                continue
            if pair_id is not None and str(entry.get("pair_id", "")) != str(pair_id):
                continue
            records.append(entry)

        records.sort(key=lambda item: (str(item.get("timestamp", "")), int(item.get("shared_pair_clock", 0))))
        return records

    def filter_pair_bursts(self, records: list[dict[str, object]], pair_id: str) -> list[dict[str, object]]:
        return [record for record in records if str(record.get("pair_id", "")) == pair_id]

    def summarize(self, records: list[dict[str, object]]) -> dict[str, object]:
        if not records:
            return {
                "total_bursts": 0,
                "max_h": 0.0,
                "avg_h": 0.0,
                "avg_tau": 0.0,
                "dominant_giants": {},
                "pair_bursts": 0,
                "bilateral_bursts": 0,
            }

        h_values = [float(record.get("h_total", 0.0)) for record in records]
        tau_values = [float(record.get("tau_threshold", 0.0)) for record in records]
        giant_counts = Counter(
            self._normalize_giant_label(record.get("dominant_giant")) for record in records
        )
        return {
            "total_bursts": len(records),
            "max_h": max(h_values),
            "avg_h": sum(h_values) / len(h_values),
            "avg_tau": sum(tau_values) / len(tau_values) if tau_values else 0.0,
            "dominant_giants": dict(giant_counts.most_common()),
            "pair_bursts": sum(1 for record in records if record.get("pair_id")),
            "bilateral_bursts": sum(1 for record in records if record.get("bilateral_burst")),
        }

    def summarize_pair(self, records: list[dict[str, object]], pair_id: str) -> dict[str, object]:
        pair_records = self.filter_pair_bursts(records, pair_id)
        if not pair_records:
            return {
                "pair_id": pair_id,
                "total_bursts": 0,
                "max_h": 0.0,
                "avg_h": 0.0,
                "avg_tau": 0.0,
                "bilateral_bursts": 0,
                "bilateral_ratio": 0.0,
                "source_manifolds": {},
                "cross_domain_giants": {},
            }

        base = self.summarize(pair_records)
        source_counts = Counter(str(record.get("source_manifold_id", "unknown")) for record in pair_records)
        cross_domain_giants = Counter(
            str(record.get("cross_domain_giant", "Entanglement Locus")) for record in pair_records
        )
        bilateral_bursts = int(base["bilateral_bursts"])
        return {
            "pair_id": pair_id,
            "total_bursts": int(base["total_bursts"]),
            "max_h": float(base["max_h"]),
            "avg_h": float(base["avg_h"]),
            "avg_tau": float(base["avg_tau"]),
            "bilateral_bursts": bilateral_bursts,
            "bilateral_ratio": float(bilateral_bursts / len(pair_records)) if pair_records else 0.0,
            "source_manifolds": dict(source_counts.most_common()),
            "cross_domain_giants": dict(cross_domain_giants.most_common()),
        }

    def summarize_weight_drift(self, telemetry_records: list[dict[str, object]]) -> dict[str, object]:
        weighted_records = [
            record
            for record in telemetry_records
            if "entangler_weight_min" in record
            or "entangler_weight_max" in record
            or record.get("entangler_top_wormholes")
        ]
        if not weighted_records:
            return {
                "tick_count": 0,
                "weight_min_mean": 0.0,
                "weight_min_std": 0.0,
                "weight_min_range": (0.0, 0.0),
                "weight_max_mean": 0.0,
                "weight_max_std": 0.0,
                "weight_max_range": (0.0, 0.0),
            }

        min_values = [float(record.get("entangler_weight_min", 1.0)) for record in weighted_records]
        max_values = [float(record.get("entangler_weight_max", 1.0)) for record in weighted_records]
        return {
            "tick_count": len(weighted_records),
            "weight_min_mean": float(np.mean(min_values)),
            "weight_min_std": float(np.std(min_values)),
            "weight_min_range": (float(min(min_values)), float(max(min_values))),
            "weight_max_mean": float(np.mean(max_values)),
            "weight_max_std": float(np.std(max_values)),
            "weight_max_range": (float(min(max_values)), float(max(max_values))),
        }

    def summarize_coherence_trend(self, telemetry_records: list[dict[str, object]]) -> dict[str, object]:
        coherence_records = [record for record in telemetry_records if "phase_coherence" in record]
        if not coherence_records:
            return {
                "tick_count": 0,
                "coherence_mean": 0.0,
                "coherence_std": 0.0,
                "coherence_range": (0.0, 0.0),
                "coherence_delta": 0.0,
                "target": 0.0,
                "latest_status": "unknown",
                "mode_counts": {},
            }

        coherence_values = [float(record.get("phase_coherence", 0.0)) for record in coherence_records]
        statuses = Counter(
            str(record.get("entangler_coherence_status", "stable")) for record in coherence_records
        )
        modes = Counter(str(record.get("entangler_mode", "active")) for record in coherence_records)
        return {
            "tick_count": len(coherence_records),
            "coherence_mean": float(np.mean(coherence_values)),
            "coherence_std": float(np.std(coherence_values)),
            "coherence_range": (float(min(coherence_values)), float(max(coherence_values))),
            "coherence_delta": float(coherence_values[-1] - coherence_values[0]),
            "target": float(coherence_records[-1].get("entangler_coherence_target", coherence_values[-1])),
            "latest_status": str(coherence_records[-1].get("entangler_coherence_status", "stable")),
            "mode_counts": dict(modes.most_common()),
            "status_counts": dict(statuses.most_common()),
        }

    def summarize_mode_switching(self, telemetry_records: list[dict[str, object]]) -> dict[str, object]:
        mode_records = [
            record
            for record in telemetry_records
            if "entangler_mode" in record
            or "entangler_next_mode" in record
            or "entangler_mode_changed" in record
        ]
        if not mode_records:
            return {
                "tick_count": 0,
                "occupancy_counts": {},
                "transition_counts": {},
                "reason_counts": {},
                "transition_total": 0,
                "explicit_transition_count": 0,
                "inferred_transition_count": 0,
                "stabilizer_run_count": 0,
                "stabilizer_dwell_mean": 0.0,
                "stabilizer_dwell_max": 0,
            }

        occupancy_counts: Counter[str] = Counter()
        transition_counts: Counter[str] = Counter()
        reason_counts: Counter[str] = Counter()
        explicit_transition_count = 0
        inferred_transition_count = 0
        stabilizer_runs: list[int] = []
        current_run_mode: str | None = None
        current_run_length = 0
        previous_mode: str | None = None
        previous_record: dict[str, object] | None = None

        for record in mode_records:
            mode_name = str(record.get("entangler_mode", "active"))
            occupancy_counts[mode_name] += 1

            if current_run_mode != mode_name:
                if current_run_mode == "Stabilizer" and current_run_length > 0:
                    stabilizer_runs.append(current_run_length)
                current_run_mode = mode_name
                current_run_length = 1
            else:
                current_run_length += 1

            if bool(record.get("entangler_mode_changed", False)):
                previous = str(record.get("entangler_previous_mode", mode_name))
                upcoming = str(record.get("entangler_next_mode", mode_name))
                if previous != upcoming:
                    transition_counts[f"{previous}->{upcoming}"] += 1
                    explicit_transition_count += 1
                    reason = str(record.get("entangler_transition_reason", "none"))
                    if reason and reason != "none":
                        reason_counts[reason] += 1
            elif previous_mode is not None and mode_name != previous_mode:
                prior_explicit = bool(
                    previous_record and previous_record.get("entangler_mode_changed", False)
                )
                prior_next_mode = (
                    str(previous_record.get("entangler_next_mode", previous_mode))
                    if previous_record
                    else previous_mode
                )
                if not prior_explicit or mode_name != prior_next_mode:
                    transition_counts[f"{previous_mode}->{mode_name}"] += 1
                    inferred_transition_count += 1

            previous_mode = mode_name
            previous_record = record

        if current_run_mode == "Stabilizer" and current_run_length > 0:
            stabilizer_runs.append(current_run_length)

        return {
            "tick_count": len(mode_records),
            "occupancy_counts": dict(occupancy_counts.most_common()),
            "transition_counts": dict(transition_counts.most_common()),
            "reason_counts": dict(reason_counts.most_common()),
            "transition_total": int(sum(transition_counts.values())),
            "explicit_transition_count": explicit_transition_count,
            "inferred_transition_count": inferred_transition_count,
            "stabilizer_run_count": len(stabilizer_runs),
            "stabilizer_dwell_mean": float(np.mean(stabilizer_runs)) if stabilizer_runs else 0.0,
            "stabilizer_dwell_max": int(max(stabilizer_runs)) if stabilizer_runs else 0,
        }

    def summarize_local_phonons(self, telemetry_records: list[dict[str, object]]) -> dict[str, object]:
        local_records = [
            record
            for record in telemetry_records
            if int(record.get("local_phonon_bundle_count", 0)) > 0
            or record.get("local_phonon_mode") is not None
        ]
        if not local_records:
            return {
                "tick_count": 0,
                "amplitude_mean": 0.0,
                "amplitude_range": (0.0, 0.0),
                "confidence_mean": 0.0,
                "confidence_range": (0.0, 0.0),
                "tier_counts": {},
                "mode_counts": {},
                "entry_total": 0,
                "exit_total": 0,
                "latest_tier": "none",
                "latest_mode": "none",
            }

        amplitudes = [float(record.get("local_phonon_amplitude", 0.0)) for record in local_records]
        confidences = [float(record.get("local_phonon_confidence", 0.0)) for record in local_records]
        tier_counts = Counter(str(record.get("local_phonon_tier", "local")) for record in local_records)
        mode_counts = Counter(str(record.get("local_phonon_mode", "none")) for record in local_records)
        return {
            "tick_count": len(local_records),
            "amplitude_mean": float(np.mean(amplitudes)),
            "amplitude_range": (float(min(amplitudes)), float(max(amplitudes))),
            "confidence_mean": float(np.mean(confidences)),
            "confidence_range": (float(min(confidences)), float(max(confidences))),
            "tier_counts": dict(tier_counts.most_common()),
            "mode_counts": dict(mode_counts.most_common()),
            "entry_total": int(
                sum(int(record.get("local_phonon_entry_count", 0)) for record in local_records)
            ),
            "exit_total": int(sum(int(record.get("local_phonon_exit_count", 0)) for record in local_records)),
            "latest_tier": str(local_records[-1].get("local_phonon_tier", "none")),
            "latest_mode": str(local_records[-1].get("local_phonon_mode", "none")),
        }

    def summarize_advisory_hints(self, telemetry_records: list[dict[str, object]]) -> dict[str, object]:
        hint_records = [
            record for record in telemetry_records if record.get("phonon_hint_status") is not None
        ]
        if not hint_records:
            return {
                "tick_count": 0,
                "status_counts": {},
                "recommendation_counts": {},
                "armed_count": 0,
                "suppressed_count": 0,
                "latest_status": "none",
                "latest_recommendation": "observe",
                "latest_reason": "none",
                "latest_decision_reason": "unknown",
                "latest_pair_stability": 0.0,
                "latest_local_stability": 0.0,
                "latest_pair_decay": 0.0,
                "latest_amplitude_trend": 0.0,
                "confidence_mean": 0.0,
            }

        status_counts = Counter(
            str(record.get("phonon_hint_status", "suppressed")) for record in hint_records
        )
        recommendation_counts = Counter(
            str(record.get("phonon_hint_recommendation", "observe")) for record in hint_records
        )
        confidences = [float(record.get("phonon_hint_confidence", 0.0)) for record in hint_records]
        latest = hint_records[-1]
        return {
            "tick_count": len(hint_records),
            "status_counts": dict(status_counts.most_common()),
            "recommendation_counts": dict(recommendation_counts.most_common()),
            "armed_count": int(status_counts.get("armed", 0)),
            "suppressed_count": int(status_counts.get("suppressed", 0)),
            "latest_status": str(latest.get("phonon_hint_status", "suppressed")),
            "latest_recommendation": str(latest.get("phonon_hint_recommendation", "observe")),
            "latest_reason": str(latest.get("phonon_hint_suppression_reason", "none")),
            "latest_decision_reason": str(latest.get("phonon_hint_decision_reason", "unknown")),
            "latest_pair_stability": float(latest.get("phonon_hint_pair_stability", 0.0)),
            "latest_local_stability": float(latest.get("phonon_hint_local_stability", 0.0)),
            "latest_pair_decay": float(latest.get("phonon_hint_pair_decay", 0.0)),
            "latest_amplitude_trend": float(latest.get("phonon_hint_amplitude_trend", 0.0)),
            "confidence_mean": float(np.mean(confidences)),
        }

    def summarize_predictive_phonon_correlations(
        self,
        telemetry_records: list[dict[str, object]],
        *,
        forward_window: int = 2,
        improvement_threshold: float = 0.02,
    ) -> dict[str, object]:
        records = [record for record in telemetry_records if "phase_coherence" in record]
        if len(records) < 2:
            return {
                "sample_count": 0,
                "forward_window": int(forward_window),
                "tier_correlations": {},
                "recommendation_correlations": {},
            }

        tier_stats: dict[str, dict[str, float]] = {}
        recommendation_stats: dict[str, dict[str, float]] = {}
        sample_count = 0

        for index, record in enumerate(records[:-1]):
            future_window = records[index + 1 : index + 1 + max(int(forward_window), 1)]
            if not future_window:
                continue

            current_coherence = float(record.get("phase_coherence", 0.0))
            future_best = max(float(item.get("phase_coherence", current_coherence)) for item in future_window)
            future_delta = float(future_best - current_coherence)
            recovery = 1.0 if future_delta > float(improvement_threshold) else 0.0
            stabilizer_entry = (
                1.0
                if any(str(item.get("entangler_mode", "active")) == "Stabilizer" for item in future_window)
                else 0.0
            )

            tier_name = str(record.get("local_phonon_tier", "none"))
            recommendation_name = str(record.get("phonon_hint_recommendation", "observe"))
            self._accumulate_predictive_stat(tier_stats, tier_name, future_delta, recovery, stabilizer_entry)
            self._accumulate_predictive_stat(
                recommendation_stats, recommendation_name, future_delta, recovery, stabilizer_entry
            )
            sample_count += 1

        return {
            "sample_count": int(sample_count),
            "forward_window": int(forward_window),
            "tier_correlations": self._finalize_predictive_stats(tier_stats),
            "recommendation_correlations": self._finalize_predictive_stats(recommendation_stats),
        }

    def score_hint_reliability(
        self,
        predictive_correlations: dict[str, object],
        *,
        min_samples: int = 3,
        recovery_weight: float = 0.65,
        stabilizer_weight: float = 0.25,
        delta_weight: float = 0.10,
        delta_normalizer: float = 0.08,
    ) -> dict[str, object]:
        minimum_samples = max(int(min_samples), 1)
        recommendation_scores = self._score_reliability_group(
            predictive_correlations.get("recommendation_correlations", {}),
            min_samples=minimum_samples,
            recovery_weight=recovery_weight,
            stabilizer_weight=stabilizer_weight,
            delta_weight=delta_weight,
            delta_normalizer=delta_normalizer,
        )
        tier_scores = self._score_reliability_group(
            predictive_correlations.get("tier_correlations", {}),
            min_samples=minimum_samples,
            recovery_weight=recovery_weight,
            stabilizer_weight=stabilizer_weight,
            delta_weight=delta_weight,
            delta_normalizer=delta_normalizer,
        )
        return {
            "sample_count": int(predictive_correlations.get("sample_count", 0)),
            "forward_window": int(predictive_correlations.get("forward_window", 0)),
            "min_samples": minimum_samples,
            "recommendation_scores": recommendation_scores,
            "tier_scores": tier_scores,
            "best_recommendation": next(iter(recommendation_scores), "none"),
            "best_tier": next(iter(tier_scores), "none"),
        }

    def summarize_hint_calibration(
        self,
        telemetry_records: list[dict[str, object]],
        *,
        forward_window: int = 2,
        min_samples: int = 3,
    ) -> dict[str, object]:
        hint_records = [
            record for record in telemetry_records if record.get("phonon_hint_status") is not None
        ]
        if not hint_records:
            return {
                "tick_count": 0,
                "sample_count": 0,
                "recommendation_calibration": {},
                "tier_calibration": {},
            }

        predictive = self.summarize_predictive_phonon_correlations(
            telemetry_records, forward_window=forward_window
        )
        reliability = self.score_hint_reliability(predictive, min_samples=min_samples)
        recommendation_calibration = self._build_calibration_group(
            hint_records,
            key_name="phonon_hint_recommendation",
            reliability_map=reliability.get("recommendation_scores", {}),
        )
        tier_calibration = self._build_calibration_group(
            hint_records,
            key_name="phonon_hint_source_tier",
            reliability_map=reliability.get("tier_scores", {}),
        )
        return {
            "tick_count": len(hint_records),
            "sample_count": int(reliability.get("sample_count", 0)),
            "forward_window": int(forward_window),
            "recommendation_calibration": recommendation_calibration,
            "tier_calibration": tier_calibration,
            "best_recommendation_alignment": next(iter(recommendation_calibration), "none"),
            "best_tier_alignment": next(iter(tier_calibration), "none"),
        }

    def summarize_hint_gate_decisions(
        self,
        telemetry_records: list[dict[str, object]],
        *,
        confidence_threshold: float = 0.55,
        reliability_threshold: float = 0.60,
        min_samples: int = 3,
        require_armed_status: bool = True,
    ) -> dict[str, object]:
        gate_records = [
            record
            for record in telemetry_records
            if "entangler_hint_gate_enabled" in record or "entangler_hint_gate_state" in record
        ]
        if not gate_records:
            return {
                "tick_count": 0,
                "enabled_count": 0,
                "passed_count": 0,
                "blocked_count": 0,
                "block_rate": 0.0,
                "reason_counts": {},
                "status_counts": {},
                "recommendation_counts": {},
                "confidence_mean": 0.0,
                "reliability_mean": 0.0,
                "sample_count_mean": 0.0,
                "provisional_count": 0,
                "first_block_tick": None,
                "first_pass_tick": None,
                "first_near_pass_tick": None,
                "first_near_pass_reason": None,
                "first_near_pass_status": None,
                "first_near_pass_confidence_gap": 0.0,
                "first_near_pass_reliability_gap": 0.0,
                "first_near_pass_sample_gap": 0,
                "near_pass_count": 0,
                "longest_block_streak": 0,
                "passed_but_nudge_blocked_count": 0,
                "first_pass_decision_reason": None,
                "first_pass_pair_stability": 0.0,
                "first_pass_local_stability": 0.0,
                "first_pass_pair_decay": 0.0,
                "first_pass_amplitude_trend": 0.0,
                "first_near_pass_decision_reason": None,
                "first_near_pass_pair_stability": 0.0,
                "first_near_pass_local_stability": 0.0,
                "first_near_pass_pair_decay": 0.0,
                "first_near_pass_amplitude_trend": 0.0,
            }

        enabled_count = 0
        passed_count = 0
        near_pass_count = 0
        provisional_count = 0
        passed_but_nudge_blocked_count = 0
        first_block_tick: int | None = None
        first_pass_tick: int | None = None
        longest_block_streak = 0
        current_block_streak = 0
        confidences: list[float] = []
        reliabilities: list[float] = []
        sample_counts: list[float] = []
        reason_counts: Counter[str] = Counter()
        status_counts: Counter[str] = Counter()
        recommendation_counts: Counter[str] = Counter()
        best_near_pass: dict[str, object] | None = None
        first_pass_signal: dict[str, object] | None = None

        for index, record in enumerate(gate_records, start=1):
            if not bool(record.get("entangler_hint_gate_enabled", False)):
                current_block_streak = 0
                continue

            enabled_count += 1
            tick = int(record.get("shared_pair_clock", record.get("entangler_pair_clock", index)))
            gate_passed = bool(record.get("entangler_hint_gate_passed", False))
            status = str(record.get("entangler_hint_gate_status", "missing"))
            confidence = float(record.get("entangler_hint_gate_confidence", 0.0))
            reliability = float(record.get("entangler_hint_gate_reliability", 0.0))
            sample_count = int(record.get("entangler_hint_gate_sample_count", 0))
            provisional = bool(record.get("entangler_hint_gate_provisional", True))
            reason = str(record.get("entangler_hint_gate_reason", "unknown"))
            confidence_gap = max(float(confidence_threshold) - confidence, 0.0)
            reliability_gap = max(float(reliability_threshold) - reliability, 0.0)
            sample_gap = max(int(min_samples) - sample_count, 0)
            status_penalty = 2.0 if bool(require_armed_status) and status != "armed" else 0.0
            provisional_penalty = 1.5 if provisional else 0.0
            near_pass_score = float(
                status_penalty + provisional_penalty + sample_gap + confidence_gap + reliability_gap
            )
            near_pass_candidate = {
                "tick": tick,
                "reason": reason,
                "status": status,
                "confidence_gap": float(confidence_gap),
                "reliability_gap": float(reliability_gap),
                "sample_gap": int(sample_gap),
                "score": near_pass_score,
                "decision_reason": str(record.get("phonon_hint_decision_reason", "unknown")),
                "pair_stability": float(record.get("phonon_hint_pair_stability", 0.0)),
                "local_stability": float(record.get("phonon_hint_local_stability", 0.0)),
                "pair_decay": float(record.get("phonon_hint_pair_decay", 0.0)),
                "amplitude_trend": float(record.get("phonon_hint_amplitude_trend", 0.0)),
            }
            if gate_passed:
                passed_count += 1
                current_block_streak = 0
                if first_pass_tick is None:
                    first_pass_tick = tick
                    first_pass_signal = near_pass_candidate
            else:
                current_block_streak += 1
                longest_block_streak = max(longest_block_streak, current_block_streak)
                if first_block_tick is None:
                    first_block_tick = tick
                reason_counts[reason] += 1
                if near_pass_score <= 1.0:
                    near_pass_count += 1
                if (
                    best_near_pass is None
                    or near_pass_score < float(best_near_pass["score"])
                    or (
                        near_pass_score == float(best_near_pass["score"])
                        and tick < int(best_near_pass["tick"])
                    )
                ):
                    best_near_pass = near_pass_candidate

            status_counts[status] += 1
            recommendation_counts[str(record.get("entangler_hint_gate_recommendation", "observe"))] += 1
            confidences.append(confidence)
            reliabilities.append(reliability)
            sample_counts.append(float(sample_count))
            provisional_count += int(provisional)

            nudge_enabled = bool(record.get("entangler_nudge_enabled", False))
            nudge_applied = bool(record.get("entangler_nudge_applied", False))
            nudge_rejection = str(record.get("entangler_nudge_rejection_reason", "disabled"))
            if gate_passed and nudge_enabled and not nudge_applied and nudge_rejection != "disabled":
                passed_but_nudge_blocked_count += 1

        blocked_count = max(enabled_count - passed_count, 0)
        return {
            "tick_count": len(gate_records),
            "enabled_count": enabled_count,
            "passed_count": passed_count,
            "blocked_count": blocked_count,
            "block_rate": float(blocked_count / enabled_count) if enabled_count else 0.0,
            "reason_counts": dict(reason_counts.most_common()),
            "status_counts": dict(status_counts.most_common()),
            "recommendation_counts": dict(recommendation_counts.most_common()),
            "confidence_mean": float(np.mean(confidences)) if confidences else 0.0,
            "reliability_mean": float(np.mean(reliabilities)) if reliabilities else 0.0,
            "sample_count_mean": float(np.mean(sample_counts)) if sample_counts else 0.0,
            "provisional_count": provisional_count,
            "first_block_tick": first_block_tick,
            "first_pass_tick": first_pass_tick,
            "first_near_pass_tick": None if best_near_pass is None else int(best_near_pass["tick"]),
            "first_near_pass_reason": None if best_near_pass is None else str(best_near_pass["reason"]),
            "first_near_pass_status": None if best_near_pass is None else str(best_near_pass["status"]),
            "first_near_pass_confidence_gap": 0.0
            if best_near_pass is None
            else float(best_near_pass["confidence_gap"]),
            "first_near_pass_reliability_gap": 0.0
            if best_near_pass is None
            else float(best_near_pass["reliability_gap"]),
            "first_near_pass_sample_gap": 0 if best_near_pass is None else int(best_near_pass["sample_gap"]),
            "near_pass_count": int(near_pass_count),
            "longest_block_streak": longest_block_streak,
            "passed_but_nudge_blocked_count": passed_but_nudge_blocked_count,
            "first_pass_decision_reason": None
            if first_pass_signal is None
            else str(first_pass_signal["decision_reason"]),
            "first_pass_pair_stability": 0.0
            if first_pass_signal is None
            else float(first_pass_signal["pair_stability"]),
            "first_pass_local_stability": 0.0
            if first_pass_signal is None
            else float(first_pass_signal["local_stability"]),
            "first_pass_pair_decay": 0.0
            if first_pass_signal is None
            else float(first_pass_signal["pair_decay"]),
            "first_pass_amplitude_trend": 0.0
            if first_pass_signal is None
            else float(first_pass_signal["amplitude_trend"]),
            "first_near_pass_decision_reason": None
            if best_near_pass is None
            else str(best_near_pass["decision_reason"]),
            "first_near_pass_pair_stability": 0.0
            if best_near_pass is None
            else float(best_near_pass["pair_stability"]),
            "first_near_pass_local_stability": 0.0
            if best_near_pass is None
            else float(best_near_pass["local_stability"]),
            "first_near_pass_pair_decay": 0.0
            if best_near_pass is None
            else float(best_near_pass["pair_decay"]),
            "first_near_pass_amplitude_trend": 0.0
            if best_near_pass is None
            else float(best_near_pass["amplitude_trend"]),
        }

    def summarize_nudge_outcomes(
        self,
        telemetry_records: list[dict[str, object]],
        *,
        forward_window: int = 2,
        improvement_threshold: float = 0.02,
    ) -> dict[str, object]:
        records = [record for record in telemetry_records if "phase_coherence" in record]
        nudge_records = [
            record
            for record in records
            if "entangler_nudge_enabled" in record or "entangler_nudge_applied" in record
        ]
        if not nudge_records:
            return {
                "tick_count": 0,
                "attempt_count": 0,
                "applied_count": 0,
                "rejection_count": 0,
                "apply_rate": 0.0,
                "positive_coherence_windows": 0,
                "positive_window_rate": 0.0,
                "stabilizer_entry_windows": 0,
                "stabilizer_entry_rate": 0.0,
                "mean_future_delta": 0.0,
                "reliability_mean": 0.0,
                "stability_score_mean": 0.0,
                "clamp_count": 0,
                "clamp_rate": 0.0,
                "reason_counts": {},
                "rejection_counts": {},
                "delta_abs_mean": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "delta_abs_max": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "reason_outcomes": {},
                "decision_reason_counts": {},
                "decision_outcomes": {},
            }

        attempt_count = 0
        applied_count = 0
        positive_windows = 0
        stabilizer_windows = 0
        clamp_count = 0
        future_deltas: list[float] = []
        reliabilities: list[float] = []
        stability_scores: list[float] = []
        delta_abs = {"aperture": [], "damping": [], "phase_offset": []}
        reason_counts: Counter[str] = Counter()
        decision_reason_counts: Counter[str] = Counter()
        rejection_counts: Counter[str] = Counter()
        reason_stats: dict[str, dict[str, float]] = {}
        decision_stats: dict[str, dict[str, float]] = {}

        for index, record in enumerate(records):
            if "entangler_nudge_enabled" not in record and "entangler_nudge_applied" not in record:
                continue
            if not bool(record.get("entangler_nudge_enabled", False)):
                continue

            attempt_count += 1
            reliabilities.append(float(record.get("entangler_nudge_reliability", 0.0)))
            stability_scores.append(float(record.get("entangler_nudge_stability_score", 0.0)))

            if bool(record.get("entangler_nudge_applied", False)):
                applied_count += 1
                reason = str(record.get("entangler_nudge_reason", "none"))
                decision_reason = str(record.get("phonon_hint_decision_reason", "unknown"))
                reason_counts[reason] += 1
                decision_reason_counts[decision_reason] += 1
                if bool(record.get("entangler_nudge_clamped", False)):
                    clamp_count += 1
                for key, entry_key in (
                    ("aperture", "entangler_nudge_aperture_delta"),
                    ("damping", "entangler_nudge_damping_delta"),
                    ("phase_offset", "entangler_nudge_phase_delta"),
                ):
                    delta_abs[key].append(abs(float(record.get(entry_key, 0.0))))

                future_window = records[index + 1 : index + 1 + max(int(forward_window), 1)]
                current_coherence = float(record.get("phase_coherence", 0.0))
                future_best = max(
                    [current_coherence]
                    + [float(item.get("phase_coherence", current_coherence)) for item in future_window]
                )
                future_delta = float(future_best - current_coherence)
                future_deltas.append(future_delta)
                recovery = 1.0 if future_delta > float(improvement_threshold) else 0.0
                stabilizer_entry = (
                    1.0
                    if any(
                        str(item.get("entangler_mode", "active")) == "Stabilizer" for item in future_window
                    )
                    else 0.0
                )
                positive_windows += int(recovery)
                stabilizer_windows += int(stabilizer_entry)
                self._accumulate_predictive_stat(
                    reason_stats, reason, future_delta, recovery, stabilizer_entry
                )
                self._accumulate_predictive_stat(
                    decision_stats, decision_reason, future_delta, recovery, stabilizer_entry
                )
            else:
                rejection = str(record.get("entangler_nudge_rejection_reason", "disabled"))
                rejection_counts[rejection] += 1

        rejection_count = max(attempt_count - applied_count, 0)
        return {
            "tick_count": len(nudge_records),
            "attempt_count": attempt_count,
            "applied_count": applied_count,
            "rejection_count": rejection_count,
            "apply_rate": float(applied_count / attempt_count) if attempt_count else 0.0,
            "positive_coherence_windows": positive_windows,
            "positive_window_rate": float(positive_windows / applied_count) if applied_count else 0.0,
            "stabilizer_entry_windows": stabilizer_windows,
            "stabilizer_entry_rate": float(stabilizer_windows / applied_count) if applied_count else 0.0,
            "mean_future_delta": float(np.mean(future_deltas)) if future_deltas else 0.0,
            "reliability_mean": float(np.mean(reliabilities)) if reliabilities else 0.0,
            "stability_score_mean": float(np.mean(stability_scores)) if stability_scores else 0.0,
            "clamp_count": clamp_count,
            "clamp_rate": float(clamp_count / applied_count) if applied_count else 0.0,
            "reason_counts": dict(reason_counts.most_common()),
            "rejection_counts": dict(rejection_counts.most_common()),
            "delta_abs_mean": {
                key: float(np.mean(values)) if values else 0.0 for key, values in delta_abs.items()
            },
            "delta_abs_max": {
                key: float(max(values)) if values else 0.0 for key, values in delta_abs.items()
            },
            "reason_outcomes": self._finalize_predictive_stats(reason_stats),
            "decision_reason_counts": dict(decision_reason_counts.most_common()),
            "decision_outcomes": self._finalize_predictive_stats(decision_stats),
        }

    def summarize_msf_guard_outcomes(
        self,
        telemetry_records: list[dict[str, object]],
    ) -> dict[str, object]:
        """Summarise per-tick MSFGuard surrogate observations.

        Reads ``entangler_nudge_msf_*`` keys persisted by
        :class:`TelemetryPanel`. Records with the guard disabled are still
        counted in ``status_counts`` (status="disabled") so a sweep variant
        can distinguish guard-off vs guard-on runs without needing the config
        column. Returns zeroed defaults when no MSF-bearing records exist.
        """
        msf_records = [
            record
            for record in telemetry_records
            if "entangler_nudge_msf_status" in record
        ]
        if not msf_records:
            return {
                "tick_count": 0,
                "enabled_tick_count": 0,
                "stable_count": 0,
                "unstable_count": 0,
                "insufficient_history_count": 0,
                "disabled_count": 0,
                "veto_count": 0,
                "veto_rate": 0.0,
                "lambda_hat_mean": 0.0,
                "lambda_hat_max": 0.0,
                "lambda_hat_p95": 0.0,
                "status_counts": {},
            }

        status_counts: Counter[str] = Counter()
        lambda_values: list[float] = []
        enabled_tick_count = 0
        veto_count = 0
        for record in msf_records:
            status = str(record.get("entangler_nudge_msf_status", "disabled"))
            status_counts[status] += 1
            if bool(record.get("entangler_nudge_msf_guard_enabled", False)):
                enabled_tick_count += 1
            lam = record.get("entangler_nudge_msf_lambda_hat")
            if lam is not None:
                try:
                    lambda_values.append(float(lam))
                except (TypeError, ValueError):
                    pass
            if (
                status == "unstable"
                and str(record.get("entangler_nudge_rejection_reason", "")) == "msf_unstable"
            ):
                veto_count += 1

        sorted_lambda = sorted(lambda_values)
        if sorted_lambda:
            lambda_max = float(sorted_lambda[-1])
            lambda_mean = float(np.mean(sorted_lambda))
            # Discrete p95 with linear interpolation on small samples.
            idx = 0.95 * (len(sorted_lambda) - 1)
            lower = int(np.floor(idx))
            upper = int(np.ceil(idx))
            if lower == upper:
                lambda_p95 = float(sorted_lambda[lower])
            else:
                frac = idx - lower
                lambda_p95 = float(
                    sorted_lambda[lower] * (1.0 - frac) + sorted_lambda[upper] * frac
                )
        else:
            lambda_max = 0.0
            lambda_mean = 0.0
            lambda_p95 = 0.0

        return {
            "tick_count": len(msf_records),
            "enabled_tick_count": enabled_tick_count,
            "stable_count": int(status_counts.get("stable", 0)),
            "unstable_count": int(status_counts.get("unstable", 0)),
            "insufficient_history_count": int(status_counts.get("insufficient_history", 0)),
            "disabled_count": int(status_counts.get("disabled", 0)),
            "veto_count": veto_count,
            "veto_rate": float(veto_count / enabled_tick_count) if enabled_tick_count else 0.0,
            "lambda_hat_mean": lambda_mean,
            "lambda_hat_max": lambda_max,
            "lambda_hat_p95": lambda_p95,
            "status_counts": dict(status_counts.most_common()),
        }

    def summarize_status_streaks(self, telemetry_records: list[dict[str, object]]) -> dict[str, object]:
        coherence_records = [record for record in telemetry_records if "entangler_coherence_status" in record]
        if not coherence_records:
            return {
                "tick_count": 0,
                "longest_decay_streak": 0,
                "longest_improving_streak": 0,
                "longest_stable_streak": 0,
                "longest_streaks": {},
                "first_stabilizer_tick": None,
            }

        longest_streaks: dict[str, int] = {}
        current_status: str | None = None
        current_streak = 0
        first_stabilizer_tick: int | None = None

        for index, record in enumerate(coherence_records, start=1):
            status = str(record.get("entangler_coherence_status", "stable"))
            if status == current_status:
                current_streak += 1
            else:
                if current_status is not None:
                    longest_streaks[current_status] = max(
                        longest_streaks.get(current_status, 0), current_streak
                    )
                current_status = status
                current_streak = 1

            if first_stabilizer_tick is None and str(record.get("entangler_mode", "active")) == "Stabilizer":
                first_stabilizer_tick = int(
                    record.get("shared_pair_clock", record.get("entangler_pair_clock", index))
                )

        if current_status is not None:
            longest_streaks[current_status] = max(longest_streaks.get(current_status, 0), current_streak)

        return {
            "tick_count": len(coherence_records),
            "longest_decay_streak": int(longest_streaks.get("decaying", 0)),
            "longest_improving_streak": int(longest_streaks.get("improving", 0)),
            "longest_stable_streak": int(longest_streaks.get("stable", 0)),
            "longest_streaks": dict(sorted(longest_streaks.items())),
            "first_stabilizer_tick": first_stabilizer_tick,
        }

    def summarize_sweep_diagnosis(
        self,
        telemetry_records: list[dict[str, object]],
        *,
        min_mode_switch_samples: int = 3,
        enter_decay_streak: int = 2,
        cycle_count: int | None = None,
    ) -> dict[str, object]:
        trend = self.summarize_coherence_trend(telemetry_records)
        switching = self.summarize_mode_switching(telemetry_records)
        streaks = self.summarize_status_streaks(telemetry_records)
        tick_count = int(trend.get("tick_count", 0))
        min_switch_ticks = max(int(min_mode_switch_samples), int(enter_decay_streak), 1)
        coherence_min, coherence_max = tuple(trend.get("coherence_range", (0.0, 0.0)))
        coherence_span = float(coherence_max - coherence_min)
        status_counts = dict(trend.get("status_counts", {}))
        transition_counts = dict(switching.get("transition_counts", {}))
        first_stabilizer_tick = streaks.get("first_stabilizer_tick")
        entry_policy_tick: int | None = None

        for index, record in enumerate(telemetry_records, start=1):
            pair_clock = int(record.get("shared_pair_clock", record.get("entangler_pair_clock", index)))
            decay_streak = int(record.get("entangler_decay_streak", 0))
            mode_name = str(record.get("entangler_mode", "active"))
            if (
                pair_clock >= int(min_mode_switch_samples)
                and decay_streak >= int(enter_decay_streak)
                and mode_name == "active"
            ):
                entry_policy_tick = pair_clock
                break

        entered_stabilizer = bool(
            int(transition_counts.get("active->Stabilizer", 0)) > 0 or first_stabilizer_tick is not None
        )
        met_entry_policy = entry_policy_tick is not None

        if entered_stabilizer:
            detail = (
                f"natural Stabilizer entry observed at tick {int(first_stabilizer_tick or entry_policy_tick or min_switch_ticks)}"
                f" with longest decaying streak {int(streaks.get('longest_decay_streak', 0))}"
            )
            return {
                "label": "entered_stabilizer",
                "detail": detail,
                "met_entry_policy": met_entry_policy,
                "entry_policy_tick": entry_policy_tick,
            }

        if tick_count < min_switch_ticks or (cycle_count is not None and int(cycle_count) < min_switch_ticks):
            detail = (
                f"only {tick_count} ticks recorded; current policy needs at least {min_switch_ticks}"
                f" to arm a natural decay-driven switch"
            )
            return {
                "label": "runtime_too_short_candidate",
                "detail": detail,
                "met_entry_policy": met_entry_policy,
                "entry_policy_tick": entry_policy_tick,
            }

        if met_entry_policy or int(streaks.get("longest_decay_streak", 0)) >= int(enter_decay_streak):
            detail = (
                f"decay streak pressure reached {int(streaks.get('longest_decay_streak', 0))}"
                f" by tick {int(entry_policy_tick or tick_count)}, suggesting thresholds or switch timing are conservative"
            )
            return {
                "label": "threshold_conservative_candidate",
                "detail": detail,
                "met_entry_policy": met_entry_policy,
                "entry_policy_tick": entry_policy_tick,
            }

        decaying_count = int(status_counts.get("decaying", 0))
        stable_like_count = int(status_counts.get("stable", 0)) + int(status_counts.get("improving", 0))
        if coherence_span < 0.12 and decaying_count <= max(1, tick_count // 4):
            detail = (
                f"coherence span {coherence_span:.3f} with only {decaying_count} decaying ticks"
                f" points to a low-variance generator regime"
            )
            return {
                "label": "low_variance_candidate",
                "detail": detail,
                "met_entry_policy": met_entry_policy,
                "entry_policy_tick": entry_policy_tick,
            }

        if stable_like_count < tick_count and tick_count <= (min_switch_ticks + 1):
            detail = f"decay appeared but the run ended after {tick_count} ticks before a sustained streak could accumulate"
            return {
                "label": "runtime_too_short_candidate",
                "detail": detail,
                "met_entry_policy": met_entry_policy,
                "entry_policy_tick": entry_policy_tick,
            }

        detail = (
            f"coherence span {coherence_span:.3f} and longest decaying streak {int(streaks.get('longest_decay_streak', 0))}"
            f" suggest more variance is needed before loosening thresholds"
        )
        return {
            "label": "low_variance_candidate",
            "detail": detail,
            "met_entry_policy": met_entry_policy,
            "entry_policy_tick": entry_policy_tick,
        }

    def summarize_top_wormhole_shifts(
        self, telemetry_records: list[dict[str, object]], top_n: int = 4
    ) -> dict[str, dict[str, object]]:
        shift_summary: dict[str, dict[str, object]] = {}
        previous_ranks: dict[str, int] = {}

        for record in telemetry_records:
            ranked = list(record.get("entangler_top_wormholes", []))[:top_n]
            current_ranks = {
                str(item.get("node_id", "unknown")): index + 1
                for index, item in enumerate(ranked)
                if item.get("node_id") is not None
            }
            current_weights = {
                str(item.get("node_id", "unknown")): float(item.get("weight", 1.0))
                for item in ranked
                if item.get("node_id") is not None
            }

            for node_id, rank in current_ranks.items():
                node_summary = shift_summary.setdefault(
                    node_id,
                    {
                        "current_weight": float(current_weights.get(node_id, 1.0)),
                        "best_rank": rank,
                        "latest_rank": rank,
                        "entries": 0,
                        "exits": 0,
                        "promotions": 0,
                        "demotions": 0,
                        "rank_history": [],
                    },
                )
                node_summary["current_weight"] = float(
                    current_weights.get(node_id, node_summary["current_weight"])
                )
                node_summary["best_rank"] = min(int(node_summary["best_rank"]), rank)
                node_summary["latest_rank"] = rank
                node_summary["rank_history"].append(rank)

                if node_id not in previous_ranks:
                    node_summary["entries"] += 1
                elif rank < previous_ranks[node_id]:
                    node_summary["promotions"] += 1
                elif rank > previous_ranks[node_id]:
                    node_summary["demotions"] += 1

            for node_id in previous_ranks:
                if node_id not in current_ranks:
                    node_summary = shift_summary.setdefault(
                        node_id,
                        {
                            "current_weight": 1.0,
                            "best_rank": previous_ranks[node_id],
                            "latest_rank": previous_ranks[node_id],
                            "entries": 0,
                            "exits": 0,
                            "promotions": 0,
                            "demotions": 0,
                            "rank_history": [],
                        },
                    )
                    node_summary["exits"] += 1

            previous_ranks = current_ranks

        return dict(
            sorted(
                shift_summary.items(),
                key=lambda item: (
                    -int(item[1].get("promotions", 0)),
                    -int(item[1].get("entries", 0)),
                    int(item[1].get("best_rank", top_n + 1)),
                    str(item[0]),
                ),
            )
        )

    def render_weight_drift_summary(self, pair_id: str, top_n: int = 4) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        drift = self.summarize_weight_drift(telemetry_records)
        if int(drift.get("tick_count", 0)) == 0:
            return "No wormhole weight telemetry available for replay."

        shifts = self.summarize_top_wormhole_shifts(telemetry_records, top_n=top_n)
        lines = [
            (
                f"Wormhole weight drift over {int(drift['tick_count'])} ticks:"
                f" min {drift['weight_min_range'][0]:.2f}-{drift['weight_min_range'][1]:.2f}"
                f" (mean={drift['weight_min_mean']:.2f}, sigma={drift['weight_min_std']:.3f}),"
                f" max {drift['weight_max_range'][0]:.2f}-{drift['weight_max_range'][1]:.2f}"
                f" (mean={drift['weight_max_mean']:.2f}, sigma={drift['weight_max_std']:.3f})"
            )
        ]

        if not shifts:
            lines.append("Top wormhole shifts: none recorded")
            return "\n".join(lines)

        lines.append("Top wormhole shifts:")
        for node_id, summary in list(shifts.items())[:top_n]:
            lines.append(
                f"  {node_id} | latest_rank={int(summary['latest_rank'])} | best_rank={int(summary['best_rank'])}"
                f" | wt={float(summary['current_weight']):.2f} | entries={int(summary['entries'])}"
                f" | exits={int(summary['exits'])} | promotions={int(summary['promotions'])}"
                f" | demotions={int(summary['demotions'])}"
            )
        return "\n".join(lines)

    def render_coherence_summary(self, pair_id: str) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        trend = self.summarize_coherence_trend(telemetry_records)
        if int(trend.get("tick_count", 0)) == 0:
            return "No coherence telemetry available for replay."

        dominant_mode = next(iter(trend.get("mode_counts", {"active": 0})), "active")
        return (
            f"Coherence trend over {int(trend['tick_count'])} ticks: "
            f"range {trend['coherence_range'][0]:.3f}-{trend['coherence_range'][1]:.3f} "
            f"(mean={trend['coherence_mean']:.3f}, sigma={trend['coherence_std']:.3f}), "
            f"delta={trend['coherence_delta']:+.3f}, target={trend['target']:.3f}, "
            f"status={trend['latest_status']}, mode={dominant_mode}"
        )

    def render_mode_switching_summary(self, pair_id: str) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        switching = self.summarize_mode_switching(telemetry_records)
        if int(switching.get("tick_count", 0)) == 0:
            return "No mode switching telemetry available for replay."

        occupancy = dict(switching.get("occupancy_counts", {}))
        transitions = dict(switching.get("transition_counts", {}))
        reasons = dict(switching.get("reason_counts", {}))
        occupancy_text = ", ".join(f"{mode}={count}" for mode, count in occupancy.items()) or "none"
        transition_text = (
            ", ".join(f"{transition}={count}" for transition, count in transitions.items()) or "none"
        )
        line = (
            f"Mode switching over {int(switching['tick_count'])} ticks: "
            f"occupancy {occupancy_text}; transitions={int(switching['transition_total'])} ({transition_text}); "
            f"Stabilizer dwell mean={float(switching['stabilizer_dwell_mean']):.2f}, "
            f"max={int(switching['stabilizer_dwell_max'])}"
        )
        if reasons:
            reason_text = ", ".join(f"{reason}={count}" for reason, count in reasons.items())
            return f"{line}\nSwitch reasons: {reason_text}"
        if (
            int(switching.get("transition_total", 0)) > 0
            and int(switching.get("explicit_transition_count", 0)) == 0
        ):
            return f"{line}\nSwitch reasons: unavailable (inferred from mode labels)"
        return f"{line}\nSwitch reasons: none"

    def render_local_phonon_summary(self, pair_id: str) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_local_phonons(telemetry_records)
        if int(summary.get("tick_count", 0)) == 0:
            return "No local phonon telemetry available for replay."

        tier_counts = dict(summary.get("tier_counts", {}))
        mode_counts = dict(summary.get("mode_counts", {}))
        return (
            f"Local phonons over {int(summary['tick_count'])} ticks: "
            f"amp {summary['amplitude_range'][0]:.3f}-{summary['amplitude_range'][1]:.3f} "
            f"(mean={summary['amplitude_mean']:.3f}), "
            f"conf {summary['confidence_range'][0]:.3f}-{summary['confidence_range'][1]:.3f} "
            f"(mean={summary['confidence_mean']:.3f}), "
            f"entries={int(summary['entry_total'])}, exits={int(summary['exit_total'])}, "
            f"latest={summary['latest_tier']}:{summary['latest_mode']}, "
            f"tiers={tier_counts}, modes={mode_counts}"
        )

    def render_advisory_hint_summary(self, pair_id: str) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_advisory_hints(telemetry_records)
        if int(summary.get("tick_count", 0)) == 0:
            return "No advisory phonon hint telemetry available for replay."

        status_counts = dict(summary.get("status_counts", {}))
        recommendation_counts = dict(summary.get("recommendation_counts", {}))
        return (
            f"Advisory phonon hints over {int(summary['tick_count'])} ticks: "
            f"armed={int(summary['armed_count'])}, suppressed={int(summary['suppressed_count'])}, "
            f"mean_conf={summary['confidence_mean']:.3f}, "
            f"latest={summary['latest_status']}:{summary['latest_recommendation']}, "
            f"reason={summary['latest_reason']}, decision={summary['latest_decision_reason']}, "
            f"signal=p{float(summary.get('latest_pair_stability', 0.0)):.2f}/"
            f"l{float(summary.get('latest_local_stability', 0.0)):.2f}/"
            f"d{float(summary.get('latest_pair_decay', 0.0)):.2f}/"
            f"a{float(summary.get('latest_amplitude_trend', 0.0)):+.2f}, "
            f"statuses={status_counts}, recommendations={recommendation_counts}"
        )

    def render_predictive_phonon_summary(self, pair_id: str, forward_window: int = 2) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_predictive_phonon_correlations(
            telemetry_records, forward_window=forward_window
        )
        if int(summary.get("sample_count", 0)) == 0:
            return "No predictive phonon correlation telemetry available for replay."

        tier_lines = self._render_predictive_group(summary.get("tier_correlations", {}), label="tiers")
        recommendation_lines = self._render_predictive_group(
            summary.get("recommendation_correlations", {}),
            label="recommendations",
        )
        return (
            f"Predictive phonon correlations over {int(summary['sample_count'])} samples with +{int(summary['forward_window'])}-tick lookahead:\n"
            f"  tiers: {tier_lines}\n"
            f"  recommendations: {recommendation_lines}"
        )

    def render_hint_reliability_summary(
        self, pair_id: str, forward_window: int = 2, min_samples: int = 3
    ) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        predictive = self.summarize_predictive_phonon_correlations(
            telemetry_records, forward_window=forward_window
        )
        summary = self.score_hint_reliability(predictive, min_samples=min_samples)
        if int(summary.get("sample_count", 0)) == 0:
            return "No hint reliability evidence available for replay."

        recommendation_lines = self._render_reliability_group(summary.get("recommendation_scores", {}))
        tier_lines = self._render_reliability_group(summary.get("tier_scores", {}))
        return (
            f"Hint reliability over {int(summary['sample_count'])} predictive samples: "
            f"best_rec={summary.get('best_recommendation', 'none')}, best_tier={summary.get('best_tier', 'none')}, "
            f"recommendations={recommendation_lines}; tiers={tier_lines}"
        )

    def render_hint_calibration_summary(
        self, pair_id: str, forward_window: int = 2, min_samples: int = 3
    ) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_hint_calibration(
            telemetry_records,
            forward_window=forward_window,
            min_samples=min_samples,
        )
        if int(summary.get("tick_count", 0)) == 0:
            return "No hint calibration evidence available for replay."

        recommendation_lines = self._render_calibration_group(summary.get("recommendation_calibration", {}))
        tier_lines = self._render_calibration_group(summary.get("tier_calibration", {}))
        return (
            f"Hint calibration over {int(summary['tick_count'])} hint ticks: "
            f"best_rec={summary.get('best_recommendation_alignment', 'none')}, best_tier={summary.get('best_tier_alignment', 'none')}, "
            f"recommendations={recommendation_lines}; tiers={tier_lines}"
        )

    def render_hint_gate_decision_summary(
        self,
        pair_id: str,
        *,
        confidence_threshold: float = 0.55,
        reliability_threshold: float = 0.60,
        min_samples: int = 3,
        require_armed_status: bool = True,
    ) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_hint_gate_decisions(
            telemetry_records,
            confidence_threshold=confidence_threshold,
            reliability_threshold=reliability_threshold,
            min_samples=min_samples,
            require_armed_status=require_armed_status,
        )
        if int(summary.get("tick_count", 0)) == 0:
            return "No hint gate telemetry available for replay."

        first_pass_tick = summary.get("first_pass_tick")
        near_pass_tick = summary.get("first_near_pass_tick")
        near_pass_fragment = "none"
        if near_pass_tick is not None:
            near_pass_fragment = (
                f"tick {int(near_pass_tick)}"
                f" ({summary.get('first_near_pass_reason', 'unknown')},"
                f" cgap={float(summary.get('first_near_pass_confidence_gap', 0.0)):.2f},"
                f" rgap={float(summary.get('first_near_pass_reliability_gap', 0.0)):.2f},"
                f" ngap={int(summary.get('first_near_pass_sample_gap', 0))},"
                f" decide={summary.get('first_near_pass_decision_reason', 'unknown')},"
                f" signal=p{float(summary.get('first_near_pass_pair_stability', 0.0)):.2f}/"
                f"l{float(summary.get('first_near_pass_local_stability', 0.0)):.2f}/"
                f"d{float(summary.get('first_near_pass_pair_decay', 0.0)):.2f}/"
                f"a{float(summary.get('first_near_pass_amplitude_trend', 0.0)):+.2f})"
            )
        first_pass_fragment = "-"
        if first_pass_tick is not None:
            first_pass_fragment = (
                f"{int(first_pass_tick)}"
                f"/{summary.get('first_pass_decision_reason', 'unknown')}"
                f"/p{float(summary.get('first_pass_pair_stability', 0.0)):.2f}"
                f"/l{float(summary.get('first_pass_local_stability', 0.0)):.2f}"
                f"/d{float(summary.get('first_pass_pair_decay', 0.0)):.2f}"
                f"/a{float(summary.get('first_pass_amplitude_trend', 0.0)):+.2f}"
            )
        return (
            f"Hint gate decisions over {int(summary.get('tick_count', 0))} ticks: "
            f"enabled={int(summary.get('enabled_count', 0))}, passed={int(summary.get('passed_count', 0))}, "
            f"blocked={int(summary.get('blocked_count', 0))}, block_rate={float(summary.get('block_rate', 0.0)):.2f}, "
            f"reasons={self._render_count_group(summary.get('reason_counts', {}), empty_label='none')}, "
            f"statuses={self._render_count_group(summary.get('status_counts', {}), empty_label='none')}, "
            f"mean_conf={float(summary.get('confidence_mean', 0.0)):.2f}, "
            f"mean_rel={float(summary.get('reliability_mean', 0.0)):.2f}, "
            f"mean_n={float(summary.get('sample_count_mean', 0.0)):.2f}, "
            f"provisional={int(summary.get('provisional_count', 0))}, "
            f"near_pass={int(summary.get('near_pass_count', 0))}, "
            f"pass_but_nudge_blocked={int(summary.get('passed_but_nudge_blocked_count', 0))}, "
            f"first_pass={first_pass_fragment}, "
            f"first_block={summary.get('first_block_tick') if summary.get('first_block_tick') is not None else '-'}, "
            f"first_near_pass={near_pass_fragment}, "
            f"longest_block_streak={int(summary.get('longest_block_streak', 0))}"
        )

    def render_nudge_outcome_summary(self, pair_id: str, forward_window: int = 2) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_nudge_outcomes(telemetry_records, forward_window=forward_window)
        if int(summary.get("tick_count", 0)) == 0:
            return "No nudge outcome telemetry available for replay."

        reason_lines = self._render_predictive_group(
            summary.get("reason_outcomes", {}), label="nudge reasons"
        )
        decision_lines = self._render_predictive_group(
            summary.get("decision_outcomes", {}), label="decision reasons"
        )
        delta_abs_mean = dict(summary.get("delta_abs_mean", {}))
        return (
            f"Nudge outcomes over {int(summary['tick_count'])} ticks: "
            f"attempts={int(summary.get('attempt_count', 0))}, applied={int(summary.get('applied_count', 0))}, "
            f"rejected={int(summary.get('rejection_count', 0))}, apply_rate={float(summary.get('apply_rate', 0.0)):.2f}, "
            f"positive={int(summary.get('positive_coherence_windows', 0))}/{max(int(summary.get('applied_count', 0)), 1)}, "
            f"stabilizer={int(summary.get('stabilizer_entry_windows', 0))}, "
            f"mean_delta={float(summary.get('mean_future_delta', 0.0)):+.3f}, "
            f"rel={float(summary.get('reliability_mean', 0.0)):.2f}, "
            f"stable={float(summary.get('stability_score_mean', 0.0)):.2f}, "
            f"clamp={int(summary.get('clamp_count', 0))}, "
            f"|d|=a{float(delta_abs_mean.get('aperture', 0.0)):.3f}/d{float(delta_abs_mean.get('damping', 0.0)):.3f}/p{float(delta_abs_mean.get('phase_offset', 0.0)):.3f}; "
            f"reasons={reason_lines}; decisions={decision_lines}; rejects={dict(summary.get('rejection_counts', {}))}"
        )

    def summarize_paper_diagnostic_proxies(
        self, telemetry_records: list[dict[str, object]]
    ) -> dict[str, object]:
        if not telemetry_records:
            return {
                "tick_count": 0,
                "synchrony_margin": {
                    "label": "unknown",
                    "basis": "unknown",
                    "coupling_posture": "unknown",
                    "evidence_signals": [],
                    "contradiction_level": "unknown",
                    "boundary_state": "unknown",
                    "support_score": 0,
                    "risk_score": 0,
                    "coupling_support_signals": [],
                    "coupling_risk_signals": [],
                    "support_signals": [],
                    "risk_signals": [],
                    "contradiction_signals": [],
                },
                "basin_fragility": {
                    "label": "unknown",
                    "support_score": 0,
                    "risk_score": 0,
                    "support_signals": [],
                    "risk_signals": [],
                },
            }

        trend = self.summarize_coherence_trend(telemetry_records)
        gate = self.summarize_hint_gate_decisions(telemetry_records)
        nudge = self.summarize_nudge_outcomes(telemetry_records)
        streaks = self.summarize_status_streaks(telemetry_records)
        switching = self.summarize_mode_switching(telemetry_records)

        coherence_mean = float(trend.get("coherence_mean", 0.0))
        coherence_delta = float(trend.get("coherence_delta", 0.0))
        latest_status = str(trend.get("latest_status", "unknown"))
        block_rate = float(gate.get("block_rate", 0.0))
        passed_count = int(gate.get("passed_count", 0))
        near_pass_count = int(gate.get("near_pass_count", 0))
        passed_but_nudge_blocked_count = int(gate.get("passed_but_nudge_blocked_count", 0))
        nudge_applied_count = int(nudge.get("applied_count", 0))
        positive_window_rate = float(nudge.get("positive_window_rate", 0.0))
        stabilizer_entry_rate = float(nudge.get("stabilizer_entry_rate", 0.0))
        transition_total = int(switching.get("transition_total", 0))
        stabilizer_dwell_max = int(switching.get("stabilizer_dwell_max", 0))
        longest_decay_streak = int(streaks.get("longest_decay_streak", 0))
        longest_improving_streak = int(streaks.get("longest_improving_streak", 0))
        longest_stable_streak = int(streaks.get("longest_stable_streak", 0))

        aperture_values = [
            float(record.get("entangler_aperture_after", record.get("wormhole_aperture", 0.0)))
            for record in telemetry_records
            if "entangler_aperture_after" in record or "wormhole_aperture" in record
        ]
        damping_values = [
            float(record.get("entangler_damping_after", record.get("damping", 0.0)))
            for record in telemetry_records
            if "entangler_damping_after" in record or "damping" in record
        ]
        phase_offset_values = [
            float(record.get("entangler_phase_after", record.get("phase_offset", 0.0)))
            for record in telemetry_records
            if "entangler_phase_after" in record or "phase_offset" in record
        ]
        coupling_strength_values = [
            max(
                float(record.get("entangler_strength", 0.0)),
                float(record.get("entanglement_strength", 0.0)),
                float(record.get("shared_flux_norm", 0.0)),
            )
            for record in telemetry_records
            if (
                "entangler_strength" in record
                or "entanglement_strength" in record
                or "shared_flux_norm" in record
            )
        ]
        aperture_mean = float(np.mean(aperture_values)) if aperture_values else 0.0
        damping_mean = float(np.mean(damping_values)) if damping_values else 0.0
        phase_offset_mean = float(np.mean(phase_offset_values)) if phase_offset_values else 0.0
        coupling_strength_mean = float(np.mean(coupling_strength_values)) if coupling_strength_values else 0.0

        synchrony_support: list[str] = []
        synchrony_risks: list[str] = []
        contradiction_signals: list[str] = []
        coupling_support: list[str] = []
        coupling_risks: list[str] = []

        if aperture_values and damping_values:
            if 0.18 <= aperture_mean <= 0.36 and 0.78 <= damping_mean <= 0.90:
                coupling_support.append("aperture_damping_permissive")
            elif aperture_mean < 0.18 or damping_mean > 0.90:
                coupling_risks.append("aperture_damping_restrictive")
            elif aperture_mean > 0.40 or damping_mean < 0.72:
                coupling_risks.append("aperture_damping_unstable")

        if phase_offset_values:
            if phase_offset_mean <= 0.20:
                coupling_support.append("phase_offset_aligned")
            elif phase_offset_mean >= 0.28:
                coupling_risks.append("phase_offset_misaligned")

        if coupling_strength_values:
            if coupling_strength_mean >= 0.90:
                coupling_support.append("shared_coupling_nontrivial")
            elif coupling_strength_mean <= 0.55:
                coupling_risks.append("shared_coupling_weak")

        coupling_support_score = len(coupling_support)
        coupling_risk_score = len(coupling_risks)
        if coupling_support_score >= (coupling_risk_score + 2):
            coupling_posture = "permissive"
        elif coupling_risk_score >= (coupling_support_score + 2):
            coupling_posture = "weak"
        else:
            coupling_posture = "strained"

        if coherence_mean >= 0.68:
            synchrony_support.append("coherence_mean_high")
        elif coherence_mean <= 0.60:
            synchrony_risks.append("coherence_mean_low")

        if coherence_delta >= 0.05:
            synchrony_support.append("coherence_improving")
        elif coherence_delta < 0.0:
            synchrony_risks.append("coherence_non_improving")

        if latest_status == "improving":
            synchrony_support.append("latest_status_improving")
        elif latest_status == "decaying":
            synchrony_risks.append("latest_status_decaying")

        if passed_count > 0 and block_rate < 0.60:
            synchrony_support.append("gate_eventually_passes")
        elif passed_count == 0 and block_rate >= 0.75:
            synchrony_risks.append("gate_persistently_blocked")

        if int(nudge.get("applied_count", 0)) > 0 and (
            positive_window_rate > 0.0 or stabilizer_entry_rate > 0.0
        ):
            synchrony_support.append("nudges_show_forward_response")
        elif int(nudge.get("applied_count", 0)) > 0 and positive_window_rate == 0.0:
            synchrony_risks.append("nudges_nonproductive")

        if longest_decay_streak >= 3:
            synchrony_risks.append("long_decay_streak")

        if near_pass_count > 0:
            contradiction_signals.append("near_pass_without_resolution")
        if int(gate.get("passed_but_nudge_blocked_count", 0)) > 0:
            contradiction_signals.append("passed_but_nudge_blocked")
        if coherence_delta > 0.0 and block_rate >= 0.75:
            contradiction_signals.append("coherence_improves_while_gate_blocks")
        if coupling_posture == "permissive" and block_rate >= 0.75:
            contradiction_signals.append("permissive_coupling_but_gate_blocks")

        if passed_count > 0 and (positive_window_rate > 0.0 or stabilizer_entry_rate > 0.0):
            boundary_state = "converting"
        elif near_pass_count > 0 or nudge_applied_count > 0 or passed_but_nudge_blocked_count > 0:
            if positive_window_rate == 0.0 and stabilizer_entry_rate == 0.0:
                boundary_state = "non_converting"
            else:
                boundary_state = "mixed_conversion"
        elif block_rate >= 0.75:
            boundary_state = "blocked"
        else:
            boundary_state = "clear"

        contradiction_level = "low"
        if len(contradiction_signals) >= 2:
            contradiction_level = "high"
        elif contradiction_signals:
            contradiction_level = "medium"

        synchrony_support_score = len(synchrony_support)
        synchrony_risk_score = len(synchrony_risks)
        if synchrony_support_score >= (synchrony_risk_score + 2):
            synchrony_label = "favorable"
        elif synchrony_risk_score >= (synchrony_support_score + 2):
            synchrony_label = "unfavorable"
        else:
            synchrony_label = "borderline"

        if synchrony_label == "favorable":
            synchrony_basis = "response_led"
        elif synchrony_label == "unfavorable" and coupling_posture in {"weak", "strained"}:
            synchrony_basis = "structure_led"
        elif synchrony_label == "unfavorable":
            synchrony_basis = "mixed"
        elif boundary_state in {"non_converting", "mixed_conversion"}:
            synchrony_basis = "boundary_led"
        elif coupling_posture == "weak":
            synchrony_basis = "structure_led"
        else:
            synchrony_basis = "mixed"

        evidence_signals: list[str] = []
        for signal in [*coupling_support, *synchrony_support, *synchrony_risks, *coupling_risks]:
            if signal not in evidence_signals:
                evidence_signals.append(signal)

        basin_support: list[str] = []
        basin_risks: list[str] = []

        if coherence_mean >= 0.70 and latest_status in {"stable", "improving"}:
            basin_support.append("coherence_holds")
        if transition_total <= 1:
            basin_support.append("low_mode_churn")
        if longest_improving_streak >= 2 or longest_stable_streak >= 2:
            basin_support.append("persistent_recovery_or_hold")
        if passed_count > 0 or positive_window_rate > 0.0:
            basin_support.append("recoverable_response_seen")

        if latest_status == "decaying":
            basin_risks.append("latest_status_decaying")
        if longest_decay_streak >= 2:
            basin_risks.append("decay_streak")
        if transition_total >= 2 and stabilizer_dwell_max <= 1:
            basin_risks.append("mode_churn")
        if block_rate >= 0.75 and near_pass_count > 0:
            basin_risks.append("near_pass_without_recovery")
        if coherence_delta <= 0.0 and block_rate >= 0.75:
            basin_risks.append("flat_or_negative_under_block")

        basin_support_score = len(basin_support)
        basin_risk_score = len(basin_risks)
        if basin_support_score >= (basin_risk_score + 2):
            basin_label = "broad"
        elif basin_risk_score >= (basin_support_score + 2):
            basin_label = "fragile"
        else:
            basin_label = "narrow"

        return {
            "tick_count": int(trend.get("tick_count", 0)),
            "coherence": trend,
            "hint_gate": gate,
            "nudge": nudge,
            "streaks": streaks,
            "mode_switching": switching,
            "synchrony_margin": {
                "label": synchrony_label,
                "basis": synchrony_basis,
                "coupling_posture": coupling_posture,
                "evidence_signals": evidence_signals,
                "contradiction_level": contradiction_level,
                "boundary_state": boundary_state,
                "support_score": synchrony_support_score,
                "risk_score": synchrony_risk_score,
                "coupling_support_signals": coupling_support,
                "coupling_risk_signals": coupling_risks,
                "support_signals": synchrony_support,
                "risk_signals": synchrony_risks,
                "contradiction_signals": contradiction_signals,
            },
            "basin_fragility": {
                "label": basin_label,
                "support_score": basin_support_score,
                "risk_score": basin_risk_score,
                "support_signals": basin_support,
                "risk_signals": basin_risks,
            },
        }

    def summarize_uncertainty_paper_recommendation(
        self, telemetry_records: list[dict[str, object]]
    ) -> dict[str, object]:
        proxies = self.summarize_paper_diagnostic_proxies(telemetry_records)
        if int(proxies.get("tick_count", 0)) == 0:
            return {"triggered": False, "reason": "no_pair_telemetry"}

        synchrony = dict(proxies.get("synchrony_margin", {}))
        basin = dict(proxies.get("basin_fragility", {}))
        gate = dict(proxies.get("hint_gate", {}))
        trend = dict(proxies.get("coherence", {}))
        switching = dict(proxies.get("mode_switching", {}))
        streaks = dict(proxies.get("streaks", {}))

        blocked_count = int(gate.get("blocked_count", 0))
        near_pass_count = int(gate.get("near_pass_count", 0))
        passed_but_nudge_blocked = int(gate.get("passed_but_nudge_blocked_count", 0))
        transition_total = int(switching.get("transition_total", 0))
        longest_decay_streak = int(streaks.get("longest_decay_streak", 0))
        coupling_posture = str(synchrony.get("coupling_posture", "unknown"))

        stable_uncertainty = bool(
            blocked_count >= 2
            or near_pass_count > 0
            or passed_but_nudge_blocked > 0
            or transition_total >= 2
            or longest_decay_streak >= 2
        )
        unresolved_synchrony = str(synchrony.get("label", "unknown")) in {"borderline", "unfavorable"}
        unresolved_basin = str(basin.get("label", "unknown")) in {"narrow", "fragile"}
        triggered = bool(stable_uncertainty and (unresolved_synchrony or unresolved_basin))
        if not triggered:
            return {
                "triggered": False,
                "reason": "no_persistent_decision_relevant_uncertainty",
                "synchrony_margin": str(synchrony.get("label", "unknown")),
                "basin_fragility": str(basin.get("label", "unknown")),
            }

        if unresolved_synchrony:
            if str(synchrony.get("label", "unknown")) == "unfavorable" and coupling_posture == "permissive":
                intervention_class = "diagnostics"
                desired_paper_role = (
                    "one paper on synchronization feasibility diagnostics for coupled nonlinear systems"
                )
            elif coupling_posture == "weak":
                intervention_class = "topology design"
                desired_paper_role = (
                    "one paper on topology-aware synchronization feasibility or controllability"
                )
            elif near_pass_count > 0 or passed_but_nudge_blocked > 0:
                intervention_class = "control policy"
                desired_paper_role = "one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence"
            else:
                intervention_class = "diagnostics"
                desired_paper_role = (
                    "one paper on synchronization feasibility diagnostics for coupled nonlinear systems"
                )
            uncertainty_summary = (
                "The pair shows unresolved synchrony uncertainty: local evidence is not cleanly separating weak hints "
                "from structural difficulty in reaching or sustaining phase alignment."
            )
            if coupling_posture == "permissive":
                local_hypotheses = [
                    "The hint gate may be conservative relative to the actual synchrony boundary.",
                    "The pair may still be close to a favorable synchronizable region even though local control evidence stays blocked.",
                ]
                unresolved = "Current telemetry shows permissive coupling posture, but does not yet separate conservative gating from genuine synchrony-boundary difficulty."
            elif coupling_posture == "weak":
                local_hypotheses = [
                    "The pair may be operating outside a favorable synchronizable region because coupling posture is too weak or misaligned.",
                    "Local control thresholds may be secondary to the present coupling and phase geometry.",
                ]
                unresolved = "Current telemetry points to structural coupling weakness, but does not yet show which topology or posture change would recover synchronizability."
            else:
                local_hypotheses = [
                    "The hint gate may be conservative relative to the actual synchrony boundary.",
                    "The pair may be operating outside a favorable synchronizable region.",
                ]
                unresolved = "Current telemetry does not yet separate weak local evidence from topology-level synchrony limits."
            telemetry_fields = [
                "phase_coherence",
                "entangler_coherence_delta",
                "entangler_coherence_status",
                "wormhole_aperture",
                "damping",
                "phase_offset",
                "entanglement_strength",
                "entangler_hint_gate_reason",
                "entangler_hint_gate_passed",
                "entangler_nudge_applied",
            ]
            replay_signals = [
                "coherence trend",
                "coupling posture summary",
                "hint gate summary",
                "nudge outcome summary",
            ]
            regimes = [
                str(synchrony.get("label", "unknown")),
                f"coupling:{coupling_posture}",
                "blocked-gate" if blocked_count > 0 else "gate-clear",
            ]
            if coupling_posture == "weak":
                novelty_relative = (
                    "Extend beyond the current working_mind synchrony and basin foundations with a more specific topology-aware "
                    "synchronization or controllability reference."
                )
            else:
                novelty_relative = (
                    "Extend beyond the current working_mind synchrony and basin foundations with a more specific controllability or "
                    "topology-aware synchronization reference."
                )
            stop_condition = "Stop if synchrony_margin becomes favorable across nearby variants or if local diagnostics clearly explain the blocked regime."
        else:
            intervention_class = "experiment design"
            desired_paper_role = "one paper on basin stability, perturbation resilience, or recovery geometry"
            uncertainty_summary = (
                "The pair shows unresolved basin uncertainty: the regime can look locally calm, but current evidence does not show whether that "
                "calm state is broadly recoverable or only narrowly stable."
            )
            local_hypotheses = [
                "The current calm regime may be a genuinely broad holding basin.",
                "The current calm regime may be a narrow basin that does not generalize across nearby variation.",
            ]
            unresolved = "Current replay and sweep evidence does not yet cleanly distinguish durable recovery from brittle local calm."
            telemetry_fields = [
                "phase_coherence",
                "entangler_mode",
                "entangler_transition_reason",
                "phonon_hint_pair_stability",
                "phonon_hint_pair_decay",
                "phonon_hint_amplitude_trend",
            ]
            replay_signals = [
                "mode switching",
                "status streaks",
                "nearby-seed persistence",
            ]
            regimes = [
                str(basin.get("label", "unknown")),
                str(trend.get("latest_status", "unknown")),
            ]
            novelty_relative = "Extend beyond the current working_mind basin framing with a source that sharpens perturbation resilience or neighborhood persistence."
            stop_condition = "Stop if basin_fragility becomes broad across adjacent variants or if replay evidence clearly shows regime persistence."

        return {
            "triggered": True,
            "uncertainty_summary": uncertainty_summary,
            "telemetry_fields": telemetry_fields,
            "replay_signals": replay_signals,
            "regimes": regimes,
            "local_hypotheses": local_hypotheses,
            "unresolved": unresolved,
            "intervention_class": intervention_class,
            "desired_paper_role": desired_paper_role,
            "preferred_search_envelope": "one paper",
            "novelty_relative": novelty_relative,
            "stop_condition": stop_condition,
            "synchrony_margin": str(synchrony.get("label", "unknown")),
            "coupling_posture": coupling_posture,
            "basin_fragility": str(basin.get("label", "unknown")),
        }

    def render_paper_diagnostic_summary(self, pair_id: str) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_paper_diagnostic_proxies(telemetry_records)
        if int(summary.get("tick_count", 0)) == 0:
            return "No paper-diagnostic telemetry available for replay."

        synchrony = dict(summary.get("synchrony_margin", {}))
        basin = dict(summary.get("basin_fragility", {}))
        return (
            f"Paper diagnostics over {int(summary.get('tick_count', 0))} ticks: "
            f"synchrony_margin={synchrony.get('label', 'unknown')} "
            f"(basis={synchrony.get('basis', 'unknown')}, coupling={synchrony.get('coupling_posture', 'unknown')}, boundary={synchrony.get('boundary_state', 'unknown')}, "
            f"contradiction={synchrony.get('contradiction_level', 'unknown')}, "
            f"evidence={self._render_signal_list(synchrony.get('evidence_signals', []), empty_label='none')}; "
            f"support={int(synchrony.get('support_score', 0))}, risk={int(synchrony.get('risk_score', 0))}, "
            f"signals={self._render_signal_list(synchrony.get('support_signals', []), empty_label='none')} | "
            f"risks={self._render_signal_list(synchrony.get('risk_signals', []), empty_label='none')} | "
            f"coupling_support={self._render_signal_list(synchrony.get('coupling_support_signals', []), empty_label='none')} | "
            f"coupling_risks={self._render_signal_list(synchrony.get('coupling_risk_signals', []), empty_label='none')} | "
            f"contradictions={self._render_signal_list(synchrony.get('contradiction_signals', []), empty_label='none')}), "
            f"basin_fragility={basin.get('label', 'unknown')} "
            f"(support={int(basin.get('support_score', 0))}, risk={int(basin.get('risk_score', 0))}, "
            f"signals={self._render_signal_list(basin.get('support_signals', []), empty_label='none')} | "
            f"risks={self._render_signal_list(basin.get('risk_signals', []), empty_label='none')})"
        )

    def render_uncertainty_paper_recommendation(self, pair_id: str) -> str:
        telemetry_records = self.load_pair_telemetry_records(pair_id=pair_id)
        summary = self.summarize_uncertainty_paper_recommendation(telemetry_records)
        if not bool(summary.get("triggered", False)):
            return "No persistent paper-recommendation uncertainty detected."

        lines = [
            "UNCERTAINTY TO PAPER RECOMMENDATION",
            "",
            "Uncertainty summary:",
            f"- current bottleneck: {summary.get('uncertainty_summary', '')}",
            f"- why current repo knowledge is still insufficient: {summary.get('unresolved', '')}",
            f"- why this is stable uncertainty rather than a one-off failure: synchrony={summary.get('synchrony_margin', 'unknown')}, coupling={summary.get('coupling_posture', 'unknown')}, basin={summary.get('basin_fragility', 'unknown')}",
            "",
            "Observed signals:",
            f"- key telemetry fields: {', '.join(str(value) for value in summary.get('telemetry_fields', []))}",
            f"- key replay or sweep signals: {', '.join(str(value) for value in summary.get('replay_signals', []))}",
            f"- recent regimes or labels involved: {', '.join(str(value) for value in summary.get('regimes', []))}",
            "",
            "Current local explanations:",
            f"- working hypothesis 1: {summary.get('local_hypotheses', [''])[0] if summary.get('local_hypotheses') else ''}",
            f"- working hypothesis 2: {summary.get('local_hypotheses', ['', ''])[1] if len(summary.get('local_hypotheses', [])) > 1 else ''}",
            f"- what remains unresolved or conflicting: {summary.get('unresolved', '')}",
            "",
            "Outside help needed:",
            f"- intervention class: {summary.get('intervention_class', 'diagnostics')}",
            f"- desired paper role: {summary.get('desired_paper_role', '')}",
            f"- preferred search envelope: {summary.get('preferred_search_envelope', 'one paper')}",
            "",
            "Search guardrails:",
            "- avoid broad literature survey: yes",
            f"- novelty relative to current working_mind: {summary.get('novelty_relative', '')}",
            f"- stop condition for searching: {summary.get('stop_condition', '')}",
        ]
        return "\n".join(lines)

    def render_pair_section(
        self,
        *,
        pair_id: str,
        section: str,
        top_n: int = 10,
        hint_gate_policy: object | None = None,
    ) -> str:
        normalized = str(section or "full").strip().lower()
        if normalized == "full":
            return self.replay(pair_id=pair_id, top_n=top_n, hint_gate_policy=hint_gate_policy)
        if normalized == "paper":
            lines = [
                f"Pair id: {pair_id}",
                "",
                "Paper diagnostic summary:",
                self.render_paper_diagnostic_summary(pair_id=pair_id),
            ]
            return "\n".join(lines)
        if normalized == "uncertainty":
            lines = [
                f"Pair id: {pair_id}",
                "",
                "Uncertainty paper recommendation:",
                self.render_uncertainty_paper_recommendation(pair_id=pair_id),
            ]
            return "\n".join(lines)
        raise ValueError(f"Unsupported pair section: {section}")

    def render(self, records: list[dict[str, object]], top_n: int = 10, width: int = 24) -> str:
        if not records:
            return "No hippocampal burst records available."

        ordered = sorted(records, key=lambda record: float(record.get("h_total", 0.0)), reverse=True)[:top_n]
        max_h = max(float(record.get("h_total", 0.0)) for record in ordered) or 1.0
        pair_mode = any(record.get("pair_id") for record in ordered)
        lines = []
        for record in ordered:
            node_id = str(record.get("node_id", "unknown"))
            h_total = float(record.get("h_total", 0.0))
            dominant_giant = self._normalize_giant_label(record.get("dominant_giant"))
            density_contrib = float(record.get("density_contrib", 0.0))
            shear_contrib = float(record.get("shear_contrib", 0.0))
            vorticity_contrib = float(record.get("vorticity_contrib", 0.0))
            bar_length = max(1, int(round((h_total / max_h) * width)))
            label = node_id
            if pair_mode:
                manifold_label = str(record.get("source_manifold_id", "pair"))
                bilateral_marker = "*" if bool(record.get("bilateral_burst", False)) else " "
                label = f"{manifold_label}:{node_id}{bilateral_marker}"
            lines.append(
                f"{label:>18} | {'#' * bar_length:<{width}} | H={h_total:0.3f} | {dominant_giant}"
                f" | d={density_contrib:0.2f} s={shear_contrib:0.2f} v={vorticity_contrib:0.2f}"
            )
        return "\n".join(lines)

    def replay(
        self,
        path: Path | None = None,
        pair_id: str | None = None,
        top_n: int = 10,
        hint_gate_policy: object | None = None,
    ) -> str:
        if pair_id is not None:
            records = self.load_burst(path) if path is not None else self.load_long_term_records()
            records = self.filter_pair_bursts(records, pair_id)
            summary = self.summarize_pair(records, pair_id)
            confidence_threshold = float(getattr(hint_gate_policy, "confidence_threshold", 0.55))
            reliability_threshold = float(getattr(hint_gate_policy, "reliability_threshold", 0.60))
            min_samples = int(getattr(hint_gate_policy, "min_samples", 3))
            require_armed_status = bool(getattr(hint_gate_policy, "require_armed_status", True))
            lines = [
                f"Pair id: {summary['pair_id']}",
                f"Burst count: {summary['total_bursts']}",
                f"Peak H-score: {summary['max_h']:.3f}",
                f"Average H-score: {summary['avg_h']:.3f}",
                f"Average adaptive tau: {summary['avg_tau']:.3f}",
                f"Bilateral bursts: {summary['bilateral_bursts']}",
                f"Bilateral ratio: {summary['bilateral_ratio']:.3f}",
                f"Source manifolds: {summary['source_manifolds']}",
                f"Cross-domain giants: {summary['cross_domain_giants']}",
                "",
                self.render(records, top_n=top_n),
                "",
                "Entangler control summary:",
                self.render_coherence_summary(pair_id=pair_id),
                self.render_mode_switching_summary(pair_id=pair_id),
                "",
                "Local phonon summary:",
                self.render_local_phonon_summary(pair_id=pair_id),
                "",
                "Advisory hint summary:",
                self.render_advisory_hint_summary(pair_id=pair_id),
                "",
                "Predictive phonon summary:",
                self.render_predictive_phonon_summary(pair_id=pair_id),
                "",
                "Hint reliability summary:",
                self.render_hint_reliability_summary(pair_id=pair_id),
                "",
                "Hint calibration summary:",
                self.render_hint_calibration_summary(pair_id=pair_id),
                "",
                "Hint gate summary:",
                self.render_hint_gate_decision_summary(
                    pair_id=pair_id,
                    confidence_threshold=confidence_threshold,
                    reliability_threshold=reliability_threshold,
                    min_samples=min_samples,
                    require_armed_status=require_armed_status,
                ),
                "",
                "Nudge outcome summary:",
                self.render_nudge_outcome_summary(pair_id=pair_id),
                "",
                "Wormhole weight summary:",
                self.render_weight_drift_summary(pair_id=pair_id, top_n=min(top_n, 4)),
                "",
                "Paper diagnostic summary:",
                self.render_paper_diagnostic_summary(pair_id=pair_id),
                "",
                "Uncertainty paper recommendation:",
                self.render_uncertainty_paper_recommendation(pair_id=pair_id),
            ]
            return "\n".join(lines)

        records = self.load_burst(path)
        summary = self.summarize(records)
        lines = [
            f"Burst count: {summary['total_bursts']}",
            f"Peak H-score: {summary['max_h']:.3f}",
            f"Average H-score: {summary['avg_h']:.3f}",
            f"Average adaptive tau: {summary['avg_tau']:.3f}",
            f"Dominant giants: {summary['dominant_giants']}",
            "",
            self.render(records, top_n=top_n),
        ]
        return "\n".join(lines)

    def _latest_burst_path(self) -> Path:
        burst_files = self.list_burst_files()
        if not burst_files:
            raise FileNotFoundError(f"No hippocampal burst files found in {self.working_dir}")
        return burst_files[-1]

    def _normalize_giant_label(self, label: object) -> str:
        normalized = str(label or "Ambient Basin")
        if normalized == "None":
            return "Ambient Basin"
        return normalized

    def _accumulate_predictive_stat(
        self,
        stat_map: dict[str, dict[str, float]],
        key: str,
        future_delta: float,
        recovery: float,
        stabilizer_entry: float,
    ) -> None:
        bucket = stat_map.setdefault(
            str(key),
            {"count": 0.0, "future_delta_sum": 0.0, "recovery_sum": 0.0, "stabilizer_entry_sum": 0.0},
        )
        bucket["count"] += 1.0
        bucket["future_delta_sum"] += float(future_delta)
        bucket["recovery_sum"] += float(recovery)
        bucket["stabilizer_entry_sum"] += float(stabilizer_entry)

    def _finalize_predictive_stats(
        self, stat_map: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        finalized: dict[str, dict[str, float]] = {}
        for key, bucket in stat_map.items():
            count = max(float(bucket.get("count", 0.0)), 1.0)
            finalized[str(key)] = {
                "count": int(bucket.get("count", 0.0)),
                "mean_future_delta": float(bucket.get("future_delta_sum", 0.0) / count),
                "recovery_rate": float(bucket.get("recovery_sum", 0.0) / count),
                "stabilizer_entry_rate": float(bucket.get("stabilizer_entry_sum", 0.0) / count),
            }
        return dict(
            sorted(
                finalized.items(),
                key=lambda item: (
                    -float(item[1].get("mean_future_delta", 0.0)),
                    -float(item[1].get("recovery_rate", 0.0)),
                    str(item[0]),
                ),
            )
        )

    def _score_reliability_group(
        self,
        stats: dict[str, dict[str, float]],
        *,
        min_samples: int,
        recovery_weight: float,
        stabilizer_weight: float,
        delta_weight: float,
        delta_normalizer: float,
    ) -> dict[str, dict[str, float | bool | int | str]]:
        scored: dict[str, dict[str, float | bool | int | str]] = {}
        for key, summary in dict(stats).items():
            sample_count = int(summary.get("count", 0))
            recovery_rate = float(summary.get("recovery_rate", 0.0))
            stabilizer_entry_rate = float(summary.get("stabilizer_entry_rate", 0.0))
            mean_future_delta = float(summary.get("mean_future_delta", 0.0))
            sample_factor = float(np.clip(sample_count / max(min_samples, 1), 0.0, 1.0))
            delta_signal = float(np.clip(mean_future_delta / max(delta_normalizer, 1e-6), 0.0, 1.0))
            reliability_score = float(
                np.clip(
                    sample_factor
                    * (
                        (recovery_weight * recovery_rate)
                        + (stabilizer_weight * stabilizer_entry_rate)
                        + (delta_weight * delta_signal)
                    ),
                    0.0,
                    1.0,
                )
            )
            provisional = bool(sample_count < max(min_samples, 1))
            scored[str(key)] = {
                "sample_count": sample_count,
                "recovery_rate": recovery_rate,
                "stabilizer_entry_rate": stabilizer_entry_rate,
                "mean_future_delta": mean_future_delta,
                "reliability_score": reliability_score,
                "sample_factor": sample_factor,
                "provisional": provisional,
                "evidence_status": "provisional" if provisional else "established",
            }

        return dict(
            sorted(
                scored.items(),
                key=lambda item: (
                    -float(item[1].get("reliability_score", 0.0)),
                    -int(item[1].get("sample_count", 0)),
                    str(item[0]),
                ),
            )
        )

    def _build_calibration_group(
        self,
        hint_records: list[dict[str, object]],
        *,
        key_name: str,
        reliability_map: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        for record in hint_records:
            key = str(record.get(key_name, "none"))
            grouped.setdefault(key, []).append(record)

        calibration: dict[str, dict[str, object]] = {}
        for key, records in grouped.items():
            confidences = [float(record.get("phonon_hint_confidence", 0.0)) for record in records]
            ages = [int(record.get("phonon_hint_age_ticks", 0)) for record in records]
            reliability = dict(reliability_map.get(key, {}))
            reliability_score = float(reliability.get("reliability_score", 0.0))
            sample_count = int(reliability.get("sample_count", 0))
            calibration_gap = float(np.mean(confidences) - reliability_score)
            provisional = bool(reliability.get("provisional", sample_count == 0))
            if calibration_gap > 0.10:
                calibration_state = "overconfident"
            elif calibration_gap < -0.10:
                calibration_state = "underconfident"
            else:
                calibration_state = "aligned"

            calibration[str(key)] = {
                "mean_confidence": float(np.mean(confidences)),
                "confidence_range": (float(min(confidences)), float(max(confidences))),
                "mean_age_ticks": float(np.mean(ages)),
                "reliability_score": reliability_score,
                "sample_count": sample_count,
                "calibration_gap": calibration_gap,
                "provisional": provisional,
                "calibration_state": calibration_state,
            }

        return dict(
            sorted(
                calibration.items(),
                key=lambda item: (
                    abs(float(item[1].get("calibration_gap", 0.0))),
                    -int(item[1].get("sample_count", 0)),
                    str(item[0]),
                ),
            )
        )

    def _render_predictive_group(self, stats: dict[str, dict[str, float]], label: str) -> str:
        if not stats:
            return f"no {label}"
        parts = []
        for key, summary in stats.items():
            parts.append(
                f"{key} d={float(summary.get('mean_future_delta', 0.0)):+.3f}"
                f" rec={float(summary.get('recovery_rate', 0.0)):.2f}"
                f" stab={float(summary.get('stabilizer_entry_rate', 0.0)):.2f}"
                f" n={int(summary.get('count', 0))}"
            )
        return "; ".join(parts)

    def _render_reliability_group(self, stats: dict[str, dict[str, object]]) -> str:
        if not stats:
            return "none"
        parts = []
        for key, summary in stats.items():
            status = str(summary.get("evidence_status", "provisional"))
            parts.append(
                f"{key} score={float(summary.get('reliability_score', 0.0)):.2f}"
                f" rec={float(summary.get('recovery_rate', 0.0)):.2f}"
                f" stab={float(summary.get('stabilizer_entry_rate', 0.0)):.2f}"
                f" d={float(summary.get('mean_future_delta', 0.0)):+.3f}"
                f" n={int(summary.get('sample_count', 0))}"
                f" {status}"
            )
        return "; ".join(parts)

    def _render_calibration_group(self, stats: dict[str, dict[str, object]]) -> str:
        if not stats:
            return "none"
        parts = []
        for key, summary in stats.items():
            provisional = " provisional" if bool(summary.get("provisional", True)) else ""
            parts.append(
                f"{key} conf={float(summary.get('mean_confidence', 0.0)):.2f}"
                f" rel={float(summary.get('reliability_score', 0.0)):.2f}"
                f" gap={float(summary.get('calibration_gap', 0.0)):+.2f}"
                f" n={int(summary.get('sample_count', 0))}"
                f" {summary.get('calibration_state', 'aligned')}{provisional}"
            )
        return "; ".join(parts)

    def _render_count_group(
        self,
        counts: dict[str, object],
        *,
        empty_label: str = "none",
        limit: int = 4,
    ) -> str:
        if not counts:
            return empty_label
        parts: list[str] = []
        for index, (key, value) in enumerate(counts.items()):
            if index >= max(int(limit), 1):
                break
            parts.append(f"{key}={int(value)}")
        return ", ".join(parts) if parts else empty_label

    def _render_signal_list(self, values: object, *, empty_label: str = "none", limit: int = 4) -> str:
        if not values:
            return empty_label
        parts: list[str] = []
        for index, value in enumerate(list(values)):
            if index >= max(int(limit), 1):
                break
            parts.append(str(value))
        return ", ".join(parts) if parts else empty_label


def main() -> None:
    parser = argparse.ArgumentParser(description="Render hippocampal burst archives.")
    parser.add_argument(
        "--working-dir", type=Path, default=None, help="Override the hippocampal working directory."
    )
    parser.add_argument(
        "--path", type=Path, default=None, help="Replay a specific hippocampal burst snapshot JSON file."
    )
    parser.add_argument(
        "--pair-id",
        type=str,
        default=None,
        help="Replay pair-aware burst history for a specific entangled pair.",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Maximum number of burst rows to render.")
    parser.add_argument(
        "--section",
        choices=["full", "paper", "uncertainty"],
        default="full",
        help="When pair replay is requested, render the full replay, only the paper diagnostic section, or only the uncertainty recommendation.",
    )
    args = parser.parse_args()

    replay = HippocampalReplay(working_dir=args.working_dir)
    if args.pair_id is not None:
        print(replay.render_pair_section(pair_id=args.pair_id, section=args.section, top_n=args.top_n))
        return
    print(replay.replay(path=args.path, pair_id=args.pair_id, top_n=args.top_n))


if __name__ == "__main__":
    main()
