#This script will create the balance sheet for a company, meant to be generated on quarter ends
#Tax functions are based on laws in Singapore

#v1 Base P&L calculations
#v2 Added Inventory Management system
#v3 Add Inventory alert system
#v4 P&L generation should only generate for the current year only
#v5 P&L and B/S generation will generate the results for this year year-to-date, as well as the previous year year-to-date. Assume quarter end generation requirements only
#v6 include Statement of Equity Changes
#v7 include cash flow statement

import pandas as pd
import numpy as np
from datetime import datetime
import time
from pprint import pprint
import math
import calendar

##Start by defining function to determine which accounts belong in the balance sheet vs P/L
def label_t_accts(a):
    if 'Expense' in a:
        return 'trial_balance'
    elif 'Unearned' in a:
        return 'balance_sheet'
    elif 'Revenue' in a:
        return 'trial_balance'
    else:
        return 'balance_sheet'


#Define inventory levels as High(>60%), Medium(30-60%), Low(1-30%), Empty(0%)
def inventory_levels_check(b):
    if b ==1:    #if all slots are empty return Empty
        return "Empty"
    elif b>=0.6: #if 60% or more of the slots are empty return Low
        return "Low"
    elif b >= 0.3:
        return "Medium" #if 30% or more of the slots are empty return Medium
    else:
        return "High" #if less than 30% of the slots are empty return High


#start up tax exemption scheme https://www.iras.gov.sg/taxes/corporate-income-tax/basics-of-corporate-income-tax/corporate-income-tax-rate-rebates-and-tax-exemption-schemes
def start_up_tax_amount(x):
    if x <= 100000:
        return x*0.17*0.25*-1 #17% corporate tax rate, 75% exemption for the first 100K of profits
    elif x <= 200000:
        return (100000*0.17*0.25 + (x-100000)*0.17*0.5)*-1  #17% corporate tax rate, 75% exemption for the first 100K of profits, 50% exemption for the next 100K
    else:
        return (100000*0.17*0.25 + 100000*0.17*0.5 + (x - 200000)*0.17)*-1

#partial tax exemption scheme
def partial_tax_amount(x):  # this is only used from the fourth Year of Assessment Onwards
    if x <= 10000:
        return (x*0.17*0.25)*-1 #17% corporate tax rate, 75% exemption for the first 100K of profits
    elif x <= 200000:
        return (10000*0.17*0.25 + (x-10000)*0.17*0.5)*-1  #17% corporate tax rate, 75% exemption for the first 10K of profits, 50% exemption for the next 190K
    else:
        return (10000*0.17*0.25 + 190000*0.17*0.5 + (x - 200000)*0.17)*-1

def date_for_tax_transaction(x,y): #x = year type int, y = quarter type int
    days_in_month = calendar.monthrange(x, y*3)[1]
    date_return = datetime(x, y*3, days_in_month) #return last day (as date) of the quarter
    date_input_new = pd.to_datetime(date_input)
    return date_return if date_return <= date_input_new else date_input_new  #Replace with current date if date is <= input date by user


#Convert timestamp to year
def convert_timestamp(ts, from_pattern, to_pattern):
    dt = datetime.strptime(ts, from_pattern)
    return datetime.strftime(dt, to_pattern)


def return_quarter_int(x):
    return math.ceil(x/3)

def flip_depreciation_expense(x,y):
    if x == 'Depreciation Expense':
        return y*-1
    else:
        return y


'''
Part 1: Inventory Management and Transaction Calculations
'''


#Retrieve full transaction list and cleaning
xlsx = pd.ExcelFile('Transactions_Raw.xlsx')
df = pd.read_excel(xlsx, 'Transaction')
price_list = pd.read_excel(xlsx, 'Price List')
shop_space = pd.read_excel(xlsx, 'Shop Space')

df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values(by = 'Date', ascending = True).reset_index(drop = True)

'''
Date Filter from USER
'''
date_input = datetime.now()
date_input = input('Please key in the date of report in YYYY-MM-DD format:')

#Define this year and last year as int
this_year = int(date_input[:4])
last_year = int(this_year-1)
prev_last_year = int(this_year-2)

this_quarter = return_quarter_int(int(date_input[5:7]))

df = df[ df['Date'] <= date_input ]


'''
Continue Set up of transactions before doing up inventory
'''

#create list of sorted dates
list_of_dates = df.Date.unique()

#column for shop name
shop_df = df[ df['Debit'].str[10:14] == 'Shop' ]
shop_df['Shop'] = shop_df['Debit'].str[10:]

list_of_shops = shop_df.Shop.unique()

#Part 1: Prepare Inventory List and COGS Expense Calculation

#Filter out Revenue transactions where by Item_Name is blank

inventory_txns = df[ (df['Credit'] == 'Revenue') | (df['Debit'].str[:9] == 'Inventory') | (df['Credit'].str[:9] == 'Inventory')]

#Let's now create our inventory list in the main warehouse.

inventory_warehouse = pd.DataFrame()

#Create empty dataframe for each shop's inventory
inventory_shops =  pd.DataFrame()

#Create empty dataframe for inventory alert data
inventory_data = pd.DataFrame()

#Create empty dataframe for profit loss retained earnings calculations
profit_loss_total = pd.DataFrame()

stmt_equity = pd.DataFrame()

stmt_equity_output = pd.DataFrame()

cashflow_stmt_output = pd.DataFrame()

