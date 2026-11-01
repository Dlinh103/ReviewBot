"""Unit tests for DiffChunker."""

from reviewbot.core.chunker import DiffChunker, estimate_tokens, format_numbered_hunk
from reviewbot.core.diff_parser import parse_patch

SAMPLE_PATCH = """@@ -1,4 +1,5 @@
 def hello():
-    print("Hi")
+    print("Hello")
+    print("World")
     return True
"""


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 16) == 4


def test_format_numbered_hunk() -> None:
    diff = parse_patch(SAMPLE_PATCH, "hello.py")
    hunk = diff.hunks[0]
    numbered = format_numbered_hunk(hunk)

    lines = numbered.splitlines()
    assert lines[0] == "@@ -1,4 +1,5 @@"
    assert lines[1] == " L1:  def hello():"
    assert lines[2] == "-    : -    print(\"Hi\")"
    assert lines[3] == "+L2: +    print(\"Hello\")"
    assert lines[4] == "+L3: +    print(\"World\")"
    assert lines[5] == " L4:      return True"


def test_chunk_file_diff_single_chunk() -> None:
    chunker = DiffChunker(max_tokens_per_chunk=1000)
    diff = parse_patch(SAMPLE_PATCH, "hello.py")
    chunks = chunker.chunk_file_diff(diff)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.file_path == "hello.py"
    assert chunk.start_line == 1
    assert chunk.end_line == 5
    assert "+L2: +    print(\"Hello\")" in chunk.numbered_diff
    assert chunk.estimated_tokens > 0


def test_chunk_file_diff_split_by_tokens() -> None:
    # 2 hunks, tiny token limit -> splits into 2 chunks
    multi_hunk_patch = """@@ -1,3 +1,3 @@
-a
+b
 c
@@ -50,3 +50,3 @@
-d
+e
 f
"""
    diff = parse_patch(multi_hunk_patch, "split.py")
    # Set limit to 10 tokens so each hunk forces a separate chunk
    chunker = DiffChunker(max_tokens_per_chunk=10)
    chunks = chunker.chunk_file_diff(diff)

    assert len(chunks) == 2
    assert chunks[0].start_line == 1
    assert chunks[1].start_line == 50
