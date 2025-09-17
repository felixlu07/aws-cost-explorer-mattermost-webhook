#!/usr/bin/env python3
"""
EC2-Others Cost Validation Script
Validates boto3 Cost Explorer data against AWS UI figures for APS1-DataTransfer-Out-Bytes
Target figures from UI:
- July 2025: $955.40
- August 2025: $2,466.28  
- September 2025: $1,448.67
"""

import boto3
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

class EC2OthersValidator:
    def __init__(self):
        self.cost_explorer = boto3.client('ce',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('AWS_SECRET_KEY'),
            region_name='us-east-1'
        )
        
        # Target figures from AWS UI
        self.target_figures = {
            '2025-07': 955.40,
            '2025-08': 2466.28,
            '2025-09': 1448.67
        }
    
    def validate_ec2_others_costs(self):
        """Validate EC2-Others APS1-DataTransfer-Out-Bytes costs against UI"""
        print("VALIDATING EC2-Others COSTS AGAINST AWS UI")
        print("=" * 50)
        print("Target figures from UI:")
        for month, amount in self.target_figures.items():
            print(f"  {month}: ${amount:.2f}")
        print()
        
        # Try different service name variations for EC2-Others
        service_names_to_try = [
            'EC2 - Other',  # This is the correct one from the service list
            'EC2-Other',
            'EC2-Others',
            'EC2 - Others', 
            'Amazon Elastic Compute Cloud - Others',
            'Amazon EC2',
            'Amazon Elastic Compute Cloud'
        ]
        
        for service_name in service_names_to_try:
            print(f"Trying service name: '{service_name}'")
            try:
                response = self.cost_explorer.get_cost_and_usage(
                    TimePeriod={
                        'Start': '2025-07-01',
                        'End': '2025-10-01'
                    },
                    Granularity='MONTHLY',
                    Metrics=['BlendedCost', 'UnblendedCost'],
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                    ],
                    Filter={
                        'And': [
                            {
                                'Dimensions': {
                                    'Key': 'SERVICE',
                                    'Values': [service_name]
                                }
                            },
                            {
                                'Dimensions': {
                                    'Key': 'USAGE_TYPE',
                                    'Values': ['APS1-DataTransfer-Out-Bytes']
                                }
                            }
                        ]
                    }
                )
                
                print("Results:")
                monthly_totals = {}
                
                for result in response['ResultsByTime']:
                    period_start = result['TimePeriod']['Start']
                    month_key = period_start[:7]  # YYYY-MM format
                    
                    total_cost = 0
                    for group in result['Groups']:
                        usage_type = group['Keys'][0]
                        blended_cost = float(group['Metrics']['BlendedCost']['Amount'])
                        unblended_cost = float(group['Metrics']['UnblendedCost']['Amount'])
                        
                        if blended_cost > 0 or unblended_cost > 0:
                            total_cost += blended_cost
                            print(f"  {month_key} - {usage_type}: ${blended_cost:.2f}")
                    
                    if total_cost > 0:
                        monthly_totals[month_key] = total_cost
                
                if monthly_totals:
                    print(f"\nMonthly totals for '{service_name}':")
                    for month, total in monthly_totals.items():
                        target = self.target_figures.get(month, 0)
                        match_status = "✓ MATCH" if abs(total - target) < 1.0 else "✗ MISMATCH"
                        print(f"  {month}: ${total:.2f} (Target: ${target:.2f}) {match_status}")
                    
                    # If we found matching data, this is likely the correct service name
                    if any(abs(total - self.target_figures.get(month, 0)) < 50 for month, total in monthly_totals.items()):
                        print(f"\n*** LIKELY CORRECT SERVICE NAME: '{service_name}' ***")
                        return service_name, monthly_totals
                else:
                    print("  No data found")
                    
            except Exception as e:
                print(f"  Error: {e}")
            
            print("-" * 30)
        
        return None, {}
    
    def get_all_ec2_services(self):
        """Get all available EC2-related services"""
        print("\nGETTING ALL EC2-RELATED SERVICES")
        print("=" * 40)
        
        try:
            response = self.cost_explorer.get_dimension_values(
                Dimension='SERVICE',
                TimePeriod={'Start': '2025-07-01', 'End': '2025-10-01'}
            )
            
            ec2_services = []
            for service in response['DimensionValues']:
                service_name = service['Value']
                if any(keyword in service_name.lower() for keyword in ['ec2', 'elastic compute', 'compute cloud']):
                    ec2_services.append(service_name)
            
            print("Available EC2-related services:")
            for service in sorted(ec2_services):
                print(f"  - {service}")
            
            return ec2_services
            
        except Exception as e:
            print(f"Error getting services: {e}")
            return []
    
    def detailed_usage_type_analysis(self, service_name):
        """Get detailed breakdown by usage type for the identified service"""
        print(f"\nDETAILED ANALYSIS FOR SERVICE: {service_name}")
        print("=" * 50)
        
        try:
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': '2025-07-01',
                    'End': '2025-10-01'
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                ],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': [service_name]
                    }
                }
            )
            
            usage_summary = {}
            
            for result in response['ResultsByTime']:
                period_start = result['TimePeriod']['Start']
                month_key = period_start[:7]
                
                if month_key not in usage_summary:
                    usage_summary[month_key] = {}
                
                for group in result['Groups']:
                    usage_type = group['Keys'][0]
                    blended_cost = float(group['Metrics']['BlendedCost']['Amount'])
                    
                    if blended_cost > 0:
                        usage_summary[month_key][usage_type] = blended_cost
            
            # Display results
            for month in sorted(usage_summary.keys()):
                print(f"\n{month}:")
                sorted_usage = sorted(usage_summary[month].items(), key=lambda x: x[1], reverse=True)
                
                for usage_type, cost in sorted_usage:
                    if 'DataTransfer' in usage_type:
                        marker = " ← TARGET" if usage_type == 'APS1-DataTransfer-Out-Bytes' else ""
                        print(f"  {usage_type}: ${cost:.2f}{marker}")
                
                # Show total for comparison
                total = sum(usage_summary[month].values())
                print(f"  TOTAL: ${total:.2f}")
            
            return usage_summary
            
        except Exception as e:
            print(f"Error in detailed analysis: {e}")
            return {}

def main():
    validator = EC2OthersValidator()
    
    # Step 1: Get all EC2 services to understand naming
    ec2_services = validator.get_all_ec2_services()
    
    # Step 2: Try to validate against UI figures
    correct_service, monthly_data = validator.validate_ec2_others_costs()
    
    if correct_service:
        print(f"\n🎯 VALIDATION SUCCESSFUL!")
        print(f"Service name: {correct_service}")
        print("Monthly comparison:")
        for month, actual in monthly_data.items():
            target = validator.target_figures.get(month, 0)
            diff = actual - target
            print(f"  {month}: Actual ${actual:.2f} vs Target ${target:.2f} (Diff: ${diff:.2f})")
        
        # Step 3: Get detailed breakdown for the correct service
        validator.detailed_usage_type_analysis(correct_service)
        
    else:
        print("\n❌ VALIDATION FAILED")
        print("Could not find matching service name or data")
        print("Available EC2 services found:")
        for service in ec2_services:
            print(f"  - {service}")

if __name__ == "__main__":
    main()
