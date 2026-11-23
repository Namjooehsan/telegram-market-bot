# NOVA Bazaar — storefront MVP

A Persian, RTL storefront landing page for the Telegram-market-bot project. The new page is served by Flask's built-in static route at:

- `https://<your-domain>/static/storefront.html`

The existing `/` health endpoint and `/miniapp` Telegram Mini App are intentionally unchanged. This first iteration presents the service categories (websites/apps, Telegram bots and Mini Apps, shops, consulting/automation, games, growth and affiliate partnerships), a product-catalog placeholder, an inquiry email draft, and explicit affiliate/payment disclosures.

## Important launch requirements

- No physical products, prices, stock, delivery policies, or testimonials are invented. The owner must provide and verify their own product details before listing them.
- The inquiry form opens the visitor's email application; it does not transmit or store personal data on the server and is not an order-management system.
- PayPal is **not connected**. A PayPal receiving email alone does not provide a secure checkout, verify payment, handle refunds, or unlock/fulfill an order. Do not describe a submitted screenshot as confirmed payment. Before accepting money, set up an eligible PayPal Business account and official hosted checkout/API credentials, add a server-side verified webhook, order records, refund/chargeback handling, and test the flow in sandbox. Never put API secrets in this repository or the browser.
- The owner-provided contact address currently appears in the page's email-draft link; it is public in the shipped page and may receive spam. Replace it in `static/storefront.html` if a separate public business contact is preferred.
- Affiliate commissions, attribution, eligible products, refund adjustment, payout thresholds, and payment dates must be agreed in writing before partners promote the store. No commission percentage or revenue guarantee is advertised. Do not use unsolicited bulk messages.
- Service descriptions are offers for discussion, not a promise of availability, quote, delivery time, or legal suitability. Confirm scope, milestones, warranty/support, cancellation, privacy and IP rights in writing before a paid engagement.

## Current limits

This MVP does not modify the existing `/` JSON health route or NOVA Mini App route; it is available under `/static/storefront.html`. It has no cart, inventory database, online payment processing, affiliate tracking, or customer data storage. To make it the domain homepage, intentionally change the Flask `/` route and add a real order/payment backend only after those systems are configured and tested.
