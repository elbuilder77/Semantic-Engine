# Definition of done

This skill is done for a given slice only when:
- provider routing behavior is explicit in code
- fallback conditions are testable
- failure behavior is normalized enough for the caller
- provider-level observability exists or is queued as a concrete next slice
- configuration is documented

This skill is not done if routing still depends on implicit defaults or hidden side effects.
