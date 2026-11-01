"""Unit tests for FileFilter."""

from reviewbot.core.file_filter import FileFilter


def test_filter_lock_files() -> None:
    ff = FileFilter()
    assert ff.is_ignored("package-lock.json", patch="@@ ...")[0] is True
    assert ff.is_ignored("pnpm-lock.yaml", patch="@@ ...")[0] is True
    assert ff.is_ignored("poetry.lock", patch="@@ ...")[0] is True
    assert ff.is_ignored("subdir/Cargo.lock", patch="@@ ...")[0] is True


def test_filter_binary_and_assets() -> None:
    ff = FileFilter()
    assert ff.is_ignored("public/logo.png", patch="@@ ...")[0] is True
    assert ff.is_ignored("assets/font.woff2", patch="@@ ...")[0] is True
    assert ff.is_ignored("image.jpg", patch=None)[0] is True


def test_filter_vendor_and_dist() -> None:
    ff = FileFilter()
    assert ff.is_ignored("node_modules/react/index.js", patch="@@ ...")[0] is True
    assert ff.is_ignored("dist/bundle.min.js", patch="@@ ...")[0] is True
    assert ff.is_ignored("vendor/autoload.php", patch="@@ ...")[0] is True


def test_retained_valid_code_files() -> None:
    ff = FileFilter()
    assert ff.is_ignored("src/main.py", patch="@@ ...")[0] is False
    assert ff.is_ignored("components/Navbar.tsx", patch="@@ ...")[0] is False
    assert ff.is_ignored("server/routes/api.go", patch="@@ ...")[0] is False


def test_filter_deleted_files() -> None:
    ff = FileFilter()
    assert ff.is_ignored("src/legacy.py", status="deleted", patch="@@ ...")[0] is True


def test_filter_large_changes() -> None:
    ff = FileFilter(max_changes_per_file=500)
    assert ff.is_ignored("big_data.json", changes=600, patch="@@ ...")[0] is True
    assert ff.is_ignored("small.py", changes=200, patch="@@ ...")[0] is False


def test_filter_files_capping() -> None:
    ff = FileFilter()
    files = [
        {"filename": f"src/file_{i}.py", "status": "modified", "changes": 10, "patch": "@@ ..."}
        for i in range(50)
    ]
    retained, skipped = ff.filter_files(files, max_files=40)
    assert len(retained) == 40
    assert len(skipped) == 10
    assert "Exceeded MAX_FILES_PER_PR cap" in skipped[0][1]
