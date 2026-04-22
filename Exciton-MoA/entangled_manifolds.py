# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from entangler import EntanglerGiant
from excitons import ExcitonEngine
from hippocampal import HippocampalPairTransducer, HippocampalTransducer
from hippocampal_replay import HippocampalReplay
from latent_mediator import LatentMediator
from shared_mediator import SharedMediator
from telemetry import OntologicalOrchestrator
from telemetry_panel import TelemetryPanel
from transducer import StatisticalPrism


PAIR_RUNTIME_PRESETS: Dict[str, Dict[str, object]] = {
    "best-pocket": {
        "cycles": 12,
        "seed": 149,
        "embedding_a_loc": 0.50,
        "embedding_b_loc": 0.57,
        "embedding_scale": 0.08,
        "embedding_drift": 0.06,
    }
}


class PairRuntimeArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pair_base_defaults: Dict[str, object] = {}

    def remember_base_defaults(self) -> None:
        self._pair_base_defaults = {
            action.dest: action.default
            for action in self._actions
            if action.dest and action.dest != argparse.SUPPRESS
        }

    def parse_known_args(self, args=None, namespace=None):
        if self._pair_base_defaults:
            self.set_defaults(**self._pair_base_defaults)
        preset_parser = argparse.ArgumentParser(add_help=False)
        preset_parser.add_argument("--runtime-preset", choices=sorted(PAIR_RUNTIME_PRESETS), default=None)
        preset_args, _ = preset_parser.parse_known_args(args)
        if preset_args.runtime_preset:
            self.set_defaults(**PAIR_RUNTIME_PRESETS[preset_args.runtime_preset])
        return super().parse_known_args(args, namespace)


@dataclass
class HintGatingPolicy:
    enabled: bool = False
    require_armed_status: bool = True
    confidence_threshold: float = 0.55
    reliability_threshold: float = 0.60
    max_age_ticks: int = 2
    min_samples: int = 3
    forward_window: int = 2
    enable_bounded_nudges: bool = False
    nudge_aperture_max_step: float = 0.04
    nudge_damping_max_step: float = 0.025
    nudge_phase_max_step: float = 0.08
    nudge_reliability_floor: float = 0.75
    nudge_requires_stability: bool = True
    nudge_stability_window: int = 4
    observe_nudge_feedback_scale: float = 0.35
    enable_near_pass_maturity_nudges: bool = False
    near_pass_confidence_gap_max: float = 0.10
    near_pass_reliability_gap_max: float = 0.12
    near_pass_sample_gap_max: int = 0
    near_pass_observe_feedback_scale: float = 0.20
    enable_negative_collapse_stabilize: bool = False


@dataclass
class EntanglementControls:
    wormhole_count: int = 12
    aperture: float = 0.25
    damping: float = 0.85
    phase_offset: float = 0.15
    entangler_mode: str = "active"
    min_mode_switch_samples: int = 3
    stabilizer_enter_decay_streak: int = 2
    stabilizer_exit_improving_streak: int = 3
    stabilizer_min_dwell_ticks: int = 2
    max_history: int = 16
    seed: int = 17
    hint_gate_policy: HintGatingPolicy = field(default_factory=HintGatingPolicy)


@dataclass(frozen=True)
class PairSweepVariant:
    variant_id: str
    cycle_count: int
    seed: int
    embedding_a_loc: float
    embedding_b_loc: float
    embedding_scale: float
    embedding_drift: float
    working_dir: Path


@dataclass(frozen=True)
class PhononBundle:
    phonon_id: str
    pair_clock: int
    source_tier: str
    carrier_giant: str
    source_nodes: Tuple[str, ...]
    mode: str
    state_vector: Tuple[float, float, float]
    amplitude: float
    phase_coherence: float
    decay_rate: float
    confidence: float
    entropy: float
    predicted_next_mode: str
    wormhole_entry_nodes: Tuple[str, ...]
    wormhole_exit_nodes: Tuple[str, ...]
    weight_delta_map: Dict[str, float]
    coherence_signature: Dict[str, object]


