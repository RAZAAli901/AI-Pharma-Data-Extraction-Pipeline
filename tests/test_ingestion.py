"""
Test suite for the PPTX Parser module.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from pipeline.ingestion.pptx_parser import (
    PPTXParser,
    SlideContent,
    TableData,
    PresentationContent,
)


class TestTableData:
    """Tests for the TableData dataclass."""

    def test_to_markdown_basic(self):
        table = TableData(
            headers=["Drug", "Phase", "Status"],
            rows=[
                {"Drug": "DrugA", "Phase": "III", "Status": "Active"},
                {"Drug": "DrugB", "Phase": "II", "Status": "Recruiting"},
            ],
        )
        md = table.to_markdown()
        assert "Drug" in md
        assert "DrugA" in md
        assert "---" in md

    def test_to_markdown_empty(self):
        table = TableData(headers=[], rows=[])
        assert table.to_markdown() == ""


class TestSlideContent:
    """Tests for the SlideContent dataclass."""

    def test_has_content_with_text(self):
        slide = SlideContent(slide_number=1, text_blocks=["Some text"])
        assert slide.has_content is True

    def test_has_content_empty(self):
        slide = SlideContent(slide_number=1)
        assert slide.has_content is False

    def test_has_content_with_table(self):
        slide = SlideContent(
            slide_number=1,
            tables=[TableData(headers=["A"], rows=[{"A": "1"}])],
        )
        assert slide.has_content is True

    def test_to_text_formatting(self):
        slide = SlideContent(
            slide_number=3,
            title="Test Slide",
            text_blocks=["Hello world"],
            speaker_notes="Some notes",
        )
        text = slide.to_text()
        assert "Slide 3" in text
        assert "Test Slide" in text
        assert "Hello world" in text
        assert "Some notes" in text


class TestPresentationContent:
    """Tests for the PresentationContent dataclass."""

    def test_content_slides_filters_empty(self):
        pres = PresentationContent(
            file_path="test.pptx",
            file_name="test.pptx",
            total_slides=3,
            slides=[
                SlideContent(slide_number=1, text_blocks=["Content"]),
                SlideContent(slide_number=2),  # Empty
                SlideContent(slide_number=3, text_blocks=["More"]),
            ],
        )
        assert len(pres.content_slides) == 2

    def test_to_full_text(self):
        pres = PresentationContent(
            file_path="test.pptx",
            file_name="test.pptx",
            total_slides=1,
            slides=[
                SlideContent(slide_number=1, title="Intro", text_blocks=["Hello"]),
            ],
        )
        full_text = pres.to_full_text()
        assert "test.pptx" in full_text
        assert "Hello" in full_text


class TestPPTXParser:
    """Tests for the PPTXParser class."""

    def test_parse_file_not_found(self):
        parser = PPTXParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("nonexistent.pptx")

    def test_parse_wrong_extension(self, tmp_path):
        fake_file = tmp_path / "test.txt"
        fake_file.touch()
        parser = PPTXParser()
        with pytest.raises(ValueError, match="Expected .pptx"):
            parser.parse(str(fake_file))
