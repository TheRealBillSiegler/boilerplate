# CLI examples

A few common tasks with concise, copy-pastable commands.

## Discover templates

- List templates found in the registry:

```powershell
boilerplate list
```

```text
  Name        Version   Description
 ───────────────────────────────────────────────────────
  project     0.2.1     A suitable base for any Python project.
  streamlit   0.1.1     Streamlit boilerplate for data applications
```

## Create a new project

- Latest project template into a new folder:

```powershell
boilerplate new project my_app
```

- Non-interactive with defaults, force overwrite if exists:

```powershell
boilerplate new project -n -f my_app
```

## Inspect a template graph

- Text tree format (the `streamlit` template extends `project`, so its graph shows the chain):

```powershell
boilerplate graph streamlit --format tree
```

```text
- streamlit@0.1.1
  - project@0.2.1
```

- JSON written to file:

```powershell
boilerplate graph project --format json -o graph.json
```

The JSON payload's shape (`streamlit` example — the `streamlit` template extends `project`):

```json
{
  "sequence": [
    "project@0.2.1",
    "streamlit@0.1.1"
  ],
  "layers": [
    {
      "specifier": "project@0.2.1",
      "name": "project",
      "version": "0.2.1",
      "path": ".../templates/project",
      "deps": []
    },
    {
      "specifier": "streamlit@0.1.1",
      "name": "streamlit",
      "version": "0.1.1",
      "path": ".../templates/streamlit",
      "deps": ["project@0.2.1"]
    }
  ]
}
```

## Compose and export artifacts

- Show final merged questions and the per-layer contributions:

```powershell
boilerplate compose project --sections final,layers
```

- Export all major sections to a directory and stay quiet:

```powershell
boilerplate compose project --all -o out --quiet
```

- Quick shape check with the stats section:

```powershell
boilerplate compose project --sections stats
```

```text
Composing: project@0.2.1
STATS
layers: 1
layers_count: 1
total_keys: 37
total_scalars: 33
top_level_fields: 9
directives:
  - _jinja_extensions
  - _secret_questions
  - _tasks
tasks: 1
max_depth: 3
delta_keys: null
delta_scalars: null
```

## Where next

- [Commands](cli.md) — the full reference for every flag shown here.
- [Customization](customization.md) — make these defaults yours.