class EntangledSOLPair:
    def __init__(
        self,
        config_a: Optional[BlankManifoldConfig] = None,
        config_b: Optional[BlankManifoldConfig] = None,
        manifold_ids: Tuple[str, str] = ("primary", "secondary"),
        pair_id: Optional[str] = None,
        controls: Optional[EntanglementControls] = None,
        working_dir: Optional[Path] = None,
        telemetry_panel: Optional[TelemetryPanel] = None,
    ):
        self.controls = controls or EntanglementControls()
        self.manifold_ids = manifold_ids
        self.pair_id = pair_id or f"{manifold_ids[0]}-{manifold_ids[1]}"
        self.working_dir = Path(working_dir) if working_dir is not None else Path(__file__).resolve().parent / "working_data"
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.rng = np.random.default_rng(self.controls.seed)
        manifold_seed_a = int(self.rng.integers(0, np.iinfo(np.int64).max))
        manifold_seed_b = int(self.rng.integers(0, np.iinfo(np.int64).max))

        self.manifold_a = BlankManifoldCore(config_a or BlankManifoldConfig(), seed=manifold_seed_a)
        self.manifold_a.generate_manifold()
        self.manifold_b = BlankManifoldCore(config_b or BlankManifoldConfig(), seed=manifold_seed_b)
        self.manifold_b.generate_manifold()

        self.telemetry_panel = telemetry_panel or TelemetryPanel(working_dir=self.working_dir)

        self.mediator_a = LatentMediator(
            self.manifold_a,
            state_path=self.working_dir / f"latent_mediator_state_{self.manifold_ids[0]}.json",
        )
        self.mediator_b = LatentMediator(
            self.manifold_b,
            state_path=self.working_dir / f"latent_mediator_state_{self.manifold_ids[1]}.json",
        )
        self.shared_mediator = SharedMediator(
            pair_id=self.pair_id,
            manifold_ids=self.manifold_ids,
            state_path=self.working_dir / f"shared_entanglement_locus_{self.pair_id}.json",
        )
        self.entangler = EntanglerGiant()

        self.prism_a = StatisticalPrism(self.manifold_a)
        self.prism_b = StatisticalPrism(self.manifold_b)
        self.excitons_a = ExcitonEngine(self.manifold_a, mediator=self.mediator_a)
        self.excitons_b = ExcitonEngine(self.manifold_b, mediator=self.mediator_b)

        self.transducer_a = HippocampalTransducer(output_dir=self.working_dir / self.manifold_ids[0])
        self.transducer_b = HippocampalTransducer(output_dir=self.working_dir / self.manifold_ids[1])
        self.pair_transducer = HippocampalPairTransducer(
            self.transducer_a,
            self.transducer_b,
            pair_id=self.pair_id,
            manifold_ids=self.manifold_ids,
            wormhole_nodes=self.wormhole_nodes if hasattr(self, "wormhole_nodes") else None,
        )
        self.orchestrator_a = OntologicalOrchestrator(
            self.manifold_a,
            mediator=self.mediator_a,
            telemetry_panel=self.telemetry_panel,
            manifold_id=self.manifold_ids[0],
        )
        self.orchestrator_b = OntologicalOrchestrator(
            self.manifold_b,
            mediator=self.mediator_b,
            telemetry_panel=self.telemetry_panel,
            manifold_id=self.manifold_ids[1],
        )

        self.wormhole_nodes = self._select_wormhole_nodes(self.controls.wormhole_count)
        self.pair_transducer.wormhole_nodes = list(self.wormhole_nodes)
        self.shared_flux = np.zeros(3, dtype=float)
        self.shared_flux_history: List[np.ndarray] = []
        self.wormhole_weight_map: Dict[str, float] = {node_id: 1.0 for node_id in self.wormhole_nodes}
        self.wormhole_weight_delta_history: List[Dict[str, float]] = []
        self.coherence_history: List[float] = []
        self.control_delta_history: List[Dict[str, float]] = []
        self.phonon_bundles: List[PhononBundle] = []
        self.local_phonon_bundles: List[PhononBundle] = []
        self.phonon_control_hints: List[Dict[str, object]] = []
        self.tick_trace_history: List[Dict[str, object]] = []
        self.last_pair_metrics: Dict[str, object] = {}
        self._mode_decay_streak = 0
        self._mode_improving_streak = 0
        self._stabilizer_dwell_ticks = 0
        self._last_mode_transition: Dict[str, object] = self._build_mode_transition(changed=False)

    def tick(self, embedding_a: Optional[np.ndarray] = None, embedding_b: Optional[np.ndarray] = None) -> Dict[str, object]:
        embedding_a = self._coerce_embedding(embedding_a, loc=0.50)
        embedding_b = self._coerce_embedding(embedding_b, loc=0.55)

        target_a = self.prism_a.global_resonance_broadcast(embedding_a)
        target_b = self.prism_b.global_resonance_broadcast(embedding_b)

        self.excitons_a.ignite_excitons(target_a)
        self.excitons_b.ignite_excitons(target_b)
        local_tick_hint = len(self.shared_flux_history) + 1
        self._record_local_phonon_bundle(
            self._build_local_phonon_bundle(
                manifold=self.manifold_a,
                manifold_id=self.manifold_ids[0],
                source_tier="local_post_giant",
                clock_hint=local_tick_hint,
                phase_coherence_hint=0.0,
            )
        )
        self._record_local_phonon_bundle(
            self._build_local_phonon_bundle(
                manifold=self.manifold_b,
                manifold_id=self.manifold_ids[1],
                source_tier="local_post_giant",
                clock_hint=local_tick_hint,
                phase_coherence_hint=0.0,
            )
        )

        previous_shared_flux = np.asarray(self.shared_flux, dtype=float).copy()
        signature_a = self.prism_a.sample_wormhole_signature(self.wormhole_nodes)
        signature_b = self.prism_b.sample_wormhole_signature(self.wormhole_nodes)
        self.shared_flux = self._update_shared_flux(signature_a, signature_b)
        self.shared_flux_history.append(self.shared_flux.copy())
        if len(self.shared_flux_history) > self.controls.max_history:
            self.shared_flux_history = self.shared_flux_history[-self.controls.max_history :]

        injection_scale = max((self.controls.aperture * (1.0 - self.controls.damping)) + 0.02, 0.02)
        pre_injection_a = self._capture_wormhole_snapshot(self.manifold_a)
        pre_injection_b = self._capture_wormhole_snapshot(self.manifold_b)
        self.excitons_a.inject_entangled_flux(
            self.wormhole_nodes,
            self.shared_flux,
            injection_scale=injection_scale,
            per_node_scale=self.wormhole_weight_map,
        )
        self.excitons_b.inject_entangled_flux(
            self.wormhole_nodes,
            self.shared_flux,
            injection_scale=injection_scale,
            per_node_scale=self.wormhole_weight_map,
        )
        injection_phase_coherence = self._cosine_similarity(signature_a, signature_b)
        dominant_injection_channel = self._dominant_channel_from_vector(self.shared_flux)
        self._record_local_phonon_bundle(
            self._build_local_phonon_bundle(
                manifold=self.manifold_a,
                manifold_id=self.manifold_ids[0],
                source_tier="local_post_injection",
                clock_hint=local_tick_hint,
                phase_coherence_hint=injection_phase_coherence,
                baseline_snapshot=pre_injection_a,
                dominant_channel_hint=dominant_injection_channel,
            )
        )
        self._record_local_phonon_bundle(
            self._build_local_phonon_bundle(
                manifold=self.manifold_b,
                manifold_id=self.manifold_ids[1],
                source_tier="local_post_injection",
                clock_hint=local_tick_hint,
                phase_coherence_hint=injection_phase_coherence,
                baseline_snapshot=pre_injection_b,
                dominant_channel_hint=dominant_injection_channel,
            )
        )

        bursts_a = self.orchestrator_a.scan_manifold()
        bursts_b = self.orchestrator_b.scan_manifold()
        pair_metrics = self._build_pair_metrics(bursts_a, bursts_b, signature_a, signature_b)
        pair_metrics["recent_phase_coherence"] = list(self.coherence_history[-4:])
        pair_metrics["recent_control_deltas"] = list(self.control_delta_history[-4:])
        pair_metrics["entangler_mode"] = str(self.controls.entangler_mode)
        shared_locus = self.shared_mediator.publish_pair_state(
            shared_flux=self.shared_flux,
            phase_coherence=float(pair_metrics["phase_coherence"]),
            wormhole_nodes=self.wormhole_nodes,
            bilateral_node_ids=pair_metrics["bilateral_node_ids"],
            top_events=pair_metrics["top_events"],
            cross_domain_giant="Entanglement Locus",
            local_consensus=self._collect_wormhole_consensus(),
            pair_metadata=pair_metrics,
        )
        replay = HippocampalReplay(working_dir=self.working_dir)
        forward_window = max(int(getattr(self.controls.hint_gate_policy, "forward_window", 2)), 1)
        min_samples = max(int(getattr(self.controls.hint_gate_policy, "min_samples", 3)), 1)
        predictive_summary = replay.summarize_predictive_phonon_correlations(
            replay.load_pair_telemetry_records(pair_id=self.pair_id),
            forward_window=forward_window,
        )
        phonon_hint_reliability = replay.score_hint_reliability(
            predictive_summary,
            min_samples=min_samples,
        )
        pair_metrics["phonon_hint_reliability"] = phonon_hint_reliability
        pair_metrics["candidate_phonon_control_hint"] = dict(shared_locus.get("latest_phonon_control_hint", {}))
        entangler_control = self.entangler.control(
            controls=self.controls,
            shared_locus_summary=shared_locus,
            shared_flux_history=self.shared_flux_history,
            pair_metrics=pair_metrics,
        )
        previous_weight_map = dict(self.wormhole_weight_map)
        self._apply_entangler_control(entangler_control)
        self.wormhole_weight_map = dict(entangler_control.get("wormhole_weight_map", self.wormhole_weight_map))
        weight_delta_map = self._compute_weight_delta_map(previous_weight_map, self.wormhole_weight_map)
        self.wormhole_weight_delta_history.append(weight_delta_map)
        if len(self.wormhole_weight_delta_history) > self.controls.max_history:
            self.wormhole_weight_delta_history = self.wormhole_weight_delta_history[-self.controls.max_history :]
        self.coherence_history.append(float(pair_metrics.get("phase_coherence", 0.0)))
        self.control_delta_history.append(
            {
                key: float(value)
                for key, value in dict(entangler_control.get("control_delta", {})).items()
            }
        )
        if len(self.coherence_history) > self.controls.max_history:
            self.coherence_history = self.coherence_history[-self.controls.max_history :]
        if len(self.control_delta_history) > self.controls.max_history:
            self.control_delta_history = self.control_delta_history[-self.controls.max_history :]
        entangler_state = self.shared_mediator.publish_entangler_control(entangler_control)
        phonon_bundle = self._build_phonon_bundle(
            pair_metrics=pair_metrics,
            shared_locus=shared_locus,
            entangler_state=entangler_state,
            previous_weight_map=previous_weight_map,
            current_weight_map=self.wormhole_weight_map,
            current_weight_delta_map=weight_delta_map,
        )
        self.phonon_bundles.append(phonon_bundle)
        if len(self.phonon_bundles) > self.controls.max_history:
            self.phonon_bundles = self.phonon_bundles[-self.controls.max_history :]
        latest_phonon_summary = self.shared_mediator.publish_phonon_bundle(self._serialize_phonon_bundle(phonon_bundle))
        latest_local_phonon_summary = self._serialize_phonon_bundle(self.local_phonon_bundles[-1]) if self.local_phonon_bundles else {}
        phonon_control_hint = self._derive_phonon_control_hint(len(self.shared_flux_history))
        self._record_phonon_control_hint(phonon_control_hint)
        latest_phonon_control_hint = self.shared_mediator.publish_phonon_control_hint(phonon_control_hint)
        shared_locus = self.shared_mediator.get_latest_summary()
        pair_metrics = self.telemetry_panel.record_pair_scan(
            pair_id=self.pair_id,
            manifold_a_id=self.manifold_ids[0],
            manifold_b_id=self.manifold_ids[1],
            wormhole_nodes=self.wormhole_nodes,
            wormhole_aperture=self.controls.aperture,
            damping=self.controls.damping,
            phase_offset=self.controls.phase_offset,
            shared_flux=self.shared_flux,
            phase_coherence=float(pair_metrics["phase_coherence"]),
            bilateral_burst_count=int(pair_metrics["bilateral_burst_count"]),
            bilateral_node_ids=pair_metrics["bilateral_node_ids"],
            max_h_cross_domain=float(pair_metrics["max_h_cross_domain"]),
            top_events=pair_metrics["top_events"],
            shared_locus_summary=shared_locus,
            entangler_control=entangler_state,
            latest_local_phonon_bundle=latest_local_phonon_summary,
            local_phonon_bundle_count=len(self.local_phonon_bundles),
            phonon_control_hint=phonon_control_hint,
        )
        pair_metrics["bilateral_node_ids"] = list(shared_locus.get("bilateral_node_ids", []))
        pair_metrics["shared_locus"] = shared_locus
        pair_metrics["entangler_control"] = entangler_state
        pair_metrics["wormhole_weight_map"] = dict(self.wormhole_weight_map)
        pair_metrics["entangler_mode"] = str(self.controls.entangler_mode)
        pair_metrics["entangler_mode_used"] = entangler_state.get("coherence_mode", str(self.controls.entangler_mode))
        pair_metrics["entangler_next_mode"] = entangler_state.get("next_coherence_mode", str(self.controls.entangler_mode))
        pair_metrics["mode_transition"] = dict(entangler_state.get("mode_transition", {}))
        pair_metrics["phonon_bundle"] = latest_phonon_summary
        pair_metrics["phonon_bundle_count"] = len(self.phonon_bundles)
        pair_metrics["local_phonon_bundle_count"] = len(self.local_phonon_bundles)
        pair_metrics["hint_gate"] = dict(entangler_state.get("hint_gate", {}))
        if self.local_phonon_bundles:
            pair_metrics["latest_local_phonon_bundle"] = self._serialize_phonon_bundle(self.local_phonon_bundles[-1])
        pair_metrics["phonon_control_hint"] = dict(latest_phonon_control_hint)
        pair_metrics["phonon_control_hint_count"] = len(self.phonon_control_hints)
        archive_result = self.pair_transducer.capture_bilateral_bursts(
            bursts_a,
            bursts_b,
            self.manifold_a.graph,
            self.manifold_b.graph,
            pair_metadata={
                **pair_metrics,
                "wormhole_nodes": self.wormhole_nodes,
                "shared_flux": self.shared_flux.tolist(),
                "cross_domain_giant": "Entanglement Locus",
                "entangler_strength": entangler_state.get("entanglement_strength", 0.0),
                "entangler_giant": entangler_state.get("dominant_giant_consensus", "Entanglement Locus"),
                "entangler_mode": str(self.controls.entangler_mode),
                "entangler_mode_used": entangler_state.get("coherence_mode", str(self.controls.entangler_mode)),
                "wormhole_weight_map": self.wormhole_weight_map,
            },
        )
        self.last_pair_metrics = pair_metrics
        self.last_pair_metrics["archive_paths"] = archive_result["paths"]
        self.last_pair_metrics["bilateral_node_ids"] = archive_result["bilateral_node_ids"]
        self._record_tick_trace(
            tick_index=local_tick_hint,
            previous_shared_flux=previous_shared_flux,
            signature_a=signature_a,
            signature_b=signature_b,
            pair_metrics=pair_metrics,
            entangler_control=entangler_control,
            entangler_state=entangler_state,
            weight_delta_map=weight_delta_map,
            previous_weight_map=previous_weight_map,
        )
        print(self.telemetry_panel.render_pair_registry(pair_ids=[self.pair_id]))

        return {
            "manifold_a": bursts_a,
            "manifold_b": bursts_b,
            "pair_metrics": pair_metrics,
            "archive_paths": archive_result["paths"],
        }

    def run_cycles(self, cycle_count: int = 1) -> List[Dict[str, object]]:
        return [self.tick() for _ in range(max(int(cycle_count), 1))]

    def run_live_cycles(
        self,
        cycle_count: int = 1,
        embedding_a_loc: float = 0.50,
        embedding_b_loc: float = 0.55,
        embedding_scale: float = 0.20,
        embedding_drift: float = 0.04,
    ) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        for cycle_index in range(max(int(cycle_count), 1)):
            embedding_a, embedding_b = self._generate_live_embeddings(
                cycle_index=cycle_index,
                embedding_a_loc=embedding_a_loc,
                embedding_b_loc=embedding_b_loc,
                embedding_scale=embedding_scale,
                embedding_drift=embedding_drift,
            )
            results.append(self.tick(embedding_a=embedding_a, embedding_b=embedding_b))
        return results

    def render_runtime_outputs(self, top_n: int = 6) -> Dict[str, str]:
        replay = HippocampalReplay(working_dir=self.working_dir)
        return {
            "registry": self.telemetry_panel.render_pair_registry(pair_ids=[self.pair_id], top_n=min(max(int(top_n), 1), 6)),
            "comparative": self.telemetry_panel.render_pair_comparative(pair_ids=[self.pair_id]),
            "replay": replay.replay(
                pair_id=self.pair_id,
                top_n=max(int(top_n), 1),
                hint_gate_policy=self.controls.hint_gate_policy,
            ),
        }

    def persist_runtime_outputs(self, top_n: int = 6) -> Dict[str, Path]:
        summaries = self.render_runtime_outputs(top_n=top_n)
        output_paths: Dict[str, Path] = {}
        for name, text in summaries.items():
            path = self.working_dir / f"{name}_summary.txt"
            path.write_text(text, encoding="utf-8")
            output_paths[name] = path
        return output_paths

    def build_run_checkpoint(
        self,
        results: Sequence[Dict[str, object]],
        *,
        runtime_context: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        pair_metrics_list = [dict(item.get("pair_metrics", {})) for item in results]
        tick_traces = self._jsonable_payload(self.tick_trace_history)
        gate_reason_history = [
            str(dict(metrics.get("hint_gate", {})).get("rejection_reason", "disabled"))
            for metrics in pair_metrics_list
        ]
        return {
            "pair_id": self.pair_id,
            "seed": int(self.controls.seed),
            "working_dir": str(self.working_dir),
            "wormhole_nodes": list(self.wormhole_nodes),
            "wormhole_fingerprint": self._fingerprint_payload(list(self.wormhole_nodes)),
            "runtime_context": self._jsonable_payload(runtime_context or {}),
            "manifolds": {
                self.manifold_ids[0]: self._build_manifold_checkpoint(self.manifold_a),
                self.manifold_ids[1]: self._build_manifold_checkpoint(self.manifold_b),
            },
            "state_loads": {
                self.manifold_ids[0]: self._jsonable_payload(self.mediator_a.get_state_load_metadata()),
                self.manifold_ids[1]: self._jsonable_payload(self.mediator_b.get_state_load_metadata()),
                "shared": self._jsonable_payload(self.shared_mediator.get_state_load_metadata()),
            },
            "scan_fingerprints": {
                self.manifold_ids[0]: {
                    "fingerprint": str(getattr(self.orchestrator_a, "last_scan_order_fingerprint", "none")),
                    "preview": list(getattr(self.orchestrator_a, "last_scan_order_preview", [])),
                },
                self.manifold_ids[1]: {
                    "fingerprint": str(getattr(self.orchestrator_b, "last_scan_order_fingerprint", "none")),
                    "preview": list(getattr(self.orchestrator_b, "last_scan_order_preview", [])),
                },
            },
            "tick_count": len(pair_metrics_list),
            "tick_trace": tick_traces,
            "signature_a_history": [list(trace.get("signature_a", [])) for trace in tick_traces],
            "signature_b_history": [list(trace.get("signature_b", [])) for trace in tick_traces],
            "shared_flux_vector_history": [list(trace.get("shared_flux_after_update", [])) for trace in tick_traces],
            "control_delta_history": [dict(trace.get("control_delta_after", {})) for trace in tick_traces],
            "coherence_feedback_history": [dict(trace.get("coherence_feedback", {})) for trace in tick_traces],
            "primary_wormhole_state_fingerprint_history": [
                str(dict(trace.get("manifolds", {})).get(self.manifold_ids[0], {}).get("wormhole_state_fingerprint", "none"))
                for trace in tick_traces
            ],
            "secondary_wormhole_state_fingerprint_history": [
                str(dict(trace.get("manifolds", {})).get(self.manifold_ids[1], {}).get("wormhole_state_fingerprint", "none"))
                for trace in tick_traces
            ],
            "primary_wormhole_edge_fingerprint_history": [
                str(dict(trace.get("manifolds", {})).get(self.manifold_ids[0], {}).get("wormhole_edge_fingerprint", "none"))
                for trace in tick_traces
            ],
            "secondary_wormhole_edge_fingerprint_history": [
                str(dict(trace.get("manifolds", {})).get(self.manifold_ids[1], {}).get("wormhole_edge_fingerprint", "none"))
                for trace in tick_traces
            ],
            "shared_pair_clock_history": [int(metrics.get("shared_pair_clock", 0)) for metrics in pair_metrics_list],
            "phase_coherence_history": [float(metrics.get("phase_coherence", 0.0)) for metrics in pair_metrics_list],
            "mode_history": [
                str(metrics.get("entangler_mode_used", metrics.get("entangler_mode", "active")))
                for metrics in pair_metrics_list
            ],
            "hint_status_history": [
                str(dict(metrics.get("phonon_control_hint", {})).get("status", "missing"))
                for metrics in pair_metrics_list
            ],
            "hint_bias_history": [
                str(dict(metrics.get("phonon_control_hint", {})).get("recommended_bias", "observe"))
                for metrics in pair_metrics_list
            ],
            "gate_state_history": [
                "pass"
                if bool(dict(metrics.get("hint_gate", {})).get("passed", False))
                else ("off" if not bool(dict(metrics.get("hint_gate", {})).get("enabled", False)) else "block")
                for metrics in pair_metrics_list
            ],
            "gate_reason_history": gate_reason_history,
            "gate_status_history": [
                str(dict(metrics.get("hint_gate", {})).get("considered_status", "missing"))
                for metrics in pair_metrics_list
            ],
            "nudge_rejection_history": [
                str(dict(metrics.get("hint_gate", {})).get("nudge_rejection_reason", "disabled"))
                for metrics in pair_metrics_list
            ],
            "first_tick_phase_coherence": float(pair_metrics_list[0].get("phase_coherence", 0.0)) if pair_metrics_list else 0.0,
            "final_mode": str(pair_metrics_list[-1].get("entangler_mode_used", pair_metrics_list[-1].get("entangler_mode", "active"))) if pair_metrics_list else str(self.controls.entangler_mode),
            "gate_reason_counts": _count_values(gate_reason_history),
        }

    def _build_manifold_checkpoint(self, manifold: BlankManifoldCore) -> Dict[str, object]:
        nodes = []
        for node_id in sorted(manifold.graph.nodes()):
            coords = [round(float(value), 6) for value in list(manifold.graph.nodes[node_id].get("coords", []))]
            nodes.append({"node_id": str(node_id), "coords": coords})

        edges = []
        for left, right, data in sorted(manifold.graph.edges(data=True), key=lambda item: (str(item[0]), str(item[1]))):
            edge_left, edge_right = sorted((str(left), str(right)))
            edges.append(
                {
                    "left": edge_left,
                    "right": edge_right,
                    "distance": round(float(data.get("distance", 0.0)), 6),
                    "repaired": bool(data.get("repaired", False)),
                }
            )

        payload = {
            "node_count": int(manifold.graph.number_of_nodes()),
            "edge_count": int(manifold.graph.number_of_edges()),
            "nodes": nodes,
            "edges": edges,
        }
        return {
            "node_count": payload["node_count"],
            "edge_count": payload["edge_count"],
            "fingerprint": self._fingerprint_payload(payload),
        }

    def _fingerprint_payload(self, payload: object) -> str:
        serialized = json.dumps(self._jsonable_payload(payload), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def _jsonable_payload(self, payload: object) -> object:
        if isinstance(payload, dict):
            return {str(key): self._jsonable_payload(value) for key, value in payload.items()}
        if isinstance(payload, (list, tuple)):
            return [self._jsonable_payload(value) for value in payload]
        if isinstance(payload, np.ndarray):
            return [self._jsonable_payload(value) for value in payload.tolist()]
        if isinstance(payload, np.generic):
            return payload.item()
        return payload

    def _record_tick_trace(
        self,
        *,
        tick_index: int,
        previous_shared_flux: np.ndarray,
        signature_a: np.ndarray,
        signature_b: np.ndarray,
        pair_metrics: Dict[str, object],
        entangler_control: Dict[str, object],
        entangler_state: Dict[str, object],
        weight_delta_map: Dict[str, float],
        previous_weight_map: Dict[str, float],
    ) -> None:
        trace = {
            "tick": int(tick_index),
            "signature_a": [float(value) for value in np.asarray(signature_a, dtype=float).reshape(-1).tolist()],
            "signature_b": [float(value) for value in np.asarray(signature_b, dtype=float).reshape(-1).tolist()],
            "phase_coherence": float(pair_metrics.get("phase_coherence", 0.0)),
            "shared_flux_before_update": [float(value) for value in np.asarray(previous_shared_flux, dtype=float).reshape(-1).tolist()],
            "shared_flux_after_update": [float(value) for value in np.asarray(self.shared_flux, dtype=float).reshape(-1).tolist()],
            "shared_flux_history_tail": [
                [float(value) for value in np.asarray(vector, dtype=float).reshape(-1).tolist()]
                for vector in self.shared_flux_history[-4:]
            ],
            "recent_phase_coherence_before": [float(value) for value in self.coherence_history[-4:]],
            "recent_control_deltas_before": [
                {key: float(value) for key, value in dict(delta).items()}
                for delta in self.control_delta_history[-4:]
            ],
            "control_delta_after": {
                key: float(value)
                for key, value in dict(entangler_control.get("control_delta", {})).items()
            },
            "coherence_feedback": dict(entangler_control.get("coherence_feedback", {})),
            "controls_after": {
                key: float(value)
                for key, value in dict(entangler_control.get("controls_after", {})).items()
            },
            "wormhole_weight_map_before": {
                str(node_id): float(value)
                for node_id, value in dict(previous_weight_map).items()
            },
            "wormhole_weight_map_after": {
                str(node_id): float(value)
                for node_id, value in dict(self.wormhole_weight_map).items()
            },
            "weight_delta_map": {
                str(node_id): float(value)
                for node_id, value in dict(weight_delta_map).items()
            },
            "manifolds": {
                self.manifold_ids[0]: self._build_tick_manifold_trace(self.manifold_a),
                self.manifold_ids[1]: self._build_tick_manifold_trace(self.manifold_b),
            },
            "shared_pair_clock": int(entangler_state.get("pair_clock", pair_metrics.get("shared_pair_clock", 0))),
        }
        self.tick_trace_history.append(trace)
        if len(self.tick_trace_history) > self.controls.max_history:
            self.tick_trace_history = self.tick_trace_history[-self.controls.max_history :]

    def _build_tick_manifold_trace(self, manifold: BlankManifoldCore) -> Dict[str, object]:
        wormhole_nodes = {}
        for node_id in self.wormhole_nodes:
            node = manifold.graph.nodes[node_id]
            neighbor_order = [str(neighbor_id) for neighbor_id in manifold.graph.neighbors(node_id)]
            wormhole_nodes[str(node_id)] = {
                "neighbor_order": neighbor_order,
                "resonance_accumulator": float(node.get("resonance_accumulator", 0.0)),
                "semantic_potential": float(node.get("semantic_potential", 0.0)),
                "state_vector": [float(value) for value in self._pad_vector(node.get("state_vector", [])).tolist()],
                "consensus_confidence": float(node.get("consensus_confidence", 0.0)),
                "consensus_entropy": float(node.get("consensus_entropy", 0.0)),
                "consensus_clock": int(node.get("consensus_clock", 0)),
                "dominant_giant": str(node.get("dominant_giant") or "Ambient Basin"),
            }

        wormhole_edges = self._capture_wormhole_edge_snapshot(manifold)
        return {
            "wormhole_nodes": wormhole_nodes,
            "wormhole_edges": wormhole_edges,
            "wormhole_state_fingerprint": self._fingerprint_payload(wormhole_nodes),
            "wormhole_edge_fingerprint": self._fingerprint_payload(wormhole_edges),
        }

    def _capture_wormhole_edge_snapshot(self, manifold: BlankManifoldCore) -> List[Dict[str, object]]:
        edges: List[Dict[str, object]] = []
        seen = set()
        for node_id in self.wormhole_nodes:
            for neighbor_id in manifold.graph.neighbors(node_id):
                edge_left, edge_right = sorted((str(node_id), str(neighbor_id)))
                edge_key = (edge_left, edge_right)
                if edge_key in seen:
                    continue
                seen.add(edge_key)
                edge = manifold.graph[node_id][neighbor_id]
                edges.append(
                    {
                        "left": edge_left,
                        "right": edge_right,
                        "weight": float(edge.get("weight", manifold.config.baseline_coupling)),
                        "residual_flux": float(edge.get("residual_flux", 0.0)),
                        "collapsed": bool(edge.get("collapsed", False)),
                        "repaired": bool(edge.get("repaired", False)),
                    }
                )
        edges.sort(key=lambda item: (str(item["left"]), str(item["right"])))
        return edges

    def _select_wormhole_nodes(self, wormhole_count: int) -> List[str]:
        node_ids = sorted(self.manifold_a.graph.nodes())
        if wormhole_count <= 0:
            return []
        if wormhole_count >= len(node_ids):
            return node_ids

        offset = int(self.rng.integers(0, len(node_ids)))
        step = max(len(node_ids) / wormhole_count, 1.0)
        indices = []
        for position in range(wormhole_count):
            index = int((offset + round(position * step)) % len(node_ids))
            if index not in indices:
                indices.append(index)

        if len(indices) < wormhole_count:
            for index in range(len(node_ids)):
                if index not in indices:
                    indices.append(index)
                if len(indices) == wormhole_count:
                    break

        return sorted(node_ids[index] for index in indices)

    def _update_shared_flux(self, signature_a: np.ndarray, signature_b: np.ndarray) -> np.ndarray:
        conjugated_b = self._phase_conjugate(signature_b)
        target_flux = 0.5 * (np.asarray(signature_a, dtype=float) + conjugated_b)
        updated_flux = (self.controls.damping * self.shared_flux) + (self.controls.aperture * target_flux)
        return np.clip(updated_flux, -10.0, 10.0)

    def _phase_conjugate(self, signature: np.ndarray) -> np.ndarray:
        vector = np.asarray(signature, dtype=float).reshape(-1)
        padded = np.zeros(3, dtype=float)
        padded[: min(vector.size, 3)] = vector[: min(vector.size, 3)]
        cosine = float(np.cos(self.controls.phase_offset))
        sine = float(np.sin(self.controls.phase_offset))
        return np.array(
            [
                (cosine * padded[0]) - (sine * padded[1]),
                (sine * padded[0]) + (cosine * padded[1]),
                cosine * padded[2],
            ],
            dtype=float,
        )

    def _build_pair_metrics(
        self,
        bursts_a: Sequence[Tuple[str, Dict[str, float]]],
        bursts_b: Sequence[Tuple[str, Dict[str, float]]],
        signature_a: np.ndarray,
        signature_b: np.ndarray,
    ) -> Dict[str, object]:
        wormhole_set = set(self.wormhole_nodes)
        burst_ids_a = {node_id for node_id, _ in bursts_a if node_id in wormhole_set}
        burst_ids_b = {node_id for node_id, _ in bursts_b if node_id in wormhole_set}
        bilateral_node_ids = sorted(burst_ids_a & burst_ids_b)
        bilateral_burst_count = len(bilateral_node_ids)
        phase_coherence = self._cosine_similarity(signature_a, signature_b)
        top_events = self._build_top_pair_events(bursts_a, bursts_b)
        max_h_cross_domain = max(
            [float(metrics.get("H_total", 0.0)) for _, metrics in list(bursts_a) + list(bursts_b)] or [0.0]
        )

        return {
            "pair_id": self.pair_id,
            "manifold_a_id": self.manifold_ids[0],
            "manifold_b_id": self.manifold_ids[1],
            "phase_coherence": phase_coherence,
            "bilateral_burst_count": bilateral_burst_count,
            "bilateral_node_ids": bilateral_node_ids,
            "max_h_cross_domain": max_h_cross_domain,
            "top_events": top_events,
        }

    def _collect_wormhole_consensus(self) -> Dict[str, Dict[str, Dict[str, object]]]:
        snapshots: Dict[str, Dict[str, Dict[str, object]]] = {}
        for manifold_id, manifold in ((self.manifold_ids[0], self.manifold_a), (self.manifold_ids[1], self.manifold_b)):
            per_node: Dict[str, Dict[str, object]] = {}
            for node_id in self.wormhole_nodes:
                node = manifold.graph.nodes[node_id]
                if "consensus_vector" not in node:
                    continue
                per_node[node_id] = {
                    "consensus_vector": np.asarray(node.get("consensus_vector", []), dtype=float).tolist(),
                    "consensus_confidence": float(node.get("consensus_confidence", 0.0)),
                    "consensus_entropy": float(node.get("consensus_entropy", 0.0)),
                    "consensus_clock": int(node.get("consensus_clock", 0)),
                    "dominant_giant": str(node.get("dominant_giant", "Ambient Basin")),
                }
            snapshots[manifold_id] = per_node
        return snapshots

    def _compute_weight_delta_map(
        self,
        previous_weight_map: Dict[str, float],
        current_weight_map: Dict[str, float],
    ) -> Dict[str, float]:
        node_ids = sorted(set(previous_weight_map) | set(current_weight_map))
        return {
            node_id: float(current_weight_map.get(node_id, 1.0) - previous_weight_map.get(node_id, 1.0))
            for node_id in node_ids
        }

    def _capture_wormhole_snapshot(self, manifold: BlankManifoldCore) -> Dict[str, Dict[str, object]]:
        snapshot: Dict[str, Dict[str, object]] = {}
        for node_id in self.wormhole_nodes:
            node = manifold.graph.nodes[node_id]
            snapshot[node_id] = {
                "state_vector": self._pad_vector(node.get("state_vector", [])).tolist(),
                "resonance_accumulator": float(node.get("resonance_accumulator", 0.0)),
                "consensus_confidence": float(node.get("consensus_confidence", 0.0)),
                "consensus_entropy": float(node.get("consensus_entropy", 0.0)),
                "dominant_giant": str(node.get("dominant_giant") or "Ambient Basin"),
            }
        return snapshot

    def _pad_vector(self, vector: object) -> np.ndarray:
        array = np.asarray(vector if vector is not None else [], dtype=float).reshape(-1)
        if array.size >= 3:
            return array[:3]
        padded = np.zeros(3, dtype=float)
        if array.size:
            padded[: array.size] = array
        return padded

    def _record_local_phonon_bundle(self, phonon_bundle: PhononBundle) -> None:
        self.local_phonon_bundles.append(phonon_bundle)
        max_local_history = max(int(self.controls.max_history) * 4, 4)
        if len(self.local_phonon_bundles) > max_local_history:
            self.local_phonon_bundles = self.local_phonon_bundles[-max_local_history:]

    def _record_phonon_control_hint(self, phonon_control_hint: Dict[str, object]) -> None:
        self.phonon_control_hints.append(dict(phonon_control_hint))
        if len(self.phonon_control_hints) > self.controls.max_history:
            self.phonon_control_hints = self.phonon_control_hints[-self.controls.max_history :]

    def _derive_phonon_control_hint(self, current_pair_tick: int) -> Dict[str, object]:
        prior_pair_bundles = self.phonon_bundles[:-1][-3:]
        prior_local_bundles = [bundle for bundle in self.local_phonon_bundles if int(bundle.pair_clock) < int(current_pair_tick)][-8:]
        latest_source_clock = max(
            [int(bundle.pair_clock) for bundle in prior_local_bundles],
            default=max(int(current_pair_tick) - 1, 0),
        )
        hint = {
            "status": "suppressed",
            "recommended_bias": "observe",
            "confidence": 0.0,
            "age_ticks": max(int(current_pair_tick) - int(latest_source_clock), 0),
            "stability_window": int(len(prior_pair_bundles) + len(prior_local_bundles)),
            "suppression_reason": "insufficient_history",
            "decision_reason": "insufficient_history",
            "source_tier": "none",
            "entry_pressure": 0.0,
            "exit_pressure": 0.0,
            "pair_stability": 0.0,
            "local_stability": 0.0,
            "pair_decay": 0.0,
            "amplitude_trend": 0.0,
        }
        if not prior_pair_bundles or len(prior_local_bundles) < 2:
            return hint

        pair_confidence = float(np.mean([bundle.confidence for bundle in prior_pair_bundles]))
        local_confidence = float(np.mean([bundle.confidence for bundle in prior_local_bundles]))
        pair_stability = float(np.mean([float(bundle.coherence_signature.get("stability_score", 0.0)) for bundle in prior_pair_bundles]))
        local_stability = float(np.mean([float(bundle.coherence_signature.get("stability_score", 0.0)) for bundle in prior_local_bundles]))
        pair_decay = float(np.mean([bundle.decay_rate for bundle in prior_pair_bundles]))
        local_amplitudes = [float(bundle.amplitude) for bundle in prior_local_bundles]
        local_tiers = [str(bundle.source_tier) for bundle in prior_local_bundles]
        entry_pressure = float(np.mean([len(bundle.wormhole_entry_nodes) for bundle in prior_local_bundles]))
        exit_pressure = float(np.mean([len(bundle.wormhole_exit_nodes) for bundle in prior_local_bundles]))
        amplitude_trend = float(local_amplitudes[-1] - local_amplitudes[0]) if len(local_amplitudes) >= 2 else 0.0
        confidence = float(np.clip((0.45 * pair_confidence) + (0.35 * local_confidence) + (0.20 * pair_stability), 0.0, 1.0))
        dominant_local_tier = max(set(local_tiers), key=local_tiers.count)
        hint.update(
            {
                "confidence": confidence,
                "age_ticks": max(int(current_pair_tick) - int(latest_source_clock), 0),
                "stability_window": int(len(prior_pair_bundles) + len(prior_local_bundles)),
                "source_tier": dominant_local_tier,
                "entry_pressure": entry_pressure,
                "exit_pressure": exit_pressure,
                "pair_stability": pair_stability,
                "local_stability": local_stability,
                "pair_decay": pair_decay,
                "amplitude_trend": amplitude_trend,
            }
        )

        if confidence < 0.35:
            hint["suppression_reason"] = "low_confidence"
            hint["decision_reason"] = "low_confidence"
            return hint
        if hint["age_ticks"] > 2:
            hint["suppression_reason"] = "stale"
            hint["decision_reason"] = "stale"
            return hint

        hint["status"] = "armed"
        hint["suppression_reason"] = "none"
        if pair_stability < 0.45 or exit_pressure > (entry_pressure + 0.25):
            hint["recommended_bias"] = "stabilize"
            hint["decision_reason"] = "stabilize_pressure_or_low_stability"
        elif (
            self.controls.hint_gate_policy.enable_negative_collapse_stabilize
            and amplitude_trend < -0.35
            and local_stability < 0.50
        ):
            hint["recommended_bias"] = "stabilize"
            hint["decision_reason"] = "stabilize_negative_amplitude_collapse"
        elif pair_decay > 0.16:
            hint["recommended_bias"] = "damp"
            hint["decision_reason"] = "damp_high_decay"
        elif amplitude_trend > 0.08 and local_stability >= 0.55:
            hint["recommended_bias"] = "loosen"
            hint["decision_reason"] = "loosen_growth_with_stability"
        else:
            hint["recommended_bias"] = "observe"
            hint["decision_reason"] = "observe_balanced_signal"
        return hint

    def _dominant_channel_from_vector(self, vector: Sequence[float]) -> str:
        padded = self._pad_vector(vector)
        channels = ("density", "shear", "vorticity")
        index = int(np.argmax(np.abs(padded))) if padded.size else 0
        return channels[index]

    def _build_local_phonon_bundle(
        self,
        manifold: BlankManifoldCore,
        manifold_id: str,
        source_tier: str,
        clock_hint: int,
        phase_coherence_hint: float,
        baseline_snapshot: Optional[Dict[str, Dict[str, object]]] = None,
        dominant_channel_hint: Optional[str] = None,
    ) -> PhononBundle:
        candidates: List[Dict[str, object]] = []
        node_delta_map: Dict[str, float] = {}
        for node_id in self.wormhole_nodes:
            node = manifold.graph.nodes[node_id]
            current_vector = self._pad_vector(node.get("state_vector", []))
            current_resonance = float(node.get("resonance_accumulator", 0.0))
            consensus_confidence = float(node.get("consensus_confidence", 0.0))
            consensus_entropy = float(node.get("consensus_entropy", 0.0))
            dominant_giant = str(node.get("dominant_giant") or "Ambient Basin")
            if baseline_snapshot is not None:
                baseline = dict(baseline_snapshot.get(node_id, {}))
                baseline_vector = self._pad_vector(baseline.get("state_vector", []))
                vector = current_vector - baseline_vector
                resonance_delta = current_resonance - float(baseline.get("resonance_accumulator", 0.0))
                node_delta_map[node_id] = float(resonance_delta)
            else:
                vector = current_vector
                resonance_delta = current_resonance
                node_delta_map[node_id] = float(np.linalg.norm(vector))

            magnitude = float(np.linalg.norm(vector) + abs(resonance_delta))
            candidates.append(
                {
                    "node_id": node_id,
                    "vector": vector,
                    "magnitude": magnitude,
                    "confidence": consensus_confidence,
                    "entropy": consensus_entropy,
                    "dominant_giant": dominant_giant,
                    "score": magnitude + consensus_confidence,
                }
            )

        candidates.sort(key=lambda item: (float(item["score"]), str(item["node_id"])), reverse=True)
        top_candidates = candidates[:2] if candidates else []
        if top_candidates:
            mean_vector = np.mean([np.asarray(item["vector"], dtype=float) for item in top_candidates], axis=0)
            mean_confidence = float(np.mean([float(item["confidence"]) for item in top_candidates]))
            mean_entropy = float(np.mean([float(item["entropy"]) for item in top_candidates]))
            carrier_giant = str(top_candidates[0]["dominant_giant"])
            source_nodes = tuple(str(item["node_id"]) for item in top_candidates)
        else:
            mean_vector = np.zeros(3, dtype=float)
            mean_confidence = 0.0
            mean_entropy = 0.0
            carrier_giant = "Ambient Basin"
            source_nodes = ()

        amplitude = float(np.linalg.norm(mean_vector))
        normalized_amplitude = float(np.clip(amplitude / 5.0, 0.0, 1.0))
        confidence = float(np.clip((0.6 * mean_confidence) + (0.4 * normalized_amplitude), 0.0, 1.0))
        positive_nodes = [node_id for node_id, delta in node_delta_map.items() if float(delta) > 0.0]
        negative_nodes = [node_id for node_id, delta in node_delta_map.items() if float(delta) < 0.0]
        positive_nodes.sort(key=lambda node_id: (float(node_delta_map[node_id]), node_id), reverse=True)
        negative_nodes.sort(key=lambda node_id: (float(node_delta_map[node_id]), node_id))
        mode = dominant_channel_hint or self._dominant_channel_from_vector(mean_vector)
        stability_score = float(np.clip((0.5 * phase_coherence_hint) + (0.5 * mean_confidence), 0.0, 1.0))
        return PhononBundle(
            phonon_id=f"phonon_{self.pair_id}_{source_tier}_{manifold_id}_{int(clock_hint):04d}",
            pair_clock=int(clock_hint),
            source_tier=source_tier,
            carrier_giant=carrier_giant,
            source_nodes=source_nodes,
            mode=mode,
            state_vector=tuple(float(value) for value in mean_vector[:3]),
            amplitude=amplitude,
            phase_coherence=float(phase_coherence_hint),
            decay_rate=float(1.0 - self.controls.damping),
            confidence=confidence,
            entropy=mean_entropy,
            predicted_next_mode=str(self.controls.entangler_mode),
            wormhole_entry_nodes=tuple(positive_nodes[:2]),
            wormhole_exit_nodes=tuple(negative_nodes[:2]),
            weight_delta_map={node_id: float(delta) for node_id, delta in node_delta_map.items()},
            coherence_signature={
                "status": source_tier,
                "trend": 0.0,
                "delta": amplitude,
                "phase_coherence": float(phase_coherence_hint),
                "control_responsiveness": 0.0,
                "stability_score": stability_score,
            },
        )

    def _smooth_weight_delta_map(self, current_weight_delta_map: Dict[str, float]) -> Dict[str, float]:
        recent_maps = self.wormhole_weight_delta_history[-2:] + [current_weight_delta_map]
        smoothed: Dict[str, float] = {}
        for node_id in sorted({key for mapping in recent_maps for key in mapping}):
            values = sorted(float(mapping.get(node_id, 0.0)) for mapping in recent_maps)
            smoothed[node_id] = float(values[len(values) // 2])
        return smoothed

    def _top_weighted_nodes(self, weight_map: Dict[str, float], top_n: int = 4) -> List[str]:
        ranked = sorted(weight_map.items(), key=lambda item: (float(item[1]), item[0]), reverse=True)
        return [node_id for node_id, _ in ranked[: max(int(top_n), 1)]]

    def _build_coherence_signature(
        self,
        phase_coherence: float,
        entangler_state: Dict[str, object],
    ) -> Dict[str, object]:
        feedback = dict(entangler_state.get("coherence_feedback", {}))
        recent_deltas = self.control_delta_history[-4:]
        responsiveness_values = []
        for delta in recent_deltas:
            responsiveness_values.append(
                abs(float(delta.get("aperture", 0.0)))
                + abs(float(delta.get("damping", 0.0)))
                + abs(float(delta.get("phase_offset", 0.0)))
            )
        responsiveness = float(np.mean(responsiveness_values)) if responsiveness_values else 0.0
        normalized_responsiveness = float(np.clip(responsiveness / 0.25, 0.0, 1.0))
        stability_score = float(
            np.clip(
                1.0 - min(abs(float(feedback.get("trend", 0.0))), 1.0) - (0.35 * normalized_responsiveness),
                0.0,
                1.0,
            )
        )
        return {
            "status": str(feedback.get("status", "stable")),
            "trend": float(feedback.get("trend", 0.0)),
            "delta": float(feedback.get("delta", 0.0)),
            "phase_coherence": float(phase_coherence),
            "control_responsiveness": responsiveness,
            "stability_score": stability_score,
        }

    def _build_phonon_bundle(
        self,
        pair_metrics: Dict[str, object],
        shared_locus: Dict[str, object],
        entangler_state: Dict[str, object],
        previous_weight_map: Dict[str, float],
        current_weight_map: Dict[str, float],
        current_weight_delta_map: Dict[str, float],
    ) -> PhononBundle:
        pair_clock = int(entangler_state.get("pair_clock", shared_locus.get("pair_clock", 0)))
        state_vector = np.asarray(shared_locus.get("shared_flux_vector", self.shared_flux.tolist()), dtype=float).reshape(-1)
        padded_vector = np.zeros(3, dtype=float)
        padded_vector[: min(state_vector.size, 3)] = state_vector[: min(state_vector.size, 3)]
        smoothed_weight_delta_map = self._smooth_weight_delta_map(current_weight_delta_map)
        previous_top = set(self._top_weighted_nodes(previous_weight_map))
        current_top = set(self._top_weighted_nodes(current_weight_map))
        coherence_signature = self._build_coherence_signature(
            phase_coherence=float(pair_metrics.get("phase_coherence", 0.0)),
            entangler_state=entangler_state,
        )
        resolved_channels = dict(shared_locus.get("resolved_channels", {}))
        locus_resolved = dict(resolved_channels.get("entanglement_locus", {}))
        confidence = float(
            np.clip(
                (0.65 * max(float(shared_locus.get("phase_coherence", 0.0)), 0.0))
                + (0.35 * min(float(pair_metrics.get("bilateral_burst_count", 0)) / max(len(self.wormhole_nodes), 1), 1.0)),
                0.0,
                1.0,
            )
        )
        return PhononBundle(
            phonon_id=f"phonon_{self.pair_id}_{pair_clock:04d}",
            pair_clock=pair_clock,
            source_tier="micro",
            carrier_giant=str(entangler_state.get("dominant_giant_consensus", shared_locus.get("cross_domain_giant", "Entanglement Locus"))),
            source_nodes=tuple(str(node_id) for node_id in pair_metrics.get("bilateral_node_ids", [])),
            mode=str(shared_locus.get("dominant_channel", "density")),
            state_vector=tuple(float(value) for value in padded_vector[:3]),
            amplitude=float(np.linalg.norm(padded_vector)),
            phase_coherence=float(pair_metrics.get("phase_coherence", 0.0)),
            decay_rate=float(1.0 - self.controls.damping),
            confidence=confidence,
            entropy=float(locus_resolved.get("consensus_entropy", 0.0)),
            predicted_next_mode=str(entangler_state.get("next_coherence_mode", self.controls.entangler_mode)),
            wormhole_entry_nodes=tuple(sorted(current_top - previous_top)),
            wormhole_exit_nodes=tuple(sorted(previous_top - current_top)),
            weight_delta_map=smoothed_weight_delta_map,
            coherence_signature=coherence_signature,
        )

    def _serialize_phonon_bundle(self, phonon_bundle: PhononBundle) -> Dict[str, object]:
        return {
            "phonon_id": phonon_bundle.phonon_id,
            "pair_clock": int(phonon_bundle.pair_clock),
            "source_tier": phonon_bundle.source_tier,
            "carrier_giant": phonon_bundle.carrier_giant,
            "source_nodes": list(phonon_bundle.source_nodes),
            "mode": phonon_bundle.mode,
            "state_vector": [float(value) for value in phonon_bundle.state_vector],
            "amplitude": float(phonon_bundle.amplitude),
            "phase_coherence": float(phonon_bundle.phase_coherence),
            "decay_rate": float(phonon_bundle.decay_rate),
            "confidence": float(phonon_bundle.confidence),
            "entropy": float(phonon_bundle.entropy),
            "predicted_next_mode": phonon_bundle.predicted_next_mode,
            "wormhole_entry_nodes": list(phonon_bundle.wormhole_entry_nodes),
            "wormhole_exit_nodes": list(phonon_bundle.wormhole_exit_nodes),
            "weight_delta_map": {node_id: float(delta) for node_id, delta in phonon_bundle.weight_delta_map.items()},
            "coherence_signature": dict(phonon_bundle.coherence_signature),
        }

    def _build_top_pair_events(
        self,
        bursts_a: Sequence[Tuple[str, Dict[str, float]]],
        bursts_b: Sequence[Tuple[str, Dict[str, float]]],
        top_n: int = 4,
    ) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        for manifold_id, bursts in ((self.manifold_ids[0], bursts_a), (self.manifold_ids[1], bursts_b)):
            for node_id, metrics in bursts:
                events.append(
                    {
                        "manifold_id": manifold_id,
                        "node_id": node_id,
                        "h_total": float(metrics.get("H_total", 0.0)),
                        "density_contrib": float(metrics.get("density_contrib", 0.0)),
                        "shear_contrib": float(metrics.get("shear_contrib", 0.0)),
                        "vorticity_contrib": float(metrics.get("vorticity_contrib", 0.0)),
                    }
                )

        events.sort(key=lambda event: float(event.get("h_total", 0.0)), reverse=True)
        return events[:top_n]

    def _coerce_embedding(self, embedding: Optional[np.ndarray], loc: float) -> np.ndarray:
        if embedding is not None:
            return np.asarray(embedding, dtype=float)
        return self.rng.normal(loc=loc, scale=0.2, size=1536)

    def _generate_live_embeddings(
        self,
        cycle_index: int,
        embedding_a_loc: float,
        embedding_b_loc: float,
        embedding_scale: float,
        embedding_drift: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        phase = float(cycle_index)
        drift = float(max(embedding_drift, 0.0))
        scale = float(max(embedding_scale, 1e-6))
        loc_a = float(embedding_a_loc) + (drift * np.sin(0.65 * phase))
        loc_b = float(embedding_b_loc) + (drift * np.cos(0.85 * phase)) - (0.35 * drift * np.sin(0.50 * phase))
        embedding_a = self.rng.normal(loc=loc_a, scale=scale, size=1536)
        embedding_b = self.rng.normal(loc=loc_b, scale=scale, size=1536)
        return embedding_a, embedding_b

    def _apply_entangler_control(self, control_report: Dict[str, object]) -> None:
        controls_after = dict(control_report.get("controls_after", {}))
        self.controls.aperture = float(controls_after.get("aperture", self.controls.aperture))
        self.controls.damping = float(controls_after.get("damping", self.controls.damping))
        self.controls.phase_offset = float(controls_after.get("phase_offset", self.controls.phase_offset))
        transition = self._evaluate_mode_transition(control_report)
        control_report["mode_transition"] = dict(transition)
        control_report["mode_decay_streak"] = self._mode_decay_streak
        control_report["mode_improving_streak"] = self._mode_improving_streak
        control_report["stabilizer_dwell_ticks"] = self._stabilizer_dwell_ticks
        control_report["next_coherence_mode"] = str(self.controls.entangler_mode)

    def _evaluate_mode_transition(self, control_report: Dict[str, object]) -> Dict[str, object]:
        feedback = dict(control_report.get("coherence_feedback", {}))
        current_mode = self._normalize_mode_name(control_report.get("coherence_mode", self.controls.entangler_mode))
        next_mode = current_mode
        status = str(feedback.get("status", "stable"))
        total_samples = int(feedback.get("history_count", 0)) + 1

        if current_mode == "Stabilizer":
            self._stabilizer_dwell_ticks += 1
        else:
            self._stabilizer_dwell_ticks = 0

        if status == "decaying":
            self._mode_decay_streak += 1
            self._mode_improving_streak = 0
        elif status == "improving":
            self._mode_improving_streak += 1
            self._mode_decay_streak = 0
        else:
            self._mode_decay_streak = 0
            self._mode_improving_streak = 0

        transition = self._build_mode_transition(
            changed=False,
            previous_mode=current_mode,
            next_mode=current_mode,
            total_samples=total_samples,
        )

        if total_samples < int(self.controls.min_mode_switch_samples):
            transition["reason"] = f"insufficient_history_{total_samples}"
            self._last_mode_transition = dict(transition)
            return transition

        if current_mode == "active" and self._mode_decay_streak >= int(self.controls.stabilizer_enter_decay_streak):
            next_mode = "Stabilizer"
            transition = self._build_mode_transition(
                changed=True,
                previous_mode=current_mode,
                next_mode=next_mode,
                reason=(
                    f"decaying_x{int(self.controls.stabilizer_enter_decay_streak)}"
                    f"_after_history{int(self.controls.min_mode_switch_samples)}"
                ),
                total_samples=total_samples,
            )
            self.controls.entangler_mode = next_mode
            self._stabilizer_dwell_ticks = 0
            self._mode_improving_streak = 0
        elif current_mode == "Stabilizer":
            if self._stabilizer_dwell_ticks < int(self.controls.stabilizer_min_dwell_ticks):
                transition["reason"] = f"stabilizer_dwell_{self._stabilizer_dwell_ticks}of{int(self.controls.stabilizer_min_dwell_ticks)}"
            elif self._mode_improving_streak >= int(self.controls.stabilizer_exit_improving_streak):
                next_mode = "active"
                transition = self._build_mode_transition(
                    changed=True,
                    previous_mode=current_mode,
                    next_mode=next_mode,
                    reason=(
                        f"improving_x{int(self.controls.stabilizer_exit_improving_streak)}"
                        f"_after_dwell{int(self.controls.stabilizer_min_dwell_ticks)}"
                    ),
                    total_samples=total_samples,
                )
                self.controls.entangler_mode = next_mode
                self._stabilizer_dwell_ticks = 0
                self._mode_decay_streak = 0

        self._last_mode_transition = dict(transition)
        return transition

    def _build_mode_transition(
        self,
        *,
        changed: bool,
        previous_mode: Optional[str] = None,
        next_mode: Optional[str] = None,
        reason: str = "none",
        total_samples: int = 0,
    ) -> Dict[str, object]:
        previous = self._normalize_mode_name(previous_mode or self.controls.entangler_mode)
        upcoming = self._normalize_mode_name(next_mode or self.controls.entangler_mode)
        return {
            "changed": bool(changed),
            "previous_mode": previous,
            "next_mode": upcoming,
            "reason": str(reason),
            "decay_streak": int(self._mode_decay_streak),
            "improving_streak": int(self._mode_improving_streak),
            "stabilizer_dwell_ticks": int(self._stabilizer_dwell_ticks),
            "total_samples": int(total_samples),
        }

    def _normalize_mode_name(self, raw_mode: object) -> str:
        normalized = str(raw_mode or "active").strip().lower()
        if normalized == "stabilizer":
            return "Stabilizer"
        return "active"

    def _cosine_similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        left_norm = float(np.linalg.norm(left))
        right_norm = float(np.linalg.norm(right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return float(np.dot(left, right) / (left_norm * right_norm))


def run_pair_runtime(
    *,
    controls: EntanglementControls,
    working_dir: Optional[Path],
    cycles: int,
    top_n: int,
    live_embeddings: bool,
    persist_summaries: bool,
    embedding_a_loc: float,
    embedding_b_loc: float,
    embedding_scale: float,
    embedding_drift: float,
    clean_run_reset: bool = False,
) -> Dict[str, object]:
    if clean_run_reset:
        if working_dir is None:
            raise ValueError("clean_run_reset requires an explicit working_dir so reset scope stays bounded")
        _reset_runtime_working_dir(Path(working_dir))

    runtime_controls = replace(
        controls,
        hint_gate_policy=replace(controls.hint_gate_policy),
    )
    pair = EntangledSOLPair(controls=runtime_controls, working_dir=working_dir)
    if live_embeddings:
        results = pair.run_live_cycles(
            cycle_count=cycles,
            embedding_a_loc=embedding_a_loc,
            embedding_b_loc=embedding_b_loc,
            embedding_scale=embedding_scale,
            embedding_drift=embedding_drift,
        )
    else:
        results = pair.run_cycles(cycle_count=cycles)

    summaries = pair.render_runtime_outputs(top_n=top_n)
    output_paths: Dict[str, Path] = {}
    if persist_summaries:
        output_paths = pair.persist_runtime_outputs(top_n=top_n)

    checkpoint = pair.build_run_checkpoint(
        results,
        runtime_context={
            "cycles": int(cycles),
            "top_n": int(top_n),
            "live_embeddings": bool(live_embeddings),
            "embedding_a_loc": float(embedding_a_loc),
            "embedding_b_loc": float(embedding_b_loc),
            "embedding_scale": float(embedding_scale),
            "embedding_drift": float(embedding_drift),
            "clean_run_reset": bool(clean_run_reset),
        },
    )
    checkpoint_path = pair.working_dir / "run_checkpoint.json"
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True, indent=2), encoding="utf-8")
    output_paths["checkpoint"] = checkpoint_path

    return {
        "pair": pair,
        "results": results,
        "summaries": summaries,
        "output_paths": output_paths,
        "checkpoint": checkpoint,
    }


def run_pair_runtime_repeated(
    *,
    controls: EntanglementControls,
    working_dir: Path,
    cycles: int,
    top_n: int,
    live_embeddings: bool,
    persist_summaries: bool,
    embedding_a_loc: float,
    embedding_b_loc: float,
    embedding_scale: float,
    embedding_drift: float,
    repeat_run_count: int,
    clean_run_reset: bool,
) -> Dict[str, object]:
    base_dir = Path(working_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    runs: List[Dict[str, object]] = []
    checkpoints: List[Dict[str, object]] = []
    comparison_paths: List[Path] = []

    for repeat_index in range(max(int(repeat_run_count), 1)):
        attempt_dir = base_dir / f"repeat_{repeat_index + 1:02d}"
        run_result = run_pair_runtime(
            controls=controls,
            working_dir=attempt_dir,
            cycles=cycles,
            top_n=top_n,
            live_embeddings=live_embeddings,
            persist_summaries=persist_summaries,
            embedding_a_loc=embedding_a_loc,
            embedding_b_loc=embedding_b_loc,
            embedding_scale=embedding_scale,
            embedding_drift=embedding_drift,
            clean_run_reset=clean_run_reset,
        )
        runs.append(run_result)
        checkpoints.append(dict(run_result["checkpoint"]))

    comparison_reports: List[Dict[str, object]] = []
    baseline_checkpoint = checkpoints[0] if checkpoints else {}
    for compare_index, checkpoint in enumerate(checkpoints[1:], start=2):
        comparison = compare_run_checkpoints(baseline_checkpoint, checkpoint)
        comparison["left_run"] = "repeat_01"
        comparison["right_run"] = f"repeat_{compare_index:02d}"
        comparison_reports.append(comparison)

        json_path = base_dir / f"repro_compare_01_vs_{compare_index:02d}.json"
        txt_path = base_dir / f"repro_compare_01_vs_{compare_index:02d}.txt"
        json_path.write_text(json.dumps(comparison, sort_keys=True, indent=2), encoding="utf-8")
        txt_path.write_text(render_run_checkpoint_comparison(comparison), encoding="utf-8")
        comparison_paths.extend([json_path, txt_path])

    return {
        "runs": runs,
        "checkpoints": checkpoints,
        "comparisons": comparison_reports,
        "comparison_paths": comparison_paths,
    }


def compare_run_checkpoints(left: Dict[str, object], right: Dict[str, object]) -> Dict[str, object]:
    static_matches = {
        "seed": left.get("seed") == right.get("seed"),
        "wormhole_nodes": left.get("wormhole_nodes") == right.get("wormhole_nodes"),
        "wormhole_fingerprint": left.get("wormhole_fingerprint") == right.get("wormhole_fingerprint"),
        "manifolds": left.get("manifolds") == right.get("manifolds"),
        "state_loads": _normalize_state_loads(left.get("state_loads", {})) == _normalize_state_loads(right.get("state_loads", {})),
        "scan_fingerprints": left.get("scan_fingerprints") == right.get("scan_fingerprints"),
    }
    sequence_matches: Dict[str, bool] = {}
    first_divergence: Optional[Dict[str, object]] = None
    for field in (
        "primary_wormhole_state_fingerprint_history",
        "secondary_wormhole_state_fingerprint_history",
        "primary_wormhole_edge_fingerprint_history",
        "secondary_wormhole_edge_fingerprint_history",
        "signature_a_history",
        "signature_b_history",
        "shared_flux_vector_history",
        "control_delta_history",
        "coherence_feedback_history",
        "shared_pair_clock_history",
        "phase_coherence_history",
        "mode_history",
        "hint_status_history",
        "hint_bias_history",
        "gate_state_history",
        "gate_reason_history",
        "gate_status_history",
        "nudge_rejection_history",
    ):
        left_values = list(left.get(field, []))
        right_values = list(right.get(field, []))
        sequence_matches[field] = left_values == right_values
        if first_divergence is None:
            first_divergence = _first_sequence_divergence(field, left_values, right_values)

    if first_divergence is None:
        for field, matched in static_matches.items():
            if not matched:
                first_divergence = {
                    "field": field,
                    "type": "static",
                    "left": left.get(field),
                    "right": right.get(field),
                }
                break

    return {
        "matches": all(static_matches.values()) and all(sequence_matches.values()),
        "static_matches": static_matches,
        "sequence_matches": sequence_matches,
        "first_divergence": first_divergence,
        "left_first_tick_phase_coherence": float(left.get("first_tick_phase_coherence", 0.0)),
        "right_first_tick_phase_coherence": float(right.get("first_tick_phase_coherence", 0.0)),
        "left_final_mode": str(left.get("final_mode", "unknown")),
        "right_final_mode": str(right.get("final_mode", "unknown")),
    }


def render_run_checkpoint_comparison(comparison: Dict[str, object]) -> str:
    lines = [
        f"[REPRO COMPARISON] {comparison.get('left_run', 'left')} vs {comparison.get('right_run', 'right')}",
        f"matches={bool(comparison.get('matches', False))}",
        f"left_first_tick_phase_coherence={float(comparison.get('left_first_tick_phase_coherence', 0.0)):.6f}",
        f"right_first_tick_phase_coherence={float(comparison.get('right_first_tick_phase_coherence', 0.0)):.6f}",
        f"left_final_mode={comparison.get('left_final_mode', 'unknown')}",
        f"right_final_mode={comparison.get('right_final_mode', 'unknown')}",
        "static_matches: " + ", ".join(f"{key}={value}" for key, value in dict(comparison.get("static_matches", {})).items()),
        "sequence_matches: " + ", ".join(f"{key}={value}" for key, value in dict(comparison.get("sequence_matches", {})).items()),
    ]
    divergence = comparison.get("first_divergence")
    if divergence:
        lines.append(
            "first_divergence: "
            + f"field={divergence.get('field', 'unknown')}"
            + (f" tick={int(divergence.get('tick_index'))}" if divergence.get("tick_index") is not None else "")
            + f" left={divergence.get('left')} right={divergence.get('right')}"
        )
    else:
        lines.append("first_divergence: none")
    return "\n".join(lines)


def run_pair_runtime_repeated_from_args(args: argparse.Namespace) -> Dict[str, object]:
    if not args.working_dir:
        raise ValueError("repeat-run mode requires --working-dir so comparison artifacts stay scoped")
    result = run_pair_runtime_repeated(
        controls=build_controls_from_args(args),
        working_dir=Path(args.working_dir),
        cycles=int(args.cycles),
        top_n=int(args.top_n),
        live_embeddings=bool(args.live_embeddings),
        persist_summaries=bool(args.persist_summaries),
        embedding_a_loc=float(args.embedding_a_loc),
        embedding_b_loc=float(args.embedding_b_loc),
        embedding_scale=float(args.embedding_scale),
        embedding_drift=float(args.embedding_drift),
        repeat_run_count=int(args.repeat_run_count),
        clean_run_reset=bool(args.clean_run_reset),
    )
    if result["comparisons"]:
        print(render_run_checkpoint_comparison(result["comparisons"][0]))
    return result


def run_pair_runtime_from_args(args: argparse.Namespace) -> Dict[str, object]:
    result = run_pair_runtime(
        controls=build_controls_from_args(args),
        working_dir=Path(args.working_dir) if args.working_dir else None,
        cycles=int(args.cycles),
        top_n=int(args.top_n),
        live_embeddings=bool(args.live_embeddings),
        persist_summaries=bool(args.persist_summaries),
        embedding_a_loc=float(args.embedding_a_loc),
        embedding_b_loc=float(args.embedding_b_loc),
        embedding_scale=float(args.embedding_scale),
        embedding_drift=float(args.embedding_drift),
        clean_run_reset=bool(args.clean_run_reset),
    )
    print(result["summaries"]["comparative"])
    print(result["summaries"]["replay"])
    return result


def build_pair_sweep_variants(args: argparse.Namespace, sweep_root_dir: Path) -> List[PairSweepVariant]:
    embedding_a_locs = list(args.sweep_embedding_a_locs or [float(args.embedding_a_loc)])
    embedding_b_locs = list(args.sweep_embedding_b_locs or [float(args.embedding_b_loc)])
    embedding_drifts = list(args.sweep_embedding_drifts or [float(args.embedding_drift)])
    cycle_counts = list(args.sweep_cycle_counts or [int(args.cycles)])
    seeds = list(args.sweep_seeds or [int(args.seed)])
    variants: List[PairSweepVariant] = []

    for variant_index, (embedding_a_loc, embedding_b_loc, embedding_drift, cycle_count, seed) in enumerate(
        product(embedding_a_locs, embedding_b_locs, embedding_drifts, cycle_counts, seeds),
        start=1,
    ):
        variant_id = (
            f"variant_{variant_index:03d}"
            f"_a{_format_float_token(float(embedding_a_loc))}"
            f"_b{_format_float_token(float(embedding_b_loc))}"
            f"_d{_format_float_token(float(embedding_drift))}"
            f"_c{int(cycle_count)}"
            f"_s{int(seed)}"
        )
        variants.append(
            PairSweepVariant(
                variant_id=variant_id,
                cycle_count=max(int(cycle_count), 1),
                seed=int(seed),
                embedding_a_loc=float(embedding_a_loc),
                embedding_b_loc=float(embedding_b_loc),
                embedding_scale=float(args.embedding_scale),
                embedding_drift=float(embedding_drift),
                working_dir=sweep_root_dir / variant_id,
            )
        )

    return variants


def run_pair_runtime_sweep(args: argparse.Namespace) -> Dict[str, object]:
    base_dir = Path(args.sweep_root_dir) if args.sweep_root_dir else _default_sweep_root_dir(args.working_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    variants = build_pair_sweep_variants(args, base_dir)
    records: List[Dict[str, object]] = []
    runs: List[Dict[str, object]] = []
    base_controls = build_controls_from_args(args)

    for variant in variants:
        controls = replace(base_controls, seed=int(variant.seed))
        run_result = run_pair_runtime(
            controls=controls,
            working_dir=variant.working_dir,
            cycles=int(variant.cycle_count),
            top_n=int(args.top_n),
            live_embeddings=True,
            persist_summaries=bool(args.persist_summaries),
            embedding_a_loc=float(variant.embedding_a_loc),
            embedding_b_loc=float(variant.embedding_b_loc),
            embedding_scale=float(variant.embedding_scale),
            embedding_drift=float(variant.embedding_drift),
            clean_run_reset=bool(args.clean_run_reset),
        )
        runs.append({"variant": variant, "result": run_result})
        records.append(
            summarize_sweep_variant(
                variant=variant,
                pair=run_result["pair"],
                controls=controls,
                live_embeddings=True,
            )
        )

    aggregate_paths = persist_sweep_outputs(records, base_dir)
    ranked_summary = aggregate_paths["ranked_summary"].read_text(encoding="utf-8")
    print(ranked_summary)
    return {
        "variants": variants,
        "runs": runs,
        "records": records,
        "output_paths": aggregate_paths,
    }


def summarize_sweep_variant(
    *,
    variant: PairSweepVariant,
    pair: EntangledSOLPair,
    controls: EntanglementControls,
    live_embeddings: bool,
) -> Dict[str, object]:
    replay = HippocampalReplay(working_dir=variant.working_dir)
    telemetry_records = replay.load_pair_telemetry_records(pair_id=pair.pair_id)
    trend = replay.summarize_coherence_trend(telemetry_records)
    switching = replay.summarize_mode_switching(telemetry_records)
    streaks = replay.summarize_status_streaks(telemetry_records)
    nudge_outcomes = replay.summarize_nudge_outcomes(
        telemetry_records,
        forward_window=int(controls.hint_gate_policy.forward_window),
    )
    gate_decisions = replay.summarize_hint_gate_decisions(
        telemetry_records,
        confidence_threshold=float(controls.hint_gate_policy.confidence_threshold),
        reliability_threshold=float(controls.hint_gate_policy.reliability_threshold),
        min_samples=int(controls.hint_gate_policy.min_samples),
        require_armed_status=bool(controls.hint_gate_policy.require_armed_status),
    )
    paper_diagnostics = replay.summarize_paper_diagnostic_proxies(telemetry_records)
    uncertainty_stub = replay.summarize_uncertainty_paper_recommendation(telemetry_records)
    diagnosis = replay.summarize_sweep_diagnosis(
        telemetry_records,
        min_mode_switch_samples=int(controls.min_mode_switch_samples),
        enter_decay_streak=int(controls.stabilizer_enter_decay_streak),
        cycle_count=int(variant.cycle_count),
    )
    advisory = replay.summarize_advisory_hints(telemetry_records)
    coherence_min, coherence_max = tuple(trend.get("coherence_range", (0.0, 0.0)))
    reasons = dict(switching.get("reason_counts", {}))
    statuses = dict(trend.get("status_counts", {}))
    occupancy = dict(switching.get("occupancy_counts", {}))
    transition_counts = dict(switching.get("transition_counts", {}))
    synchrony_margin = dict(paper_diagnostics.get("synchrony_margin", {}))
    basin_fragility = dict(paper_diagnostics.get("basin_fragility", {}))

    return {
        "variant_id": variant.variant_id,
        "pair_id": pair.pair_id,
        "working_dir": str(variant.working_dir),
        "cycles": int(variant.cycle_count),
        "seed": int(variant.seed),
        "live_embeddings": bool(live_embeddings),
        "embedding_a_loc": float(variant.embedding_a_loc),
        "embedding_b_loc": float(variant.embedding_b_loc),
        "embedding_scale": float(variant.embedding_scale),
        "embedding_drift": float(variant.embedding_drift),
        "aperture": float(controls.aperture),
        "damping": float(controls.damping),
        "phase_offset": float(controls.phase_offset),
        "hint_gate_enabled": bool(controls.hint_gate_policy.enabled),
        "hint_confidence_threshold": float(controls.hint_gate_policy.confidence_threshold),
        "hint_reliability_threshold": float(controls.hint_gate_policy.reliability_threshold),
        "hint_min_samples": int(controls.hint_gate_policy.min_samples),
        "hint_forward_window": int(controls.hint_gate_policy.forward_window),
        "bounded_nudges_enabled": bool(controls.hint_gate_policy.enable_bounded_nudges),
        "observe_nudge_feedback_scale": float(controls.hint_gate_policy.observe_nudge_feedback_scale),
        "near_pass_maturity_nudges_enabled": bool(controls.hint_gate_policy.enable_near_pass_maturity_nudges),
        "near_pass_confidence_gap_max": float(controls.hint_gate_policy.near_pass_confidence_gap_max),
        "near_pass_reliability_gap_max": float(controls.hint_gate_policy.near_pass_reliability_gap_max),
        "near_pass_sample_gap_max": int(controls.hint_gate_policy.near_pass_sample_gap_max),
        "near_pass_observe_feedback_scale": float(controls.hint_gate_policy.near_pass_observe_feedback_scale),
        "negative_collapse_stabilize_enabled": bool(controls.hint_gate_policy.enable_negative_collapse_stabilize),
        "nudge_reliability_floor": float(controls.hint_gate_policy.nudge_reliability_floor),
        "nudge_requires_stability": bool(controls.hint_gate_policy.nudge_requires_stability),
        "nudge_stability_window": int(controls.hint_gate_policy.nudge_stability_window),
        "min_history": int(controls.min_mode_switch_samples),
        "enter_decay_streak": int(controls.stabilizer_enter_decay_streak),
        "exit_improving_streak": int(controls.stabilizer_exit_improving_streak),
        "min_dwell": int(controls.stabilizer_min_dwell_ticks),
        "max_history": int(controls.max_history),
        "tick_count": int(trend.get("tick_count", 0)),
        "coherence_min": float(coherence_min),
        "coherence_max": float(coherence_max),
        "coherence_mean": float(trend.get("coherence_mean", 0.0)),
        "coherence_std": float(trend.get("coherence_std", 0.0)),
        "coherence_delta": float(trend.get("coherence_delta", 0.0)),
        "coherence_range_span": float(coherence_max - coherence_min),
        "coherence_target": float(trend.get("target", 0.0)),
        "latest_status": str(trend.get("latest_status", "unknown")),
        "final_mode": str(pair.controls.entangler_mode),
        "occupancy_counts": occupancy,
        "occupancy_active": int(occupancy.get("active", 0)),
        "occupancy_stabilizer": int(occupancy.get("Stabilizer", 0)),
        "status_counts": statuses,
        "decaying_count": int(statuses.get("decaying", 0)),
        "improving_count": int(statuses.get("improving", 0)),
        "stable_count": int(statuses.get("stable", 0)),
        "transition_total": int(switching.get("transition_total", 0)),
        "transition_counts": transition_counts,
        "transition_active_to_stabilizer": int(transition_counts.get("active->Stabilizer", 0)),
        "transition_stabilizer_to_active": int(transition_counts.get("Stabilizer->active", 0)),
        "reason_counts": reasons,
        "longest_decay_streak": int(streaks.get("longest_decay_streak", 0)),
        "longest_improving_streak": int(streaks.get("longest_improving_streak", 0)),
        "longest_stable_streak": int(streaks.get("longest_stable_streak", 0)),
        "first_stabilizer_tick": streaks.get("first_stabilizer_tick"),
        "nudge_tick_count": int(nudge_outcomes.get("tick_count", 0)),
        "nudge_attempt_count": int(nudge_outcomes.get("attempt_count", 0)),
        "nudge_applied_count": int(nudge_outcomes.get("applied_count", 0)),
        "nudge_rejection_count": int(nudge_outcomes.get("rejection_count", 0)),
        "nudge_apply_rate": float(nudge_outcomes.get("apply_rate", 0.0)),
        "nudge_positive_coherence_windows": int(nudge_outcomes.get("positive_coherence_windows", 0)),
        "nudge_positive_window_rate": float(nudge_outcomes.get("positive_window_rate", 0.0)),
        "nudge_stabilizer_entry_windows": int(nudge_outcomes.get("stabilizer_entry_windows", 0)),
        "nudge_stabilizer_entry_rate": float(nudge_outcomes.get("stabilizer_entry_rate", 0.0)),
        "nudge_mean_future_delta": float(nudge_outcomes.get("mean_future_delta", 0.0)),
        "nudge_reliability_mean": float(nudge_outcomes.get("reliability_mean", 0.0)),
        "nudge_stability_score_mean": float(nudge_outcomes.get("stability_score_mean", 0.0)),
        "nudge_clamp_count": int(nudge_outcomes.get("clamp_count", 0)),
        "nudge_clamp_rate": float(nudge_outcomes.get("clamp_rate", 0.0)),
        "nudge_mean_abs_aperture_delta": float(dict(nudge_outcomes.get("delta_abs_mean", {})).get("aperture", 0.0)),
        "nudge_mean_abs_damping_delta": float(dict(nudge_outcomes.get("delta_abs_mean", {})).get("damping", 0.0)),
        "nudge_mean_abs_phase_delta": float(dict(nudge_outcomes.get("delta_abs_mean", {})).get("phase_offset", 0.0)),
        "hint_gate_tick_count": int(gate_decisions.get("tick_count", 0)),
        "hint_gate_enabled_count": int(gate_decisions.get("enabled_count", 0)),
        "hint_gate_passed_count": int(gate_decisions.get("passed_count", 0)),
        "hint_gate_blocked_count": int(gate_decisions.get("blocked_count", 0)),
        "hint_gate_block_rate": float(gate_decisions.get("block_rate", 0.0)),
        "hint_gate_mean_confidence": float(gate_decisions.get("confidence_mean", 0.0)),
        "hint_gate_mean_reliability": float(gate_decisions.get("reliability_mean", 0.0)),
        "hint_gate_mean_sample_count": float(gate_decisions.get("sample_count_mean", 0.0)),
        "hint_gate_provisional_count": int(gate_decisions.get("provisional_count", 0)),
        "hint_gate_near_pass_count": int(gate_decisions.get("near_pass_count", 0)),
        "hint_gate_first_pass_tick": gate_decisions.get("first_pass_tick"),
        "hint_gate_first_block_tick": gate_decisions.get("first_block_tick"),
        "hint_gate_first_near_pass_tick": gate_decisions.get("first_near_pass_tick"),
        "hint_gate_first_near_pass_reason": gate_decisions.get("first_near_pass_reason"),
        "hint_gate_first_near_pass_status": gate_decisions.get("first_near_pass_status"),
        "hint_gate_first_near_pass_confidence_gap": float(gate_decisions.get("first_near_pass_confidence_gap", 0.0)),
        "hint_gate_first_near_pass_reliability_gap": float(gate_decisions.get("first_near_pass_reliability_gap", 0.0)),
        "hint_gate_first_near_pass_sample_gap": int(gate_decisions.get("first_near_pass_sample_gap", 0)),
        "hint_gate_first_pass_decision_reason": gate_decisions.get("first_pass_decision_reason"),
        "hint_gate_first_pass_pair_stability": float(gate_decisions.get("first_pass_pair_stability", 0.0)),
        "hint_gate_first_pass_local_stability": float(gate_decisions.get("first_pass_local_stability", 0.0)),
        "hint_gate_first_pass_pair_decay": float(gate_decisions.get("first_pass_pair_decay", 0.0)),
        "hint_gate_first_pass_amplitude_trend": float(gate_decisions.get("first_pass_amplitude_trend", 0.0)),
        "hint_gate_first_near_pass_decision_reason": gate_decisions.get("first_near_pass_decision_reason"),
        "hint_gate_first_near_pass_pair_stability": float(gate_decisions.get("first_near_pass_pair_stability", 0.0)),
        "hint_gate_first_near_pass_local_stability": float(gate_decisions.get("first_near_pass_local_stability", 0.0)),
        "hint_gate_first_near_pass_pair_decay": float(gate_decisions.get("first_near_pass_pair_decay", 0.0)),
        "hint_gate_first_near_pass_amplitude_trend": float(gate_decisions.get("first_near_pass_amplitude_trend", 0.0)),
        "hint_gate_longest_block_streak": int(gate_decisions.get("longest_block_streak", 0)),
        "hint_gate_passed_but_nudge_blocked_count": int(gate_decisions.get("passed_but_nudge_blocked_count", 0)),
        "paper_synchrony_margin": str(synchrony_margin.get("label", "unknown")),
        "paper_synchrony_basis": str(synchrony_margin.get("basis", "unknown")),
        "paper_synchrony_coupling_posture": str(synchrony_margin.get("coupling_posture", "unknown")),
        "paper_synchrony_evidence": ",".join(str(signal) for signal in synchrony_margin.get("evidence_signals", [])),
        "paper_synchrony_contradiction": str(synchrony_margin.get("contradiction_level", "unknown")),
        "paper_synchrony_boundary_state": str(synchrony_margin.get("boundary_state", "unknown")),
        "paper_synchrony_support_score": int(synchrony_margin.get("support_score", 0)),
        "paper_synchrony_risk_score": int(synchrony_margin.get("risk_score", 0)),
        "paper_synchrony_contradiction_count": len(list(synchrony_margin.get("contradiction_signals", []))),
        "paper_basin_fragility": str(basin_fragility.get("label", "unknown")),
        "paper_basin_support_score": int(basin_fragility.get("support_score", 0)),
        "paper_basin_risk_score": int(basin_fragility.get("risk_score", 0)),
        "paper_uncertainty_triggered": bool(uncertainty_stub.get("triggered", False)),
        "paper_uncertainty_intervention_class": str(uncertainty_stub.get("intervention_class", uncertainty_stub.get("reason", "none"))),
        "paper_uncertainty_desired_paper_role": str(uncertainty_stub.get("desired_paper_role", "none")),
        "paper_uncertainty_summary": str(uncertainty_stub.get("uncertainty_summary", uncertainty_stub.get("reason", ""))),
        "hint_latest_decision_reason": str(advisory.get("latest_decision_reason", "unknown")),
        "hint_latest_pair_stability": float(advisory.get("latest_pair_stability", 0.0)),
        "hint_latest_local_stability": float(advisory.get("latest_local_stability", 0.0)),
        "hint_latest_pair_decay": float(advisory.get("latest_pair_decay", 0.0)),
        "hint_latest_amplitude_trend": float(advisory.get("latest_amplitude_trend", 0.0)),
        "met_entry_policy": bool(diagnosis.get("met_entry_policy", False)),
        "entry_policy_tick": diagnosis.get("entry_policy_tick"),
        "diagnosis_label": str(diagnosis.get("label", "unknown")),
        "diagnosis_detail": str(diagnosis.get("detail", "")),
        "hint_gate_reason_counts": dict(gate_decisions.get("reason_counts", {})),
        "hint_gate_status_counts": dict(gate_decisions.get("status_counts", {})),
        "hint_gate_recommendation_counts": dict(gate_decisions.get("recommendation_counts", {})),
        "nudge_reason_counts": dict(nudge_outcomes.get("reason_counts", {})),
        "nudge_decision_reason_counts": dict(nudge_outcomes.get("decision_reason_counts", {})),
        "nudge_rejection_counts": dict(nudge_outcomes.get("rejection_counts", {})),
    }


def persist_sweep_outputs(records: Sequence[Dict[str, object]], sweep_root_dir: Path) -> Dict[str, Path]:
    from paper_finder_artifact import write_paper_finder_recommendation

    jsonl_path = sweep_root_dir / "sweep_summary.jsonl"
    csv_path = sweep_root_dir / "sweep_summary.csv"
    ranked_summary_path = sweep_root_dir / "sweep_ranked_summary.txt"
    compact_comparison_path = sweep_root_dir / "sweep_compact_comparison.txt"
    paper_diagnostics_path = sweep_root_dir / "sweep_paper_diagnostics.txt"
    paper_handoff_path = sweep_root_dir / "sweep_uncertainty_paper_handoff.md"
    paper_recommendation_path = sweep_root_dir / "paper_finder_recommendation.md"
    jsonl_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )
    write_sweep_csv(records, csv_path)
    ranked_summary_path.write_text(render_sweep_ranked_summary(records), encoding="utf-8")
    compact_comparison_path.write_text(render_sweep_compact_comparison(records), encoding="utf-8")
    paper_diagnostics_path.write_text(render_sweep_paper_diagnostics(records), encoding="utf-8")
    paper_handoff_path.write_text(render_sweep_uncertainty_paper_handoff(records), encoding="utf-8")
    write_paper_finder_recommendation(uncertainty_handoff_path=paper_handoff_path, output_path=paper_recommendation_path)
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "ranked_summary": ranked_summary_path,
        "compact_comparison": compact_comparison_path,
        "paper_diagnostics": paper_diagnostics_path,
        "paper_handoff": paper_handoff_path,
        "paper_recommendation": paper_recommendation_path,
    }


def write_sweep_csv(records: Sequence[Dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "variant_id",
        "pair_id",
        "working_dir",
        "cycles",
        "seed",
        "live_embeddings",
        "embedding_a_loc",
        "embedding_b_loc",
        "embedding_scale",
        "embedding_drift",
        "aperture",
        "damping",
        "phase_offset",
        "hint_gate_enabled",
        "hint_confidence_threshold",
        "hint_reliability_threshold",
        "hint_min_samples",
        "hint_forward_window",
        "bounded_nudges_enabled",
        "observe_nudge_feedback_scale",
        "near_pass_maturity_nudges_enabled",
        "near_pass_confidence_gap_max",
        "near_pass_reliability_gap_max",
        "near_pass_sample_gap_max",
        "near_pass_observe_feedback_scale",
        "negative_collapse_stabilize_enabled",
        "nudge_reliability_floor",
        "nudge_requires_stability",
        "nudge_stability_window",
        "min_history",
        "enter_decay_streak",
        "exit_improving_streak",
        "min_dwell",
        "max_history",
        "tick_count",
        "coherence_min",
        "coherence_max",
        "coherence_mean",
        "coherence_std",
        "coherence_delta",
        "coherence_range_span",
        "coherence_target",
        "latest_status",
        "final_mode",
        "occupancy_active",
        "occupancy_stabilizer",
        "decaying_count",
        "improving_count",
        "stable_count",
        "transition_total",
        "transition_active_to_stabilizer",
        "transition_stabilizer_to_active",
        "longest_decay_streak",
        "longest_improving_streak",
        "longest_stable_streak",
        "first_stabilizer_tick",
        "nudge_tick_count",
        "nudge_attempt_count",
        "nudge_applied_count",
        "nudge_rejection_count",
        "nudge_apply_rate",
        "nudge_positive_coherence_windows",
        "nudge_positive_window_rate",
        "nudge_stabilizer_entry_windows",
        "nudge_stabilizer_entry_rate",
        "nudge_mean_future_delta",
        "nudge_reliability_mean",
        "nudge_stability_score_mean",
        "nudge_clamp_count",
        "nudge_clamp_rate",
        "nudge_mean_abs_aperture_delta",
        "nudge_mean_abs_damping_delta",
        "nudge_mean_abs_phase_delta",
        "hint_gate_tick_count",
        "hint_gate_enabled_count",
        "hint_gate_passed_count",
        "hint_gate_blocked_count",
        "hint_gate_block_rate",
        "hint_gate_mean_confidence",
        "hint_gate_mean_reliability",
        "hint_gate_mean_sample_count",
        "hint_gate_provisional_count",
        "hint_gate_near_pass_count",
        "hint_gate_first_pass_tick",
        "hint_gate_first_block_tick",
        "hint_gate_first_near_pass_tick",
        "hint_gate_first_near_pass_reason",
        "hint_gate_first_near_pass_status",
        "hint_gate_first_near_pass_confidence_gap",
        "hint_gate_first_near_pass_reliability_gap",
        "hint_gate_first_near_pass_sample_gap",
        "hint_gate_first_pass_decision_reason",
        "hint_gate_first_pass_pair_stability",
        "hint_gate_first_pass_local_stability",
        "hint_gate_first_pass_pair_decay",
        "hint_gate_first_pass_amplitude_trend",
        "hint_gate_first_near_pass_decision_reason",
        "hint_gate_first_near_pass_pair_stability",
        "hint_gate_first_near_pass_local_stability",
        "hint_gate_first_near_pass_pair_decay",
        "hint_gate_first_near_pass_amplitude_trend",
        "hint_gate_longest_block_streak",
        "hint_gate_passed_but_nudge_blocked_count",
        "paper_synchrony_margin",
        "paper_synchrony_basis",
        "paper_synchrony_coupling_posture",
        "paper_synchrony_evidence",
        "paper_synchrony_contradiction",
        "paper_synchrony_boundary_state",
        "paper_synchrony_support_score",
        "paper_synchrony_risk_score",
        "paper_synchrony_contradiction_count",
        "paper_basin_fragility",
        "paper_basin_support_score",
        "paper_basin_risk_score",
        "paper_uncertainty_triggered",
        "paper_uncertainty_intervention_class",
        "paper_uncertainty_desired_paper_role",
        "paper_uncertainty_summary",
        "hint_latest_decision_reason",
        "hint_latest_pair_stability",
        "hint_latest_local_stability",
        "hint_latest_pair_decay",
        "hint_latest_amplitude_trend",
        "met_entry_policy",
        "entry_policy_tick",
        "diagnosis_label",
        "diagnosis_detail",
        "reason_counts",
        "status_counts",
        "transition_counts",
        "occupancy_counts",
        "hint_gate_reason_counts",
        "hint_gate_status_counts",
        "hint_gate_recommendation_counts",
        "nudge_reason_counts",
        "nudge_decision_reason_counts",
        "nudge_rejection_counts",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    **{key: record.get(key) for key in fieldnames},
                    "reason_counts": json.dumps(record.get("reason_counts", {}), sort_keys=True),
                    "status_counts": json.dumps(record.get("status_counts", {}), sort_keys=True),
                    "transition_counts": json.dumps(record.get("transition_counts", {}), sort_keys=True),
                    "occupancy_counts": json.dumps(record.get("occupancy_counts", {}), sort_keys=True),
                    "hint_gate_reason_counts": json.dumps(record.get("hint_gate_reason_counts", {}), sort_keys=True),
                    "hint_gate_status_counts": json.dumps(record.get("hint_gate_status_counts", {}), sort_keys=True),
                    "hint_gate_recommendation_counts": json.dumps(record.get("hint_gate_recommendation_counts", {}), sort_keys=True),
                    "nudge_reason_counts": json.dumps(record.get("nudge_reason_counts", {}), sort_keys=True),
                    "nudge_decision_reason_counts": json.dumps(record.get("nudge_decision_reason_counts", {}), sort_keys=True),
                    "nudge_rejection_counts": json.dumps(record.get("nudge_rejection_counts", {}), sort_keys=True),
                }
            )


def render_sweep_ranked_summary(records: Sequence[Dict[str, object]]) -> str:
    if not records:
        return "[PAIR SWEEP] no variants were executed."

    diagnosis_counts: Dict[str, int] = {}
    for record in records:
        label = str(record.get("diagnosis_label", "unknown"))
        diagnosis_counts[label] = diagnosis_counts.get(label, 0) + 1

    ranked_records = sorted(records, key=_sweep_rank_key, reverse=True)
    transition_variants = sum(1 for record in records if int(record.get("transition_active_to_stabilizer", 0)) > 0)
    entry_ready_variants = sum(1 for record in records if bool(record.get("met_entry_policy", False)))
    uncertainty_variants = sum(1 for record in records if bool(record.get("paper_uncertainty_triggered", False)))
    triggered_records = [record for record in records if bool(record.get("paper_uncertainty_triggered", False))]
    paper_priority = _best_paper_priority_record(records)
    lines = [
        f"[PAIR SWEEP] variants={len(records)}",
        f"Natural active->Stabilizer entries: {transition_variants}",
        f"Runs meeting current entry policy: {entry_ready_variants}",
        f"Paper uncertainty triggers: {uncertainty_variants}",
        "Paper-priority leader: " + _compact_bucket_line(paper_priority),
        "Paper-trigger consensus: " + _paper_trigger_consensus_summary(triggered_records, len(records)),
        "Diagnosis counts: "
        + ", ".join(f"{label}={count}" for label, count in sorted(diagnosis_counts.items())),
        "Synchrony labels: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_margin").items())),
        "Synchrony boundary states: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_boundary_state").items())),
        "Coupling postures: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_coupling_posture").items())),
        "Basin labels: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_basin_fragility").items())),
        "",
        "Ranked variants by natural decay pressure:",
    ]

    for record in ranked_records:
        lines.append(
            "  "
            + (
                f"{record['variant_id']} | seed={int(record['seed'])} | cycles={int(record['cycles'])}"
                f" | locA={float(record['embedding_a_loc']):.3f} | locB={float(record['embedding_b_loc']):.3f}"
                f" | drift={float(record['embedding_drift']):.3f} | transitions={int(record['transition_total'])}"
                f" | decay_streak={int(record['longest_decay_streak'])}"
                f" | coherence={float(record['coherence_min']):.3f}-{float(record['coherence_max']):.3f}"
                f" | delta={float(record['coherence_delta']):+.3f}"
                f" | gate={int(record.get('hint_gate_passed_count', 0))}/{int(record.get('hint_gate_enabled_count', 0))}"
                f" {_gate_diagnostic_fragment(record)}"
                f" | nudge={int(record.get('nudge_applied_count', 0))}/{int(record.get('nudge_attempt_count', 0))}"
                f" | n+={int(record.get('nudge_positive_coherence_windows', 0))}"
                f" | sync={record.get('paper_synchrony_margin', 'unknown')}/{record.get('paper_synchrony_boundary_state', 'unknown')}"
                f" | coupling={record.get('paper_synchrony_coupling_posture', 'unknown')}"
                f" | basin={record.get('paper_basin_fragility', 'unknown')}"
                f" | paper={'yes' if bool(record.get('paper_uncertainty_triggered', False)) else 'no'}"
                f" | final_mode={record['final_mode']} | diagnosis={record['diagnosis_label']}"
            )
        )
        lines.append(f"    detail: {record['diagnosis_detail']}")
        lines.append(
            "    paper: "
            + (
                f"intervention={record.get('paper_uncertainty_intervention_class', 'none')}; "
                f"role={record.get('paper_uncertainty_desired_paper_role', 'none')}"
            )
        )
        lines.append(f"    working_dir: {record['working_dir']}")

    return "\n".join(lines)


