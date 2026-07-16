# Definition of done

This skill is done for a given slice only when:
- insecure or ambiguous runtime behavior is removed, isolated, or explicitly documented
- failure behavior is deterministic
- tests cover the changed path
- sensitive data leakage risk is addressed
- config changes are documented

This skill is not done if the code is “better” but failure behavior remains undefined.
