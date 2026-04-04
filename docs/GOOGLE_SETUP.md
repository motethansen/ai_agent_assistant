# Google API Setup Guide

This guide covers everything needed to connect Google Calendar, Google Tasks,
and Gmail to the AI Agent Assistant via n8n.

All Google credentials live in n8n's credential store — no `token.json` or
`credentials.json` files are needed in the Python project.

---

## Part 1 — Create a Google Cloud Project

Do this once. The same project and OAuth client are reused for all three
Google services.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project picker (top-left) → **New Project**
3. Name it `ai-agent-assistant` → **Create**
4. Make sure the new project is selected in the picker before continuing

---

## Part 2 — Enable the Required APIs

In your project, enable each API you intend to use.

1. Go to **APIs & Services → Library**
2. Search for and enable each of the following:

| Service | API to enable |
|---------|--------------|
| Google Calendar | **Google Calendar API** |
| Google Tasks | **Tasks API** |
| Gmail | **Gmail API** |

Click **Enable** on each. This takes a few seconds per API.

---

## Part 3 — Configure the OAuth Consent Screen

This is required before you can create OAuth credentials.

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in the required fields:
   - **App name**: `AI Agent Assistant`
   - **User support email**: your Gmail address
   - **Developer contact email**: your Gmail address
4. Click **Save and Continue** through the Scopes screen (no custom scopes needed here)
5. On the **Test users** screen, click **Add users** → add your Gmail address
6. Click **Save and Continue** → **Back to Dashboard**

> The app stays in "Testing" mode. That is fine for personal use — you are the
> only test user and tokens do not expire after 7 days unless you publish the app.

---

## Part 4 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Application type: **Web application**
4. Name: `n8n local`
5. Under **Authorised redirect URIs**, click **Add URI** and add:
   ```
   http://localhost:5679/rest/oauth2-credential/callback
   ```
6. Click **Create**
7. A dialog shows your **Client ID** and **Client Secret** — copy both, you will need them in n8n

---

## Part 5 — Add Credentials in n8n

Do this for each Google service you want to use. Start n8n first:

```bash
docker compose up -d n8n
# Open: http://localhost:5679
```

### Google Calendar

1. In n8n: **Settings (gear icon) → Credentials → New**
2. Search for **Google Calendar OAuth2 API** → select it
3. Paste your **Client ID** and **Client Secret** from Part 4
4. Click **Connect my account** — a Google sign-in window opens
5. Sign in with your Gmail account → grant the Calendar permission
6. The credential status turns green: **Connected**
7. Name it `Google Calendar — personal` → **Save**

### Google Tasks

1. **Credentials → New** → search **Google Tasks OAuth2 API**
2. Paste the same **Client ID** and **Client Secret**
3. Click **Connect my account** → sign in → grant the Tasks permission
4. Name it `Google Tasks — personal` → **Save**

### Gmail

1. **Credentials → New** → search **Google Gmail OAuth2 API** (or **Gmail OAuth2**)
2. Paste the same **Client ID** and **Client Secret**
3. Click **Connect my account** → sign in → grant the Gmail permission
   (read-only is sufficient for the digest workflow)
4. Name it `Gmail — personal` → **Save**

---

## Part 6 — Wire Credentials into Workflows

After importing workflows (see `INSTALL.md` → n8n Setup), each Google node
needs to be linked to the credential you just created.

1. Open the workflow in the n8n editor
2. Click any **Google Calendar**, **Google Tasks**, or **Gmail** node
3. In the **Credential** dropdown, select the matching credential you saved above
4. Click **Save** (top-right)
5. Repeat for every Google node in the workflow
6. Toggle the workflow **Active**

---

## Part 7 — Enable in `.config`

```ini
# Google Tasks — triggers n8n workflow for pull/push
ENABLE_GOOGLE_TASKS=true

# Gmail digest — triggers n8n gmail-digest workflow
ENABLE_GMAIL=true
```

Google Calendar is now fully managed by n8n. Remove `ENABLE_GOOGLE_CALENDAR`
from `.config` if it is still present — it has no effect.

---

## Troubleshooting

**"redirect_uri_mismatch" error during OAuth**
: The redirect URI in Google Cloud does not match n8n's callback URL.
  Go to **Google Cloud → Credentials → edit your OAuth client** and confirm
  `http://localhost:5679/rest/oauth2-credential/callback` is listed exactly.

**n8n shows "Token expired" on a credential**
: Click the credential → **Reconnect** → sign in again. This happens if the
  Google Cloud app is in Testing mode and the 7-day refresh window passes
  without use. For permanent access, publish the app (OAuth consent screen →
  **Publish App**) — no review is needed for personal-use apps with standard scopes.

**Gmail API 403 "insufficientPermissions"**
: The Gmail credential was granted with too narrow a scope. Delete the
  credential in n8n, revoke it at [myaccount.google.com/permissions](https://myaccount.google.com/permissions),
  and re-add with the correct Gmail OAuth2 credential type.

**Google Tasks returns empty list**
: The Tasks API may not be enabled. Go to **Google Cloud → APIs & Services →
  Library** and confirm the **Tasks API** shows as **Enabled**.

**Port 5679 not reachable from the OAuth redirect**
: This usually means n8n is not running. Run `docker compose up -d n8n` and
  confirm `http://localhost:5679` loads before attempting OAuth.
