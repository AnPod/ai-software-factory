## What changes

## Why

## Checklist

- [ ] `python3 scripts/validate_skills.py`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `bash tests/test_install.sh`
- [ ] New or changed skills keep the untrusted-data rule, write only to `.aiwerk/brain/`, and have an eval case when they write to the brain
- [ ] No tokens, keys, internal URLs or personal data in the diff
