# excel_processing.py

import pandas as pd
from django.utils.timezone import now
from .models import MutualFundData, UploadedFile
import pandas as pd
from django.shortcuts import render
from django.http import JsonResponse

import matplotlib.pyplot as plt
import io
import base64

def process_amc_excel_file(amc, scheme, file):
    """
    Determines which function to call based on the AMC.
    """
    amc_functions = {
        "JM Financial Mutual Fund": JM_Financial_Mutual_Fund,
        "SBI Mutual Fund" : SBI_Mutual_Fund,
        "ICICI Prudential Mutual Fund" : ICICI_Prudential_Mutual_Fund,
        #"Aditya Birla Sun Life Mutual Fund": Aditya_Birla_Sun_Life_Mutual_Fund,
        
       
    }
    print(f"Processing AMC: {amc.name}")
    processing_function = amc_functions.get(amc.name, default_excel_processing)
    processing_function(file, scheme,amc)
    print(amc.name)


def safe_strip(value):
    """Convert to string and strip if it's not NaN."""
    if isinstance(value, str):
        return value.strip()
    return str(value) if pd.notna(value) else ''  # Convert NaN to empty string


def JM_Financial_Mutual_Fund(file, scheme, amc):
    print(amc.name)
    print(f'Scheme Name: {scheme.scheme_name}')
    print("Processing Excel file for AMC and updating the existing data in MutualFundData.")

    try:
        df = pd.read_excel(file, header=3)
        df.columns = df.columns.str.strip().str.replace('\n', ' ', regex=True)  # Clean column names

        # Replace "NIL" with 0 and handle missing values
        df.replace("NIL", 0, inplace=True)
        df.fillna({
            'Quantity': 0,
            'Market Value (Rs. In Lakhs)': 0,
            '% age to NAV': 0,
            'ISIN': '',
        }, inplace=True)

        # Convert Quantity to numeric if available
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        elif 'Quantity/Face Value' in df.columns:
            df['Quantity/Face Value'] = pd.to_numeric(df['Quantity/Face Value'], errors='coerce').fillna(0)
            df.rename(columns={'Quantity/Face Value': 'Quantity'}, inplace=True)

        if 'Market Value (Rs. In Lakhs)' in df.columns:
            df['Market Value (Rs. In Lakhs)'] = pd.to_numeric(df['Market Value (Rs. In Lakhs)'], errors='coerce').fillna(0)

        # Handle 'Yield %' column safely
        if 'Yield %' in df.columns:
            df['Yield %'] = df['Yield %'].astype(str).str.rstrip('%').replace('nan', None)
            df['Yield %'] = pd.to_numeric(df['Yield %'], errors='coerce').fillna(0)

        # Check if the uploaded file already exists in the database
        uploaded_file = UploadedFile.objects.filter(amc=amc, scheme=scheme).first()

        

        # Delete old MutualFundData records for the scheme
        deleted_count, _ = MutualFundData.objects.filter(scheme=scheme).delete()
        if deleted_count > 0:
            print(f"Deleted {deleted_count} existing records for scheme: {scheme.scheme_name}")

        # Initialize category totals
        equity_total = debt_total = money_market_total = others_total = cash_equivalents_total = treps_reverse_repo_total = alternative_investment_funds_units_total = government_securities_total = net_current_assets_total= 0
        industry_investments = {}  # Store industry-wise investments
        instrument_nav_percentages = []  # Store top 5 instruments by NAV

        current_category = None  # Keep track of current category
        
        category_totals = {
            'Equity': 0,
            'Debt': 0,
            'Money Market': 0,
            'Cash & Cash Equivalents': 0,
            'Government Securities': 0,
            'Alternative Investment Funds Units': 0,
            'Reverse Repo/Corporate': 0,
            'Net Current Assets'
            'Others': 0
            }

        for index, row in df.iterrows():
            name = safe_strip(str(row.get('Name of the Instruments', ''))).lower()
            if name.startswith("grand total"):
                break
            if name.startswith("net assets"):
                break

            # Detect section headers and update category
            if name.startswith('equity'):
                current_category = 'Equity'
                continue
            elif name.startswith('debt'):
                current_category = 'Debt'
                continue
            elif 'triparty repo' in name:
                current_category = 'Reverse Repo/Corporate'
                continue
            elif name.startswith('money market'):
                current_category = 'Money Market'
                continue
            elif name.startswith('government securities'):
                current_category = 'Government Securities'
                continue
            elif name.startswith('cash & cash equivalents'):
                current_category = 'Cash & Cash Equivalents'
                continue
            elif any(keyword in name for keyword in ['reverse repo', 'corporate debt repo']):
                current_category = 'Reverse Repo/Corporate'
                continue
            elif name.startswith('alternative investment'):
                current_category = 'Alternative Investment Funds Units'
                continue
            elif name.startswith('net current assets'):
                #current_category = 'Net Current Assets'
                net_current_assets_total = row.get('Market Value (Rs. In Lakhs)', 0)
                continue
            elif name.startswith('other'):
                current_category = 'Others'
                continue

            if not name or 'ISIN' not in df.columns:
                continue  # Skip rows without ISIN or instrument name

            row_name = name.lower()


            # Skip any row where 'subtotal' is present
            if "subtotal" in row_name:
                print(f"Skipping subtotal row: {name}")
                continue

            # Process only 'total' rows (excluding 'subtotal')
            if "total" in row_name:
                market_value = row.get('Market Value (Rs. In Lakhs)', 0)

                # Ensure we add a category's total only once
                if current_category not in category_totals:
                    category_totals[current_category] = market_value
                else:
                    print(f"Skipping duplicate total for category: {current_category}")
                    continue  # Avoid adding duplicate total values

                # Assign correct totals to each category
                if current_category == 'Equity':
                    equity_total += market_value
                elif current_category == 'Debt':
                    debt_total += market_value
                elif current_category == 'Money Market':
                    money_market_total += market_value
                elif current_category == 'Cash & Cash Equivalents':
                    cash_equivalents_total += market_value
                elif current_category == 'Government Securities':
                    government_securities_total += market_value
                elif current_category == 'Alternative Investment Funds Units':
                    alternative_investment_funds_units_total += market_value
                elif current_category == 'Reverse Repo/Corporate':
                    treps_reverse_repo_total += market_value
                elif current_category == 'Net Current Assets':
                    net_current_assets_total += market_value
                elif current_category == 'Others':
                    others_total += market_value

                # Print debugging output
                print(f"{current_category} Total: {market_value}")

            isin = safe_strip(str(row.get('ISIN', '')))
            if not isin:
                continue

            instrument_type = current_category if current_category else 'Others'
            market_value = row.get('Market Value (Rs. In Lakhs)', 0)

            category_totals = {}

           
            # # Insert new record into MutualFundData
            instrument = MutualFundData(
                amc=amc,
                scheme=scheme,
                instrument_name=name,
                isin=isin,
                industry_rating=safe_strip(row.get('Industry/Rating', '')),
                quantity=row.get('Quantity', 0),
                market_value=market_value,
                percentage_to_nav=row.get('% age to NAV', 0),
                yield_percentage=row.get('Yield %', None),
                ytc=row.get('^YTC (AT1/Tier 2 bonds)', None),
                instrument_type=instrument_type,
            )
            instrument.save()

            # Aggregate industry investments
            industry_rating = safe_strip(row.get('Industry/Rating', ''))
            if industry_rating:
                industry_investments[industry_rating] = industry_investments.get(industry_rating, 0) + market_value

            # Store top 5 instruments by NAV
            nav_percentage = row.get('% age to NAV', 0)
            instrument_nav_percentages.append((name, nav_percentage, market_value))

       # combined_others_total = money_market_total + others_total + cash_equivalents_total + treps_reverse_repo_total + alternative_investment_funds_units_total
        #print(f'combined others total: {combined_others_total}')
        
        total_market_value = equity_total + debt_total  + money_market_total + cash_equivalents_total + treps_reverse_repo_total + net_current_assets_total+ alternative_investment_funds_units_total + government_securities_total + others_total
        #print(f' line number 862 : total market value: {total_market_value}')
        
        total = total_market_value if total_market_value > 0 else 1
        equity_percentage = (equity_total / total) * 100
        debt_percentage = (debt_total / total) * 100
        #others_percentage = (combined_others_total / total) * 100

        # Get top 5 industries by market value
        sorted_industries = sorted(industry_investments.items(), key=lambda x: x[1], reverse=True)[:5]
        top_sector = [{"industry": industry, "investment": round(investment, 2)} for industry, investment in sorted_industries]
        print(top_sector)
        # Get top 5 instruments by NAV
        sorted_instruments = sorted(instrument_nav_percentages, key=lambda x: x[1], reverse=True)[:5]
        top_holdings = [{"instrument_name": instrument, "nav_percentage": round(nav_percentage, 2)}
                        for instrument, nav_percentage, _ in sorted_instruments]

        #Print results
        print(' line number 878------------------------------------------')
        print(f"Equity Total: {equity_total}")
        print(f"Debt Total: {debt_total}")
        print(f"Money Market Total: {money_market_total}")
        print(f"Others Total: {others_total}")
        print(f'Government Securities Total: {government_securities_total}')
        print(f'Cash & Cash Equivalents Total: {cash_equivalents_total}')
        print(f'Treps/Reverse Repo/Corporate Total: {treps_reverse_repo_total}')
        print(f'Alternative Investment Funds Units Total: {alternative_investment_funds_units_total}')
        print(f'Net Current Assets Total: {net_current_assets_total}')
        print(f"Total Market Value: {total_market_value}")
        print('------------------------------------------')
        print(f'Category Totl in Dictionary{category_totals}')
        print('hello world ganesh')
        print(f"Top Sectors: {top_sector}")
        print(f"Top Holdings: {top_holdings}")
        final_others_total = money_market_total + others_total + treps_reverse_repo_total + alternative_investment_funds_units_total+ net_current_assets_total+ government_securities_total+ cash_equivalents_total
        print('+++++++++++++++++++++++++++++++++++++++++')
        print(f"Equity Total: {equity_total}")
        print(f"Debt Total: {debt_total}")
        print(f"Others Total: {final_others_total}")
        print(f'Cash & Cash Equivalents Total: {cash_equivalents_total}')
        print('+++++++++++++++++++++++++++++++++++++++++')
        
        category_totals = {
            'Equity': equity_total,
            'Debt': debt_total,
            # 'Money Market': money_market_total,
            'Others': final_others_total,
            'Total Market Value': total_market_value,
            # 'Government Securities': government_securities_total,
            # 'Cash & Cash Equivalents': cash_equivalents_total,
            # 'Treps/Reverse Repo/Corporate': treps_reverse_repo_total,
            # 'Alternative Investment Funds Units': alternative_investment_funds_units_total,
            # 'Net Current Assets': net_current_assets_total
            
        }
        print('------------------------------------------')
        print(f'Category Totl in Dictionary{category_totals}')
        
        # Update the uploaded file record
        if uploaded_file:
            try:
            # uploaded_file.equity_total = equity_total
            # uploaded_file.debt_total = debt_total
            # uploaded_file.other_total = others_total
            # uploaded_file.total_market_value = total_market_value
                uploaded_file.top_holdings = top_holdings
                uploaded_file.top_sectors = top_sector
                uploaded_file.category_total = category_totals
                uploaded_file.save()
                
            except Exception as e:
                print(f"Error updating the file: {e}")

    except Exception as e:
        print(f"Error processing file: {e}")
        
