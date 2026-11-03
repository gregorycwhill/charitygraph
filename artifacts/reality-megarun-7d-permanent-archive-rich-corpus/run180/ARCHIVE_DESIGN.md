# Private archive design

Root: `C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\Source Archive` (outside Git). Immutable source objects use `objects/sha256/aa/bb/<sha>.<ext>`; acquisition events append to `registries/acquisition-events.jsonl`. A repeat object is deduplicated while every retrieval retains a separate event. Derivatives live only under this experiment root and are identified by source SHA plus page locator.
