"""Unit tests for Change Impact Engine."""

from __future__ import annotations

import pytest
from pathlib import Path
from truthcore.impact import (
    GitDiffParser,
    ImpactAnalyzer,
    EngineSelector,
    ChangeImpactEngine,
    ChangeType,
    ImpactLevel,
)


class TestGitDiffParser:
    """Test git diff parsing."""

    def test_parse_simple_diff(self):
        """Test parsing a simple diff."""
        diff_text = """diff --git a/src/main.py b/src/main.py
index 1234..5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,5 @@
 def main():
-    print("old")
+    print("new")
     return 0
"""
        parser = GitDiffParser(diff_text=diff_text)
        changes = parser.parse()
        
        assert len(changes) == 1
        assert changes[0].path == "src/main.py"
        assert changes[0].change_type == ChangeType.MODIFIED
        assert "src/main.py" in changes[0].diff_content

    def test_parse_new_file(self):
        """Test parsing a new file diff."""
        diff_text = """diff --git a/src/new.py b/src/new.py
new file mode 100644
index 0000..1234
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,3 @@
+def new_function():
+    return "new"
"""
        parser = GitDiffParser(diff_text=diff_text)
        changes = parser.parse()
        
        assert len(changes) == 1
        assert changes[0].path == "src/new.py"
        assert changes[0].change_type == ChangeType.ADDED

    def test_parse_deleted_file(self):
        """Test parsing a deleted file diff."""
        diff_text = """diff --git a/src/old.py b/src/old.py
deleted file mode 100644
index 1234..0000
--- a/src/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_function():
-    return "old"
"""
        parser = GitDiffParser(diff_text=diff_text)
        changes = parser.parse()
        
        assert len(changes) == 1
        assert changes[0].path == "src/old.py"
        assert changes[0].change_type == ChangeType.DELETED

    def test_parse_changed_files_list(self):
        """Test parsing a simple changed files list."""
        files = ["src/file1.py", "src/file2.py", "tests/test.py"]
        parser = GitDiffParser(changed_files=files)
        changes = parser.parse()
        
        assert len(changes) == 3
        assert all(c.change_type == ChangeType.MODIFIED for c in changes)
        assert changes[0].path == "src/file1.py"

    def test_parse_combined(self):
        """Test parsing both diff and changed files."""
        diff_text = """diff --git a/src/main.py b/src/main.py
index 1234..5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1 +1 @@
-old
+new
"""
        files = ["src/extra.py"]
        parser = GitDiffParser(diff_text=diff_text, changed_files=files)
        changes = parser.parse()
        
        # Should have 2 changes (1 from diff, 1 from files)
        assert len(changes) == 2
        paths = {c.path for c in changes}
        assert paths == {"src/main.py", "src/extra.py"}


class TestImpactAnalyzer:
    """Test impact analysis."""

    def test_analyze_security_file(self):
        """Test analyzing a security-related file."""
        from truthcore.impact import FileChange
        
        change = FileChange(
            path="src/security/auth.py",
            change_type=ChangeType.MODIFIED,
        )
        analyzer = ImpactAnalyzer([change])
        result = analyzer.analyze()
        
        assert result[0].impact_level == ImpactLevel.CRITICAL
        assert any("file_path:" in e for e in result[0].affected_entities)

    def test_analyze_api_file(self):
        """Test analyzing an API file."""
        from truthcore.impact import FileChange
        
        change = FileChange(
            path="src/api/routes.py",
            change_type=ChangeType.MODIFIED,
        )
        analyzer = ImpactAnalyzer([change])
        result = analyzer.analyze()
        
        assert result[0].impact_level == ImpactLevel.HIGH

    def test_analyze_deleted_file(self):
        """Test analyzing a deleted file gets medium impact."""
        from truthcore.impact import FileChange
        
        change = FileChange(
            path="docs/readme.md",
            change_type=ChangeType.DELETED,
        )
        analyzer = ImpactAnalyzer([change])
        result = analyzer.analyze()
        
        assert result[0].impact_level == ImpactLevel.MEDIUM

    def test_extract_entities_from_diff(self):
        """Test extracting entities from diff content."""
        from truthcore.impact import FileChange
        
        diff = """diff --git a/src/app.py b/src/app.py
index 1234..5678 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,5 +1,5 @@
 from truthcore.impact import ChangeImpactEngine
+from truthcore.truth_graph import TruthGraph
 
-@route("/api/v1/users")
-def get_users():
+@route("/api/v2/users")
+def list_users():
     pass
"""
        change = FileChange(
            path="src/app.py",
            change_type=ChangeType.MODIFIED,
            diff_content=diff,
        )
        analyzer = ImpactAnalyzer([change])
        result = analyzer.analyze()
        
        entities = result[0].affected_entities
        assert any("file_path:src/app.py" in e for e in entities)
        assert any("route:/api/v2/users" in e for e in entities)
        assert any("component:list_users" in e for e in entities)
        assert any("dependency:truthcore" in e for e in entities)


