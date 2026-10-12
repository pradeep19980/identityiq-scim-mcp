# Publish this project as a public GitHub repository

## Option A — GitHub website (no CLI)

1. Download and extract the repository ZIP.
2. Sign in at https://github.com and choose **New repository**.
3. Name it `identityiq-scim-mcp`, choose **Public**, and leave **Initialize with a README** unchecked (the ZIP already contains one).
4. Create the repository. On its empty page, select **uploading an existing file**.
5. Upload the extracted files **and directories**, preserving paths such as `src/`, `docs/`, `.github/workflows/`. Some browsers hide dotfiles: check that `.gitignore`, `.env.example`, and `.github/` were included.
6. Before committing, verify no `.env`, OAuth client secrets, private addresses, log exports or live identities have been added.
7. Commit to `main`. The README will appear automatically on the repository's home page.

## Option B — GitHub CLI

Install Git and GitHub CLI from https://git-scm.com and https://cli.github.com, and log in:

```bash
gh auth login
cd identityiq-scim-mcp
git init
git branch -M main
git add .
git status # review staged files for private information
git commit -m "Initial open source IdentityIQ SCIM MCP connector"
gh repo create identityiq-scim-mcp --public --source=. --remote=origin --push
```

If you already created a GitHub repository of the same name, add its remote manually and push instead of running `gh repo create` again.

This ZIP is source code. It has **not** been published to your GitHub account by the project author.
