# Security

- Never commit `.env`, API keys, database passwords, or tunnel credentials.
- Use `.env.example` as the template; keep real secrets only on your machine or in your host's secret store.
- If a secret was ever committed, rotate it immediately and treat the old value as compromised (rewriting git history does not remove clones that already pulled it).

To report a vulnerability in this project, open a private security advisory on GitHub or contact the maintainers.
