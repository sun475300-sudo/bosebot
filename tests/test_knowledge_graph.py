"""Knowledge graph tests."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_graph import KnowledgeGraph


# ---------------------------------------------------------------------------
# Sample FAQ fixture
# ---------------------------------------------------------------------------

SAMPLE_FAQ = [
    {
        "id": "A",
        "category": "GENERAL",
        "question": "보세전시장이 무엇인가요?",
        "answer": "보세전시장은 보세구역입니다.",
        "legal_basis": ["관세법 제190조"],
        "keywords": ["보세전시장", "정의", "보세구역"],
    },
    {
        "id": "B",
        "category": "IMPORT_EXPORT",
        "question": "반입/반출 신고가 필요한가요?",
        "answer": "네, 반출입신고를 해야 합니다.",
        "legal_basis": ["보세전시장 운영에 관한 고시 제10조"],
        "keywords": ["반입", "반출", "신고"],
    },
    {
        "id": "C",
        "category": "GENERAL",
        "question": "보세전시장과 보세창고의 차이?",
        "answer": "목적이 다릅니다.",
        "legal_basis": ["관세법 제190조"],
        "keywords": ["보세전시장", "보세창고", "차이"],
    },
]


@pytest.fixture
def graph():
    return KnowledgeGraph.build_from_faq(SAMPLE_FAQ)


@pytest.fixture
def empty_graph():
    return KnowledgeGraph()


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------


class TestNodeCRUD:
    def test_add_node(self, empty_graph):
        empty_graph.add_node("n1", "faq", {"q": "test"})
        assert "n1" in empty_graph.nodes
        assert empty_graph.nodes["n1"]["type"] == "faq"

    def test_add_node_invalid_type(self, empty_graph):
        with pytest.raises(ValueError):
            empty_graph.add_node("n1", "invalid_type")

    def test_add_node_all_types(self, empty_graph):
        for t in KnowledgeGraph.VALID_NODE_TYPES:
            empty_graph.add_node(f"n_{t}", t)
        assert len(empty_graph.nodes) == 4


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


class TestEdgeCRUD:
    def test_add_edge(self, empty_graph):
        empty_graph.add_node("a", "faq")
        empty_graph.add_node("b", "concept")
        empty_graph.add_edge("a", "b", "related_to")
        assert len(empty_graph.edges) == 1
        assert empty_graph.edges[0]["source"] == "a"

    def test_add_edge_invalid_relation(self, empty_graph):
        empty_graph.add_node("a", "faq")
        empty_graph.add_node("b", "faq")
        with pytest.raises(ValueError):
            empty_graph.add_edge("a", "b", "bad_relation")

    def test_add_edge_missing_source(self, empty_graph):
        empty_graph.add_node("b", "faq")
        with pytest.raises(KeyError):
            empty_graph.add_edge("missing", "b", "related_to")

    def test_add_edge_missing_target(self, empty_graph):
        empty_graph.add_node("a", "faq")
        with pytest.raises(KeyError):
            empty_graph.add_edge("a", "missing", "related_to")

    def test_duplicate_edge_updates_weight(self, empty_graph):
        empty_graph.add_node("a", "faq")
        empty_graph.add_node("b", "faq")
        empty_graph.add_edge("a", "b", "related_to", weight=1.0)
        empty_graph.add_edge("a", "b", "related_to", weight=2.0)
        assert len(empty_graph.edges) == 1
        assert empty_graph.edges[0]["weight"] == 2.0

    def test_add_edge_with_weight(self, empty_graph):
        empty_graph.add_node("a", "faq")
        empty_graph.add_node("b", "faq")
        empty_graph.add_edge("a", "b", "cites", weight=0.5)
        assert empty_graph.edges[0]["weight"] == 0.5


# ---------------------------------------------------------------------------
# Build from FAQ
# ---------------------------------------------------------------------------


class TestBuildFromFAQ:
    def test_builds_faq_nodes(self, graph):
        faq_nodes = [n for n in graph.nodes.values() if n["type"] == "faq"]
        assert len(faq_nodes) == 3

    def test_builds_category_nodes(self, graph):
        cat_nodes = [n for n in graph.nodes.values() if n["type"] == "category"]
        assert len(cat_nodes) == 2  # GENERAL, IMPORT_EXPORT

    def test_builds_law_nodes(self, graph):
        law_nodes = [n for n in graph.nodes.values() if n["type"] == "law"]
        assert len(law_nodes) == 2  # 관세법 제190조, 고시 제10조

    def test_builds_concept_nodes(self, graph):
        concept_nodes = [n for n in graph.nodes.values() if n["type"] == "concept"]
        # All unique keywords across 3 items
        assert len(concept_nodes) > 0

    def test_category_edges(self, graph):
        part_of_edges = [e for e in graph.edges if e["relation"] == "part_of"]
        assert len(part_of_edges) == 3  # A->GENERAL, B->IMPORT_EXPORT, C->GENERAL

    def test_cites_edges(self, graph):
        cites_edges = [e for e in graph.edges if e["relation"] == "cites"]
        # A and C both cite 관세법 제190조, so there's faq->law edges + faq<->faq cites
        assert len(cites_edges) > 0

    def test_related_to_edges(self, graph):
        related_edges = [e for e in graph.edges if e["relation"] == "related_to"]
        assert len(related_edges) > 0

    def test_shared_keyword_creates_related_edge(self, graph):
        """A and C both have keyword '보세전시장' -> related_to edge."""
        related = [
            e for e in graph.edges
            if e["relation"] == "related_to"
            and {e["source"], e["target"]} == {"faq_A", "faq_C"}
        ]
        assert len(related) >= 1

    def test_shared_law_creates_cites_edge(self, graph):
        """A and C both cite 관세법 제190조 -> cites edge between them."""
        cites = [
            e for e in graph.edges
            if e["relation"] == "cites"
            and {e["source"], e["target"]} == {"faq_A", "faq_C"}
        ]
        assert len(cites) >= 1

    def test_empty_faq_list(self):
        g = KnowledgeGraph.build_from_faq([])
        assert len(g.nodes) == 0
        assert len(g.edges) == 0

    def test_build_from_real_faq(self):
        """Build graph from the actual data/faq.json."""
        faq_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "faq.json",
        )
        with open(faq_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        g = KnowledgeGraph.build_from_faq(data["items"])
        stats = g.get_graph_stats()
        assert stats["node_count"] > 30
        assert stats["edge_count"] > 30


# ---------------------------------------------------------------------------
# Neighbor queries
# ---------------------------------------------------------------------------


class TestGetNeighbors:
    def test_depth_1(self, graph):
        neighbors = graph.get_neighbors("faq_A")
        assert len(neighbors) > 0

    def test_depth_2(self, graph):
        n1 = graph.get_neighbors("faq_A", depth=1)
        n2 = graph.get_neighbors("faq_A", depth=2)
        assert len(n2) >= len(n1)

    def test_filter_by_relation(self, graph):
        neighbors = graph.get_neighbors("faq_A", relation="part_of", depth=1)
        # Should include only category node
        types = {n["type"] for n in neighbors}
        assert "category" in types

    def test_missing_node(self, graph):
        with pytest.raises(KeyError):
            graph.get_neighbors("nonexistent")


# ---------------------------------------------------------------------------
# Path finding
# ---------------------------------------------------------------------------


class TestFindPath:
    def test_self_path(self, graph):
        assert graph.find_path("faq_A", "faq_A") == ["faq_A"]

    def test_direct_path(self, graph):
        """A and C are directly connected via shared keyword."""
        path = graph.find_path("faq_A", "faq_C")
        assert len(path) >= 2
        assert path[0] == "faq_A"
        assert path[-1] == "faq_C"

    def test_indirect_path(self, graph):
        """A can reach C's category through the graph."""
        path = graph.find_path("faq_A", "cat_GENERAL")
        assert len(path) >= 2
        assert path[0] == "faq_A"
        assert path[-1] == "cat_GENERAL"

    def test_no_path(self, empty_graph):
        empty_graph.add_node("x", "faq")
        empty_graph.add_node("y", "faq")
        assert graph_find_path_empty(empty_graph) == []

    def test_missing_source(self, graph):
        with pytest.raises(KeyError):
            graph.find_path("missing", "faq_A")

    def test_missing_target(self, graph):
        with pytest.raises(KeyError):
            graph.find_path("faq_A", "missing")