def render_sweep_compact_comparison(records: Sequence[Dict[str, object]]) -> str:
    if not records:
        return "[PAIR SWEEP COMPARISON] no variants were executed."

    ranked_records = sorted(records, key=_sweep_rank_key, reverse=True)
    diagnosis_counts = _count_diagnosis_labels(records)
    triggered_records = [record for record in records if bool(record.get("paper_uncertainty_triggered", False))]
    natural_entry = _best_ranked_record(
        ranked_records,
        lambda record: int(record.get("transition_active_to_stabilizer", 0)) > 0,
    )
    threshold_ready = _best_ranked_record(
        ranked_records,
        lambda record: bool(record.get("met_entry_policy", False))
        and int(record.get("transition_active_to_stabilizer", 0)) == 0,
    )
    decay_pressure = _best_ranked_record(
        ranked_records,
        lambda record: int(record.get("transition_active_to_stabilizer", 0)) == 0
        and (
            int(record.get("longest_decay_streak", 0)) > 0
            or float(record.get("coherence_delta", 0.0)) < 0.0
        ),
    )
    calm_long_run = _best_ranked_record(
        sorted(records, key=_calm_long_run_key, reverse=True),
        lambda record: str(record.get("diagnosis_label", "")) == "low_variance_candidate",
    )
    paper_priority = _best_paper_priority_record(records)

    lines = [
        f"[PAIR SWEEP COMPARISON] variants={len(records)}",
        "Diagnosis counts: "
        + ", ".join(f"{label}={count}" for label, count in sorted(diagnosis_counts.items())),
        "Best natural entry: " + _compact_bucket_line(natural_entry),
        "Best threshold-ready no switch: " + _compact_bucket_line(threshold_ready),
        "Strongest decay pressure without entry: " + _compact_bucket_line(decay_pressure),
        "Calmest long run: " + _compact_bucket_line(calm_long_run),
        "Best paper-triggered uncertainty: " + _compact_bucket_line(paper_priority),
        "Paper-trigger consensus: " + _paper_trigger_consensus_summary(triggered_records, len(records)),
        "Synchrony boundary states: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_boundary_state").items())),
        "Coupling postures: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_coupling_posture").items())),
        "",
        "Diagnosis-grouped leaders:",
    ]

    lines.extend(_render_diagnosis_grouped_winners(ranked_records, top_n=3))
    lines.extend(
        [
            "",
            "Parameter pockets:",
        ]
    )
    lines.extend(_render_parameter_pocket_summaries(records, ranked_records))
    lines.extend(
        [
            "",
            "Columns:",
            "rank | variant_id | cycles | seed | locA | locB | drift | mode | a2s | decay | coh_min | coh_max | delta | span | nudges | gate | n+ | sync | basin | paper | policy | switch_tick | policy_tick | diagnosis | rank_reason | working_dir",
            "",
        ]
    )

    for index, record in enumerate(ranked_records, start=1):
        lines.append(_render_compact_record_line(record, rank=str(index)))

    return "\n".join(lines)


