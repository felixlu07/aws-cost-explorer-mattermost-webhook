module.exports = {
  apps: [
    {
      name: 'aws-billing-summary',
      script: '/home/felix.lu07/fr8labs-aws-billing/venv/bin/python',
      args: '/home/felix.lu07/fr8labs-aws-billing/daily_aws_billing_summary.py',
      cwd: '/home/felix.lu07/fr8labs-aws-billing',
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      },
      cron_restart: '0 9 * * *', // Run daily at 9:00 AM UTC
      log_file: '/home/felix.lu07/fr8labs-aws-billing/logs/aws-billing.log',
      error_file: '/home/felix.lu07/fr8labs-aws-billing/logs/aws-billing-error.log',
      out_file: '/home/felix.lu07/fr8labs-aws-billing/logs/aws-billing-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'aws-billing-manual',
      script: '/home/felix.lu07/fr8labs-aws-billing/venv/bin/python',
      args: '/home/felix.lu07/fr8labs-aws-billing/daily_aws_billing_summary.py --manual',
      cwd: '/home/felix.lu07/fr8labs-aws-billing',
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      },
      // This one is for manual triggering only - no cron
      log_file: '/home/felix.lu07/fr8labs-aws-billing/logs/aws-billing-manual.log',
      error_file: '/home/felix.lu07/fr8labs-aws-billing/logs/aws-billing-manual-error.log',
      out_file: '/home/felix.lu07/fr8labs-aws-billing/logs/aws-billing-manual-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