def graph_find_path_empty(g):
    return g.find_path("x", "y")


# ---------------------------------------------------------------------------
# Subgraph
# ---------------------------------------------------------------------------


class TestGetSubgraph:
    def test_subgraph_contains_center(self, graph):
        sub = graph.get_subgraph("faq_A", depth=1)
        ids = {n["id"] for n in sub["nodes"]}
        assert "faq_A" in ids

    def test_subgraph_depth(self, graph):
        s1 = graph.get_subgraph("faq_A", depth=1)
        s2 = graph.get_subgraph("faq_A", depth=2)
        assert len(s2["nodes"]) >= len(s1["nodes"])

    def test_subgraph_edges_within_nodes(self, graph):
        sub = graph.get_subgraph("faq_A", depth=1)
        ids = {n["id"] for n in sub["nodes"]}
        for e in sub["edges"]:
            assert e["source"] in ids
            assert e["target"] in ids

    def test_missing_node(self, graph):
        with pytest.raises(KeyError):
            graph.get_subgraph("nonexistent")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearchNodes:
    def test_search_by_id(self, graph):
        results = graph.search_nodes("faq_A")
        assert any(r["id"] == "faq_A" for r in results)

    def test_search_by_keyword(self, graph):
        results = graph.search_nodes("보세전시장")
        assert len(results) > 0

    def test_search_case_insensitive(self, graph):
        results = graph.search_nodes("GENERAL")
        assert any(r["type"] == "category" for r in results)

    def test_search_no_results(self, graph):
        results = graph.search_nodes("xyznonexistent123")
        assert results == []


