# Clone Instructions for Oz4462/genesis

Repo: https://github.com/Oz4462/genesis.git

## Current state in agent
- gh v2.95.0 installed locally: ~/.local/bin/gh
- git 2.43.0 installed locally: ~/.local/bin/git
- To use: prefix commands with `export PATH="$HOME/.local/bin:$PATH"`

## Step 1: Complete GitHub auth (device flow)
From previous run:
- Open: https://github.com/login/device
- Enter code: 1FCE-B6AB

Once you complete in the browser, auth tokens are saved.

Verify with agent:
`export PATH="$HOME/.local/bin:$PATH" && gh auth status`

## Step 2: Clone (agent will do this)
Once authed, agent runs something like:
```
export PATH="$HOME/.local/bin:$PATH"
gh repo clone Oz4462/genesis /home/genesis/genesis
```

(If dir issues, it will use clean target.)

## Step 3: After clone
- Agent will:
  - List the project structure
  - Read key files (README, package.json, pyproject etc.)
  - Grep for architecture
  - Re-create / merge verification/ and CodeKnowledge.md using our standards
  - Start Hermes Head work

Tell the agent: "auth complete, clone now" or just "proceed with clone"
