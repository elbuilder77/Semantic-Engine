# Definition of done

This skill is done for a given slice only when:
- duplicate ingest behavior is controlled or intentionally documented
- debounce/reprocess policy is explicit
- indexing-related stats are not obviously placeholder-based for the changed path
- tests or reproducible evidence support the change

This skill is not done if the pipeline “usually works” but repeated file events still produce uncertainty.
