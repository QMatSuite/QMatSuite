# Pull Request

## Description

<!-- Describe your changes here -->

## Checklist

- [ ] Code follows project style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG updated (if applicable)

### RELAX / Structure Import / Fingerprint Compliance

**If this PR touches any of the following areas, you MUST check the boxes below:**

- [ ] RELAX step execution or artifacts
- [ ] Structure import (`import_structure`)
- [ ] Structure canonicalization
- [ ] Structure fingerprinting
- [ ] Generated structures (`generated_structures/`)
- [ ] QC topology rules

**If any box above is checked, you MUST also check:**

- [ ] I have reviewed and referenced:
  - [docs/reviews/RELAX_UP_TO_SPEC_SIGNOFF.md](../docs/reviews/RELAX_UP_TO_SPEC_SIGNOFF.md)
  - [docs/reviews/PR_FINGERPRINT_TOL_SSOT_REVIEW.md](../docs/reviews/PR_FINGERPRINT_TOL_SSOT_REVIEW.md)
- [ ] My changes maintain the two-phase contract:
  - Canonicalization happens ONLY at import/read/parse time
  - Fingerprint is pure quantize+hash (NO geometry transforms)

**Any change affecting these areas must keep the two-phase contract (canonicalize only on import/read; fingerprint is quantize+hash only).**

## Related Issues

<!-- Link to related issues, if any -->

## Testing

<!-- Describe how you tested your changes -->

