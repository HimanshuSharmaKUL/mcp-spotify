# mcp-spotify


#### Describe the vibe. Get the playlist! ✨

This is a Python-based MCP (Model Context Protocol) server that allows AI agents (like Claude, Cursor) to create, manage, and populate Spotify playlists using the Spotify Web API.

## 🚀 Features


- You can create new private playlists
- Can search songs by name
- Add tracks to playlists
- Fully compatible with MCP client tool systems like Claude Desktop, Cursor, or your custom client

## 🔧 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/HimanshuSharmaKUL/mcp-spotify.git
cd mcp-spotify
```

### 2. Create `.env` file
Create a .env file in the repo and collect the following credentials for Spotify API integration

```ini
CLIENT_ID=your_spotify_client_id
CLIENT_SECRET=your_spotify_client_secret
REDIRECT_URI=http://localhost:8888/callback
```

### 3. Install `uv` if not installed

### 4. Install dependencies
```bash
uv pip install -r requirements.txt
```

### 5a. Run it with mcp inspector
```bash
npx @modelcontextprotocol/inspector uv run mcpspotify_server.py
```

### 5b. Can also integrate it with Claude Desktop
Add the following in your the `config.json` of your Claude Desktop. Add it under the `mcpServers`
```json
"mcp-spotify": {
    "command": "uv",
    "args": [
      "--directory",
      "C:\\Path\\To\\mcp-spotify-playlist",
      "run",
      "mcpspotify_server.py"
    ]
  }
```