for date in list_of_dates:

    '''
    Warehouse Inventory
    '''

    #Only include transactions for the current date
    daily_inventory_total = inventory_txns[ inventory_txns['Date'] == date ]

    #Only include inventory warehouse transactions
    daily_inv_txn = daily_inventory_total[daily_inventory_total['Debit'] == 'Inventory']

    #Update Inventory List first
    daily_inv_txn = daily_inv_txn.groupby('Item_Name').sum()

    #Calculate average price for current batch
    daily_inv_txn['Price'] = daily_inv_txn['Credit_Amount'] / daily_inv_txn['Quantity']

    #drop columns
    daily_inv_txn = daily_inv_txn.drop(columns = ['Debit_Amount','Credit_Amount'])

    #Calculate total inventory cost sitting in warehouse
    daily_inv_txn['Inventory_Value'] = daily_inv_txn['Quantity']*daily_inv_txn['Price']


    inventory_warehouse = pd.concat([inventory_warehouse, daily_inv_txn])

    #Recalculate Cost Price, by the average costing method
    inventory_warehouse = inventory_warehouse.groupby(['Item_Name']).sum()



    #Recalculate cost price using average costing method
    inventory_warehouse['Price'] = inventory_warehouse['Inventory_Value'] / inventory_warehouse['Quantity']

    #IF quantity is 0, set cost price to 0
    inventory_warehouse['Price'] = inventory_warehouse['Price'].fillna(0)

    #Done with warehouse calculations
    #Move inventory to other shops, maintain each of their own inventory levels
    daily_inv_shop_txn = daily_inventory_total[daily_inventory_total['Debit'] != 'Inventory']

    daily_inv_shop_txn = daily_inv_shop_txn[daily_inv_shop_txn['Debit'].str[10:14] == 'Shop' ]

    #Remove any inventory movement txns that are already filled (i.e. code was previously run on it)
    daily_inv_shop_txn = daily_inv_shop_txn[(daily_inv_shop_txn['Debit_Amount'].isnull() ) | (daily_inv_shop_txn['Credit_Amount'].isnull() )]








    '''
    Calculate individual inventory in each shop
    '''


    #Now we start adding warehouse inventory to individual shop inventory, then recalculate the average price in each shop


    #clean daily inventory txns to only include txns involving restocking

    daily_shop_add = daily_inv_shop_txn
    daily_shop_add['Shop_Name'] = daily_shop_add['Debit'].str[10:]

    #Clean up dataframe to only include important details
    daily_shop_add = daily_shop_add.drop(columns = ['Debit','Credit','Debit_Amount','Credit_Amount','Comments','Ref_Number'])

    #Join dataframe with main warehouse dataframe to pull out average price
    daily_shop_add = pd.merge(daily_shop_add,inventory_warehouse[['Price']] ,right_index = True,left_on = 'Item_Name', how = 'left')

    #Recalculate total cost price for each line
    daily_shop_add['Inventory_Value'] = daily_shop_add['Quantity'] * daily_shop_add['Price']

    #drop date column
    daily_shop_add = daily_shop_add.drop(columns = ['Date'])


    ###Concatenate to main shop warehouse dataframe
    inventory_shops = pd.concat([inventory_shops,daily_shop_add])
    inventory_shops = inventory_shops.reset_index(drop = True)
    #group by Item_Name and Shop Name, then recalculate average price
    inventory_shops = inventory_shops.groupby(['Item_Name','Shop_Name']).sum()


    #reset index
    inventory_shops = inventory_shops.reset_index()

    #Recalculate average price for inventory in each shop, Quantity and Inventory Value are both summed up, so reverse calculate the new average price
    inventory_shops['Price'] =  inventory_shops['Inventory_Value'] / inventory_shops['Quantity']

    #change the average price to 0 if number is NaN
    inventory_shops['Price'] = inventory_shops['Price'].fillna(0)

    #Sort by Shop Name to allow user to see inventory easily
    inventory_shops = inventory_shops.sort_values('Shop_Name')

    '''
    Deducting inventory from warehouse that is transferred into individual shops
    '''
    daily_shop_add_total = daily_shop_add.groupby('Item_Name').sum().reset_index()
    #Rename columns to make column names unique
    daily_shop_add_total = daily_shop_add_total.rename(columns = {'Quantity': 'Deduct_Quantity','Item_Name':'Item'} )




    #Join dataframes together, and deduct the quantity from the main warehouse
    inventory_warehouse = pd.merge(inventory_warehouse, daily_shop_add_total[['Item','Deduct_Quantity']] , left_index = True, right_on = 'Item',how = 'left' )

    #set index as item_name
    inventory_warehouse = inventory_warehouse.rename(columns = {'Item':'Item_Name'})
    inventory_warehouse = inventory_warehouse.set_index('Item_Name')



    #fill na as quantity 0 for deduct quantity
    inventory_warehouse['Deduct_Quantity'] = inventory_warehouse['Deduct_Quantity'].fillna(0)

    #Update quantity in warehouse
    inventory_warehouse['Quantity'] = inventory_warehouse['Quantity'] - inventory_warehouse['Deduct_Quantity']

    #Update Inventory Value in warehouse
    inventory_warehouse['Inventory_Value'] = inventory_warehouse['Quantity'] * inventory_warehouse['Price']

    #Drop Deduct_Quantity column
    inventory_warehouse = inventory_warehouse.drop(columns = ['Deduct_Quantity'])

    #Recalculate inventory value

    '''
    Individual Shop Inventory in 1 DataFrame
    '''

    #Inventory is stocked up. Now we will do the daily COGS Expense calculations and add those transactions into the list

    #First, we take all revenue transactions for the day
    rev_txns =  daily_inventory_total[daily_inventory_total['Credit'] == 'Revenue']
    rev_txns['Quantity'] = 1

    #We will filter out the price list we should use
    daily_price_list = price_list
    #Find difference in days between price list and current date
    daily_price_list['Diff_in_Days'] = (date - daily_price_list['Effective_From']).dt.days
    #filter out price where the diff in days is negative. Only use the price that is positive and has the lowest days diff in the list
    daily_price_list = daily_price_list[daily_price_list['Diff_in_Days'] >= 0]

    #find minimum number of days, then use it to filter out the price list to the latest available date
    min_days = daily_price_list['Diff_in_Days'].min()

    daily_price_list = daily_price_list[daily_price_list['Diff_in_Days'] == min_days]

    #Drop item name column from revenue txns, then take it from the price list table
    rev_txns = rev_txns.drop(columns = 'Item_Name')

    #Now that we have the retail price used, we join this to the main table to determine which items are being sold.
    rev_txns = pd.merge(rev_txns, daily_price_list[['Item_Name','Sale_Price']], left_on = 'Debit_Amount',right_on = 'Sale_Price')





    '''
    Create COGS Expense Transactions
    '''
    #Revenue Transactions are now filled with the items. Now, we will create a new table and calculate the retail price, then we will append this back to the txn table.
    daily_cogs_exp = rev_txns

    #Left join inventory warehouse to retrieve average cost price
    daily_cogs_exp = pd.merge(daily_cogs_exp, inventory_shops[['Item_Name','Shop_Name','Price']],  how = 'left',left_on = ['Item_Name','Comments'], right_on = ['Item_Name','Shop_Name'])

    #Change debit and credit tags, as well as debit/credit amounts
    daily_cogs_exp['Debit'] = 'COGS Expense'
    daily_cogs_exp['Credit'] = 'Inventory'
    daily_cogs_exp['Debit_Amount'] = daily_cogs_exp['Quantity'] * daily_cogs_exp['Price']
    daily_cogs_exp['Credit_Amount'] = daily_cogs_exp['Quantity'] * daily_cogs_exp['Price']

    '''
    Calculate daily sales and remove quantity from respective shop inventory
    '''
    daily_sales = pd.DataFrame()

    daily_sales = daily_cogs_exp[['Date','Quantity','Item_Name','Shop_Name']]

    #Sum up all sales quantity, group by Shop and Item_Name

    daily_sales = daily_sales.groupby(['Item_Name','Shop_Name']).sum().reset_index()

    #Rename columns first before rejoining back to shop inventory

    daily_sales = daily_sales.rename(columns = {'Item_Name':'Item_Name', 'Shop_Name':'Shop_Name','Quantity':'Sale_Quantity'} )

    #Merge daily sales quantity into shop inventory dataframe and deduct balance from inventory
    inventory_shops = pd.merge(inventory_shops,daily_sales[['Item_Name','Shop_Name','Sale_Quantity']] , how = 'left', left_on = ['Item_Name','Shop_Name'], right_on = ['Item_Name','Shop_Name'] )

    #Remove Quantity Sold from inventory, then drop Sale Quantity column
    inventory_shops['Sale_Quantity'] = inventory_shops['Sale_Quantity'].fillna(0)
    inventory_shops['Quantity'] = inventory_shops['Quantity'] - inventory_shops['Sale_Quantity']
    inventory_shops = inventory_shops.drop(columns = ['Sale_Quantity'] )

    #Recalculate Inventory Value
    inventory_shops['Inventory_Value'] = inventory_shops['Quantity'] * inventory_shops['Price']

    #print(inventory_shops)

    '''
    Append daily COGS Expense into transaction list
    '''

    #Prepare daily_cogs_exp table to be appended back into the full transactions list
    daily_cogs_exp = daily_cogs_exp.drop(columns = ['Sale_Price','Shop_Name','Price'])

    #Append back to raw transaction table
    df = pd.concat([df,daily_cogs_exp], axis = 0)





    '''
    Create specific inventory data table, to create an inventory alert and be used for sales analysis
    '''

    #Filter out the correct shop space that has been allocated to each product
    #Pull out dataframe with shop space data
    shop_space_today = shop_space

    #Add the date input into the dataframe
    shop_space_today['date_input'] = date

    #Find the difference in days between shop date and date input
    shop_space_today['Diff_in_Days'] = (date - shop_space_today['Effective_From']).dt.days

    #filter out data where diff in days is negative.
    shop_space_today = shop_space_today[shop_space_today['Diff_in_Days'] >= 0]
    #find the minimum number of days, then use it to filter out the shop space to the latest configuaration
    min_days_shop = shop_space_today['Diff_in_Days'].min()

    shop_space_today = shop_space_today[shop_space_today['Diff_in_Days'] == min_days_shop]


    #Now, we merge the shop_space data into the current inventory levels. A new table will be created so that further sales analysis can be done.

    inventory_df = inventory_shops

    #Merge shop space data into inventory data, then calculate the number of empty slots and whether any slots are empty

    inventory_df = pd.merge(inventory_df,shop_space_today[['Item_Name','Shop_Name','Slots','date_input']], how = 'left',left_on=['Item_Name','Shop_Name'],right_on=['Item_Name','Shop_Name'])

    #Calculate empty slots in each shop for each item
    inventory_df['Empty_Slots'] = inventory_df['Slots'] - inventory_df['Quantity']

    #Calculate the % of empty slots
    inventory_df['%_empty_slots'] = (inventory_df['Empty_Slots'] / inventory_df['Slots']).round(2)

    #Inventory level check
    inventory_df['Level'] = inventory_df['%_empty_slots'].apply(lambda x: inventory_levels_check(x))

    inventory_data = pd.concat([inventory_data, inventory_df],axis = 0)




