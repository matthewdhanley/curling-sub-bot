# Discord Curling Sub Bot

A Discord bot for managing substitute requests in a curling league. Members can post sub requests, volunteer to fill them, and sign up to be notified when subs are needed.

## Features

- `/request-sub` — Post a sub request (league type, date, time, team, notes)
- `/open-subs` — View all open sub requests (only visible to you)
- `/join-sub-list` — Get assigned the `subs` role to be notified of new requests
- `/leave-sub-list` — Remove yourself from the subs list
- `/post-guide` — Post a pinned how-to embed and set the channel topic (admin only)

## Setup

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → give it a name → **Create**
3. Go to **Bot** → click **Reset Token** and copy the token
4. Go to **OAuth2 → URL Generator**, select scopes: `bot`, `applications.commands`
5. Select bot permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Manage Roles`, `Manage Messages`, `Manage Channels`
6. Open the generated URL, select your server, and authorize

### 2. Get Your IDs

Enable Developer Mode in Discord: **User Settings → Advanced → Developer Mode**

- **Guild ID** — Right-click your server name → Copy Server ID
- **Channel ID** — Right-click the subs channel → Copy Channel ID

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```
DISCORD_BOT_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
SUBS_CHANNEL_ID=your_channel_id_here
DB_PATH=/data/subbot.db
```

### 4. Run with Docker

```bash
docker compose up -d --build
docker compose logs -f
```

The SQLite database is stored in a Docker volume and persists across restarts and rebuilds.

## Discord Server Setup

### Create the `subs` role

1. Go to **Server Settings → Roles → Create Role**
2. Name it exactly `subs`
3. Enable **Allow anyone to @mention this role** so the bot can ping it

### Set the role hierarchy

The bot's role must sit **above** the `subs` role in the role list, otherwise it can't assign or remove it. Go to **Server Settings → Roles** and drag the bot's role above `subs`.

### Run the guide command

Once everything is set up, run `/post-guide` in the subs channel. This will:
- Set the channel topic
- Post a pinned how-to embed for members

## Deployment (VPS)

```bash
git clone <repo> discord-sub-bot
cd discord-sub-bot
cp .env.example .env
# Fill in .env with your values
docker compose up -d --build
```

To update after a code change:

```bash
git pull
docker compose up -d --build
```

## How It Works

1. A member runs `/request-sub` and fills in the modal form
2. The bot posts an embed to the subs channel and pings `@subs`
3. Members click **Volunteer** to offer themselves — they can click again to un-volunteer
4. Once a sub is found, anyone clicks **Close Request** to mark it as filled and disable the buttons
