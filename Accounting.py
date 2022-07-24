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
#Retrieve full transaction list and cleaning
df = pd.read_excel('Transactions.xlsx')
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values(by = 'Date', ascending = True).reset_index(drop = True)

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

#T-accounts at time 0
t_accts =  dict( zip(resulting_list,listofzeros) )

#Now we will loop through every sorted date from earliest to latest to update the T-Accounts

#create list of sorted dates
list_of_dates = df.Date.unique()

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

profit_loss = profit_loss.append([gross_profit,operating_profit,tax_payable,profit_after_tax], ignore_index = True).sort_values('ranking')
#profit_loss = profit_loss.set_index(PL_sort.index).sort()

#balance sheet
balance_sheet = t_account_balance[t_account_balance['group'] == 'balance_sheet']

#append tax payable into balance sheet
balance_sheet = balance_sheet.append([tax_payable_balance_sheet,profit_after_tax_balance_sheet], ignore_index = True )

#Add grouping to balance sheet
balance_sheet['asset_grouping'] = balance_sheet['T_Account_Name'].map(custom_dict_balance_sheet)
#Convert negative credit values to positive values
balance_sheet['Balance'] = np.where( balance_sheet['asset_grouping'] == 'Equity', abs(balance_sheet['Balance']), balance_sheet['Balance'])
balance_sheet['Balance'] = np.where( balance_sheet['asset_grouping'] == 'Liabilities', abs(balance_sheet['Balance']), balance_sheet['Balance'])

#sort balance sheet by asset grouping Asset--> Equity --> Liabilities
balance_sheet = balance_sheet.sort_values('asset_grouping')

#drop ranking and group
profit_loss = profit_loss.drop(columns = ['ranking','group']).rename(columns= {'T_Account_Name': 'P&L Category'})
#balance_sheet = balance_sheet.drop(columns = ['group']).rename(columns= {'T_Account_Name': 'Category'})

#Export Financial Statements to Excel
with pd.ExcelWriter('FS_BS.xlsx') as writer:
    profit_loss.to_excel(writer, sheet_name='profit_loss', index = False)
    balance_sheet.to_excel(writer, sheet_name='balance_sheet', index = False)
