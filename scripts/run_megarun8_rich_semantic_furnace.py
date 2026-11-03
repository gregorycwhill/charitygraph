"""Bounded Mega-run 8 corpus/representation runner.

This intentionally reuses the capture-first, content-addressed run-180 runner.
It adds only public first-party report archives and makes no canonical change.
"""
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("run7", HERE / "run_megarun7_archive_rich.py")
run7 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run7)

# The repository artifact name was created read-only by the filesystem before
# this runner started.  Keep a readable pointer there, and place append-heavy
# disposable output in the separately authorised runtime root.
run7.OUT = Path(r"C:\CharityGraph-runtime\reality-megarun-8-rich-semantic-furnace")

# These are deliberately bounded official archive landing pages.  The runner
# captures the landing page first and only then follows its PDF link.
run7.COHORT.extend([
    ("caritas-australia", "Caritas Australia", "annual report 2023-24",
     "https://www.caritas.org.au/reports/annual-reports/",
     "https://www.caritas.org.au/media/sn0fypr3/annual-report-2023-24_digital.pdf"),
    ("the-smith-family", "The Smith Family", "annual impact report 2024-25",
     "https://www.thesmithfamily.com.au/about-us/finances/our-annual-results", None),
    ("wwf-australia", "WWF-Australia", "annual report 2024",
     "https://wwf.org.au/annual-report-2024", None),
])

if __name__ == "__main__":
    run7.main()