def render_sweep_paper_diagnostics(records: Sequence[Dict[str, object]]) -> str:
    if not records:
        return "[PAIR SWEEP PAPER] no variants were executed."

    ranked_records = sorted(records, key=_paper_priority_key, reverse=True)
    lines = [
        f"[PAIR SWEEP PAPER] variants={len(records)}",
        "Synchrony labels: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_margin").items())),
        "Synchrony boundary states: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_boundary_state").items())),
        "Coupling postures: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_synchrony_coupling_posture").items())),
        "Basin labels: " + ", ".join(f"{label}={count}" for label, count in sorted(_count_label_field(records, "paper_basin_fragility").items())),
        f"Uncertainty triggers: {sum(1 for record in records if bool(record.get('paper_uncertainty_triggered', False)))}",
        "",
        "Variant paper-facing diagnostics:",
    ]
    for record in ranked_records:
        lines.append(
            "  "
            + (
                f"{record['variant_id']} | sync={record.get('paper_synchrony_margin', 'unknown')}"
                f" ({int(record.get('paper_synchrony_support_score', 0))}/{int(record.get('paper_synchrony_risk_score', 0))})"
                f" | basin={record.get('paper_basin_fragility', 'unknown')}"
                f" ({int(record.get('paper_basin_support_score', 0))}/{int(record.get('paper_basin_risk_score', 0))})"
                f" | contradictions={int(record.get('paper_synchrony_contradiction_count', 0))}"
                f" | basis={record.get('paper_synchrony_basis', 'unknown')}"
                f" | coupling={record.get('paper_synchrony_coupling_posture', 'unknown')}"
                f" | boundary={record.get('paper_synchrony_boundary_state', 'unknown')}"
                f" | contradiction={record.get('paper_synchrony_contradiction', 'unknown')}"
                f" | paper={'yes' if bool(record.get('paper_uncertainty_triggered', False)) else 'no'}"
            )
        )
        lines.append(
            "    "
            + (
                f"intervention={record.get('paper_uncertainty_intervention_class', 'none')} | "
                f"role={record.get('paper_uncertainty_desired_paper_role', 'none')}"
            )
        )
        lines.append(f"    evidence: {record.get('paper_synchrony_evidence', 'none') or 'none'}")
        lines.append(f"    summary: {record.get('paper_uncertainty_summary', '')}")
        lines.append(f"    working_dir: {record['working_dir']}")
    return "\n".join(lines)


