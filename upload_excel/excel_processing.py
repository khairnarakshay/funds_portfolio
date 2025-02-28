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

        if uploaded_file:
            print("Existing Portfolio found, updating the totals!")
        else:
            uploaded_file = UploadedFile.objects.create(
                amc=amc,
                scheme=scheme,
                file=file,
                update_logs=now()  # Adjust timestamp
            )
            print("New Portfolio created!")

        # Delete old MutualFundData records for the scheme
        deleted_count, _ = MutualFundData.objects.filter(scheme=scheme).delete()
        if deleted_count > 0:
            print(f"Deleted {deleted_count} existing records for scheme: {scheme.scheme_name}")

        # Initialize category totals
        equity_total = debt_total = money_market_total = others_total = cash_equivalents_total = treps_reverse_repo_total = alternative_investment_funds_units_total = 0
        industry_investments = {}  # Store industry-wise investments
        instrument_nav_percentages = []  # Store top 5 instruments by NAV

        current_category = None  # Keep track of current category
        
        category_totals = {
            'Equity': 0,
            'Debt': 0,
            'Money Market': 0,
            'Cash & Cash Equivalents': 0,
            'Alternative Investment Funds Units': 0,
            'Reverse Repo/Corporate': 0,
            'Others': 0
            }

        for index, row in df.iterrows():
            name = safe_strip(str(row.get('Name of the Instruments', ''))).lower()
            if name.startswith("grand total"):
                break

            # Detect section headers and update category
            if name.startswith('equity'):
                current_category = 'Equity'
                continue
            elif name.startswith('debt'):
                current_category = 'Debt'
                continue
            elif name.startswith('money market'):
                current_category = 'Money Market'
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
                elif current_category == 'Alternative Investment Funds Units':
                    alternative_investment_funds_units_total += market_value
                elif current_category == 'Reverse Repo/Corporate':
                    treps_reverse_repo_total += market_value
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
            row_name = name.lower()

            # Skip any row where 'subtotal' is present
            if "subtotal" in row_name:
                print(f"Skipping subtotal row: {name}")
                continue

            # Now process only 'total' rows (excluding 'subtotal')
            if "total" in row_name:
                market_value = row.get('Market Value (Rs. In Lakhs)', 0)

                # Ensure that we only add a category's total once
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
                elif current_category == 'Alternative Investment Fund Units':
                    alternative_investment_funds_units_total += market_value
                elif current_category == 'Reverse Repo/Corporate':
                    treps_reverse_repo_total += market_value
                elif current_category == 'Others':
                    others_total += market_value
                
                # Print debugging output
                print(f"{current_category} Total: {market_value}")

                
            isin = safe_strip(str(row.get('ISIN', '')))
            if not isin:
                continue

            instrument_type = current_category if current_category else 'Others'
            market_value = row.get('Market Value (Rs. In Lakhs)', 0)

            # Insert new record into MutualFundData
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
            industry_rating = safe_strip(row.get('Rating / Industry^', ''))
            if industry_rating:
                industry_investments[industry_rating] = industry_investments.get(industry_rating, 0) + market_value

            # Store top 5 instruments by NAV
            nav_percentage = row.get('% age to NAV', 0)
            instrument_nav_percentages.append((name, nav_percentage, market_value))

       # combined_others_total = money_market_total + others_total + cash_equivalents_total + treps_reverse_repo_total + alternative_investment_funds_units_total
        #print(f'combined others total: {combined_others_total}')
        
        total_market_value = equity_total + debt_total  + money_market_total + cash_equivalents_total + treps_reverse_repo_total + alternative_investment_funds_units_total
        #print(f' line number 862 : total market value: {total_market_value}')
        
        total = total_market_value if total_market_value > 0 else 1
        equity_percentage = (equity_total / total) * 100
        debt_percentage = (debt_total / total) * 100
        #others_percentage = (combined_others_total / total) * 100

        # Get top 5 industries by market value
        sorted_industries = sorted(industry_investments.items(), key=lambda x: x[1], reverse=True)[:5]
        top_sector = [{"industry": industry, "investment": round(investment, 2)} for industry, investment in sorted_industries]

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
        print(f'Cash & Cash Equivalents Total: {cash_equivalents_total}')
        print(f'Treps/Reverse Repo/Corporate Total: {treps_reverse_repo_total}')
        print(f'Alternative Investment Funds Units Total: {alternative_investment_funds_units_total}')
        print(f"Total Market Value: {total_market_value}")
        print('------------------------------------------')
        print(f'Category Totl in Dictionary{category_totals}')
        print(f"Top Sectors: {top_sector}")
        print(f"Top Holdings: {top_holdings}")
        
        category_totals = {
            'Equity': equity_total,
            'Debt': debt_total,
            'Money Market': money_market_total,
            'Others': others_total,
            'Cash & Cash Equivalents': cash_equivalents_total,
            'Treps/Reverse Repo/Corporate': treps_reverse_repo_total,
            'Alternative Investment Funds Units': alternative_investment_funds_units_total
            
        }
        print('------------------------------------------')
        print(f'Category Totl in Dictionary{category_totals}')
        
        # Update the uploaded file record
        if uploaded_file:
            uploaded_file.equity_total = equity_total
            uploaded_file.debt_total = debt_total
            uploaded_file.other_total = others_total
            uploaded_file.total_market_value = total_market_value
            uploaded_file.top_holdings = top_holdings
            uploaded_file.top_sectors = top_sector
            uploaded_file.category_total = category_totals
            uploaded_file.save()
        result = {
        "status": "success",
        "message": "",
        "data": {}
    }
        result["data"] = {
            "equity_total": equity_total,
            "debt_total": debt_total,
            "others_total": others_total,
            "total_market_value": total_market_value,
            "equity_percentage": equity_percentage,
            "debt_percentage": debt_percentage,
            #"others_percentage": others_percentage,
            "top_sectors": top_sector,
            "top_holdings": top_holdings,
        }
        result["message"] = "Data processed and updated successfully!"
        
        return JsonResponse(result)

    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        print(traceback.format_exc())  # This will print more detailed traceback info



