# Automatic social media posts

Every morning, right after the website updates, ResearchBoard can post a
"Today in Research" summary with an image card to your **Facebook Page** and
**LinkedIn**. A platform without keys is simply skipped, so you can set up one
now and the other later.

You add the keys yourself as **repository secrets**: GitHub → this repository →
**Settings → Secrets and variables → Actions → New repository secret**.
Never paste keys into a file or a chat.

---

## Facebook Page (about 15 minutes)

1. **Have a Facebook Page** for ResearchBoard (facebook.com → Pages → Create new Page).
   You must be an admin of the Page.
2. Go to **developers.facebook.com → My Apps → Create App**. Choose the use case
   for managing a Page (Pages API) and finish the steps. The app can stay in
   development mode: it works for Pages you admin.
3. Open the **Graph API Explorer** (Tools menu). Pick your app, then
   **Get Token → Get User Access Token** and tick these permissions:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`.
   Click **Generate Access Token** and approve.
4. **Make it long-lived:** open the **Access Token Debugger** (Tools menu),
   paste the token, click **Debug**, then **Extend Access Token** and copy the new token.
5. Back in the Graph API Explorer, paste the long-lived token and run the query
   `me/accounts`. Find your Page in the result and copy its
   **`id`** and **`access_token`**. A Page token made from a long-lived user
   token does not expire.
6. Add two secrets:
   - `FB_PAGE_ID`: the Page id
   - `FB_PAGE_TOKEN`: the Page access_token

---

## LinkedIn, personal profile (about 10 minutes, no approval needed)

1. Go to **linkedin.com/developers → Create app**. LinkedIn asks you to link the app
   to a LinkedIn Company Page. Create a free "ResearchBoard" page if you don't have one.
2. In the app's **Products** tab, add **Share on LinkedIn** and
   **Sign In with LinkedIn using OpenID Connect**. Both are approved instantly.
3. In the **Auth** tab, open the **OAuth 2.0 tools → Create token**, tick the scopes
   `openid`, `profile` and `w_member_social`, and approve.
4. Add the secret `LINKEDIN_TOKEN` with that token.

**Important:** these tokens last **60 days**. Make a new one (step 3) and replace
the secret before then. If it runs out, the website keeps working and only the
LinkedIn post stops.

## LinkedIn, company page (needs LinkedIn approval)

1. In the same app, under **Products**, request the **Community Management API**.
   LinkedIn reviews it, which usually takes 1–2 weeks.
2. After approval, create a token with the scope `w_organization_social`
   (you must be an admin of the page).
3. Add the secrets:
   - `LINKEDIN_TOKEN`: the new token
   - `LINKEDIN_AUTHOR`: `urn:li:organization:12345`, where 12345 is the number
     in your company page's admin URL.
4. Optional: approved apps can get **refresh tokens** (valid one year). Add
   `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` and `LINKEDIN_REFRESH_TOKEN`,
   and a fresh token is created automatically every day.

---

## Testing

GitHub → **Actions → Update data and publish site → Run workflow**. Open the run
and look at the **Post to social media** step. Each platform shows `posted`,
`skipped`, `already posted` (it posts once per day), or `FAILED` with the reason.

## Changing the address in posts

Posts link to `https://researchboard.github.io` until you set the repository
**variable** `SITE_URL` (the Variables tab next to Secrets), for example
`https://researchboard.net`, once your domain is connected.