def render_sweep_uncertainty_paper_handoff(records: Sequence[Dict[str, object]]) -> str:
    if not records:
        return "# UNCERTAINTY TO PAPER RECOMMENDATION\n\nNo sweep variants were executed."

    selected = _best_paper_priority_record(records)
    if selected is None:
        return "# UNCERTAINTY TO PAPER RECOMMENDATION\n\nNo sweep variant crossed the bounded uncertainty trigger."

    triggered = [record for record in records if bool(record.get("paper_uncertainty_triggered", False))]
    hypotheses = _local_hypotheses_for_record(selected)
    telemetry_fields = ", ".join(_telemetry_fields_for_record(selected))
    replay_signals = ", ".join(_replay_signals_for_record(selected))
    regimes = ", ".join(_regime_labels_for_record(selected))
    consensus_summary = _paper_trigger_consensus_summary(triggered, len(records))
    selection_basis = _paper_selection_basis(selected, triggered, len(records))
    return "\n".join(
        [
            "# UNCERTAINTY TO PAPER RECOMMENDATION",
            "",
            f"Selected variant: {selected['variant_id']}",
            f"Working dir: {selected['working_dir']}",
            f"Sweep trigger coverage: {len(triggered)}/{len(records)} variants",
            f"Selection basis: {selection_basis}",
            f"Consensus pattern: {consensus_summary}",
            "",
            "## Uncertainty summary",
            f"- current bottleneck: {selected.get('paper_uncertainty_summary', '')}",
            f"- why current repo knowledge is still insufficient: {_unresolved_summary_for_record(selected)}",
            f"- why this is stable uncertainty rather than a one-off failure: {_stable_uncertainty_reason(selected)}",
            "",
            "## Observed signals",
            f"- key telemetry fields: {telemetry_fields}",
            f"- key replay or sweep signals: {replay_signals}",
            f"- recent regimes or labels involved: {regimes}",
            "",
            "## Current local explanations",
            f"- working hypothesis 1: {hypotheses[0]}",
            f"- working hypothesis 2: {hypotheses[1]}",
            f"- what remains unresolved or conflicting: {_unresolved_summary_for_record(selected)}",
            "",
            "## Outside help needed",
            f"- intervention class: {selected.get('paper_uncertainty_intervention_class', 'diagnostics')}",
            f"- desired paper role: {selected.get('paper_uncertainty_desired_paper_role', 'one paper')}",
            "- preferred search envelope: one paper",
            "",
            "## Search guardrails",
            "- avoid broad literature survey: yes",
            f"- novelty relative to current `working_mind`: {_novelty_summary_for_record(selected)}",
            f"- stop condition for searching: {_stop_condition_for_record(selected)}",
            "",
            "## Expected outputs",
            "- one recommended paper or a very small candidate set",
            "- stable source URL",
            "- suggested local filename",
            "- one-paragraph rationale tied back to the uncertainty summary",
            "- ready handoff into `paper-intake-handoff-template.md` if accepted",
        ]
    )