'''
##End of daily run of calculations
'''



#Clean up today's inventory data to figure out which items need restocking (We use the latest available date to see if txns are up to date)
#If Date input != date of report you entered, txns are not updated.

#Find all dates where data is available
inventory_list_dates = inventory_data.date_input.max()

#Only retrieve the final date of data
inventory_data_final = inventory_data[inventory_data['date_input'] == inventory_list_dates]


#Compare final data date with date of input by user

date_input_date = datetime.strptime(date_input, '%Y-%m-%d').date()

inventory_data_final['Updated?'] =  inventory_data_final['date_input'].apply(lambda x: "UPDATED" if x >= date_input_date else "NOT UPDATED" )



'''
Sort out transaction list by date (for final output)
'''

df = df.sort_values('Date')





'''
Part 2: Create Financial Statements and update Transaction Data with Tax Liabilities
'''

#Create Unique List of T-Accounts

first_list = df.Debit.unique()
second_list = df.Credit.unique()

in_first = set(first_list)
in_second = set(second_list)

resulting_list = list(first_list)
#Unique List of T-Accounts
resulting_list.extend(x for x in second_list if x not in resulting_list)

#create list of 0s to create dictionary
listofzeros = [0] * len(resulting_list)

#Now we will loop through every sorted date from earliest to latest to update the T-Accounts
#T-accounts at time 0
t_accts =  dict( zip(resulting_list,listofzeros) )


t_acct_df = pd.DataFrame()

for date in list_of_dates:
    #filter out transactions to current date
    new_df = df[df['Date'] == date].reset_index()
    #make one side negative so that T-Account will balance
    new_df['Credit_Amount'] = new_df['Credit_Amount'] * -1
    #calculate daily total debit amounts
    daily_debit_df = pd.DataFrame( new_df.groupby(['Debit']).sum()['Debit_Amount'] )
    #calculate daily total credit amounts
    daily_credit_df = pd.DataFrame( new_df.groupby(['Credit']).sum()['Credit_Amount'] )
    #place into 1 dataframe for extraction
    daily_sum = pd.concat([daily_debit_df,daily_credit_df], axis = 0)

    daily_sum['Date'] = date
    #append to main dataframe
    t_acct_df = pd.concat([t_acct_df,daily_sum],axis = 0)

#Consolidate T-Accounts, note that the positive/negative signs may not be representative
t_acct_df.index.name = 'T_Account_Name'


