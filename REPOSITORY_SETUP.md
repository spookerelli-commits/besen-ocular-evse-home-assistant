# Repository setup

The runtime code and collaboration files are complete. Before first public
push, replace the two placeholders below in `manifest.json` with the final
repository URL and add the owner's exact GitHub username to `codeowners`:

```json
"codeowners": ["@GITHUB_USERNAME"],
"documentation": "https://github.com/GITHUB_USERNAME/ocular-evse-home-assistant",
"issue_tracker": "https://github.com/GITHUB_USERNAME/ocular-evse-home-assistant/issues"
```

These values cannot be completed safely without the account's exact GitHub
username. HACS publication validation requires all three fields.

Recommended repository name: `ocular-evse-home-assistant`.

After pushing:

1. Enable GitHub Actions and confirm the **Tests** workflow passes.
2. Create a `v0.3.2` release from the supplied install ZIP.
3. Add the repository to HACS as a custom integration for field testing.
4. Keep the release marked pre-release until another charger/firmware is
   confirmed.