def _sweep_rank_key(record: Dict[str, object]) -> Tuple[int, int, float, float, int]:
    decay_pressure = max(-float(record.get("coherence_delta", 0.0)), 0.0)
    return (
        int(int(record.get("transition_active_to_stabilizer", 0)) > 0),
        int(record.get("longest_decay_streak", 0)),
        decay_pressure,
        float(record.get("coherence_range_span", 0.0)),
        int(bool(record.get("met_entry_policy", False))),
    )


def _count_diagnosis_labels(records: Sequence[Dict[str, object]]) -> Dict[str, int]:
    diagnosis_counts: Dict[str, int] = {}
    for record in records:
        label = str(record.get("diagnosis_label", "unknown"))
        diagnosis_counts[label] = diagnosis_counts.get(label, 0) + 1
    return diagnosis_counts


def _count_label_field(records: Sequence[Dict[str, object]], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        label = str(record.get(field, "unknown"))
        counts[label] = counts.get(label, 0) + 1
    return counts


def _paper_priority_key(record: Dict[str, object]) -> Tuple[int, int, int, int, float, float, int, int, float]:
    return (
        int(bool(record.get("paper_uncertainty_triggered", False))),
        int(record.get("paper_synchrony_risk_score", 0)) + int(record.get("paper_basin_risk_score", 0)),
        int(record.get("paper_synchrony_contradiction_count", 0)),
        int(record.get("hint_gate_near_pass_count", 0)),
        -float(record.get("hint_gate_first_near_pass_confidence_gap", 1.0)),
        -float(record.get("hint_gate_first_near_pass_reliability_gap", 1.0)),
        -int(record.get("hint_gate_first_near_pass_sample_gap", 999)),
        int(record.get("longest_decay_streak", 0)),
        max(-float(record.get("coherence_delta", 0.0)), 0.0),
    )


def _best_paper_priority_record(records: Sequence[Dict[str, object]]) -> Optional[Dict[str, object]]:
    triggered = [record for record in records if bool(record.get("paper_uncertainty_triggered", False))]
    if not triggered:
        return None
    return sorted(triggered, key=_paper_priority_key, reverse=True)[0]


def _paper_trigger_consensus_summary(triggered: Sequence[Dict[str, object]], total_records: int) -> str:
    if not triggered:
        return "no bounded uncertainty trigger"

    def dominant(field: str) -> Tuple[str, int]:
        counts = _count_label_field(triggered, field)
        label, count = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0]
        return label, count

    sync_label, sync_count = dominant("paper_synchrony_margin")
    basin_label, basin_count = dominant("paper_basin_fragility")
    diagnosis_label, diagnosis_count = dominant("diagnosis_label")
    intervention_label, intervention_count = dominant("paper_uncertainty_intervention_class")
    unanimous = len(triggered) == total_records and all(
        count == len(triggered)
        for count in (sync_count, basin_count, diagnosis_count, intervention_count)
    )
    prefix = "unanimous sweep consensus" if unanimous else "dominant triggered pattern"
    return (
        f"{prefix}: intervention={intervention_label} ({intervention_count}/{len(triggered)}), "
        f"sync={sync_label} ({sync_count}/{len(triggered)}), "
        f"basin={basin_label} ({basin_count}/{len(triggered)}), "
        f"diagnosis={diagnosis_label} ({diagnosis_count}/{len(triggered)})"
    )