# ---------------------------------------------------------------------------
# Related concepts
# ---------------------------------------------------------------------------


class TestGetRelatedConcepts:
    def test_returns_concept_nodes(self, graph):
        concepts = graph.get_related_concepts("faq_A")
        for c in concepts:
            assert c["type"] == "concept"

    def test_missing_node(self, graph):
        with pytest.raises(KeyError):
            graph.get_related_concepts("missing")


# ---------------------------------------------------------------------------
# Stats & export
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_keys(self, graph):
        stats = graph.get_graph_stats()
        assert "node_count" in stats
        assert "edge_count" in stats
        assert "density" in stats
        assert "node_types" in stats
        assert "relation_types" in stats

    def test_stats_counts(self, graph):
        stats = graph.get_graph_stats()
        assert stats["node_count"] == len(graph.nodes)
        assert stats["edge_count"] == len(graph.edges)

    def test_density_range(self, graph):
        d = graph.get_graph_stats()["density"]
        assert 0 <= d <= 1

    def test_empty_graph_stats(self, empty_graph):
        stats = empty_graph.get_graph_stats()
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["density"] == 0.0


class TestExport:
    def test_export_structure(self, graph):
        data = graph.export_graph()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_export_node_fields(self, graph):
        data = graph.export_graph()
        for node in data["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "data" in node

    def test_export_edge_fields(self, graph):
        data = graph.export_graph()
        for edge in data["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge
            assert "weight" in edge


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

from web_server import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


class TestKnowledgeGraphAPI:
    def test_get_full_graph(self, client):
        res = client.get("/api/admin/knowledge/graph")
        assert res.status_code == 200
        data = res.get_json()
        assert "graph" in data
        assert "stats" in data
        assert "nodes" in data["graph"]
        assert "edges" in data["graph"]

    def test_get_node(self, client):
        res = client.get("/api/admin/knowledge/node/faq_A")
        assert res.status_code == 200
        data = res.get_json()
        assert "node" in data
        assert "neighbors" in data
        assert data["node"]["id"] == "faq_A"

    def test_get_node_not_found(self, client):
        res = client.get("/api/admin/knowledge/node/nonexistent_xyz")
        assert res.status_code == 404

    def test_get_path(self, client):
        res = client.get("/api/admin/knowledge/path?from=faq_A&to=faq_C")
        assert res.status_code == 200
        data = res.get_json()
        assert "path" in data
        assert "length" in data
        assert data["path"][0] == "faq_A"
        assert data["path"][-1] == "faq_C"

    def test_get_path_missing_params(self, client):
        res = client.get("/api/admin/knowledge/path")
        assert res.status_code == 400

    def test_get_path_node_not_found(self, client):
        res = client.get("/api/admin/knowledge/path?from=faq_A&to=nonexistent_xyz")
        assert res.status_code == 404

    def test_rebuild_graph(self, client):
        res = client.post("/api/admin/knowledge/rebuild")
        assert res.status_code == 200
        data = res.get_json()
        assert "stats" in data
        assert data["stats"]["node_count"] > 0