import traceback
print(traceback.format_exc())  # This will print more detailed traceback info
        
        

def SBI_Mutual_Fund(file, scheme, amc):
    print(amc.name)
    print(f'scheme name :{scheme.scheme_name}')
    
    print("Processing Excel file for AMC and updating the existing data in MutualFundData.")

    try:
        df = pd.read_excel(file, header=5)
        df.columns = df.columns.str.strip()  # Clean column names
        df.columns = df.columns.str.replace('\n', ' ', regex=True)
        #df['Market Value (Rs. In Lakhs)'] = pd.to_numeric(df['Market value (Rs. in Lakhs)'], errors='coerce').fillna(0)
        
        market_value_col = next((col for col in df.columns if col.lower().startswith("market value")), None)

        if market_value_col:
            df[market_value_col] = pd.to_numeric(df[market_value_col], errors='coerce').fillna(0)
        else:
            print("Error: Market value column not found!")
            

        print("Available columns:", df.columns.tolist()) 
        # Replace "NIL" with 0 and fill missing values for numeric columns
        df.replace("NIL", 0, inplace=True)
        df.fillna({
         'Quantity': 0,
         'Market value (Rs. in Lakhs)': 0,
         '% to AUM': 0,
         'YTC %##': 0,
         'YTM %': 0,
         'ISIN': '',
        }, inplace=True)
        
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        elif 'Quantity/Face Value' in df.columns:
            df['Quantity/Face Value'] = pd.to_numeric(df['Quantity/Face Value'], errors='coerce').fillna(0)
            df.rename(columns={'Quantity/Face Value': 'Quantity'}, inplace=True)
            
      
        
        # Replace '#' or other non-numeric values with NaN
        df['% to AUM'] = pd.to_numeric(df['% to AUM'], errors='coerce').fillna(0)

        
        df['YTM %'] = pd.to_numeric(df['YTM %'], errors='coerce').fillna(0)
        
        if 'YTM %' in df.columns:
            df['YTM %'] = df['YTM %'].astype(str).str.rstrip('%').replace('nan', None)
            df['YTM %'] = pd.to_numeric(df['YTM %'], errors='coerce').fillna(0)
            
        
        # Check if the uploaded file already exists in the database
        uploaded_file = UploadedFile.objects.filter(amc=amc, scheme=scheme).first()

        deleted_count, _ = MutualFundData.objects.filter(scheme=scheme).delete()
        if deleted_count > 0:
            print(f"Deleted {deleted_count} existing records for scheme: {scheme.scheme_name}")
        
        # Initialize individual category totals
        
        equity_total = 0
        debt_total = 0
        money_market_total = 0
        others_current = 0
        others_total = 0
        Other_current_assets_total = 0
       

        industry_investments = {}
        instrument_aum_percentages = []

        for index, row in df.iterrows():
            name = safe_strip(row.get('Name of the Instrument / Issuer', ''))
            lower_name = name.lower()
            
            # Detect section header rows and update current_category
             # Exit the loop immediately
            if lower_name .startswith( "grand total"):
                break 
            if lower_name.startswith('equity'):
                current_category = 'Equity'
                continue
            elif lower_name.startswith('debt'):
                current_category = 'Debt'
                continue
            elif lower_name.startswith('money market'):
                current_category = 'Money Market'
                continue
            elif lower_name.startswith('other'):
                current_category = 'Others'
                continue
            #elif lower_name.startswith('other current'):
                #continue

            if not name:
                continue

            # Check if the row contains "Total" and update category total
            if "total" in lower_name :
                
                market_value = row['Market value (Rs. in Lakhs)']
                if current_category == 'Equity':
                    
                    equity_total += market_value  # Accumulate if multiple total rows exist
                    print(f"Equity Total: {equity_total}")
                elif current_category == 'Debt':
                    debt_total += market_value
                    print(f"Debt Total: {debt_total}")
                elif current_category == 'Money Market':
                    money_market_total += market_value
                    print(f"Money Market Total: {money_market_total}")
                elif current_category == 'Others':
                    others_total += market_value
                    print(f"Others Total: {others_total}")
                elif current_category == 'Other Current': 
                    
                    Other_current_assets_total += market_value
                    print(f"Other Current Total: {Other_current_assets_total}")
                continue  # Skip processing further for "Total" row
            print(f'current category : {current_category}')
           
                
            if not name:
                continue
                
            isin = safe_strip(row.get('ISIN', ''))
            market_value = safe_strip(row.get('Market value (Rs. in Lakhs)', ''))

            if not isin :
                continue  

            instrument_type = current_category if current_category else 'Others'
            market_value = row['Market value (Rs. in Lakhs)']

            instrument = MutualFundData(
                amc=amc,
                scheme=scheme,
                instrument_name=name,
                isin=isin,
                industry_rating=safe_strip(row.get('Industry / Rating', '')),
                quantity=row['Quantity'],
                market_value=market_value,
                percentage_to_nav=row['% to AUM'],
                yield_percentage=row['YTM %'],
                ytc=row.get('YTC %##', None),
                instrument_type=instrument_type,
            )
            instrument.save()

            # Aggregate investment for industry/ratings
            industry_rating = safe_strip(row.get('Rating / Industry^', ''))
            if industry_rating:
                industry_investments[industry_rating] = industry_investments.get(industry_rating, 0) + market_value

            # Store the top 5 instruments by % to NAV
            nav_percentage = row['% to AUM']
            instrument_aum_percentages.append((name, nav_percentage, market_value))
            
            
        others_total = others_total 
        # Calculate combined Money Market and Others into one category
        combined_others_total = money_market_total + others_total + Other_current_assets_total

        # Calculate the overall total market value
        total_market_value = equity_total + debt_total + others_total + money_market_total
        total = total_market_value if total_market_value > 0 else 1

        equity_percentage = (equity_total / total) * 100
        debt_percentage = (debt_total / total) * 100
        others_percentage = (combined_others_total / total) * 100

     # Get top 5 industries by total market value
        sorted_industries = sorted(industry_investments.items(), key=lambda x: x[1], reverse=True)[:5]
        top_sectors = [{"industry": industry, "investment": round(investment, 2)} for industry, investment in sorted_industries]

        # Get top 5 instruments by % to NAV
        sorted_instruments = sorted(instrument_aum_percentages, key=lambda x: x[1], reverse=True)[:5]
        top_holdings = [{"instrument_name": instrument, "nav_percentage": round(nav_percentage, 2)} for instrument, nav_percentage, _ in sorted_instruments]

        

        print("Top Sectors:", top_sectors)
        print("Top Holdings:", top_holdings)



        print("Equity Total:", equity_total)
        print("Debt Total:", debt_total)
        print("Money Market Total:", money_market_total)
        print("Others Total:", others_total)
        print("Total Market Value:", total_market_value)
        print("Equity Percentage:", equity_percentage)
        print("Debt Percentage:", debt_percentage)
        print("Others Percentage:", others_percentage)
        print("Top Industries:", top_sectors)
        print("Top Instruments:", top_holdings)
        print("Data saved successfully!")
        
        category_totals = { 
                           'Equity': equity_total,
                           'Debt': debt_total,
                           'Money Market': money_market_total,
                           'Others': others_total,
                           'Total Market Value': total_market_value,
                            }  
        
               # Ensure uploaded file exists
        if uploaded_file:
            try:
                # Update the uploaded file with the latest totals
                print('Final Before update into DB - Others Total:', others_total)
                
                
                
                
                # Top sectors and holdings
                uploaded_file.category_total = category_totals
                uploaded_file.top_sectors = top_sectors
                uploaded_file.top_holdings = top_holdings
                
                # Save changes to the database
                uploaded_file.save()
                print('File updated successfully!')
            
            except Exception as e:
                print(f"Error updating the file: {e}")
                   
        else:
            print("No uploaded file found.")
    

    
    except Exception as e:
        print(f"Error reading Excel file: {e}")          
        
     
