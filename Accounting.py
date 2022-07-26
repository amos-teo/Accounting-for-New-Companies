#This script will create the balance sheet for a company that has just been incorporated for the first year.
#More versions to come along, including year-to-year P&L generation and updating of accounting balances, inventory management and financial analytics
#Tax functions are based on laws in Singapore






##Start by defining function to determine which accounts belong in the balance sheet vs P/L
def label_t_accts(a):
    if 'Expense' in a:
        return 'trial_balance'
    elif 'Revenue' in a:
        return 'trial_balance'
    else:
        return 'balance_sheet'




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

import pandas as pd
import numpy as np
from datetime import datetime



'''
Part 1: Inventory Management and Transaction Calculations
'''


#Retrieve full transaction list and cleaning
xlsx = pd.ExcelFile('Transactions_Data.xlsx')
df = pd.read_excel(xlsx, 'Transaction')
price_list = pd.read_excel(xlsx, 'Price List')

df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values(by = 'Date', ascending = True).reset_index(drop = True)

'''
Date Filter from USER
'''
date_input = datetime.now()
date_input = input('Please key in the date of report in YYYY-MM-DD format:')
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
    daily_price_list['Diff_in_Days'] = (date - daily_price_list['Effective_Till']).dt.days
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
#sum all the positive and negative balances
t_account_balance = t_acct_df.groupby('T_Account_Name').sum()
#add all the credit and debit balance to find the final T-Account balance
t_account_balance['Balance'] = t_account_balance['Debit_Amount'] + t_account_balance['Credit_Amount']
#drop debit and credit columns
t_account_balance = t_account_balance.drop(columns = ['Debit_Amount','Credit_Amount'] ).reset_index()

#now, everything that is positive is debit and everything that is negative is credit
t_account_balance['group'] = t_account_balance['T_Account_Name'].apply(lambda x: label_t_accts(x) )

#Drop inventory in shops (for presentation)
t_account_balance = t_account_balance[(t_account_balance['Balance'] != 0) & (t_account_balance['T_Account_Name'].str[:10] != 'Inventory_' )  ]

###We will start doing the P/L statement now
profit_loss = t_account_balance[t_account_balance['group'] == 'trial_balance']

#flip balance for P/L
profit_loss['Balance'] = profit_loss['Balance'] * -1

#Please edit this dictionary to manually set the order of categories in P&L statement and Balance Sheet
custom_dict = {'Revenue':0, 'COGS Expense':1, 'Rent Expense':3, 'Transportation Expense':3}
custom_dict_balance_sheet = {'Cash': 'Asset', 'Inventory': 'Asset','AR': 'Asset','Share Capital': 'Equity','Retained Earnings': 'Equity','Tax Payable': 'Liabilities'}

#sort by dictionary above
profit_loss['ranking'] = profit_loss['T_Account_Name'].map(custom_dict)
profit_loss = profit_loss.sort_values(by = 'T_Account_Name', key = lambda x: x.map(custom_dict))

#Add Gross Profit and Operating Profit Before Tax into trial_balance
gross_profit = {'T_Account_Name': 'Gross Profit', 'Balance': np.sum( profit_loss[profit_loss['ranking'] <= 1]['Balance'] ), 'group':'trial_balance', 'ranking': 2}
operating_profit = {'T_Account_Name': 'Operating Profit', 'Balance': np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ), 'group':'trial_balance', 'ranking': 4}
tax_payable = {'T_Account_Name': 'Tax Payable', 'Balance': start_up_tax_amount(np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) ), 'group':'trial_balance', 'ranking': 5}
profit_after_tax = {'T_Account_Name': 'Profit After Tax', 'Balance': np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) + start_up_tax_amount(np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) ), 'group':'trial_balance', 'ranking': 6}
tax_payable_balance_sheet = {'T_Account_Name': 'Tax Payable', 'Balance':start_up_tax_amount(np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) ), 'group': 'balance_sheet'}
profit_after_tax_balance_sheet = {'T_Account_Name': 'Retained Earnings', 'Balance': np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) + start_up_tax_amount(np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) ), 'group':'balance_sheet'}

tax_payable_transaction = {'Date': date_input,'Debit':'Tax Expense', 'Debit_Amount': start_up_tax_amount(np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) ) *-1,
                            'Credit_Amount': start_up_tax_amount(np.sum( profit_loss[profit_loss['ranking'] <= 3]['Balance'] ) ) *-1,'Credit':'Tax Payable', 'Comments':'','Quantity':'' , 'Ref_Number':'','Item_Name':''}


profit_loss = profit_loss.append([gross_profit,operating_profit,tax_payable,profit_after_tax], ignore_index = True).sort_values('ranking')
#profit_loss = profit_loss.set_index(PL_sort.index).sort()

#balance sheet
balance_sheet = t_account_balance[t_account_balance['group'] == 'balance_sheet']



#append tax payable into balance sheet
balance_sheet = balance_sheet.append([tax_payable_balance_sheet], ignore_index = True )

#Add grouping to balance sheet
balance_sheet['asset_grouping'] = balance_sheet['T_Account_Name'].map(custom_dict_balance_sheet)

#Convert negative credit values to positive values
balance_sheet['Balance'] = np.where( balance_sheet['asset_grouping'] == 'Equity', abs(balance_sheet['Balance']), balance_sheet['Balance'])
balance_sheet['Balance'] = np.where( balance_sheet['asset_grouping'] == 'Liabilities', abs(balance_sheet['Balance']), balance_sheet['Balance'])

#append Retained Earnings into balance sheet
balance_sheet = balance_sheet.append([profit_after_tax_balance_sheet], ignore_index = True )

#Add grouping to balance sheet
balance_sheet['asset_grouping'] = balance_sheet['T_Account_Name'].map(custom_dict_balance_sheet)

#sort balance sheet by asset grouping Asset--> Equity --> Liabilities
balance_sheet = balance_sheet.sort_values('asset_grouping')

#drop ranking and group
profit_loss = profit_loss.drop(columns = ['ranking','group']).rename(columns= {'T_Account_Name': 'P&L Category'})
balance_sheet = balance_sheet.drop(columns = ['group']).rename(columns= {'T_Account_Name': 'Category'})


#Remove tax payable txn for current year which was calculated before the date of input, and append tax payable to transaction
#Find year of date of input
date_input_output = date_input[:10]
#Remove previous tax transaction that was previously calculated
df = df[(df['Credit_Amount'] != 'Tax Payable') & (df['Date'] < date_input)]
#Append tax journal entry into txn list
df = df.append(tax_payable_transaction, ignore_index = True)


print(df)

'''
Export P&L,Balance Sheet, Inventory and Transactions into a single sheet
'''
#Export Financial Statements to Excel
with pd.ExcelWriter( str(date_input_output)+str(' ')+'FS_BS.xlsx') as writer:
    profit_loss.to_excel(writer, sheet_name='Profit & Loss', index = False)
    balance_sheet.to_excel(writer, sheet_name='Balance Sheet', index = False)
    inventory_warehouse.to_excel(writer, sheet_name='Inventory Warehouse', index = True)
    inventory_shops.to_excel(writer, sheet_name='Inventory Shop', index = False)
    df.to_excel(writer, sheet_name='Transactions Cleaned', index = False)