def SBI_Mutual_Fund(file, scheme, amc):
    print(amc.name)
    print(f'scheme name :{scheme.scheme_name}')
    """
    
    Processes Excel file for the AMC and updates existing entry in MutualFundData if it exists.
    """
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
            
            
        # market_value_col = next((col for col in df.columns if col.lower().startswith("market value")), None)
        #df['Market Value\n(Rs. In Lakhs)'] = pd.to_numeric(df['Market value (Rs. in Lakhs)'], errors='coerce').fillna(0)
        
        
        # Replace '#' or other non-numeric values with NaN
        df['% to AUM'] = pd.to_numeric(df['% to AUM'], errors='coerce').fillna(0)

        
        df['YTM %'] = pd.to_numeric(df['YTM %'], errors='coerce').fillna(0)
        
        if 'YTM %' in df.columns:
            df['YTM %'] = df['YTM %'].astype(str).str.rstrip('%').replace('nan', None)
            df['YTM %'] = pd.to_numeric(df['YTM %'], errors='coerce').fillna(0)
            
        
        # Check if the uploaded file already exists in the database
        uploaded_file = UploadedFile.objects.filter(amc=amc, scheme=scheme).first()
        if uploaded_file:
            # Update the existing entry in MutualFundData
            print("Existing Portfolio found, updating the totals!")
        else:
            # Create a new entry in MutualFundData
            uploaded_file = UploadedFile.objects.create(
                amc=amc,
                scheme=scheme,
                file=file,
                update_logs=now()  # Adjust 'uploaded_at' to current time only if you're creating a new record
            )
            print("New Portfolio created!")
            
        #check if the MutualFundData already exists for the schem\
        #if exists then delete all the records for the scheme
        
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
            elif lower_name.startswith('other current'):
                continue

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
            # print(f"Processing row: {name}")
            # #print(f"Market Value: {market_value}")
            # print(f"Category: {current_category}")
            # print(f"Lower Name: {lower_name}")
            # print(f"Name: {name}")
            # print(f"Row: {row}")
                
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
        others_total = others_total + Other_current_assets_total+ money_market_total
        # Calculate combined Money Market and Others into one category
        combined_others_total = money_market_total + others_total + Other_current_assets_total

        # Calculate the overall total market value
        total_market_value = equity_total + debt_total + others_total 
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
                
                # Update the uploaded file fields
                uploaded_file.equity_total = equity_total
                uploaded_file.debt_total = debt_total
                # uploaded_file.money_market_total = money_market_total  # Uncomment if needed
                uploaded_file.other_total = others_total
                uploaded_file.total_market_value = total_market_value
                
                # Uncomment these if percentages are needed:
                # uploaded_file.equity_percentage = equity_percentage
                # uploaded_file.debt_percentage = debt_percentage
                # uploaded_file.others_percentage = others_percentage
                
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
        result = {
        "status": "success",
        "message": "",
        "data": {}
    }
        result["data"] = {
            "equity_total": equity_total,
            "debt_total": debt_total,
            "others_total": others_total,
            "total_market_value": total_market_value,
            "equity_percentage": equity_percentage,
            "debt_percentage": debt_percentage,
            "others_percentage": others_percentage,
            "top_sectors": top_sectors,
            "top_holdings": top_holdings,
        }
        result["message"] = "Data processed and updated successfully!"
        
        return JsonResponse(result)

    
    
    except Exception as e:
        print(f"Error reading Excel file: {e}")          
        
        # Create a dictionary to store the total investment per industry/industry rating
        #industry_investments = {}
        
        # Create a list to store the instruments and their % age to NAV for top 5
        #instrument_aum_percentages = []
        
        # # Process each row in the DataFrame
        # for index, row in df.iterrows():
        #     name = safe_strip(row.get('Name of the Instrument / Issuer', ''))
        #     lower_name = name.lower()
            
        #     if lower_name.startswith('equity'):
        #         current_category = 'Equity'
        #         continue
        #     elif lower_name.startswith('debt'):
        #         current_category = 'Debt'
        #         continue
        #     elif lower_name.startswith('money market'):
        #         current_category = 'Money Market'
        #         continue
        #     elif lower_name.startswith('other'):
        #         current_category = 'Others'
        #         continue
        #     elif lower_name.startswith('other current'):
        #         continue
            
        #     if not name:
        #         continue
        #     isin = safe_strip(row.get('ISIN', ''))
        #     market_value = safe_strip(row.get('Market value (Rs. in Lakhs)', ''))

        #     if not isin and not market_value:
        #         continue  # Skip only if both ISIN and Market Value are missing

        #     if not isin:
        #     # Handle the case where ISIN is missing but Market Value exists
        #         print(f"Missing ISIN, but Market Value is present: {market_value}")
            
        #     # Determine instrument type; default to 'Others' if current_category is not set
        #     instrument_type = current_category if current_category else 'Others'
        #     market_value = row['Market value (Rs. in Lakhs)']
        
        
        # for index, row in df.iterrows():
        #     name = safe_strip(row.get('Name of the Instrument / Issuer', ''))
        #     lower_name = name.lower()
    

        #     if lower_name.startswith('equity'):
        #         current_category = 'Equity'
        #         continue
        #     elif lower_name.startswith('debt'):
        #         current_category = 'Debt'
        #         continue
        #     elif lower_name.startswith('money market'):
        #         current_category = 'Money Market'
        #         continue
        #     elif lower_name.startswith('other'):
        #         current_category = 'Others'
        #         continue
        #     elif lower_name.startswith('other current'):
        #         continue

        #     if not name:
        #         continue

        #     isin = safe_strip(row.get('ISIN', ''))
        #     market_value = safe_strip(row.get('Market value (Rs. in Lakhs)', ''))

        #     if not isin and not market_value:
        #         continue  # Skip only if both ISIN and Market Value are missing

        #     if not isin:
        #     # Handle the case where ISIN is missing but Market Value exists
        #         print(f"Missing ISIN, but Market Value is present: {market_value}")
    
        #     # Determine instrument type; default to 'Others' if current_category is not set
        #     instrument_type = current_category if current_category else 'Others'
        #     market_value = row['Market value (Rs. in Lakhs)']
    
    
        # category_totals = {}  # Dictionary to store total for each category
        # current_category = None  # Track the current category

        # for index, row in df.iterrows():
        #     name = safe_strip(row.get('Name of the Instrument / Issuer', ''))
        #     lower_name = name.lower()

        #     # Check for category headers and update the current category
        #     if lower_name.startswith('equity'):
        #         current_category = 'Equity'
        #         continue
        #     elif lower_name.startswith('debt'):
        #         current_category = 'Debt'
        #         continue
        #     elif lower_name.startswith('money market'):
        #         current_category = 'Money Market'
        #         continue
        #     elif lower_name.startswith('other'):
        #         current_category = 'Others'
        #         continue
        #     elif lower_name.startswith('other current'):
        #         continue

        #  # Skip empty names
        #     if not name:
        #         continue

        #     market_value = safe_strip(row.get('Market value (Rs. in Lakhs)', ''))
    
        #         # Convert market_value to a float for calculations
        #     try:
        #         market_value = float(market_value.replace(',', '')) if market_value else 0
        #     except ValueError:
        #         market_value = 0  # Default to 0 if conversion fails

        #      # If "Total" is found in the row, add the market value to the category total
        #     if "total" in lower_name:
        #         if current_category:
        #             category_totals[current_category] = category_totals.get(current_category, 0) + market_value
        #             continue  # Skip further processing for "Total" rows

        #     isin = safe_strip(row.get('ISIN', ''))

        #     if not isin and not market_value:
        #         continue  # Skip only if both ISIN and Market Value are missing

        #     if not isin:
        #         # Handle the case where ISIN is missing but Market Value exists
        #         print(f"Missing ISIN, but Market Value is present: {market_value}")

        #         # Determine instrument type; default to 'Others' if current_category is not set
        #     instrument_type = current_category if current_category else 'Others'

