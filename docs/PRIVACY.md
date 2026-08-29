# Privacy and Public Repository Safety

Model Council is developed for publication in a public GitHub repository.
Local identity, credentials and private project material must therefore remain
outside the versioned repository.

## Never commit

- API keys, bearer tokens, refresh tokens, passwords or private keys;
- `.env` files or credential-store exports;
- absolute home-directory paths containing a real local username;
- personal email addresses unless the contributor intentionally publishes one;
- hostnames, account identifiers or machine-specific diagnostics that identify
  a private workstation;
- runtime databases, generated Artifacts, private prompts or copied user
  project content;
- local worktrees, diffs or logs from a private downstream repository.

Configuration examples must use environment-variable references and generic
placeholders. Runtime and discovery state remains local and ignored by Git.

## Required board-completion gate

After every development board:

1. inspect all changed and untracked files;
2. run the full automated test suite;
3. run `python scripts/privacy_scan.py --history`;
4. inspect `git diff` and the staged diff before committing;
5. inspect tracked filenames and `.gitignore`;
6. check commit-author metadata for an intentionally public or GitHub noreply
   address;
7. commit only after every finding is resolved or explicitly documented;
8. verify the pushed public commit contains no local runtime files.

The scanner reports only file, line and finding type. It deliberately does not
echo possible secret values.

## External model boundary

Repository contents and derived private-project details must not be sent to an
external model service without explicit user authorization. Discovery scans,
doctor checks and privacy scans must remain local and must not be treated as
authorization for a real model invocation.
