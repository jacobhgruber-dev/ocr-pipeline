# Custom Profiles

Place YAML files here to define custom document profiles. Profiles in this
directory are loaded automatically and appear in `--list-profiles`.

## Format

Each file must contain:

```yaml
name: my_profile_name
description: A short description of the document type.
system_prompt: |
  You are an OCR auditor for...

  Rules:
  1. ...
suggested_engines:
  - marker
  - mathpix
suggested_languages:
  - en
suggested_model: gemini-2.5-flash
best_model: gemini-2.5-flash
```