'''
Prepare T-Accounts for Balance Sheet
'''
t_acct_df['Year'] = t_acct_df['Date'].apply(lambda x : x.year)
t_acct_df['Quarter'] = t_acct_df['Date'].apply(lambda x : x.quarter)


#sum all the positive and negative balances
t_account_balance = t_acct_df.groupby(['T_Account_Name','Year','Quarter']).sum()


#add all the credit and debit balance to find the final T-Account balance
t_account_balance['Balance'] = t_account_balance['Debit_Amount'] + t_account_balance['Credit_Amount']
#drop debit and credit columns
t_account_balance = t_account_balance.drop(columns = ['Debit_Amount','Credit_Amount'] ).reset_index()

#now, everything that is positive is debit and everything that is negative is credit
t_account_balance['group'] = t_account_balance['T_Account_Name'].apply(lambda x: label_t_accts(x) )

#Drop inventory in shops (for presentation)
t_account_balance = t_account_balance[(t_account_balance['Balance'] != 0) & (t_account_balance['T_Account_Name'].str[:10] != 'Inventory_' )  ]


'''
P&L statement calculation for total retained earnings
'''


###We will start doing the P/L statement now
profit_loss = t_account_balance[t_account_balance['group'] == 'trial_balance']


#flip balance for P/L
profit_loss['Balance'] = profit_loss['Balance'] * -1

#Please edit this dictionary to manually set the order of categories in P&L statement and Balance Sheet
custom_dict = {'Revenue':0,'Ad Revenue':0, 'COGS Expense':1, 'Rent Expense':3, 'Transportation Expense':3,'Depreciation Expense':3}
custom_dict_balance_sheet = {'Cash': 'Asset', 'Inventory': 'Asset','AR': 'Asset','Equipment':'Asset','Share Capital': 'Equity','Retained Earnings': 'Equity','Tax Payable': 'Liabilities','AP':'Liabilities','Unearned Ad Revenue':'Liabilities'}

#sort by dictionary above
profit_loss['ranking'] = profit_loss['T_Account_Name'].map(custom_dict)
profit_loss = profit_loss.sort_values(by = 'T_Account_Name', key = lambda x: x.map(custom_dict))


#balance sheet dataframe
balance_sheet = t_account_balance[t_account_balance['group'] == 'balance_sheet']


'''
Calculate tax payable each year and append back to profit_loss table to find total tax payable and total retained earnings
'''
list_of_dates_str =  [str(x)[:10] for x in list_of_dates]
list_of_years = [convert_timestamp( ts, '%Y-%m-%d','%Y') for ts in list_of_dates_str]
unique_years = set(list_of_years)
unique_years = sorted(unique_years)
unique_quarters = [1,2,3,4]
balance_sheet_output = pd.DataFrame()


from datetime import datetime

#Loop between year and quarter to calculate amount for each period
for year in unique_years:

    #Create / Reset current year total profits and tax payable, to be used to calculate quarterly tax amounts

    tax_payable_year_sum = 0
    operating_profit_year_sum = 0


    for quarter in unique_quarters:

        profit_loss_yearly = profit_loss[profit_loss['Year'].astype(str) == year.strip() ]

        profit_loss_yearly = profit_loss_yearly[profit_loss_yearly['Quarter'] == quarter ]

        year_final_day = int(datetime.strptime(year, '%Y').date().year)
        year_final_day = datetime(year_final_day, 12, 31)

        #calculate rolling year operating profit and tax payable, to append back to main dataframes
        operating_profit_year_sum = operating_profit_year_sum + np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] )

        #Prepare transaction dataframe for export to statement of changes in equity
        txn_per_quarter = df
        txn_per_quarter['Year'] = txn_per_quarter['Date'].apply(lambda x : x.year).astype(int)
        txn_per_quarter['Quarter'] = txn_per_quarter['Date'].apply(lambda x : x.quarter).astype(int)

        #Filter out current year and quarter data
        txn_per_quarter = txn_per_quarter[(txn_per_quarter['Year'] == int(year)) & (txn_per_quarter['Quarter'] == int(quarter))]

        #Filter out share capital or dividend related transactions only
        txn_per_quarter = txn_per_quarter[ (txn_per_quarter['Debit'].str.contains('Retained Earnings') & (txn_per_quarter['Credit'].str.contains('Dividend') )) | (txn_per_quarter['Credit'].str.contains('Share Capital') ) ]


        #Add Gross Profit and Operating Profit Before Tax into trial_balance
        gross_profit = {'T_Account_Name': 'Gross Profit','Quarter': quarter , 'Balance': np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 1]['Balance'] ), 'group':'trial_balance', 'ranking': 2}
        operating_profit = {'T_Account_Name': 'Operating Profit','Quarter': quarter , 'Balance': np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ), 'group':'trial_balance', 'ranking': 4}
        tax_payable = {'T_Account_Name': 'Tax Payable','Quarter': quarter , 'Balance': start_up_tax_amount(operating_profit_year_sum) - tax_payable_year_sum, 'group':'trial_balance', 'ranking': 5}
        profit_after_tax = {'T_Account_Name': 'Profit After Tax','Quarter': quarter , 'Balance': np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ) + start_up_tax_amount(operating_profit_year_sum) - tax_payable_year_sum, 'group':'trial_balance', 'ranking': 6}
        tax_payable_balance_sheet = {'T_Account_Name': 'Tax Payable','Year':year,'Quarter': quarter ,'Balance': start_up_tax_amount(operating_profit_year_sum) - tax_payable_year_sum, 'group': 'balance_sheet'}
        profit_after_tax_balance_sheet = {'T_Account_Name': 'Retained Earnings','Year':year,'Quarter': quarter , 'Balance': (np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ) + start_up_tax_amount(operating_profit_year_sum) - tax_payable_year_sum)*-1, 'group':'balance_sheet'}

        tax_payable_transaction = {'Date': date_for_tax_transaction(int(year),quarter) ,'Debit':'Tax Expense', 'Debit_Amount': start_up_tax_amount(np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ) ) *-1,
                                    'Credit_Amount': start_up_tax_amount(np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ) ) *-1,'Credit':'Tax Payable', 'Comments':'Calculated Tax Payable','Quantity':'' , 'Ref_Number':'','Item_Name':''}


        #Update dictionary to be added to statement to changes in equity
        proceeds_from_issuing_shares = {'Category':'Proceeds from issuance','Equity Type':'Common Stock','Year':year,'Quarter':quarter,'Balance':np.sum(txn_per_quarter[txn_per_quarter['Credit']=='Share Capital']['Credit_Amount']) }
        dividend_payouts = {'Category':'Dividends paid','Equity Type':'Retained Earnings','Year':year,'Quarter':quarter,'Balance': (np.sum(txn_per_quarter[txn_per_quarter['Credit']=='Dividend Payable']['Credit_Amount']))*-1 }
        retained_earnings = {'Category':'Profit/Loss','Equity Type':'Retained Earnings','Year':year,'Quarter':quarter,'Balance': (np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ) + start_up_tax_amount(operating_profit_year_sum) - tax_payable_year_sum) }

        #Calculate total tax payable for the year so far, to be used for the next quarter
        tax_payable_year_sum = tax_payable_year_sum + start_up_tax_amount(np.sum( profit_loss_yearly[profit_loss_yearly['ranking'] <= 3]['Balance'] ) )


        #Append tax payable yearly back to P&L
        profit_loss_yearly = profit_loss_yearly.append([gross_profit,operating_profit,tax_payable,profit_after_tax], ignore_index = True).sort_values('ranking')
        profit_loss_yearly['Year'] = int(year)


        #Append yearly profit loss back into main dataframe
        profit_loss_total = pd.concat([profit_loss_total,profit_loss_yearly],axis = 0)

        #append tax payable into balance sheet
        balance_sheet = balance_sheet.append([tax_payable_balance_sheet,profit_after_tax_balance_sheet], ignore_index = True )

        #Append tax payable to txns
        df = df.append([tax_payable_transaction],ignore_index = True)

        #Append equity movements into stmt of changes to equity
        temp_stmt_equity_df = pd.DataFrame([proceeds_from_issuing_shares,dividend_payouts,retained_earnings])
        stmt_equity = pd.concat([stmt_equity,temp_stmt_equity_df], axis = 0,ignore_index = True)