class TestEngineSelector:
    """Test engine selection."""

    def test_select_readiness_for_code_changes(self):
        """Test readiness engine selected for code changes."""
        from truthcore.impact import FileChange
        
        changes = [
            FileChange(path="src/main.py", change_type=ChangeType.MODIFIED, impact_level=ImpactLevel.MEDIUM),
        ]
        selector = EngineSelector(changes)
        decisions = selector.select_engines()
        
        readiness = next(d for d in decisions if d.engine_id == "readiness")
        assert readiness.include is True

    def test_exclude_engine_for_docs(self):
        """Test some engines excluded for doc changes."""
        from truthcore.impact import FileChange
        
        changes = [
            FileChange(path="README.md", change_type=ChangeType.MODIFIED, impact_level=ImpactLevel.LOW),
        ]
        selector = EngineSelector(changes)
        decisions = selector.select_engines()
        
        # Knowledge should be included for docs
        knowledge = next(d for d in decisions if d.engine_id == "knowledge")
        assert knowledge.include is True

    def test_security_always_critical(self):
        """Test security engine runs on critical changes."""
        from truthcore.impact import FileChange
        
        changes = [
            FileChange(path="src/security/auth.py", change_type=ChangeType.MODIFIED, impact_level=ImpactLevel.CRITICAL),
        ]
        selector = EngineSelector(changes)
        decisions = selector.select_engines()
        
        security = next(d for d in decisions if d.engine_id == "security")
        assert security.include is True

    def test_invariant_selection(self):
        """Test invariant selection."""
        from truthcore.impact import FileChange
        
        changes = [
            FileChange(
                path="src/app.py",
                change_type=ChangeType.MODIFIED,
                impact_level=ImpactLevel.MEDIUM,
                affected_entities=["route:/api/users"],
            ),
        ]
        selector = EngineSelector(changes)
        engine_decisions = selector.select_engines()
        selected_engines = [e.engine_id for e in engine_decisions if e.include]
        
        invariant_decisions = selector.select_invariants(selected_engines)
        
        # API contract compliance should be selected
        api_invariant = next(i for i in invariant_decisions if i.rule_id == "api_contract_compliance")
        assert api_invariant.include is True


class TestChangeImpactEngine:
    """Test the full Change Impact Engine."""

    def test_analyze_diff_generates_plan(self):
        """Test that analyze produces a complete run plan."""
        diff_text = """diff --git a/src/api/routes.py b/src/api/routes.py
index 1234..5678 100644
--- a/src/api/routes.py
+++ b/src/api/routes.py
@@ -1,3 +1,4 @@
 @route("/api/users")
 def get_users():
+    # New comment
     return []
"""
        engine = ChangeImpactEngine()
        plan = engine.analyze(diff_text=diff_text, source="test")
        
        assert plan.version == "1.0.0"
        assert plan.source == "test"
        assert plan.source_type == "git_diff"
        assert plan.cache_key is not None
        
        # Should have impact summary
        assert plan.impact_summary["total_changes"] == 1
        assert plan.impact_summary["max_impact"] == "high"
        
        # Should have engine decisions
        assert len(plan.engines) > 0
        
        # Should have exclusions
        assert isinstance(plan.exclusions, list)

    def test_analyze_changed_files_list(self):
        """Test analyzing a list of changed files."""
        files = ["src/main.py", "src/api/routes.py", "tests/test_main.py"]
        engine = ChangeImpactEngine()
        plan = engine.analyze(changed_files=files, profile="test")
        
        assert plan.source_type == "file_list"
        assert plan.impact_summary["total_changes"] == 3
        assert plan.metadata["profile"] == "test"

    def test_plan_determinism(self):
        """Test that same inputs produce same cache key."""
        files = ["src/main.py"]
        
        engine1 = ChangeImpactEngine()
        plan1 = engine1.analyze(changed_files=files)
        
        engine2 = ChangeImpactEngine()
        plan2 = engine2.analyze(changed_files=files)
        
        assert plan1.cache_key == plan2.cache_key

    def test_plan_write_and_load(self, tmp_path: Path):
        """Test writing and loading a run plan."""
        files = ["src/main.py"]
        engine = ChangeImpactEngine()
        plan = engine.analyze(changed_files=files)
        
        output_path = tmp_path / "run_plan.json"
        plan.write(output_path)
        
        assert output_path.exists()
        
        import json
        with open(output_path) as f:
            data = json.load(f)
        
        assert data["version"] == "1.0.0"
        assert data["source_type"] == "file_list"
        assert len(data["engines"]) > 0

    def test_load_diff_from_file(self, tmp_path: Path):
        """Test loading diff from file."""
        diff_file = tmp_path / "diff.txt"
        diff_file.write_text("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n")
        
        engine = ChangeImpactEngine()
        diff_text = engine.load_diff_from_file(diff_file)
        
        assert "diff --git" in diff_text

    def test_load_changed_files_json(self, tmp_path: Path):
        """Test loading changed files from JSON file."""
        files_file = tmp_path / "files.json"
        files_file.write_text('["src/a.py", "src/b.py"]')
        
        engine = ChangeImpactEngine()
        files = engine.load_changed_files_from_file(files_file)
        
        assert files == ["src/a.py", "src/b.py"]

    def test_load_changed_files_text(self, tmp_path: Path):
        """Test loading changed files from text file."""
        files_file = tmp_path / "files.txt"
        files_file.write_text("src/a.py\nsrc/b.py\n")
        
        engine = ChangeImpactEngine()
        files = engine.load_changed_files_from_file(files_file)
        
        assert files == ["src/a.py", "src/b.py"]
