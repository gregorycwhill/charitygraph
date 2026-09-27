from charitygraph.packet_locators import resolve_locator

def test_single_and_inclusive_range_resolution():
    units = {f"L{i:04d}": f"line {i}" for i in range(40, 44)}
    assert resolve_locator(units, "L0040") == "line 40"
    assert resolve_locator(units, "L0040-L0043") == "line 40\nline 41\nline 42\nline 43"
    assert resolve_locator(units, "L0040-L0044") is None
