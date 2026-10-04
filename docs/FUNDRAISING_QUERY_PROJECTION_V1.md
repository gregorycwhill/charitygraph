# Fundraising query projection v1

**Status:** local, provider-free bounded query helper; neither a public-contract change nor a search-index implementation.

`fundraising_query` answers only from supplied governed cards and money-scope links. Each match returns observation IDs, retained evidence and relevant coverage, plus the non-causal joint-coverage state. Its denominator is the supplied unique subject set, not a population denominator.

The current helpers cover current evidenced facets (including conjunctive F2F plus regular giving), evidence freshness, disclosed expenditure, explicitly campaign/appeal-linked gross proceeds, and method-known/aggregate-finance coexistence. Freshness excludes evidence outside the requested date bound; it does not convert a subject into a negative result. Finance beside a practice stays non-attributed unless the money link itself is explicit at a lower grain.

No helper accepts a provider, calls a provider, performs natural-language matching, allocates finance, or emits effectiveness, ROI, or causal revenue claims. Empty result sets are bounded query outcomes; callers must retain coverage to distinguish source silence, unavailable data and unprocessed work.