'''
Calculate and prepare P&L and B/S output for report generation
'''



#Filter out this year and previous year data only for P&L generation
profit_loss_this_year = profit_loss_total[ (profit_loss_total['Year'] == this_year) | (profit_loss_total['Year'] == last_year) ]

#P&L generation for YTD data - Only take data up to current quarter only
profit_loss_year_output = profit_loss_this_year[profit_loss_this_year['Quarter'] <= this_quarter ]

#Group P&L by T_Account_Name,year,group, and ranking (drop quarter data)
profit_loss_year_output = profit_loss_year_output.groupby(['T_Account_Name','Year','group','ranking']).sum().reset_index()

profit_loss_year_output = profit_loss_year_output.sort_values('ranking')

#Pivot table to show this year and last year's P&L as column data instead
profit_loss_year_output = profit_loss_year_output.pivot_table('Balance',['T_Account_Name','ranking'],'Year').reset_index().sort_values('ranking')

#Round all numbers to 2 dp
profit_loss_year_output = profit_loss_year_output.round(2)

#Balance Sheet - Loop by last year and this year, then calculate QTD numbers accordingly.
for year in [last_year,this_year]:

    #For every year, take all T Accounts for the whole year, and for the current year, take T Accounts only till the particular quarter
    balance_sheet_year_loop = balance_sheet[  (balance_sheet['Year'].astype(int) < year) | ( (balance_sheet['Year'].astype(int) == year) & (balance_sheet['Quarter'] <= this_quarter))    ]

    #Add grouping to balance sheet
    balance_sheet_year_loop['asset_grouping'] = balance_sheet_year_loop['T_Account_Name'].map(custom_dict_balance_sheet)


    balance_sheet_year_loop = balance_sheet_year_loop.groupby(['T_Account_Name','asset_grouping']).sum().reset_index()

    #Convert negative credit values to positive values
    balance_sheet_year_loop['Balance'] = np.where( balance_sheet_year_loop['asset_grouping'] == 'Equity', abs(balance_sheet_year_loop['Balance']), balance_sheet_year_loop['Balance'])
    balance_sheet_year_loop['Balance'] = np.where( balance_sheet_year_loop['asset_grouping'] == 'Liabilities', abs(balance_sheet_year_loop['Balance']), balance_sheet_year_loop['Balance'])

    #Add grouping to balance sheet
    balance_sheet_year_loop['asset_grouping'] = balance_sheet_year_loop['T_Account_Name'].map(custom_dict_balance_sheet)

    #Sum up asset accounts on the balance sheet
    balance_sheet_year_loop = balance_sheet_year_loop.groupby(['T_Account_Name','asset_grouping']).sum().reset_index()


    #Add year to balance sheet df to be used to pivot later
    balance_sheet_year_loop['Year'] = year

    #sort balance sheet by asset grouping Asset--> Equity --> Liabilities
    balance_sheet_year_loop = balance_sheet_year_loop.sort_values('asset_grouping')

    balance_sheet_output = pd.concat([balance_sheet_output,balance_sheet_year_loop])



    #prepare stmt of changes to equity output
    stmt_equity_year = stmt_equity.groupby(['Category','Equity Type','Year']).sum().reset_index()


    stmt_equity_output = pd.concat([stmt_equity_output,stmt_equity_year],axis = 0, ignore_index = True)
    #end of loop

'''New loop to calculate line items required for cash flow statement
Data required from the past 3 years: P&L for the full year, AP/AR balances, Depreciation Expense, Operating Profit, Taxes Paid, Dividends Paid, Purchase or Disposal of equipment'''


