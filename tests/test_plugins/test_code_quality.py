"""Tests for code_quality plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.code_quality import (
    compute_stats,
    cyclomatic_complexity,
    comment_ratio,
    detect_duplicates,
    find_god_classes,
    find_long_methods,
)


class TestComputeStats:
    def test_empty_repo(self):
        with tempfile.TemporaryDirectory() as d:
            stats = compute_stats(Path(d))
            assert stats["total_files"] == 0
            assert stats["total_loc"] == 0

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "test.py").write_text("line1\nline2\nline3\n")
            stats = compute_stats(repo)
            assert stats["total_files"] == 1
            assert stats["total_loc"] == 3
            assert ".py" in stats["by_extension"]

    def test_multiple_extensions(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "a.py").write_text("a\nb\n")
            (repo / "b.js").write_text("x\ny\nz\n")
            stats = compute_stats(repo)
            assert stats["total_files"] == 2
            assert stats["total_loc"] == 5
            assert ".py" in stats["by_extension"]
            assert ".js" in stats["by_extension"]

    def test_skips_git_and_target(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".git").mkdir()
            (repo / ".git" / "config").write_text("data\n")
            (repo / "target").mkdir()
            (repo / "target" / "out.txt").write_text("build\n")
            (repo / "src.py").write_text("real\n")
            stats = compute_stats(repo)
            assert stats["total_files"] == 1

    def test_skips_empty_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "empty.py").write_text("")
            (repo / "real.py").write_text("content\n")
            stats = compute_stats(repo)
            assert stats["total_files"] == 1


class TestCyclomaticComplexity:
    def test_empty_content(self):
        assert cyclomatic_complexity("") == 1

    def test_no_branches(self):
        assert cyclomatic_complexity("int x = 1;") == 1

    def test_single_if(self):
        assert cyclomatic_complexity("if (x > 0) { return 1; }") == 2

    def test_multiple_branches(self):
        code = "if (a) { } else if (b) { } for (;;) { } while (x) { }"
        # if=1, else_if=1, for=1, while=1 → 4 branches + 1 = 5
        assert cyclomatic_complexity(code) == 5

    def test_case_and_catch(self):
        code = "switch (x) { case 1: break; case 2: break; } try { } catch (Exception e) { }"
        # case x2, catch x1 = 3 + 1 = 4
        assert cyclomatic_complexity(code) == 4


class TestCommentRatio:
    def test_no_lines(self):
        assert comment_ratio("") == 0.0

    def test_all_comments(self):
        assert comment_ratio("// comment\n# another\n") == 1.0

    def test_half_comments(self):
        assert comment_ratio("// comment\ncode\n") == 0.5

    def test_block_comments(self):
        content = "/* start\n * middle\n */\ncode\n"
        assert comment_ratio(content) == 0.75  # 3 comment lines out of 4


class TestDetectDuplicates:
    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "A.java").write_text(
                "public class A {\n  void m() { int x=1; int y=2; int z=3; int a=4; int b=5; int c=6; }\n}\n"
            )
            dupes = detect_duplicates(repo, min_lines=3)
            assert len(dupes) == 0

    def test_duplicates_detected(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            shared = (
                "    int a = 100;\n"
                "    int b = 200;\n"
                "    int c = 300;\n"
                "    int d = 400;\n"
                "    int e = 500;\n"
                "    int f = 600;\n"
            )
            (repo / "A.java").write_text(
                "public class A {\n" + shared + "\n    int g = 700;\n}\n"
            )
            (repo / "B.java").write_text(
                "public class B {\n" + shared + "\n    int h = 800;\n}\n"
            )
            dupes = detect_duplicates(repo, min_lines=6)
            assert len(dupes) >= 1


class TestFindGodClasses:
    def test_no_god_classes(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Small.java").write_text("public class Small {\n  int x;\n}\n")
            result = find_god_classes(repo)
            assert len(result) == 0

    def test_finds_god_class(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            lines = ["public class BigClass {"]
            for i in range(510):
                lines.append(f"  int field{i};")
            lines.append("}")
            (repo / "BigClass.java").write_text("\n".join(lines))
            result = find_god_classes(repo)
            assert len(result) >= 1
            assert "BigClass.java" in result[0]["file"]
            assert result[0]["loc"] > 500

    def test_respects_custom_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Medium.java").write_text("x\n" * 100)
            result = find_god_classes(repo, threshold=50)
            assert len(result) >= 1
            result_strict = find_god_classes(repo, threshold=200)
            assert len(result_strict) == 0


class TestFindLongMethods:
    def test_no_long_methods(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Short.java").write_text(
                "public class Short {\n"
                "  public void m() { int x = 1; }\n"
                "}\n"
            )
            result = find_long_methods(repo)
            assert len(result) == 0

    def test_finds_long_method(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            lines = [
                "public class Processor {",
                "  public void process() {",
            ]
            for i in range(60):
                lines.append(f"    int x{i} = {i};")
            lines.append("  }")
            lines.append("}")
            (repo / "Processor.java").write_text("\n".join(lines))
            result = find_long_methods(repo)
            assert len(result) >= 1
            assert result[0]["method"] == "process"
            assert result[0]["loc"] > 50

    def test_private_method(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            lines = [
                "public class Worker {",
                "  private void doWork() {",
            ]
            for i in range(55):
                lines.append(f"    step{i}();")
            lines.append("  }")
            lines.append("}")
            (repo / "Worker.java").write_text("\n".join(lines))
            result = find_long_methods(repo)
            assert len(result) >= 1
