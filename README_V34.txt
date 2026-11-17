BTN POOL & WALLET ANALYZER V34 — SAICON EDITION

CONTENTS
- index.html: combined Pool Analyzer + Wallet Analyzer interface.
- server.py: local Python server, BaseScan direct-table proxy, and pool-API forwarding.
- saicon-logo.png: supplied SAICON logo displayed beside the application title.
- START_BTN_WALLET_ANALYZER_V34.bat: Windows launcher.

WHAT IS INCLUDED
1) POOL ANALYZER
   - Reads BTN/USDC pool swaps from The Graph through your Cloudflare Worker.
   - Automatically follows every pagination cursor until all swaps in the selected date range are loaded.
   - Shows buy/sell totals, trader-wallet rankings, swap history and CSV export.
   - Lets you open the complete BTN transfer history for any ranked trader wallet.
   - The Cloudflare Worker endpoint is no longer shown in the app or browser-side JavaScript. The browser calls the local server at /pool-api, and the local server forwards the request to the Worker.

2) WALLET ANALYZER
   - Retains the V33 BaseScan direct-table method.
   - Reads the BaseScan token-transfer table for a selected wallet.
   - Uses BaseScan's reported total/page count and loads every expected page.
   - Keeps the existing movement classification and CSV export.

IMPORTANT
- The The Graph API key remains stored as a Cloudflare Worker secret. Do not put it in index.html or server.py.
- The Worker URL is stored in server.py for local forwarding. It is not shown in the app or browser-side JavaScript.
- Pool wallet ranking uses the transaction-origin wallet returned by the subgraph.
- The pool, BTN and USDC token contracts and the known Uniswap Universal Router are excluded from trader rankings.
- Wallet history depends on BaseScan's public HTML table. If BaseScan changes its page structure or blocks requests, the parser may need updating.
- Both analyzers require internet access.

HOW TO RUN
1. Extract all files into the same folder.
2. Double-click START_BTN_WALLET_ANALYZER_V34.bat.
3. The app opens at http://127.0.0.1:8765/index.html.
4. In Pool Analyzer, choose a date range and click Analyze Pool.
5. To inspect a wallet, click Analyze beside its address. The app switches to Wallet Analyzer and loads that wallet's BTN history.

If Windows says Python is missing, install Python 3 from python.org and enable "Add Python to PATH".
