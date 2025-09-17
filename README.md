# AWS Daily Billing Summary

This project provides automated daily AWS billing summaries posted to Mattermost, showing 5-day rolling averages with cost filtering and percentage change indicators.

## Features

- 📊 **5-day rolling average** calculation for AWS service costs
- 💰 **Cost filtering** - excludes services with daily average < $10
- 📈 **Percentage change indicators** comparing recent vs previous periods
- 🚀 **Automated daily posting** to Mattermost via webhook
- 🔧 **Manual trigger capability** for testing
- 📝 **PM2 process management** with logging

## Setup

### 1. Environment Variables
Ensure your `.env` file contains:
```
AWS_ACCESS_KEY=your_access_key
AWS_SECRET_KEY=your_secret_key
AWS_REGION=ap-southeast-1
MATTERMOST_AWS_BILLING_INCOMING_WEBHOOK=your_webhook_url
```

### 2. Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> Note: A project-level `.gitignore` is included to keep secrets and local-only files out of version control (e.g., `.env`, `venv/`, `logs/`, and `run_manual_test.sh`).

### 3. PM2 Setup
```bash
# Start the scheduled daily process
pm2 start ecosystem.config.js --only aws-billing-summary

# Save PM2 configuration
pm2 save
pm2 startup
```

## Usage

### Manual Testing
```bash
# Using the test script
./run_manual_test.sh

# Or directly with PM2
pm2 start ecosystem.config.js --only aws-billing-manual
```

### Scheduled Operation
The script runs automatically daily at 9:00 AM UTC via PM2 cron.

### PM2 Management
```bash
# View running processes
pm2 list

# View logs
pm2 logs aws-billing-summary

# Stop processes
pm2 stop aws-billing-summary
pm2 stop aws-billing-manual

# Restart processes
pm2 restart aws-billing-summary
```

## Output Format

The Mattermost message includes:
- **Total period cost** and **average daily cost**
- **Top services** sorted by 5-day average (highest to lowest)
- **Percentage change indicators**:
  - 📈 Significant increase (>10%)
  - 📉 Significant decrease (<-10%)
  - ↗️ Moderate increase (0-10%)
  - ↘️ Moderate decrease (0 to -10%)
  - ➡️ No change (0%)

## File Structure

```
fr8labs-aws-billing/
├── daily_aws_billing_summary.py  # Main script
├── ecosystem.config.js           # PM2 configuration
├── requirements.txt              # Python dependencies
├── run_manual_test.sh            # Manual test script (gitignored)
├── .env                          # Environment variables
├── venv/                         # Virtual environment
└── logs/                         # PM2 log files
```

## Troubleshooting

1. **No data retrieved**: Check AWS credentials and permissions
2. **Mattermost posting fails**: Verify webhook URL in .env
3. **PM2 cron not working**: Ensure PM2 is properly configured with `pm2 startup`
4. **Cost threshold too high**: Adjust `cost_threshold` in the script if needed

## Customization

- **Cost threshold**: Modify `self.cost_threshold` in `AWSBillingSummary.__init__()`
- **Days to analyze**: Change the `days` parameter in method calls
- **Schedule time**: Update `cron_restart` in `ecosystem.config.js`
- **Top services limit**: Adjust the slice `[:10]` in `format_mattermost_message()`

## Publish to GitHub (Checklist)

1. Commit the code:
   ```bash
   git init
   git add .
   git commit -m "feat: AWS daily billing summary with PM2 + Mattermost"
   ```
2. Create a new GitHub repository (private is recommended) and add it as a remote:
   ```bash
   git remote add origin git@github.com:<your-org>/<your-repo>.git
   git push -u origin main
   ```

### Security Checklist

- Ensure `.env` is NOT committed (already covered by `.gitignore`).
- Keep `run_manual_test.sh` out of git (already covered by `.gitignore`).
- Never store AWS credentials in code or `ecosystem.config.js`.
- Restrict IAM permissions for the Cost Explorer access key to least privilege.