def _paper_selection_basis(
    selected: Dict[str, object],
    triggered: Sequence[Dict[str, object]],
    total_records: int,
) -> str:
    if len(triggered) == total_records:
        return (
            "representative triggered variant chosen from a sweep-wide consensus, "
            f"favoring stronger near-pass maturity (near-passes={int(selected.get('hint_gate_near_pass_count', 0))}, "
            f"confidence-gap={float(selected.get('hint_gate_first_near_pass_confidence_gap', 0.0)):.2f}, "
            f"reliability-gap={float(selected.get('hint_gate_first_near_pass_reliability_gap', 0.0)):.2f})"
        )
    return (
        "highest-priority triggered variant chosen by risk, contradiction count, and near-pass maturity, "
        f"with near-passes={int(selected.get('hint_gate_near_pass_count', 0))}"
    )


def _best_ranked_record(
    ranked_records: Sequence[Dict[str, object]],
    predicate,
) -> Optional[Dict[str, object]]:
    for record in ranked_records:
        if predicate(record):
            return record
    return None


def _calm_long_run_key(record: Dict[str, object]) -> Tuple[int, float, int]:
    return (
        int(record.get("cycles", 0)),
        -float(record.get("coherence_range_span", 0.0)),
        -int(record.get("longest_decay_streak", 0)),
    )


def _compact_bucket_line(record: Optional[Dict[str, object]]) -> str:
    if record is None:
        return "none"
    return (
        f"{record['variant_id']}"
        f" (cycles={int(record['cycles'])}, seed={int(record['seed'])}, "
        f"diagnosis={record['diagnosis_label']}, gate={int(record.get('hint_gate_passed_count', 0))}/{int(record.get('hint_gate_enabled_count', 0))}"
        f" {_gate_diagnostic_fragment(record)}, sync={record.get('paper_synchrony_margin', 'unknown')}/{record.get('paper_synchrony_boundary_state', 'unknown')}, coupling={record.get('paper_synchrony_coupling_posture', 'unknown')}, "
        f"basin={record.get('paper_basin_fragility', 'unknown')}, paper={'yes' if bool(record.get('paper_uncertainty_triggered', False)) else 'no'}, reason={_compact_rank_reason(record)})"
    )


def _compact_rank_reason(record: Dict[str, object]) -> str:
    if int(record.get("transition_active_to_stabilizer", 0)) > 0:
        return "entered"
    if bool(record.get("met_entry_policy", False)):
        return "threshold_ready_no_switch"
    if int(record.get("longest_decay_streak", 0)) > 0 or float(record.get("coherence_delta", 0.0)) < 0.0:
        return "decay_pressure"
    if str(record.get("diagnosis_label", "")) == "runtime_too_short_candidate":
        return "too_short"
    return "calm"


def _render_diagnosis_grouped_winners(
    ranked_records: Sequence[Dict[str, object]],
    top_n: int,
) -> List[str]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for record in ranked_records:
        label = str(record.get("diagnosis_label", "unknown"))
        grouped.setdefault(label, []).append(record)

    lines: List[str] = []
    for label in sorted(grouped):
        records = grouped[label][:top_n]
        lines.append(f"{label}: top {len(records)}")
        for index, record in enumerate(records, start=1):
            lines.append(_render_compact_record_line(record, rank=f"{label}#{index}"))
    return lines


def _render_parameter_pocket_summaries(
    records: Sequence[Dict[str, object]],
    ranked_records: Sequence[Dict[str, object]],
) -> List[str]:
    lines: List[str] = []
    lines.extend(_render_single_parameter_pocket_summary("cycles", _group_records_by_cycles(records), ranked_records))
    lines.append("")
    lines.extend(_render_single_parameter_pocket_summary("drift", _group_records_by_drift(records), ranked_records))
    lines.append("")
    lines.extend(_render_single_parameter_pocket_summary("loc_pair", _group_records_by_location_pair(records), ranked_records))
    return lines


def _render_single_parameter_pocket_summary(
    label: str,
    grouped_records: Dict[str, List[Dict[str, object]]],
    ranked_records: Sequence[Dict[str, object]],
) -> List[str]:
    lines = [
        f"[{label}] key | runs | entries | mean_span | mean_decay | top_variant | top_reason",
    ]
    for key in sorted(grouped_records):
        pocket_records = grouped_records[key]
        top_record = _best_ranked_record(ranked_records, lambda record, ids={id(item) for item in pocket_records}: id(record) in ids)
        lines.append(
            " | ".join(
                [
                    key,
                    str(len(pocket_records)),
                    str(sum(1 for record in pocket_records if int(record.get("transition_active_to_stabilizer", 0)) > 0)),
                    f"{_mean_metric(pocket_records, 'coherence_range_span'):.3f}",
                    f"{_mean_metric(pocket_records, 'longest_decay_streak'):.2f}",
                    "-" if top_record is None else str(top_record["variant_id"]),
                    "-" if top_record is None else _compact_rank_reason(top_record),
                ]
            )
        )
    return lines


