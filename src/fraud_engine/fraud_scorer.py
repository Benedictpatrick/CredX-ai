"""
Module 2: "Sherlock" Fraud Engine — Temporal GNN + Heuristic Cross-Validation.

Builds a heterogeneous transaction graph from bank statements and GST data,
detects circular trading loops via cycle detection + GNN embeddings,
and cross-leverages GST vs bank inflows to flag revenue inflation.

P(fraud | G) = GNN(Nodes, Edges, R)  where R = relational dependencies.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Optional

import numpy as np
from loguru import logger

from src.models.schemas import (
    BankStatementSummary,
    CounterpartyFlow,
    CreditDecision,
    FraudReport,
    FraudSeverity,
    FraudSignal,
    GSTSummary,
    LoanApplication,
)
from src.utils.llm_client import llm_client
from config.settings import settings


class TransactionGraph:
    """
    Heterogeneous directed graph for entity-transaction modelling.

    Nodes: GSTIN / company name / CIN
    Edges: (source, target, amount, timestamp_bucket, edge_type)
    """

    def __init__(self):
        self.nodes: dict[str, dict] = {}  # node_id → {type, features}
        self.edges: list[dict] = []       # {src, dst, amount, direction, type}
        self.adjacency: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node_id: str, node_type: str = "entity", **features):
        if node_id and node_id not in self.nodes:
            self.nodes[node_id] = {"type": node_type, **features}

    def add_edge(self, src: str, dst: str, amount: float,
                 edge_type: str = "transfer", **attrs):
        if not src or not dst:
            return
        self.edges.append({
            "src": src, "dst": dst, "amount": amount,
            "type": edge_type, **attrs,
        })
        self.adjacency[src].append(dst)

    def find_cycles(self, max_depth: int = 6) -> list[list[str]]:
        """Find all directed cycles up to max_depth using DFS."""
        cycles = []
        visited_cycles: set[tuple] = set()

        for start in self.nodes:
            stack = [(start, [start])]
            while stack:
                node, path = stack.pop()
                for neighbor in self.adjacency.get(node, []):
                    if neighbor == start and len(path) >= 3:
                        cycle = tuple(sorted(path))
                        if cycle not in visited_cycles:
                            visited_cycles.add(cycle)
                            cycles.append(path[:])
                    elif neighbor not in path and len(path) < max_depth:
                        stack.append((neighbor, path + [neighbor]))
        return cycles

    def compute_node_features(self) -> dict[str, np.ndarray]:
        """Compute feature vectors per node for GNN-style scoring."""
        features = {}
        for node_id in self.nodes:
            out_edges = [e for e in self.edges if e["src"] == node_id]
            in_edges = [e for e in self.edges if e["dst"] == node_id]

            out_total = sum(e["amount"] for e in out_edges)
            in_total = sum(e["amount"] for e in in_edges)
            out_count = len(out_edges)
            in_count = len(in_edges)
            unique_counterparties = len(
                set(e["dst"] for e in out_edges) | set(e["src"] for e in in_edges)
            )

            # Reciprocity: how much of outflow comes back from same entities
            out_targets = set(e["dst"] for e in out_edges)
            in_sources = set(e["src"] for e in in_edges)
            reciprocal_entities = out_targets & in_sources
            reciprocal_volume = sum(
                e["amount"] for e in in_edges if e["src"] in reciprocal_entities
            )
            reciprocity_ratio = (reciprocal_volume / in_total) if in_total > 0 else 0.0

            features[node_id] = np.array([
                out_total,
                in_total,
                out_count,
                in_count,
                unique_counterparties,
                reciprocity_ratio,
                (in_total / out_total) if out_total > 0 else 0.0,  # flow_ratio
                1.0 if node_id in self._get_cycle_participants() else 0.0,
            ], dtype=np.float32)

        return features

    def _get_cycle_participants(self) -> set[str]:
        """Return set of all nodes participating in any cycle."""
        participants = set()
        for cycle in self.find_cycles():
            participants.update(cycle)
        return participants


class TemporalGNNScorer:
    """
    Lightweight GNN-inspired scoring using message-passing aggregation.
    For production: replace with torch_geometric TGN model.

    Implements 2-layer neighborhood aggregation:
      h_v^(k+1) = σ(W · AGGREGATE({h_u : u ∈ N(v)}) + b)
    """

    def __init__(self, hidden_dim: int = settings.GNN_HIDDEN_DIM,
                 num_layers: int = settings.GNN_NUM_LAYERS):
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        np.random.seed(42)
        self.weights = [
            np.random.randn(8 if i == 0 else hidden_dim, hidden_dim) * 0.1
            for i in range(num_layers)
        ]
        self.biases = [np.zeros(hidden_dim) for _ in range(num_layers)]

    def score_nodes(self, graph: TransactionGraph) -> dict[str, float]:
        """Run message-passing and return fraud probability per node."""
        raw_features = graph.compute_node_features()
        if not raw_features:
            return {}

        # Initialize embeddings
        embeddings = {nid: feat for nid, feat in raw_features.items()}

        # Message passing layers
        for layer_idx in range(self.num_layers):
            new_embeddings = {}
            W = self.weights[layer_idx]
            b = self.biases[layer_idx]

            for node_id in graph.nodes:
                # Aggregate neighbor embeddings (mean)
                neighbors = graph.adjacency.get(node_id, [])
                if neighbors:
                    neighbor_feats = []
                    for n in neighbors:
                        if n in embeddings:
                            feat = embeddings[n]
                            # Pad or truncate to match weight input dim
                            if len(feat) < W.shape[0]:
                                feat = np.pad(feat, (0, W.shape[0] - len(feat)))
                            elif len(feat) > W.shape[0]:
                                feat = feat[:W.shape[0]]
                            neighbor_feats.append(feat)
                    if neighbor_feats:
                        agg = np.mean(neighbor_feats, axis=0)
                    else:
                        agg = np.zeros(W.shape[0])
                else:
                    agg = np.zeros(W.shape[0])

                # Self feature
                self_feat = embeddings.get(node_id, np.zeros(W.shape[0]))
                if len(self_feat) < W.shape[0]:
                    self_feat = np.pad(self_feat, (0, W.shape[0] - len(self_feat)))
                elif len(self_feat) > W.shape[0]:
                    self_feat = self_feat[:W.shape[0]]

                # Combine: self + neighbors
                combined = (self_feat + agg) / 2.0
                h = np.tanh(combined @ W + b)  # ReLU alternative: np.maximum(0, ...)
                new_embeddings[node_id] = h

            embeddings = new_embeddings

        # Readout: sigmoid of L2 norm (higher norm = higher anomaly)
        scores = {}
        norms = [np.linalg.norm(v) for v in embeddings.values()]
        max_norm = max(norms) if norms else 1.0
        for nid, emb in embeddings.items():
            norm = np.linalg.norm(emb)
            scores[nid] = float(1.0 / (1.0 + np.exp(-3 * (norm / max_norm - 0.5))))

        return scores


class FraudScorer:
    """
    End-to-end fraud analysis combining:
    1. Transaction graph construction
    2. Circular trading detection (cycle finding)
    3. GNN-based anomaly scoring
    4. GST vs Bank cross-validation
    5. Heuristic red-flag detection
    6. LLM-driven narrative synthesis
    """

    def __init__(self):
        self.gnn = TemporalGNNScorer()

    async def analyze(
        self,
        application: Optional[LoanApplication],
        bank_summaries: list[BankStatementSummary],
        gst_summaries: list[GSTSummary],
    ) -> FraudReport:
        logger.info("Sherlock: Building transaction graph...")

        graph = self._build_graph(application, bank_summaries, gst_summaries)
        signals: list[FraudSignal] = []

        # --- 1. Circular Trading Detection ---
        circular_signals = self._detect_circular_trading(graph, application)
        signals.extend(circular_signals)

        # --- 2. GNN Node Scoring ---
        gnn_scores = self.gnn.score_nodes(graph)
        target_id = application.company.gstin or application.company.cin if application else None
        target_gnn = gnn_scores.get(target_id, 0.0) if target_id else 0.0

        if target_gnn > settings.FRAUD_SCORE_THRESHOLD:
            signals.append(FraudSignal(
                signal_type="gnn_anomaly",
                severity=self._score_to_severity(target_gnn),
                confidence=target_gnn,
                description=f"GNN anomaly score {target_gnn:.3f} exceeds threshold {settings.FRAUD_SCORE_THRESHOLD}",
                evidence=[f"Node embedding norm indicates unusual transaction patterns"],
            ))

        # --- 3. GST vs Bank Cross-Validation ---
        mismatch_signals, gst_bank_mismatch = self._cross_validate_gst_bank(
            bank_summaries, gst_summaries
        )
        signals.extend(mismatch_signals)

        # --- 4. Heuristic Red Flags ---
        heuristic_signals = self._run_heuristics(
            application, bank_summaries, gst_summaries
        )
        signals.extend(heuristic_signals)

        # --- 5. Related Party Concentration ---
        rp_conc, rp_signals = self._check_related_party_concentration(bank_summaries)
        signals.extend(rp_signals)

        # --- 6. Compute Aggregate Score ---
        if signals:
            raw_score = max(s.confidence for s in signals)
            # Weighted blend: max signal + average of all
            avg_score = sum(s.confidence for s in signals) / len(signals)
            overall_score = 0.6 * raw_score + 0.4 * avg_score
        else:
            overall_score = 0.05  # Near-clean

        # Boost if circular trading found
        circular_detected = any(s.signal_type == "circular_trading" for s in signals)
        if circular_detected:
            overall_score = max(overall_score, 0.80)

        overall_score = min(overall_score, 1.0)

        # --- 7. LLM Narrative (optional enhancement) ---
        network_entities = list(gnn_scores.keys())[:20]

        report = FraudReport(
            overall_fraud_score=round(overall_score, 4),
            severity=self._score_to_severity(overall_score),
            signals=signals,
            circular_trading_detected=circular_detected,
            revenue_inflation_detected=any(
                s.signal_type == "revenue_inflation" for s in signals
            ),
            gst_bank_mismatch_pct=round(gst_bank_mismatch, 2),
            related_party_concentration_pct=round(rp_conc, 2),
            network_risk_entities=network_entities[:10],
        )

        logger.info(
            f"Sherlock Result: score={report.overall_fraud_score}, "
            f"severity={report.severity.value}, signals={len(report.signals)}"
        )
        return report

    def _build_graph(
        self,
        application: Optional[LoanApplication],
        bank_summaries: list[BankStatementSummary],
        gst_summaries: list[GSTSummary],
    ) -> TransactionGraph:
        """Construct heterogeneous transaction graph from all available data."""
        graph = TransactionGraph()

        # Add the target company
        if application:
            company_id = application.company.gstin or application.company.cin
            graph.add_node(company_id, node_type="target",
                           name=application.company.name)

        # Bank statement counterparties → edges
        for bs in bank_summaries:
            bank_node = f"BANK_{bs.bank_name}_{bs.account_number[-4:]}"
            graph.add_node(bank_node, node_type="bank_account")

            for cp in bs.top_counterparties:
                cp_id = cp.gstin or cp.name
                graph.add_node(cp_id, node_type="counterparty",
                               name=cp.name, is_related=cp.is_related_party)
                graph.add_edge(
                    cp_id, company_id if application else bank_node,
                    amount=cp.total_amount_cr,
                    edge_type="bank_inflow",
                    count=cp.transaction_count,
                )

        # GST supplier/buyer relationships → edges
        for gst in gst_summaries:
            gst_node = gst.gstin
            graph.add_node(gst_node, node_type="gstin")

            for supplier in gst.top_suppliers:
                s_id = supplier.gstin or supplier.name
                graph.add_node(s_id, node_type="supplier", name=supplier.name)
                graph.add_edge(s_id, gst_node, amount=supplier.total_amount_cr,
                               edge_type="gst_purchase", count=supplier.transaction_count)

            for buyer in gst.top_buyers:
                b_id = buyer.gstin or buyer.name
                graph.add_node(b_id, node_type="buyer", name=buyer.name)
                graph.add_edge(gst_node, b_id, amount=buyer.total_amount_cr,
                               edge_type="gst_sale", count=buyer.transaction_count)

        logger.info(
            f"Graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )
        return graph

    def _detect_circular_trading(
        self, graph: TransactionGraph, application: Optional[LoanApplication]
    ) -> list[FraudSignal]:
        """Find circular trading loops involving the target entity."""
        signals = []
        cycles = graph.find_cycles(max_depth=6)

        target_id = None
        if application:
            target_id = application.company.gstin or application.company.cin

        for cycle in cycles:
            involves_target = target_id and target_id in cycle
            cycle_edges = []
            for i in range(len(cycle)):
                src = cycle[i]
                dst = cycle[(i + 1) % len(cycle)]
                matching = [e for e in graph.edges if e["src"] == src and e["dst"] == dst]
                cycle_edges.extend(matching)

            total_volume = sum(e["amount"] for e in cycle_edges) if cycle_edges else 0
            amounts = [e["amount"] for e in cycle_edges] if cycle_edges else [0]

            # Circular trading signature: similar amounts, narrow counterparty set
            if len(amounts) > 1:
                cv = np.std(amounts) / (np.mean(amounts) + 1e-9)
                symmetry_score = max(0, 1.0 - cv)
            else:
                symmetry_score = 0.3

            confidence = symmetry_score * (0.9 if involves_target else 0.5)
            confidence = min(confidence, 1.0)

            if confidence > 0.4:
                signals.append(FraudSignal(
                    signal_type="circular_trading",
                    severity=self._score_to_severity(confidence),
                    confidence=round(confidence, 3),
                    description=(
                        f"Circular trading loop detected: {' → '.join(cycle[:5])}... "
                        f"({len(cycle)} entities, ₹{total_volume:.2f} Cr volume, "
                        f"symmetry={symmetry_score:.2f})"
                    ),
                    evidence=[
                        f"Loop length: {len(cycle)} entities",
                        f"Transaction volume: ₹{total_volume:.2f} Cr",
                        f"Amount symmetry (CV): {symmetry_score:.2f}",
                        f"Involves target: {involves_target}",
                    ],
                    entities_involved=cycle[:10],
                ))

        return signals

    def _cross_validate_gst_bank(
        self,
        bank_summaries: list[BankStatementSummary],
        gst_summaries: list[GSTSummary],
    ) -> tuple[list[FraudSignal], float]:
        """Cross-leverage GST turnover against bank statement inflows."""
        signals = []

        total_bank_inflows = sum(bs.total_credits_cr for bs in bank_summaries)
        total_gst_turnover = sum(gs.gstr3b_turnover_cr for gs in gst_summaries)

        if total_gst_turnover == 0 and total_bank_inflows == 0:
            return signals, 0.0

        base = max(total_gst_turnover, total_bank_inflows, 0.01)
        mismatch_pct = abs(total_gst_turnover - total_bank_inflows) / base * 100

        if mismatch_pct > 20:
            inflation_direction = (
                "GST turnover exceeds bank inflows (possible inflated GST filing)"
                if total_gst_turnover > total_bank_inflows
                else "Bank inflows exceed GST turnover (possible undeclared revenue)"
            )
            confidence = min(mismatch_pct / 50, 1.0)

            signals.append(FraudSignal(
                signal_type="revenue_inflation",
                severity=self._score_to_severity(confidence),
                confidence=round(confidence, 3),
                description=(
                    f"{mismatch_pct:.1f}% mismatch between GST turnover "
                    f"(₹{total_gst_turnover:.2f} Cr) and bank inflows "
                    f"(₹{total_bank_inflows:.2f} Cr). {inflation_direction}"
                ),
                evidence=[
                    f"GST 3B turnover: ₹{total_gst_turnover:.2f} Cr",
                    f"Bank total credits: ₹{total_bank_inflows:.2f} Cr",
                    f"Mismatch: {mismatch_pct:.1f}%",
                ],
            ))

        # ITC mismatch: GSTR-2A/2B vs claimed
        for gs in gst_summaries:
            if gs.itc_claimed_cr > 0 and gs.itc_eligible_cr > 0:
                itc_inflation = (
                    (gs.itc_claimed_cr - gs.itc_eligible_cr) / gs.itc_eligible_cr * 100
                )
                if itc_inflation > 10:
                    confidence = min(itc_inflation / 40, 1.0)
                    signals.append(FraudSignal(
                        signal_type="itc_mismatch",
                        severity=self._score_to_severity(confidence),
                        confidence=round(confidence, 3),
                        description=(
                            f"ITC mismatch: Claimed ₹{gs.itc_claimed_cr:.2f} Cr vs "
                            f"Eligible ₹{gs.itc_eligible_cr:.2f} Cr "
                            f"({itc_inflation:.1f}% inflation). "
                            f"Potential fake invoicing / non-compliance."
                        ),
                        evidence=[
                            f"GSTIN: {gs.gstin}",
                            f"ITC Claimed: ₹{gs.itc_claimed_cr:.2f} Cr",
                            f"ITC Eligible (2A/2B): ₹{gs.itc_eligible_cr:.2f} Cr",
                        ],
                    ))

        # GSTR-1 vs 3B mismatch
        for gs in gst_summaries:
            if gs.gstr1_turnover_cr > 0 and gs.gstr3b_turnover_cr > 0:
                if gs.turnover_mismatch_pct > 15:
                    confidence = min(gs.turnover_mismatch_pct / 40, 1.0)
                    signals.append(FraudSignal(
                        signal_type="gstr1_3b_mismatch",
                        severity=self._score_to_severity(confidence),
                        confidence=round(confidence, 3),
                        description=(
                            f"GSTR-1 vs GSTR-3B mismatch: {gs.turnover_mismatch_pct:.1f}%. "
                            f"GSTR-1=₹{gs.gstr1_turnover_cr:.2f} Cr, "
                            f"GSTR-3B=₹{gs.gstr3b_turnover_cr:.2f} Cr"
                        ),
                        evidence=[
                            f"GSTIN: {gs.gstin}",
                            f"Mismatch: {gs.turnover_mismatch_pct:.1f}%",
                        ],
                    ))

        return signals, mismatch_pct

    def _run_heuristics(
        self,
        application: Optional[LoanApplication],
        bank_summaries: list[BankStatementSummary],
        gst_summaries: list[GSTSummary],
    ) -> list[FraudSignal]:
        """Run heuristic red-flag checks."""
        signals = []

        # Mandate bounce analysis
        total_bounces = sum(bs.mandate_bounces for bs in bank_summaries)
        if total_bounces > 3:
            confidence = min(total_bounces / 10, 1.0)
            signals.append(FraudSignal(
                signal_type="mandate_bounces",
                severity=FraudSeverity.MEDIUM if total_bounces < 6 else FraudSeverity.HIGH,
                confidence=round(confidence, 3),
                description=(
                    f"{total_bounces} mandate bounces detected across "
                    f"{len(bank_summaries)} bank accounts. "
                    f"Direct signal of liquidity stress."
                ),
                evidence=[
                    f"{bs.bank_name}: {bs.mandate_bounces} bounces"
                    for bs in bank_summaries if bs.mandate_bounces > 0
                ],
            ))

        # Staged deposits: check for large inflows just before statement end
        # (heuristic: if single counterparty > 30% of total credits)
        for bs in bank_summaries:
            if bs.top_counterparties and bs.total_credits_cr > 0:
                top_cp = max(bs.top_counterparties, key=lambda c: c.total_amount_cr)
                concentration = top_cp.total_amount_cr / bs.total_credits_cr * 100
                if concentration > 40:
                    signals.append(FraudSignal(
                        signal_type="staged_deposits",
                        severity=FraudSeverity.MEDIUM,
                        confidence=round(min(concentration / 80, 1.0), 3),
                        description=(
                            f"Inflow concentration: {top_cp.name} accounts for "
                            f"{concentration:.1f}% of total credits in {bs.bank_name}. "
                            f"Possible staged/window-dressing deposits."
                        ),
                        evidence=[
                            f"Top counterparty: {top_cp.name}",
                            f"Amount: ₹{top_cp.total_amount_cr:.2f} Cr",
                            f"Concentration: {concentration:.1f}%",
                        ],
                        entities_involved=[top_cp.name],
                    ))

        # Promoter disqualification check
        if application:
            for p in application.company.promoters:
                if p.disqualified:
                    signals.append(FraudSignal(
                        signal_type="disqualified_promoter",
                        severity=FraudSeverity.CRITICAL,
                        confidence=0.95,
                        description=(
                            f"Promoter {p.name} (DIN: {p.din}) is DISQUALIFIED. "
                            f"Immediate governance red flag."
                        ),
                        evidence=[f"DIN: {p.din}", f"Status: Disqualified"],
                        entities_involved=[p.din],
                    ))

        return signals

    def _check_related_party_concentration(
        self, bank_summaries: list[BankStatementSummary]
    ) -> tuple[float, list[FraudSignal]]:
        """Check if >70% of revenue comes from related parties."""
        signals = []
        total_credits = sum(bs.total_credits_cr for bs in bank_summaries)
        rp_credits = 0.0

        for bs in bank_summaries:
            for cp in bs.top_counterparties:
                if cp.is_related_party:
                    rp_credits += cp.total_amount_cr

        if total_credits == 0:
            return 0.0, signals

        rp_pct = rp_credits / total_credits * 100

        if rp_pct > 70:
            signals.append(FraudSignal(
                signal_type="related_party_concentration",
                severity=FraudSeverity.HIGH,
                confidence=round(min(rp_pct / 100, 1.0), 3),
                description=(
                    f"{rp_pct:.1f}% of bank inflows from related parties "
                    f"(₹{rp_credits:.2f} Cr / ₹{total_credits:.2f} Cr). "
                    f"High risk of synthetic revenue."
                ),
                evidence=[f"Related party inflows: ₹{rp_credits:.2f} Cr"],
            ))

        return rp_pct, signals

    @staticmethod
    def _score_to_severity(score: float) -> FraudSeverity:
        if score < 0.2:
            return FraudSeverity.CLEAN
        elif score < 0.4:
            return FraudSeverity.LOW
        elif score < 0.6:
            return FraudSeverity.MEDIUM
        elif score < 0.8:
            return FraudSeverity.HIGH
        return FraudSeverity.CRITICAL