# Print final category totals
            # print("Category Totals:", category_totals)
            # category_totals = {}  # Dictionary to store total for each category
            # current_category = None  # Track the current category

  

        #     # Insert new data into MutualFundData
        #     instrument = MutualFundData(
        #         amc=amc,
        #         scheme=scheme,
        #         instrument_name=name,
        #         isin=isin,
        #         industry_rating=safe_strip(row.get('Industry / Rating', '')),
        #         quantity=row['Quantity'],
        #         market_value=market_value,
        #         percentage_to_nav=row['% to AUM'],
        #         yield_percentage=row['YTM %'],
        #         ytc=row.get('YTC %##', None),
        #         instrument_type=instrument_type,
        #     )
        #     instrument.save()
            
        #     # Update totals based on the instrument type
        #     if instrument_type  == 'Equity':
        #         equity_total += market_value
        #     elif instrument_type == 'Debt':
        #         debt_total += market_value
        #     elif instrument_type == 'Money Market':
        #         money_market_total += market_value
        #     elif instrument_type == 'Others Current':
        #         others_current += market_value
        #     elif instrument_type == 'Others':
        #         others_total += market_value+money_market_total+others_current
        #     print ('current_category:',current_category)
        #     print(f'name : {name}')
        #     print(f'equity_total : {equity_total}')
        #     print(f'debt_total : {debt_total}')
        #     print(f'money_market_total : {money_market_total}')
        #     print(f'others_total : {others_total}')
        #     #print('current category total',category_totals)
            
        #     # Aggregate investment for industry/ratings
        #     industry_rating = safe_strip(row.get('Rating / Industry^', ''))
        #     if industry_rating:
        #         if industry_rating not in industry_investments:
        #             industry_investments[industry_rating] = 0
        #         industry_investments[industry_rating] += market_value
            
        #     # Store the top 5 instruments by % age to NAV
        #     nav_percentage = row['% to AUM']
        #     instrument_aum_percentages.append((name, nav_percentage, market_value))
        
        # # Calculate combined Money Market and Others into one category
        # combined_others_total = money_market_total + others_total
        
        # # Calculate the overall total market value
        # total_market_value = equity_total + debt_total + combined_others_total
        
        # # Calculate percentage shares (avoiding division by zero)
        # total = total_market_value if total_market_value > 0 else 1
        # equity_percentage = (equity_total / total) * 100
        # debt_percentage = (debt_total / total) * 100
        # others_percentage = (combined_others_total / total) * 100
        
        # # Get top 5 industries/ratings by total market value
        # sorted_industries = sorted(industry_investments.items(), key=lambda x: x[1], reverse=True)[:5]
        # top_sectors = [{"industry": industry, "investment": round(investment, 2)} for industry, investment in sorted_industries]
        
        # # Get top 5 instruments by % age to NAV
        # sorted_instruments = sorted(instrument_aum_percentages, key=lambda x: x[1], reverse=True)[:5]
        
        # top_holdings = [{"instrument_name": instrument, "nav_percentage": round(nav_percentage, 2)} for instrument, nav_percentage, _ in sorted_instruments]
        
        # # Log totals and top instruments/industries
        # print("Equity Total:", equity_total)
        # print("Debt Total:", debt_total)
        # print("Money Market Total:", money_market_total)
        # print("Others Total:", others_total)
        # print("Total Market Value:", total_market_value)
        # print("Equity Percentage:", equity_percentage)
        # print("Debt Percentage:", debt_percentage)
        # print("Others Percentage:", others_percentage)
        # print("Top Industries:", top_sectors)
        # print("Top Instruments:", top_holdings)
        # print("Data saved successfully!")
        
        # # Update the uploaded file with the latest totals
        # print('Final Before update it into db others_total:',others_total)
        # if uploaded_file:
            
        #     uploaded_file.equity_total = equity_total
        #     uploaded_file.debt_total = debt_total
        #     #uploaded_file.money_market_total = money_market_total
        #     uploaded_file.others_total = others_total
        #     uploaded_file.total_market_value = total_market_value
        #     #uploaded_file.equity_percentage = equity_percentage
        #    # uploaded_file.debt_percentage = debt_percentage
        #     #uploaded_file.others_percentage = others_percentage
        #     uploaded_file.top_sectors = top_sectors
        #     uploaded_file.top_holdings = top_holdings
        #     uploaded_file.save()
        
   
        
        
        
        

def default_excel_processing(file, scheme, amc):
    """
    Default function for AMCs without specific processing logic.
    """
    print(f"Default processing for {scheme.scheme_name}. No specific function defined.")