def _group_records_by_cycles(records: Sequence[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for record in records:
        key = str(int(record.get("cycles", 0)))
        grouped.setdefault(key, []).append(record)
    return grouped


def _group_records_by_drift(records: Sequence[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for record in records:
        key = f"{float(record.get('embedding_drift', 0.0)):.3f}"
        grouped.setdefault(key, []).append(record)
    return grouped


def _group_records_by_location_pair(records: Sequence[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for record in records:
        key = (
            f"{float(record.get('embedding_a_loc', 0.0)):.3f}/"
            f"{float(record.get('embedding_b_loc', 0.0)):.3f}"
        )
        grouped.setdefault(key, []).append(record)
    return grouped


def _mean_metric(records: Sequence[Dict[str, object]], key: str) -> float:
    if not records:
        return 0.0
    return sum(float(record.get(key, 0.0)) for record in records) / float(len(records))


def _render_compact_record_line(record: Dict[str, object], rank: str) -> str:
    policy_flag = "yes" if bool(record.get("met_entry_policy", False)) else "no"
    switch_tick = record.get("first_stabilizer_tick")
    policy_tick = record.get("entry_policy_tick")
    gate_fragment = (
        f"{int(record.get('hint_gate_passed_count', 0))}/{int(record.get('hint_gate_enabled_count', 0))}"
        f" {_gate_diagnostic_fragment(record)}"
    )
    return " | ".join(
        [
            rank,
            str(record["variant_id"]),
            str(int(record["cycles"])),
            str(int(record["seed"])),
            f"{float(record['embedding_a_loc']):.3f}",
            f"{float(record['embedding_b_loc']):.3f}",
            f"{float(record['embedding_drift']):.3f}",
            str(record["final_mode"]),
            str(int(record.get("transition_active_to_stabilizer", 0))),
            str(int(record.get("longest_decay_streak", 0))),
            f"{float(record['coherence_min']):.3f}",
            f"{float(record['coherence_max']):.3f}",
            f"{float(record['coherence_delta']):+.3f}",
            f"{float(record['coherence_range_span']):.3f}",
            f"{int(record.get('nudge_applied_count', 0))}/{int(record.get('nudge_attempt_count', 0))}",
            gate_fragment,
            str(int(record.get("nudge_positive_coherence_windows", 0))),
            f"{record.get('paper_synchrony_margin', 'unknown')}/{record.get('paper_synchrony_boundary_state', 'unknown')}",
            str(record.get("paper_basin_fragility", "unknown")),
            "yes" if bool(record.get("paper_uncertainty_triggered", False)) else "no",
            policy_flag,
            "-" if switch_tick is None else str(int(switch_tick)),
            "-" if policy_tick is None else str(int(policy_tick)),
            str(record["diagnosis_label"]),
            _compact_rank_reason(record),
            str(record["working_dir"]),
        ]
    )


def _top_gate_reason_fragment(record: Dict[str, object]) -> str:
    reason_counts = dict(record.get("hint_gate_reason_counts", {}))
    if not reason_counts:
        return "top=none"
    reason, count = next(iter(reason_counts.items()))
    return f"top={reason}:{int(count)}"


def _gate_diagnostic_fragment(record: Dict[str, object]) -> str:
    fragments = [_top_gate_reason_fragment(record)]
    first_pass_tick = record.get("hint_gate_first_pass_tick")
    if first_pass_tick is not None:
        fragments.append(f"pass@{int(first_pass_tick)}")
    near_pass_tick = record.get("hint_gate_first_near_pass_tick")
    if near_pass_tick is not None:
        fragments.append(
            (
                f"near@{int(near_pass_tick)}:{record.get('hint_gate_first_near_pass_reason', 'unknown')}"
                f"/c{float(record.get('hint_gate_first_near_pass_confidence_gap', 0.0)):.2f}"
                f"/r{float(record.get('hint_gate_first_near_pass_reliability_gap', 0.0)):.2f}"
                f"/n{int(record.get('hint_gate_first_near_pass_sample_gap', 0))}"
            )
        )
    return " ".join(fragments)


def _telemetry_fields_for_record(record: Dict[str, object]) -> List[str]:
    intervention = str(record.get("paper_uncertainty_intervention_class", "diagnostics"))
    if intervention == "topology design":
        return [
            "phase_coherence",
            "entangler_coherence_delta",
            "entangler_coherence_status",
            "wormhole_aperture",
            "damping",
            "phase_offset",
            "entanglement_strength",
        ]
    if intervention in {"control policy", "diagnostics"}:
        return [
            "phase_coherence",
            "entangler_coherence_delta",
            "entangler_coherence_status",
            "entangler_hint_gate_reason",
            "entangler_hint_gate_passed",
            "entangler_nudge_applied",
        ]
    return [
        "phase_coherence",
        "entangler_mode",
        "entangler_transition_reason",
        "phonon_hint_pair_stability",
        "phonon_hint_pair_decay",
        "phonon_hint_amplitude_trend",
    ]


def _replay_signals_for_record(record: Dict[str, object]) -> List[str]:
    intervention = str(record.get("paper_uncertainty_intervention_class", "diagnostics"))
    if intervention == "topology design":
        return ["coherence trend", "coupling posture summary", "paper diagnostic summary", "sweep ranking"]
    if intervention in {"control policy", "diagnostics"}:
        return ["coherence trend", "hint gate summary", "nudge outcome summary", "sweep ranking"]
    return ["mode switching", "status streaks", "paper diagnostic summary", "sweep ranking"]


def _regime_labels_for_record(record: Dict[str, object]) -> List[str]:
    return [
        str(record.get("paper_synchrony_margin", "unknown")),
        f"coupling:{record.get('paper_synchrony_coupling_posture', 'unknown')}",
        str(record.get("paper_basin_fragility", "unknown")),
        str(record.get("diagnosis_label", "unknown")),
    ]


def _local_hypotheses_for_record(record: Dict[str, object]) -> List[str]:
    intervention = str(record.get("paper_uncertainty_intervention_class", "diagnostics"))
    coupling_posture = str(record.get("paper_synchrony_coupling_posture", "unknown"))
    if intervention == "topology design" or coupling_posture == "weak":
        return [
            "The pair may sit outside a favorable synchronizable region because the current coupling posture is too weak or misaligned.",
            "Local threshold tuning may be secondary to aperture, damping, phase, or coupling-geometry changes in this neighborhood.",
        ]
    if intervention in {"control policy", "diagnostics"}:
        return [
            "The hint gate may still be conservative relative to the actual synchrony boundary in this neighborhood.",
            "The pair may sit in a structurally unfavorable synchronizable region even when local evidence intermittently improves.",
        ]
    return [
        "The current calm regime may be locally recoverable but too narrow to survive nearby variation.",
        "The current calm regime may reflect a genuinely broad basin that the existing sweep is undersampling.",
    ]


def _unresolved_summary_for_record(record: Dict[str, object]) -> str:
    if str(record.get("paper_uncertainty_intervention_class", "diagnostics")) == "topology design":
        return (
            f"Current sweep evidence points to {record.get('paper_synchrony_coupling_posture', 'unknown')} coupling posture with "
            f"{record.get('paper_synchrony_margin', 'unknown')} synchrony, but does not yet show which topology or posture change would recover synchronizability."
        )
    return (
        f"Current sweep evidence leaves {record.get('paper_synchrony_margin', 'unknown')} synchrony posture and "
        f"{record.get('paper_basin_fragility', 'unknown')} basin posture only partially explained by local diagnostics."
    )


def _stable_uncertainty_reason(record: Dict[str, object]) -> str:
    return (
        f"The trigger persists across gate blocks={int(record.get('hint_gate_blocked_count', 0))}, "
        f"near-passes={int(record.get('hint_gate_near_pass_count', 0))}, contradictions={int(record.get('paper_synchrony_contradiction_count', 0))}, "
        f"and diagnosis={record.get('diagnosis_label', 'unknown')}."
    )


def _novelty_summary_for_record(record: Dict[str, object]) -> str:
    if str(record.get("paper_uncertainty_intervention_class", "diagnostics")) == "topology design":
        return "Extend beyond the current synchrony-margin and basin-stability seeds with a more specific topology-aware synchronization or controllability source."
    if str(record.get("paper_uncertainty_intervention_class", "diagnostics")) in {"control policy", "diagnostics"}:
        return "Extend beyond the current synchrony-margin and basin-stability seeds with a tighter synchronization feasibility or controllability source."
    return "Extend beyond the current basin-stability seed with a source that sharpens perturbation resilience or neighborhood persistence."


def _stop_condition_for_record(record: Dict[str, object]) -> str:
    if str(record.get("paper_uncertainty_intervention_class", "diagnostics")) in {"control policy", "topology design", "diagnostics"}:
        return "Stop if nearby variants move the synchrony label to favorable or if local diagnostics clearly explain the blocked regime."
    return "Stop if nearby variants move the basin label to broad or if replay evidence clearly demonstrates durable recovery." 


def _default_sweep_root_dir(working_dir: Optional[str]) -> Path:
    if working_dir:
        return Path(working_dir) / "sweep_runs"
    return Path(__file__).resolve().parent / "working_data" / "sweep_runs"


def _reset_runtime_working_dir(working_dir: Path) -> None:
    if working_dir.exists():
        shutil.rmtree(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)


def _count_values(values: Sequence[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _normalize_state_loads(state_loads: object) -> Dict[str, object]:
    normalized: Dict[str, object] = {}
    for channel_id, payload in dict(state_loads or {}).items():
        payload_dict = dict(payload or {})
        normalized[str(channel_id)] = {
            key: value
            for key, value in payload_dict.items()
            if key != "state_path"
        }
    return normalized


def _first_sequence_divergence(field: str, left_values: Sequence[object], right_values: Sequence[object]) -> Optional[Dict[str, object]]:
    max_len = max(len(left_values), len(right_values))
    for index in range(max_len):
        left_value = left_values[index] if index < len(left_values) else None
        right_value = right_values[index] if index < len(right_values) else None
        if left_value != right_value:
            return {
                "field": field,
                "type": "sequence",
                "tick_index": index + 1,
                "left": left_value,
                "right": right_value,
            }
    return None


def _format_float_token(value: float) -> str:
    token = f"{float(value):.3f}".replace("-", "m").replace(".", "p")
    return token


def main():
    parser = build_pair_runtime_parser()
    args = parser.parse_args()
    if args.sweep and not args.live_embeddings:
        parser.error("Sweep mode requires live embeddings so the sweep exercises the real runtime.")
    if args.sweep and int(args.repeat_run_count) > 1:
        parser.error("Repeat-run mode is currently supported only for non-sweep runtimes.")
    if args.sweep:
        return run_pair_runtime_sweep(args)
    if int(args.repeat_run_count) > 1:
        return run_pair_runtime_repeated_from_args(args)
    return run_pair_runtime_from_args(args)


def build_pair_runtime_parser() -> argparse.ArgumentParser:
    parser = PairRuntimeArgumentParser(description="Run the entangled pair runtime with configurable Entangler switching thresholds.")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--working-dir", default=None)
    parser.add_argument(
        "--runtime-preset",
        choices=sorted(PAIR_RUNTIME_PRESETS),
        default=None,
        help="Apply an evidence-backed runtime preset before parsing explicit overrides.",
    )
    parser.add_argument("--sweep", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--sweep-root-dir", default=None)
    parser.add_argument("--sweep-embedding-a-locs", type=float, nargs="+", default=None)
    parser.add_argument("--sweep-embedding-b-locs", type=float, nargs="+", default=None)
    parser.add_argument("--sweep-embedding-drifts", type=float, nargs="+", default=None)
    parser.add_argument("--sweep-cycle-counts", type=int, nargs="+", default=None)
    parser.add_argument("--sweep-seeds", type=int, nargs="+", default=None)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--clean-run-reset", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--repeat-run-count", type=int, default=1)
    parser.add_argument("--wormhole-count", type=int, default=12)
    parser.add_argument("--aperture", type=float, default=0.25)
    parser.add_argument("--damping", type=float, default=0.85)
    parser.add_argument("--phase-offset", type=float, default=0.15)
    parser.add_argument("--entangler-mode", choices=["active", "Stabilizer"], default="active")
    parser.add_argument("--min-history", type=int, default=3)
    parser.add_argument("--enter-decay-streak", type=int, default=2)
    parser.add_argument("--exit-improving-streak", type=int, default=3)
    parser.add_argument("--min-dwell", type=int, default=2)
    parser.add_argument("--max-history", type=int, default=16)
    parser.add_argument("--enable-hint-gate", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--hint-confidence-threshold", type=float, default=0.55)
    parser.add_argument("--hint-reliability-threshold", type=float, default=0.60)
    parser.add_argument("--hint-max-age-ticks", type=int, default=2)
    parser.add_argument("--hint-min-samples", type=int, default=3)
    parser.add_argument("--hint-forward-window", type=int, default=2)
    parser.add_argument("--enable-bounded-nudges", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enable-negative-collapse-stabilize", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--nudge-aperture-max-step", type=float, default=0.04)
    parser.add_argument("--nudge-damping-max-step", type=float, default=0.025)
    parser.add_argument("--nudge-phase-max-step", type=float, default=0.08)
    parser.add_argument("--nudge-reliability-floor", type=float, default=0.75)
    parser.add_argument("--nudge-requires-stability", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--nudge-stability-window", type=int, default=4)
    parser.add_argument("--enable-near-pass-maturity-nudges", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--near-pass-confidence-gap-max", type=float, default=0.10)
    parser.add_argument("--near-pass-reliability-gap-max", type=float, default=0.12)
    parser.add_argument("--near-pass-sample-gap-max", type=int, default=0)
    parser.add_argument("--near-pass-observe-feedback-scale", type=float, default=0.20)
    parser.add_argument("--embedding-a-loc", type=float, default=0.50)
    parser.add_argument("--embedding-b-loc", type=float, default=0.55)
    parser.add_argument("--embedding-scale", type=float, default=0.20)
    parser.add_argument("--embedding-drift", type=float, default=0.04)
    parser.add_argument("--top-n", type=int, default=6)
    parser.add_argument("--live-embeddings", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--persist-summaries", action=argparse.BooleanOptionalAction, default=True)
    parser.remember_base_defaults()
    return parser


def build_controls_from_args(args: argparse.Namespace) -> EntanglementControls:
    return EntanglementControls(
        wormhole_count=int(args.wormhole_count),
        aperture=float(args.aperture),
        damping=float(args.damping),
        phase_offset=float(args.phase_offset),
        entangler_mode=str(args.entangler_mode),
        min_mode_switch_samples=int(args.min_history),
        stabilizer_enter_decay_streak=int(args.enter_decay_streak),
        stabilizer_exit_improving_streak=int(args.exit_improving_streak),
        stabilizer_min_dwell_ticks=int(args.min_dwell),
        max_history=int(args.max_history),
        seed=int(args.seed),
        hint_gate_policy=HintGatingPolicy(
            enabled=bool(args.enable_hint_gate),
            confidence_threshold=float(args.hint_confidence_threshold),
            reliability_threshold=float(args.hint_reliability_threshold),
            max_age_ticks=int(args.hint_max_age_ticks),
            min_samples=int(args.hint_min_samples),
            forward_window=int(args.hint_forward_window),
            enable_bounded_nudges=bool(args.enable_bounded_nudges),
            enable_negative_collapse_stabilize=bool(args.enable_negative_collapse_stabilize),
            nudge_aperture_max_step=float(args.nudge_aperture_max_step),
            nudge_damping_max_step=float(args.nudge_damping_max_step),
            nudge_phase_max_step=float(args.nudge_phase_max_step),
            nudge_reliability_floor=float(args.nudge_reliability_floor),
            nudge_requires_stability=bool(args.nudge_requires_stability),
            nudge_stability_window=int(args.nudge_stability_window),
            enable_near_pass_maturity_nudges=bool(args.enable_near_pass_maturity_nudges),
            near_pass_confidence_gap_max=float(args.near_pass_confidence_gap_max),
            near_pass_reliability_gap_max=float(args.near_pass_reliability_gap_max),
            near_pass_sample_gap_max=int(args.near_pass_sample_gap_max),
            near_pass_observe_feedback_scale=float(args.near_pass_observe_feedback_scale),
        ),
    )


if __name__ == "__main__":
    main()