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

## Examples

See the `examples/` directory for complete profile YAML files that you can
copy and customize. These were profiles removed from the built-in set to
keep the core pipeline universal:

- `theological_journal.yaml` — Historical theological journals
- `irish_hagiography.yaml` — Irish language dictionary/hagiography texts
- `citation_focused.yaml` — Documents where citation accuracy is paramount
