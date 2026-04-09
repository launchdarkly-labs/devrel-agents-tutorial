# Umbra Account Management

## Creating an Account

Sign up at umbra.dev:

1. Authenticate with GitHub, GitLab, or Bitbucket
2. Authorize Umbra to access your repositories
3. Create or join a team

No email/password accounts - we use your Git provider for authentication.

## Account Types

### Hobby (Free)

- 100 GB bandwidth/month
- 100,000 function invocations/month
- 100 build minutes/month
- Community support only
- Single developer use

### Pro ($20/month)

- 1 TB bandwidth/month
- 1M function invocations/month
- 1,000 build minutes/month
- Email support (24-hour response)
- Password protection for previews
- Basic analytics

### Team ($50/month per seat)

- 5 TB bandwidth/month (shared)
- 10M function invocations/month
- 5,000 build minutes/month
- Priority support (4-hour response)
- Team collaboration features
- Advanced analytics
- SAML SSO

### Enterprise

- Custom limits
- Dedicated support engineer
- 99.99% SLA
- Custom contracts
- SOC 2 / HIPAA compliance
- Contact sales@umbra.dev

## Cancellation Policy

**You can cancel your subscription at any time with no cancellation fee.**

When you cancel:
- Access continues until the end of your billing period
- Deployments stay live until period ends
- After that, projects downgrade to Hobby limits
- Your code and configuration remain - just redeploy when you resubscribe

To cancel: Settings → Billing → Cancel Plan

## Upgrading and Downgrading

### Upgrading

- Takes effect immediately
- Prorated charge for remainder of billing period
- New limits apply instantly

### Downgrading

- Takes effect at next billing cycle
- If you exceed new plan limits, you'll need to reduce usage first
- Projects over bandwidth limits will be suspended, not deleted

## Team Management

### Inviting Members

1. Go to Team Settings → Members
2. Enter GitHub/GitLab/Bitbucket username
3. Select role: Admin, Developer, or Viewer
4. They'll receive an invite notification

### Roles

| Permission | Viewer | Developer | Admin |
|------------|--------|-----------|-------|
| View deployments | ✓ | ✓ | ✓ |
| Trigger deploys | | ✓ | ✓ |
| Manage domains | | ✓ | ✓ |
| Manage env vars | | ✓ | ✓ |
| Manage team | | | ✓ |
| Billing | | | ✓ |

### Removing Members

Admins can remove members from Team Settings. Their deployments remain - they just lose access.

## Free Trial

**14-day free trial of Pro features. No credit card required.**

During trial:
- Full Pro limits
- All Pro features
- Trial banner on dashboard

After trial:
- Add payment method to continue on Pro
- Or automatically downgrade to Hobby
- No data loss either way

## Billing

### Payment Methods

- Credit/debit cards (Visa, Mastercard, Amex)
- PayPal
- Wire transfer (Enterprise only)

### Payment Failures

**We retry failed payments 3 times over 9 days. After that, your account is downgraded to Hobby tier.**

Timeline:
- Day 1: Payment fails, first retry
- Day 4: Second retry
- Day 9: Final retry
- Day 10: Downgrade to Hobby, deployments suspended if over limits

Update payment method: Settings → Billing → Payment Method

### Invoices

- Available in Settings → Billing → Invoices
- Sent automatically via email
- Include detailed usage breakdown

## Security

### Two-Factor Authentication

Managed through your Git provider (GitHub/GitLab/Bitbucket). Enable 2FA there.

### Access Tokens

Generate personal access tokens for CI/CD:

1. Settings → Tokens
2. Create Token
3. Select scopes (deploy, read-only, full)
4. Token shown once - save it securely

Tokens can be revoked anytime.

### Audit Logs

Team and Enterprise plans:
- All actions logged
- Export to CSV
- Retention: 90 days (Team), 1 year (Enterprise)

## Data Export

Export your configuration and settings:

1. Settings → Data → Export
2. Includes: umbra.toml, environment variables (encrypted), project settings
3. Does not include: source code (that's in your Git repo), build artifacts

## Account Deletion

To delete your account:

1. Remove all projects first
2. Settings → Account → Delete Account
3. 7-day grace period
4. After deletion: all data permanently removed, deployments taken offline

This cannot be undone.
