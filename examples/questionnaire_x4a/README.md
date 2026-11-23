# X4A private questionnaire preview

This static prototype displays a deliberately restricted projection of the
existing Plan Australia and Arche Health experiments. It is not a v0.5 public
card, a canonical observation, a Viewer deployment or a publication. The
experimental data, generated output and cohort manifest remain outside Git.

In the managed environment, run:

```powershell
python examples/questionnaire_x4a/build_preview.py "$env:TEMP\charitygraph-x4a-preview"
```

Open `index.html` in the generated directory. The scripts load locally, so no
server, provider request or existing browser profile is needed. Source links
open public source locations only when selected by the user. The output includes
an explicitly proposed, not execution-approved, X4B cohort manifest.

The builder verifies retained X2/X3/X3B hashes and joins records by exact
source-scoped program IDs. The overlay includes only an explicit allowlist of
display fields: no raw source passages, source filesystem references, provider
responses, probabilities, caches or credentials. It uses the existing Viewer
stylesheet and a separate, private presentation overlay so the public schema,
release bytes and Viewer selection remain unchanged.

Plan's financial figure remains at charity scope. Program assessments are
provisional; Arche's report claims are historical; the model's unsupported
direct-provider selection is displayed as insufficiently established.
The twelve-charity manifest describes captured sources and existing E5A
decisions but does not authorize further acquisition or provider processing.

Focused verification:

```powershell
$env:X4A_SAVED_PREVIEW = '<private preview directory>'
python -m pytest tests/test_questionnaire_x4a.py tests/test_questionnaire_x1.py tests/test_v05_fixture_adapter.py -p no:cacheprovider
```

The saved-preview test checks its files and data against the frozen inputs;
the JavaScript interaction test uses a simulated DOM. Browser rendering, if
needed, must use an isolated headless process with a separate temporary profile.
Do not attach to the user's desktop or existing browser session.
