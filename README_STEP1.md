# Step 1 package — routes + folderized pages

What changed:
- campaigns.html -> /campaigns/index.html
- team.html      -> /team/index.html
- players.html   -> /players/index.html

Navigation:
- Campaigns page now routes to /team/ and /players/
- Players page routes back to /campaigns/

Notes:
- /assets/* absolute paths remain unchanged.
- _redirects is included (safe). It helps platforms that support it to normalize /team -> /team/.
