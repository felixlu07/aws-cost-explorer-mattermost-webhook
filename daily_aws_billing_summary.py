#!/usr/bin/env python3
"""
Daily AWS Billing Summary Script
Posts a 5-day rolling average summary of AWS costs to Mattermost
Filters out services with costs below $10 and sorts by highest to lowest cost
"""

import boto3
import pandas as pd
import os
import sys
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()

class AWSBillingSummary:
    def __init__(self):
        self.cost_explorer = boto3.client('ce',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('AWS_SECRET_KEY'),
            region_name='us-east-1'  # Cost Explorer is only available in us-east-1
        )
        self.webhook_url = os.getenv('MATTERMOST_AWS_BILLING_INCOMING_WEBHOOK')
        self.cost_threshold = 10.0  # Minimum cost to include in report
        # Holders for aggregated values used during formatting
        self._other_daily = None  # dict[date] -> cost for services below threshold
        self._last_date_list = None
        
        # Service name mappings to shorter/acronym versions
        self.service_name_map = {
            'Amazon Relational Database Service': 'RDS',
            'Amazon Elastic Compute Cloud - Compute': 'EC2 Compute',
            'Amazon Elastic Compute Cloud': 'EC2',
            'EC2 - Other': 'EC2 Other',
            'Amazon Simple Storage Service': 'S3',
            'Amazon EC2 Container Registry (ECR)': 'ECR',
            'Amazon Virtual Private Cloud': 'VPC',
            'Amazon Elastic Load Balancing': 'ELB',
            'AmazonCloudWatch': 'CloudWatch',
            'AWS Global Accelerator': 'Global Accelerator',
            'Savings Plans for AWS Compute usage': 'Savings Plans',
            'Amazon CloudFront': 'CloudFront',
            'AWS Lambda': 'Lambda',
            'Amazon ElastiCache': 'ElastiCache',
            'Amazon Elasticsearch Service': 'Elasticsearch',
            'Amazon OpenSearch Service': 'OpenSearch',
            'AWS Key Management Service': 'KMS',
            'Amazon Route 53': 'Route 53',
            'AWS Certificate Manager': 'ACM',
            'Amazon Simple Notification Service': 'SNS',
            'Amazon Simple Queue Service': 'SQS',
            'AWS Systems Manager': 'Systems Manager',
            'Amazon API Gateway': 'API Gateway'
        }
    
    def get_short_service_name(self, service_name):
        """Convert long service names to shorter versions/acronyms"""
        return self.service_name_map.get(service_name, service_name)
        
    def get_date_range(self, days=5):
        """Get date range for the past N days"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    
    def get_aws_costs(self, days=5):
        """Get AWS costs for the past N days, grouped by service"""
        start_date, end_date = self.get_date_range(days)
        
        print(f"Fetching AWS unblended costs from {start_date} to {end_date}")
        print("Excluding record types: Refund, Credit (to mirror AWS Console)")
        
        try:
            # We'll page through results to be safe, though this query typically fits in one page
            next_token = None
            service_costs = defaultdict(dict)  # dict of service -> {date: cost}
            
            while True:
                params = {
                    'TimePeriod': {
                        'Start': start_date,
                        'End': end_date
                    },
                    'Granularity': 'DAILY',
                    'Metrics': ['UnblendedCost'],
                    'GroupBy': [
                        {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                    ],
                    # Match console by excluding credits/refunds
                    'Filter': {
                        'Not': {
                            'Dimensions': {
                                'Key': 'RECORD_TYPE',
                                'Values': ['Refund', 'Credit']
                            }
                        }
                    }
                }
                if next_token:
                    params['NextPageToken'] = next_token
                response = self.cost_explorer.get_cost_and_usage(**params)

                # Process the response to calculate daily costs per service
                for result in response['ResultsByTime']:
                    date = result['TimePeriod']['Start']
                    for group in result['Groups']:
                        service = group['Keys'][0]
                        cost = float(group['Metrics']['UnblendedCost']['Amount'])
                        if cost > 0:
                            if service not in service_costs:
                                service_costs[service] = {}
                            # Sum in case pagination returns split groups (defensive)
                            service_costs[service][date] = service_costs[service].get(date, 0.0) + cost

                next_token = response.get('NextPageToken')
                if not next_token:
                    break

            # Debug surface for RDS
            rds_key_variants = [
                'Amazon Relational Database Service',
                'Amazon RDS Service',
                'Amazon RDS'
            ]
            for key in rds_key_variants:
                if key in service_costs:
                    total = sum(service_costs[key].values())
                    print(f"[DEBUG] RDS service '{key}' total for window: ${total:.2f}")
                    break
            
            return service_costs
            
        except Exception as e:
            print(f"Error fetching AWS costs: {e}")
            return {}
    
    def calculate_service_summaries(self, service_costs, days=5):
        """Calculate service summaries with daily breakdown"""
        # Get the date range to ensure we have all dates
        start_date, end_date = self.get_date_range(days)
        
        # Generate list of all dates in range
        date_list = []
        current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        while current_date < end_date_obj:
            date_list.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        service_summaries = []
        # Track aggregated daily costs for services below threshold
        other_daily = {d: 0.0 for d in date_list}
        
        for service, daily_costs in service_costs.items():
            if not daily_costs:
                continue
            
            # Create daily breakdown with 0 for missing days
            daily_breakdown = {}
            total_cost = 0
            
            for date in date_list:
                cost = daily_costs.get(date, 0.0)
                daily_breakdown[date] = cost
                total_cost += cost
            
            avg_daily_cost = total_cost / len(date_list) if date_list else 0
            
            # Aggregate services below threshold into 'Other costs'
            if avg_daily_cost < self.cost_threshold:
                for date in date_list:
                    other_daily[date] += daily_breakdown[date]
                continue
            
            # Calculate percentage change (compare last 2 days vs previous 3 days)
            costs_list = [daily_breakdown[date] for date in date_list]
            if len(costs_list) >= 4:
                recent_costs = costs_list[-2:]  # Last 2 days
                previous_costs = costs_list[-5:-2]  # Previous 3 days
                
                recent_avg = sum(recent_costs) / len(recent_costs) if recent_costs else 0
                previous_avg = sum(previous_costs) / len(previous_costs) if previous_costs else 0
                
                if previous_avg > 0:
                    percentage_change = ((recent_avg - previous_avg) / previous_avg) * 100
                else:
                    percentage_change = 0
            else:
                percentage_change = 0
            
            service_summaries.append({
                'service': service,
                'original_service': service,
                'daily_breakdown': daily_breakdown,
                'total_cost': total_cost,
                'avg_daily_cost': avg_daily_cost,
                'percentage_change': percentage_change,
                'date_list': date_list
            })
        
        # Sort by average daily cost (highest to lowest)
        service_summaries.sort(key=lambda x: x['avg_daily_cost'], reverse=True)
        
        # Save aggregates for formatting later (do not add to list to avoid affecting top N)
        self._other_daily = other_daily
        self._last_date_list = date_list

        return service_summaries
    
    def format_mattermost_message(self, service_summaries, days=5):
        """Format the summary as a Mattermost message with daily breakdown table"""
        if not service_summaries:
            return "No AWS costs found above the $10 threshold for the past 5 days."
        
        start_date, end_date = self.get_date_range(days)
        
        # Calculate total costs
        total_avg_daily = sum(s['avg_daily_cost'] for s in service_summaries)
        total_period = sum(s['total_cost'] for s in service_summaries)
        
        message = f"## 📊 AWS Cost Summary ({start_date} to {end_date})\n\n"
        message += f"**Total Cost:** ${total_period:.2f} | **Average Daily Cost:** ${total_avg_daily:.2f}\n"
        message += f"*Showing unblended costs (true usage costs before account-level discounts)*\n\n"
        
        # Get date list from first service (they should all have the same dates)
        if service_summaries:
            date_list = service_summaries[0]['date_list']
            
            # Create table header with daily columns
            header = "| Service | Total | Avg |"
            separator = "|---------|-------|-----|"
            
            for date in date_list:
                # Format date as MM-DD for brevity
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                short_date = date_obj.strftime('%m-%d')
                header += f" {short_date} |"
                separator += "------|"
            
            header += " Change |\n"
            separator += "--------|\n"
            
            message += header + separator
            
            # Add table rows (limit to top 10 for readability)
            for service in service_summaries[:10]:
                service_name = service['service']
                avg_cost = service['avg_daily_cost']
                total_cost = service['total_cost']
                change = service['percentage_change']
                daily_breakdown = service['daily_breakdown']
                
                
                # Format percentage change with emoji
                if change > 10:
                    change_indicator = f"📈+{change:.0f}%"
                elif change < -10:
                    change_indicator = f"📉{change:.0f}%"
                elif change > 0:
                    change_indicator = f"↗️+{change:.0f}%"
                elif change < 0:
                    change_indicator = f"↘️{change:.0f}%"
                else:
                    change_indicator = "➡️0%"
                
                # Build row with daily costs
                row = f"| {service_name} | ${total_cost:.0f} | ${avg_cost:.0f} |"
                
                for date in date_list:
                    daily_cost = daily_breakdown[date]
                    if daily_cost > 0:
                        row += f" ${daily_cost:.0f} |"
                    else:
                        row += " $0 |"
                
                row += f" {change_indicator} |\n"
                message += row

            # Append 'Other costs' aggregated row (for services below threshold)
            if self._other_daily and any(v > 0 for v in self._other_daily.values()):
                other_total = sum(self._other_daily.values())
                other_avg = other_total / len(self._other_daily) if self._other_daily else 0
                row = f"| Other costs | ${other_total:.0f} | ${other_avg:.0f} |"
                for date in date_list:
                    dc = self._other_daily[date]
                    row += f" ${dc:.0f} |" if dc > 0 else " $0 |"
                row += " — |\n"
                message += row

            # Separator row (dashes) before daily total to keep within the same table
            sep = "| — | — | — |" + (" — |" * len(date_list)) + " — |\n"
            message += sep

            # Append 'Daily Total' row (sum of all services including Other)
            # Compute per-day totals from shown services plus other_daily
            daily_totals = {d: 0.0 for d in date_list}
            # Include all services above threshold (not only displayed top 10)
            for svc in service_summaries:
                for d in date_list:
                    daily_totals[d] += svc['daily_breakdown'][d]
            if self._other_daily:
                for d in date_list:
                    daily_totals[d] += self._other_daily[d]
            total_all = sum(daily_totals.values())
            avg_all = total_all / len(date_list) if date_list else 0

            # Compute percentage change for Daily Total (last 2 days vs previous 3)
            totals_list = [daily_totals[d] for d in date_list]
            if len(totals_list) >= 4:
                recent_totals = totals_list[-2:]
                previous_totals = totals_list[-5:-2]
                recent_avg = sum(recent_totals) / len(recent_totals) if recent_totals else 0
                previous_avg = sum(previous_totals) / len(previous_totals) if previous_totals else 0
                if previous_avg > 0:
                    total_change = ((recent_avg - previous_avg) / previous_avg) * 100
                else:
                    total_change = 0
            else:
                total_change = 0

            # Format change indicator consistent with services
            if total_change > 10:
                total_change_indicator = f"📈+{total_change:.0f}%"
            elif total_change < -10:
                total_change_indicator = f"📉{total_change:.0f}%"
            elif total_change > 0:
                total_change_indicator = f"↗️+{total_change:.0f}%"
            elif total_change < 0:
                total_change_indicator = f"↘️{total_change:.0f}%"
            else:
                total_change_indicator = "➡️0%"

            total_row = f"| Daily Total | ${total_all:.0f} | ${avg_all:.0f} |"
            for d in date_list:
                dc = daily_totals[d]
                total_row += f" ${dc:.0f} |" if dc > 0 else " $0 |"
            total_row += f" {total_change_indicator} |\n"
            message += total_row
            
            if len(service_summaries) > 10:
                remaining = len(service_summaries) - 10
                message += f"\n*... and {remaining} more services above ${self.cost_threshold} threshold*\n"
        
        message += f"\n---\n*Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*"
        
        return message
    
    def send_to_mattermost(self, message):
        """Send message to Mattermost via webhook"""
        if not self.webhook_url:
            print("ERROR: MATTERMOST_AWS_BILLING_INCOMING_WEBHOOK not set in .env file")
            return False
        
        payload = {
            "text": message,
            "username": "AWS Billing Bot",
            "icon_emoji": ":money_with_wings:"
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            print("✅ Successfully sent message to Mattermost")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending to Mattermost: {e}")
            return False
    
    def run_daily_summary(self):
        """Main method to run the daily summary"""
        print("🚀 Starting AWS Daily Billing Summary")
        print("=" * 50)
        
        # Get AWS costs for the past 5 days
        service_costs = self.get_aws_costs(days=5)
        
        if not service_costs:
            print("❌ No cost data retrieved")
            return False
        
        print(f"📊 Retrieved data for {len(service_costs)} services")
        
        # Print summary of top services found
        service_totals = []
        for service in service_costs.keys():
            total_cost = sum(service_costs[service].values())
            avg_cost = total_cost / len(service_costs[service]) if service_costs[service] else 0
            service_totals.append((service, total_cost, avg_cost))
        
        # Sort by total cost and show top 5
        service_totals.sort(key=lambda x: x[1], reverse=True)
        print("Top 5 services by usage cost:")
        for service, total, avg in service_totals[:5]:
            if total > 0:
                print(f"  - {service}: ${avg:.2f}/day")
        
        # Calculate summaries with daily breakdown
        service_summaries = self.calculate_service_summaries(service_costs)
        
        if not service_summaries:
            print("❌ No services found above the cost threshold")
            return False
        
        print(f"📈 {len(service_summaries)} services above ${self.cost_threshold} threshold")
        
        # Format message
        message = self.format_mattermost_message(service_summaries)
        
        # Print to console for debugging
        print("\n" + "="*50)
        print("MESSAGE TO BE SENT:")
        print("="*50)
        print(message)
        print("="*50)
        
        # Send to Mattermost
        success = self.send_to_mattermost(message)
        
        if success:
            print("✅ Daily summary completed successfully")
        else:
            print("❌ Failed to send daily summary")
        
        return success

def main():
    """Main function"""
    # Check if this is a manual run
    manual_run = len(sys.argv) > 1 and sys.argv[1] == '--manual'
    
    if manual_run:
        print("🔧 Manual trigger activated")
    else:
        print("⏰ Scheduled run activated")
    
    # Create and run the billing summary
    billing_summary = AWSBillingSummary()
    success = billing_summary.run_daily_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
