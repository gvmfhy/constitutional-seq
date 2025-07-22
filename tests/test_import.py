"""Test basic imports and setup."""

def test_import():
    """Test that the package can be imported."""
    import genbank_tool
    assert genbank_tool.__version__ == "0.1.0"


def test_dependencies():
    """Test that core dependencies are available."""
    import requests
    import click
    import openpyxl
    import Bio
    
    # Basic smoke test
    assert requests.__version__
    assert click.__version__
    assert openpyxl.__version__
    assert Bio.__version__