for year in [prev_last_year,last_year,this_year]:

    '''Add Cash Balances into cash flow statement'''
    #Calculate balance sheet numbers to be used for cash flow statement
    balance_sheet_cash = balance_sheet[ (balance_sheet['Year'].astype(int) <= year) & (balance_sheet['T_Account_Name'] == 'Cash')]

    #Sum up all cash transactions to find the ending cash balance for the year
    balance_sheet_cash = balance_sheet_cash.groupby(['T_Account_Name']).sum().reset_index()

    #Add year and label Category name
    balance_sheet_cash['Year'] = year

    #Return actual day for cash if it's on the date of report, else return 'end of year'
    if year == this_year:
        balance_sheet_cash['T_Account_Name'] = balance_sheet_cash['T_Account_Name'] + ' as of ' + str(date_input)

    else:
        balance_sheet_cash['T_Account_Name'] = balance_sheet_cash['T_Account_Name'] + ' as of end of ' + str(year)

    cashflow_stmt_output = pd.concat([cashflow_stmt_output,balance_sheet_cash],axis = 0,ignore_index = True)

    '''Add operating profit before tax and depreciation expense'''
    #Find out total operating profit for current year, as well as depreciation expense (if any)
    profit_loss_cashflow = profit_loss_total[(profit_loss_total['T_Account_Name'] == 'Operating Profit') & (profit_loss_total['Year'].astype(int) == year )
                            | (profit_loss_total['T_Account_Name'] == 'Depreciation Expense') & (profit_loss_total['Year'].astype(int) == year ) ]

    #only include past 2 years of profits into cash flow statement
    profit_loss_cashflow = profit_loss_cashflow[profit_loss_cashflow['Year'] >= last_year ]

    try:
        profit_loss_cashflow['Balance'] = profit_loss_cashflow.apply(lambda x : flip_depreciation_expense( x['T_Account_Name'], x['Balance'] ), axis = 1 )
    except:
        pass
    #Sum up year/ year to date profits
    profit_loss_cashflow = profit_loss_cashflow.groupby(['T_Account_Name','Year']).sum().reset_index()

    #Prepare dataframe properly for export to main cash flow dataframe
    profit_loss_cashflow = profit_loss_cashflow[['T_Account_Name','Quarter','Balance','Year']]

    #Export to cashflow dataframe
    cashflow_stmt_output = pd.concat([cashflow_stmt_output,profit_loss_cashflow],axis = 0,ignore_index= True)


    '''Add changes in operating assets and liabilities into cashflow statement'''
    #Include AR, AP, Unearned Revenue, Inventory only
    balance_sheet_cashflow = balance_sheet[(balance_sheet['T_Account_Name'] == 'AR') | (balance_sheet['T_Account_Name'] == 'AP')
                                            | (balance_sheet['T_Account_Name'] == 'Inventory') | (balance_sheet['T_Account_Name'] == 'Unearned Ad Revenue')]

    #Filter out current year data
    balance_sheet_cashflow = balance_sheet_cashflow[balance_sheet_cashflow['Year'] == year]

    #Only include past 2 years of data only
    balance_sheet_cashflow = balance_sheet_cashflow[balance_sheet_cashflow['Year'] >= last_year]

    #Sum up changes to various t accounts
    balance_sheet_cashflow = balance_sheet_cashflow.groupby(['T_Account_Name','Year']).sum().reset_index()

    #Flip sign on balances to account for cash flow
    balance_sheet_cashflow['Balance'] = balance_sheet_cashflow['Balance']*-1

    #Rearrange columns, then append back to cash flow output dataframe
    balance_sheet_cashflow = balance_sheet_cashflow[['T_Account_Name','Quarter','Balance','Year']]

    cashflow_stmt_output = pd.concat([cashflow_stmt_output,balance_sheet_cashflow],axis = 0,ignore_index= True)

    '''Add any equipment that are purchased in the year into CFI'''
    #Go back to transaction data to retrieve actual cash payments for equipment
    equipment_cashflow = df[ ( (df['Debit'] == 'Equipment') & (df['Credit'] == 'Cash') ) | ( (df['Credit'] == 'Equipment Payable') & (df['Debit'] == 'Cash') ) ]

    #Only include past 2 years of data only
    equipment_cashflow = equipment_cashflow[equipment_cashflow['Year'] >= last_year]
    #Filter out current year data only
    equipment_cashflow = equipment_cashflow[equipment_cashflow['Year'] == year]

    #Change name to Equipment
    equipment_cashflow['T_Account_Name'] = 'Equipment'
    equipment_cashflow['Balance'] = equipment_cashflow['Debit_Amount']*-1
    #Filter out data if equipment purchase was not in last 2 years
    equipment_cashflow = equipment_cashflow.groupby(['T_Account_Name','Year']).sum().reset_index()

    #equipment_cashflow['Year'] = year

    #Only keep relevant columns before joining back to cashflow statement
    equipment_cashflow = equipment_cashflow[['T_Account_Name','Quarter','Balance','Year']]

    #Join equipment payment back to dataframe
    cashflow_stmt_output = pd.concat([cashflow_stmt_output,equipment_cashflow], axis = 0, ignore_index=True)

    '''Add taxes that are actually paid out'''
    #Filter out transactions for taxes that are actually paid out in cash
    taxes_cashflow = df[ (df['Debit'] == 'Tax Payable') & (df['Credit'] == 'Cash') ]

    #Only include past 2 years of data only
    taxes_cashflow = taxes_cashflow[taxes_cashflow['Year'] >= last_year]

    #Filer out current year data only
    taxes_cashflow  = taxes_cashflow[taxes_cashflow['Year'] == year]

    #Change name to Taxes Paid
    taxes_cashflow['T_Account_Name'] = 'Taxes Paid'
    taxes_cashflow['Balance'] = taxes_cashflow['Debit_Amount']*-1

    #Sum up all taxes paid
    taxes_cashflow = taxes_cashflow.groupby(['T_Account_Name','Year']).sum().reset_index()

    #taxes_cashflow['Year']
    #Only keep relevant columns before joining back to cashflow statement
    taxes_cashflow = taxes_cashflow[['T_Account_Name','Quarter','Balance','Year']]

    #Join taxes paid back to dataframe
    cashflow_stmt_output = pd.concat([cashflow_stmt_output,taxes_cashflow], axis = 0, ignore_index=True)

    '''Add Share capital issuance and deduct dividends actually paid'''
    #Filter out dividends actually paid out and cash raised from issuing shares
    equity_cashflow = df[ ( (df['Debit'] == 'Dividend Payable') & (df['Credit'] == 'Cash') ) | ( (df['Debit'] == 'Cash') & (df['Credit'] == 'Share Capital') ) ]

    #Only include past 2 years of data only
    equity_cashflow = equity_cashflow[equity_cashflow['Year'] >= last_year]

    #Filer out current year data only
    equity_cashflow  = equity_cashflow[equity_cashflow['Year'] == year]

    equity_cashflow['T_Account_Name'] = ""
    equity_cashflow['Balance'] = 0

    #Change share capital to proceeds from issuance, dividend to dividends paid
    try:
        #Rename T Account
        equity_cashflow['T_Account_Name'] = equity_cashflow.apply(lambda x: 'Dividends paid' if x['Debit'] == 'Dividend Payable' else ( 'Proceeds from issuance' if x['Credit'] == 'Share Capital' else '' ), axis = 1 )

        #Change balance to negative for dividends
        equity_cashflow['Balance'] = equity_cashflow.apply(lambda x: x['Debit_Amount']*-1 if x['Debit'] == 'Dividend Payable' else x['Debit_Amount'], axis =1 )

    except:
        pass

    #Sum up all equity transactions with cash flows
    equity_cashflow = equity_cashflow.groupby(['T_Account_Name','Year']).sum().reset_index()
    #Only keep relevant columns before joining back to cashflow statement
    equity_cashflow = equity_cashflow[['T_Account_Name','Quarter','Balance','Year']]
    #Join equity transactions back to dataframe
    cashflow_stmt_output = pd.concat([cashflow_stmt_output,equity_cashflow], axis = 0, ignore_index=True)



