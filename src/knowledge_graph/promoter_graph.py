"""
Promoter Knowledge Graph — Bipartite graph linking Companies and Directors.

Built from MCA filings: Companies (C) ↔ Directors (D) via directorship edges.
Enables director interlock detection, group exposure analysis, and
circular ownership identification using graph traversal.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from loguru import logger

from src.models.schemas import CompanyProfile, DirectorInterlock, PromoterInfo


class PromoterKnowledgeGraph:
    """
    Bipartite Knowledge Graph: Company ↔ Director.

    Nodes:
      - Company: {cin, name, status, sector}
      - Director: {din, name, disqualified}

    Edges:
      - (din, cin): directorship with designation and shareholding
    """

    def __init__(self):
        self.companies: dict[str, dict] = {}        # cin → metadata
        self.directors: dict[str, dict] = {}         # din → metadata
        self.edges: list[tuple[str, str, dict]] = [] # (din, cin, attrs)
        self.din_to_cins: dict[str, set[str]] = defaultdict(set)
        self.cin_to_dins: dict[str, set[str]] = defaultdict(set)

    def add_company(self, cin: str, name: str, **kwargs):
        self.companies[cin] = {"name": name, **kwargs}

    def add_director(self, din: str, name: str, **kwargs):
        self.directors[din] = {"name": name, **kwargs}

    def add_directorship(self, din: str, cin: str, **attrs):
        """Link a director to a company."""
        self.edges.append((din, cin, attrs))
        self.din_to_cins[din].add(cin)
        self.cin_to_dins[cin].add(din)

    def build_from_application(self, company: CompanyProfile):
        """Seed the KG from a loan application's company profile."""
        self.add_company(
            cin=company.cin,
            name=company.name,
            sector=company.sector,
            status="target",
        )

        for p in company.promoters:
            self.add_director(
                din=p.din,
                name=p.name,
                disqualified=p.disqualified,
                cibil=p.cibil_score,
            )
            self.add_directorship(
                din=p.din,
                cin=company.cin,
                designation=p.designation,
                shareholding_pct=p.shareholding_pct,
            )

            # Add other directorships
            for other_cin in p.other_directorships:
                self.add_company(other_cin, name=f"Company_{other_cin}")
                self.add_directorship(din=p.din, cin=other_cin)

    def find_interlocks(self, target_cin: str) -> list[DirectorInterlock]:
        """
        Find all director interlocks for the target company.
        An interlock exists when a director serves on multiple boards.
        """
        interlocks = []
        target_directors = self.cin_to_dins.get(target_cin, set())

        for din in target_directors:
            all_companies = self.din_to_cins.get(din, set())
            if len(all_companies) <= 1:
                continue  # Not an interlock

            director_meta = self.directors.get(din, {})
            company_names = [
                self.companies.get(c, {}).get("name", c) for c in all_companies
            ]
            failed = [
                self.companies.get(c, {}).get("name", c)
                for c in all_companies
                if self.companies.get(c, {}).get("status") in ("failed", "ibc", "struck_off")
            ]

            # Risk score based on number of boards + failed companies
            board_count = len(all_companies)
            risk = min(0.1 * (board_count - 1) + 0.3 * len(failed), 1.0)
            if director_meta.get("disqualified"):
                risk = max(risk, 0.9)

            interlocks.append(DirectorInterlock(
                din=din,
                name=director_meta.get("name", din),
                companies=company_names,
                failed_companies=failed,
                risk_score=round(risk, 3),
            ))

        return interlocks

    def find_common_directors(self, cin1: str, cin2: str) -> list[str]:
        """Find directors common to two companies."""
        dirs1 = self.cin_to_dins.get(cin1, set())
        dirs2 = self.cin_to_dins.get(cin2, set())
        return list(dirs1 & dirs2)

    def get_group_exposure(self, target_cin: str) -> dict:
        """
        Compute group-level exposure: all companies reachable via
        shared directors within 2 hops of the target company.
        """
        # Hop 1: directors of target
        directors = self.cin_to_dins.get(target_cin, set())
        # Hop 2: all companies those directors are on
        related_companies = set()
        for din in directors:
            related_companies.update(self.din_to_cins.get(din, set()))
        related_companies.discard(target_cin)

        return {
            "target_cin": target_cin,
            "group_companies": [
                {
                    "cin": c,
                    "name": self.companies.get(c, {}).get("name", c),
                    "status": self.companies.get(c, {}).get("status", "active"),
                    "common_directors": [
                        self.directors.get(d, {}).get("name", d)
                        for d in self.find_common_directors(target_cin, c)
                    ],
                }
                for c in related_companies
            ],
            "total_group_companies": len(related_companies),
            "shared_directors": len(directors),
        }

    def detect_circular_ownership(self, target_cin: str, max_depth: int = 4) -> list[list[str]]:
        """
        Detect circular ownership: company A's promoter → company B → 
        company B's promoter → company A (via back to target).
        """
        cycles = []
        visited: set[tuple] = set()

        def dfs(current_cin: str, path: list[str]):
            if len(path) > max_depth:
                return
            directors = self.cin_to_dins.get(current_cin, set())
            for din in directors:
                companies = self.din_to_cins.get(din, set())
                for next_cin in companies:
                    if next_cin == target_cin and len(path) >= 3:
                        cycle = tuple(sorted(path))
                        if cycle not in visited:
                            visited.add(cycle)
                            cycles.append(path[:])
                    elif next_cin not in path:
                        path.append(next_cin)
                        dfs(next_cin, path)
                        path.pop()

        dfs(target_cin, [target_cin])
        return cycles

    def get_stats(self) -> dict:
        return {
            "companies": len(self.companies),
            "directors": len(self.directors),
            "edges": len(self.edges),
            "avg_boards_per_director": (
                sum(len(v) for v in self.din_to_cins.values()) /
                max(len(self.din_to_cins), 1)
            ),
        }