import re    
def ICICI_Prudential_Mutual_Fund(file, scheme, amc):
    print(amc.name)
    print(f'Scheme name: {scheme.scheme_name}')
    
    print("Processing Excel file for AMC and updating the existing data in MutualFundData.")
    
    try:
        df = pd.read_excel(file, header=3)
        df.columns = df.columns.str.strip()  # Clean column names   
        df.columns = df.columns.str.replace('\n', ' ', regex=True)
                
        market_value_col = next((col for col in df.columns if re.match(r"(?i)Exposure/Market\s?Value\(Rs\.Lakh\)", col.strip())), None)

        if market_value_col:
            df[market_value_col] = pd.to_numeric(df[market_value_col], errors='coerce').fillna(0)
        else:
            print("Market Value column not found in the Excel file.")
            return  # Exit if market value column is missing
        
        print("Available columns:", df.columns.tolist())
        
        df.replace("NIL", 0, inplace=True)
         # Replace "NIL" with 0 and fill missing values for numeric columns
        df.replace("NIL", 0, inplace=True)
        df.fillna({
         'Quantity': 0,
         'Market value (Rs. in Lakhs)': 0,
         '% to Nav': 0,
         'Yield of the instrument': 0,
         'Yield to Call @': 0,
         'ISIN': '',
        }, inplace=True)
        
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        elif 'Quantity/Face Value' in df.columns:
            df['Quantity/Face Value'] = pd.to_numeric(df['Quantity/Face Value'], errors='coerce').fillna(0)
            df.rename(columns={'Quantity/Face Value': 'Quantity'}, inplace=True)
            
        df['% to Nav'] = pd.to_numeric(df['% to Nav'], errors='coerce').fillna(0)
        df['Yield of the instrument'] = pd.to_numeric(df['Yield of the instrument'], errors='coerce').fillna(0)
        
         # Check if the uploaded file already exists in the database
        uploaded_file = UploadedFile.objects.filter(amc=amc, scheme=scheme).first()

        deleted_count, _ = MutualFundData.objects.filter(scheme=scheme).delete()
        if deleted_count > 0:
            print(f"Deleted {deleted_count} existing records for scheme: {scheme.scheme_name}")
          

        # Initialize a category totals dictionary
        category_totals = {
            'Equity': 0,
            'Debt': 0,
            'Money Market': 0,
            'Others': 0,
            'Reverse Repo': 0,
            'Treps': 0,
            'Units of Real Estate Investment Trust (REITs)': 0,
            'Units of an Alternative Investment Fund (AIF)': 0,
            'Gold': 0,
            'Net Current Assets': 0
        }
        
        current_category = None  # Initialize category variable
        industry_investments = {}
        instrument_aum_percentages = []
       
        

        # for index, row in df.iterrows():
        #     name = safe_strip(row.get('Company/Issuer/Instrument Name', '')).lower()
        #     market_value = row.get(market_value_col, 0)  # Ensure valid market value

        #     if not market_value or isinstance(market_value, str):
        #         market_value = 0  # Handle invalid market values

        #     # If a category header is found, update `current_category` and store its market value
        #     if name.startswith('equity & equity related'):
        #         current_category = 'Equity'
        #     elif name.startswith('debt'):
        #         current_category = 'Debt'
        #     elif name.startswith('money market'):
        #         current_category = 'Money Market'
        #     elif name.startswith('reverse repo'):
        #         current_category = 'Reverse Repo'
        #     elif name.startswith('treps'):
        #         current_category = 'Treps'
        #     elif name.startswith('gold'):
        #         current_category = 'Gold'
        #     elif name.startswith('units of real estate investment trust (reits)'):
        #         current_category = 'Units of Real Estate Investment Trust (REITs)'
        #     elif name.startswith('units of an alternative investment fund (aif)'):
        #         current_category = 'Units of an Alternative Investment Fund (AIF)'
        #     elif name.startswith('net current assets'):
        #         current_category = 'Net Current Assets'
        #     elif name.startswith('other'):
        #         current_category = 'Others'

        #     # Store only the market value of the category header row
        #     if current_category and name.startswith(current_category.lower()):
        #         category_totals[current_category] = market_value
        #         print(f"Set category total for {current_category}: {market_value}")
        #         continue  # Skip further processing for category header rows
        # for index, row in df.iterrows():
        #     name = safe_strip(row.get('Company/Issuer/Instrument Name', '')).lower()
        #     market_value = row.get(market_value_col, 0)  # Ensure valid market value

        #     if not market_value or isinstance(market_value, str):
        #         market_value = 0  # Handle invalid market values
        #     name = safe_strip(row.get('Company/Issuer/Instrument Name', '')).lower()
    
        #     # Stop processing when 'Total Net Assets' is encountered
        #     if name.startswith('total net assets'):
        #         print("Reached 'Total Net Assets' row. Stopping processing.")
        #         break
            
        #     # If a category header is found, update `current_category` and store its market value
        #     if "equity & equity related" in name:
        #         current_category = 'Equity'
        #     elif "debt" in name:
        #         current_category = 'Debt'
        #     elif "money market" in name:
        #         current_category = 'Money Market'
        #     elif "reverse repo" in name:
        #         current_category = 'Reverse Repo'
        #     elif "treps" in name:
        #         current_category = 'Treps'
        #     elif "gold" in name:
        #         current_category = 'Gold'
        #     elif "units of real estate investment trust (reits)" in name:
        #         current_category = 'Units of Real Estate Investment Trust (REITs)'
        #     elif "units of an alternative investment fund (aif)" in name:
        #         current_category = 'Units of an Alternative Investment Fund (AIF)'
        #     elif "net current assets" in name:
        #         current_category = 'Net Current Assets'
        #     elif "others" in name:
        #         current_category = 'Others'

        #     # Store only the market value of the category header row
        #     if current_category and any(keyword in name for keyword in ["equity & equity related", "debt", "money market", "reverse repo", "treps", "gold", "units of real estate investment trust (reits)", "units of an alternative investment fund (aif)", "net current assets", "other"]):
        #         category_totals[current_category] = market_value
        #         print(f"Set category total for {current_category}: {market_value}")
        #         continue  # Skip further processing for category header rows

        #     # Other rows should not modify category_totals, only belong to the category
        
        # Define category mappings for exact match
      
        # Define category mapping (lowercased for optimized lookup)
        category_mapping = {
            "equity & equity related instruments": "Equity",
            "debt": "Debt",
            "money market": "Money Market",
            "reverse repo": "Reverse Repo",
            "treps": "Treps",
            "gold": "Gold",
            "units of real estate investment trust (reits)": "Units of Real Estate Investment Trust (REITs)",
            "units of an alternative investment fund (aif)": "Units of an Alternative Investment Fund (AIF)",
            "net current assets": "Net Current Assets",
            "others": "Others",
            "units of mutual funds": "Units of Mutual Funds"
        }

        category_mapping = {k.lower(): v for k, v in category_mapping.items()}  # Convert keys to lowercase

        # Initialize category-related variables
        category_totals = {v: 0 for v in category_mapping.values()}
        current_category = None  

        # Identify the correct Market Value column dynamically
        market_value_col = next((col for col in df.columns if re.match(r"(?i)Exposure/Market\s?Value\(Rs\.Lakh\)", col.strip())), None)
        if not market_value_col:
            print("Market Value column not found.")
            return  # Exit if the required column is missing

        # Loop through rows once, optimizing category detection
        for index, row in df.iterrows():
            name = str(row.get('Company/Issuer/Instrument Name', '')).strip().lower()

            # Stop processing when 'Total Net Assets' is encountered
            if "total net assets" in name:
                print("Reached 'Total Net Assets' row. Stopping processing.")
                break

            # Extract Market Value and convert safely
            market_value = pd.to_numeric(row.get(market_value_col, 0), errors='coerce')
            market_value = 0 if pd.isna(market_value) else market_value  # Handle NaN cases
            #skip blanck row 
            
            # if not name:
            #     continue
            #skip line where quantity is not present 
            # quantity = row.get('Quantity', '')
            # if not quantity:
            #     continue
            
            # **Ensure `key` is always defined within the loop**
            for key, category in category_mapping.items():
                key_lower = key.lower().strip()  # Normalize key
                if key_lower == "reverse repo":
                    # **Exact match for "Reverse Repo" only**
                    if name.strip() == key:
                        current_category = category
                        category_totals[current_category] = market_value
                        print(f"Exact Match Found: {current_category}, Market Value: {market_value}")
                        break  # Exit loop after match
                elif key_lower == "gold":
                    if name.startswith("gold "):  # **Only match "Gold" at the start**
                        current_category = category
                        category_totals[current_category] = market_value
                        print(f"Gold Category Assigned: {current_category}, Market Value: {market_value}")
                        break
                elif key_lower == "debt":
                    if name.startswith("debt "):  # **Only match "Debt" at the start**
                        current_category = category
                        category_totals[current_category] = market_value
                        print(f"Debt Category Assigned: {current_category}, Market Value: {market_value}")
                        break
                elif key_lower == "units of an alternative investment fund (aif)":
                    if name == key_lower:  # **Full case-insensitive match**
                        current_category = category
                        category_totals[current_category] = market_value
                        print(f"AIF Category Assigned: {current_category}, Market Value: {market_value}")
                        break
                elif key_lower == "units of real estate investment trust (reits)":
                    if name == key_lower:  # **Exact match for REITs**
                        current_category = category
                        category_totals[current_category] = market_value
                        print(f"REITs Category Assigned: {current_category}, Market Value: {market_value}")
                        break
                else:
                    # **Full-word match for all other categories**
                    pattern = r'\b' + re.escape(key) + r'\b'
                    if re.search(pattern, name):  
                        current_category = category
                        category_totals[current_category] = market_value
                        print(f"Category Identified: {current_category}, Market Value: {market_value}")
                        break  # Exit loop after match

            # Process valid data rows (excluding category headers)
            if current_category:
                instrument_type = current_category  # Assign instrument type

            # Extract Market Value and convert safely
            market_value = pd.to_numeric(row.get(market_value_col, 0), errors='coerce')
            market_value = 0 if pd.isna(market_value) else market_value  # Handle NaN cases

            # Optimized category matching (direct dictionary lookup)

        # Check for category match ensuring full-word match
            


            # Collect data for industry and instrument AUM
            industry = safe_strip(row.get('Industry / Rating', ''))
            if industry:
                industry_investments[industry] = industry_investments.get(industry, 0) + row[market_value_col]

            instrument_name = name
            nav_percentage = row.get('% to Nav', 0)
            instrument_aum_percentages.append((instrument_name, nav_percentage, row[market_value_col]))

            # Insert data into the database
            instrument_type = current_category if current_category else 'Others'
            instrumnet = MutualFundData(
                amc=amc,
                scheme=scheme,
                instrument_name=name,
                isin=safe_strip(row.get('ISIN', '')),
                industry_rating=safe_strip(row.get('Industry / Rating', '')),
                quantity=row['Quantity'],
                market_value=row[market_value_col],  # Store actual market value, not the column name
                percentage_to_nav=row['% to Nav'],
                yield_percentage=row['Yield of the instrument'],
                ytc=row.get('Yield to Call @', None),
                instrument_type=instrument_type,
            )
            instrumnet.save()
        
        total_market_value = sum(category_totals.values())    
        print('Category Totals:', category_totals)
        print('Total market value:', total_market_value )
        
        # Get top 5 industries by total market value
        # Filter out rows where 'ISIN' is empty
        
        
       # Initialize lists to hold industry and instrument data
        industry_investments = {}
        instrument_aum_percentages = []

        # Loop over each row in the dataframe
        for _, row in df.iterrows():
            # Check if ISIN is blank or missing, skip the row if ISIN is blank or NaN
            if pd.isna(row['ISIN']) or row['ISIN'] == '':
                continue  # Skip this row if ISIN is blank or missing
            
            # Extract industry and market value data for top 5 industries
            industry = row['Industry/Rating']
            market_value = row['Exposure/Market Value(Rs.Lakh)']
            if industry in industry_investments:
                industry_investments[industry] += market_value
            else:
                industry_investments[industry] = market_value
            
            # Extract instrument and NAV percentage data for top 5 instruments
            instrument_name = row['Company/Issuer/Instrument Name']
            nav_percentage = row.get('% to Nav', 0)
            instrument_aum_percentages.append((instrument_name, nav_percentage, row['Exposure/Market Value(Rs.Lakh)']))

        # Get top 5 industries by total market value
        sorted_industries = sorted(industry_investments.items(), key=lambda x: x[1], reverse=True)[:5]
        top_sectors = [{"industry": industry, "investment": round(investment, 2)} for industry, investment in sorted_industries]

        # Get top 5 instruments by % to NAV
        sorted_instruments = sorted(instrument_aum_percentages, key=lambda x: x[1], reverse=True)[:5]
        top_holdings = [{"instrument_name": instrument, "nav_percentage": round(nav_percentage, 2)} for instrument, nav_percentage, _ in sorted_instruments]

        # Print results
        
        


        if uploaded_file:
            print("file uploded....")
            try:
                # Update the uploaded file with the latest totals
                # Top sectors and holdings
                uploaded_file.category_total = category_totals
                uploaded_file.top_sectors = top_sectors
                uploaded_file.top_holdings = top_holdings
                
                # Save changes to the database
                uploaded_file.save()
                print('File updated successfully!')
            
            except Exception as e:
                print(f"Error updating the file: {e}")
        else :
            print("No file uploaded")

    except Exception as e:
        print(f"Error reading Excel file: {e}")



def default_excel_processing(file, scheme, amc):
    """
    Default function for AMCs without specific processing logic.
    """
    print(f"Default processing for {scheme.scheme_name}. No specific function defined.")