'''Final Clean Up'''
#Ranking to arrange cash flow statement line by line
cashflow_ranking_dict = {'Operating Profit':1,'Depreciation Expense':2,'AP':3,'AR':3,'Inventory':3,'Unearned Ad Revenue':3,'Taxes Paid':4,'Equipment':6,'Dividends paid':8,'Proceeds from issuance':8,
                        'Cash as of end of '+str(prev_last_year):11,'Cash as of end of '+str(last_year):11,'Cash as of '+str(date_input):11 }

#Ranking to segregate into cash flow from operations, investing, financing, and final reconciliation
cashflow_type_dict = {'Operating Profit':'Cashflow from Operations','Depreciation Expense':'Cashflow from Operations','AP':'Cashflow from Operations','AR':'Cashflow from Operations','Inventory':'Cashflow from Operations',
                        'Unearned Ad Revenue':'Cashflow from Operations','Taxes Paid':'Cashflow from Operations','Equipment':'Cashflow from Investing','Dividends paid':'Cashflow from Financing','Proceeds from issuance':'Cashflow from Financing',
                        'Cash as of end of '+str(prev_last_year):'Final Reconciliation','Cash as of end of '+str(last_year):'Final Reconciliation','Cash as of '+str(date_input):'Final Reconciliation' }




#Rename T_Account to category
cashflow_stmt_output = cashflow_stmt_output.rename(columns = {'T_Account_Name':'Category'})



#Pivot table to show years as columns in cashflow statement
cashflow_stmt_output = cashflow_stmt_output.pivot_table('Balance',['Category'],'Year').reset_index()

#Place rank mapping into cashflow statement to arrange data for export
cashflow_stmt_output['ranking'] = cashflow_stmt_output['Category'].map(cashflow_ranking_dict)

#Add second ranking to push all cash balances to the bottom of the statement
cashflow_stmt_output['ranking_main'] = cashflow_stmt_output.Category.apply(lambda x: 2 if 'Cash as of' in x else 1 )

#Place cashflow type mapping into cashflow statement
cashflow_stmt_output['Cashflow type'] = cashflow_stmt_output['Category'].map(cashflow_type_dict)

#sort out cashflow statement
cashflow_stmt_output = cashflow_stmt_output.sort_values(['ranking_main','ranking','Category'])

#Filter out final cash balances, then rearrange them to show initial and final cash balance
cashflow_final_balance = cashflow_stmt_output[cashflow_stmt_output['ranking_main'] == 2]
#Value of cash balances over the years, return 0 if error
try:
    cashflow_balance_prev_last_year = np.sum(cashflow_final_balance[prev_last_year])
except:
    cashflow_balance_prev_last_year = 0

try:
    cashflow_balance_last_year = np.sum(cashflow_final_balance[last_year])
except:
    cashflow_balance_last_year = 0

cash_initial_dict = {'Category':'Cash and cash equivalents, beginning of period',prev_last_year:0,last_year:cashflow_balance_prev_last_year,
                    this_year:cashflow_balance_last_year,'ranking':11, 'ranking_main':2,'Cashflow type':'Final Reconciliation' }


cash_final_dict = {'Category':'Cash and cash equivalents, end of period',prev_last_year:0,last_year: cashflow_balance_last_year,
                    this_year:np.sum(cashflow_final_balance[this_year]),'ranking':12, 'ranking_main':2,'Cashflow type':'Final Reconciliation' }



#Remove cash balances from cashflow output, then append dictionaries back in
cashflow_stmt_output = cashflow_stmt_output[cashflow_stmt_output['ranking_main'] == 1]

try:
    cashflow_from_ops_last_year = np.sum(cashflow_stmt_output[cashflow_stmt_output['ranking'] <=4 ][last_year])
    cashflow_from_inv_last_year = np.sum(cashflow_stmt_output[(cashflow_stmt_output['ranking'] >4) & (cashflow_stmt_output['ranking'] <=7) ][last_year])
    cashflow_from_fin_last_year = np.sum(cashflow_stmt_output[(cashflow_stmt_output['ranking'] >7) & (cashflow_stmt_output['ranking'] <=9) ][last_year])
    cashflow_total_last_year = np.sum(cashflow_stmt_output[last_year])
except:
    cashflow_from_ops_last_year = 0
    cashflow_from_inv_last_year = 0
    cashflow_from_fin_last_year = 0
    cashflow_total_last_year = 0

#Create subtotal and total for cash flows from operations, investing, financing, and total cash change
cashflow_from_operations_dict = {'Category':'Net cash from operations',prev_last_year:0,last_year:cashflow_from_ops_last_year,
                    this_year:np.sum(cashflow_stmt_output[cashflow_stmt_output['ranking'] <=4 ][this_year]),'ranking':5, 'ranking_main':1,'Cashflow type':'Cashflow from Operations' }

cashflow_from_investing_dict = {'Category':'Net cash from investing',prev_last_year:0,last_year:cashflow_from_inv_last_year,
                    this_year:np.sum(cashflow_stmt_output[(cashflow_stmt_output['ranking'] >4) & (cashflow_stmt_output['ranking'] <=7)][this_year]),'ranking':7, 'ranking_main':1,'Cashflow type':'Cashflow from Investing' }

cashflow_from_financing_dict = {'Category':'Net cash from financing',prev_last_year:0,last_year:cashflow_from_fin_last_year,
                    this_year:np.sum(cashflow_stmt_output[(cashflow_stmt_output['ranking'] >7) & (cashflow_stmt_output['ranking'] <=9) ][this_year]),'ranking':9, 'ranking_main':1,'Cashflow type':'Cashflow from Financing' }

cashflow_change_total = {'Category':'Net change in cash and cash equivalents',prev_last_year:0,last_year:cashflow_total_last_year,
                    this_year:np.sum(cashflow_stmt_output[this_year]),'ranking':10, 'ranking_main':1,'Cashflow type':'Net change in cash' }
#Prepare dictionaries to export back to cashflow statement
cash_balance_join = pd.DataFrame([cash_initial_dict,cash_final_dict,cashflow_from_operations_dict,cashflow_from_investing_dict,cashflow_from_financing_dict,cashflow_change_total])


#Join cash balances back to dataframe
cashflow_stmt_output = pd.concat([cashflow_stmt_output,cash_balance_join],axis = 0,ignore_index = True)
#Resort dataframe
cashflow_stmt_output = cashflow_stmt_output.sort_values(['ranking_main','ranking','Category']).fillna(0)

#Only keep relevant data columns for export
cashflow_stmt_output = cashflow_stmt_output[['Category',last_year,this_year,'Cashflow type']]


#Round all numbers to 2 decimal places
cashflow_stmt_output = cashflow_stmt_output.round(2)

#pivot table to place equity type in columns
stmt_equity_output = stmt_equity_output.pivot_table('Balance',['Category','Year'],'Equity Type').sort_values(['Year','Category']).fillna(0).reset_index()


#Retrieve the initial Retained Earnings and Share Capital Amounts 2 years before the year of date of input to prepare output
equity_stmt_beg = {'Category':'Balance as of end of '+str(prev_last_year),'Year':str(prev_last_year),'Common Stock':np.sum(stmt_equity_output[stmt_equity_output['Year'].astype(int) < last_year ]['Common Stock'] ), 'Retained Earnings': np.sum(stmt_equity_output[stmt_equity_output['Year'].astype(int) < last_year ]['Retained Earnings'] ) }
equity_stmt_mid = {'Category':'Balance as of end of '+str(last_year),'Year':str(last_year),'Common Stock':np.sum(stmt_equity_output[stmt_equity_output['Year'].astype(int) < this_year ]['Common Stock'] ), 'Retained Earnings': np.sum(stmt_equity_output[stmt_equity_output['Year'].astype(int) < this_year ]['Retained Earnings'] )}
equity_stmt_end = {'Category':'Balance as of  '+str(date_input),'Year': str(this_year),'Common Stock':np.sum(stmt_equity_output[stmt_equity_output['Year'].astype(int) < this_year+1 ]['Common Stock'] ), 'Retained Earnings': np.sum(stmt_equity_output[stmt_equity_output['Year'].astype(int) < this_year+1 ]['Retained Earnings'] ) }

equity_stmt_add = pd.DataFrame([equity_stmt_beg,equity_stmt_mid,equity_stmt_end])

#Filter out equity statement line items for the past 2 years only
stmt_equity_output = stmt_equity_output[stmt_equity_output['Year'].astype(int) >= last_year]

#stmt_equity_output round to 2 decimal places
stmt_equiity_output = stmt_equity_output.round(2)

#Concatenate starting equity balances into equity statement dataframe
stmt_equity_output = pd.concat([stmt_equity_output,equity_stmt_add],axis = 0,ignore_index = True)

#Define row mapping to set equity statement output to correct rows

mapping_dict = {'Dividends paid':3,'Proceeds from issuance':1,'Profit/Loss':2,'Balance as of end of '+str(prev_last_year):4,'Balance as of end of '+str(last_year):4,'Balance as of end of '+str(date_input):4}

#Add mapping to equity statement
stmt_equity_output['ranking'] = stmt_equity_output['Category'].map(mapping_dict)

#Arrange equity statement accordingly for export
stmt_equity_output = stmt_equity_output.sort_values(['Year','ranking']).drop(columns = 'ranking')

stmt_equity_output['Total'] = stmt_equity_output['Retained Earnings'] + stmt_equity_output['Common Stock']

#Round all numbers to 2 decimal places
stmt_equity_output = stmt_equity_output.round(2)

#Filter out balance sheet line items that are < $0.01
balance_sheet_output = balance_sheet_output.round(2)
balance_sheet_output = balance_sheet_output[balance_sheet_output['Balance'] >= 0.005 ]

#Pivot balance sheet to show yearly data in column
balance_sheet_output = balance_sheet_output.pivot_table('Balance',['T_Account_Name','asset_grouping'],'Year').reset_index().sort_values('asset_grouping')

#Fill NA columns with 0
balance_sheet_output = balance_sheet_output.fillna(0)



#Prepare output - drop ranking and group
profit_loss_year_output = profit_loss_year_output.drop(columns = ['ranking']).rename(columns= {'T_Account_Name': 'P&L Category'})
profit_loss_total = profit_loss_total.drop(columns = ['ranking','group']).rename(columns= {'T_Account_Name': 'P&L Category'})
balance_sheet_output = balance_sheet_output.rename(columns= {'T_Account_Name': 'Category','asset_grouping':'Asset Category',last_year:str(last_year)+'Q'+str(this_quarter),this_year:str(this_year)+'Q'+str(this_quarter)})

#Remove tax payable txn for current year which was calculated before the date of input, and append tax payable to transaction
#Find year of date of input
date_input_output = date_input[:10]
#Remove previous tax transaction that was previously calculated
df = df[(df['Credit_Amount'] != 'Tax Payable')]
df = df.sort_values('Date')


'''
Ending: Export P&L,Balance Sheet, Inventory and Transactions into a single sheet
'''
#Export Financial Statements to Excel
with pd.ExcelWriter( str(date_input_output)+str(' ')+'FS_BS.xlsx') as writer:
    profit_loss_year_output.to_excel(writer, sheet_name='Profit & Loss YTD', index = False)
    balance_sheet_output.to_excel(writer, sheet_name='Balance Sheet Today', index = False)
    stmt_equity_output.to_excel(writer, sheet_name='Stmt of Chng to Equity', index = False)
    cashflow_stmt_output.to_excel(writer, sheet_name='Cash Flow Statement', index = False)
    inventory_warehouse.to_excel(writer, sheet_name='Inventory Warehouse', index = True)
    inventory_shops.to_excel(writer, sheet_name='Inventory Shop', index = False)
    df.to_excel(writer, sheet_name='Transactions Cleaned', index = False)
    inventory_data_final.to_excel(writer, sheet_name = 'Inventory Stock Check', index = False)
