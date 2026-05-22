ㅇ"""
This module defines a mapping from standardized metric names (e.g. "revenue", "net_income", etc.) to 
lists of possible XBRL concept tags that could represent those metrics in the US GAAP taxonomy. 
This mapping is used by the FactExtractor to extract the relevant financial data from the company facts provided by 
the SEC's XBRL filings.
"""

CONCEPT_MAP = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "assets": [
        "Assets",
    ],
    "liabilities": [
        "Liabilities",
    ],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ],
    "inventory": [
        "InventoryNet",
    ],
    "accounts_receivable": [
        "AccountsReceivableNetCurrent",
    ],
    "accounts_payable": [
        "AccountsPayableCurrent",
    ],


    # Additional metrics to extract beyond the core 10. These are not guaranteed to be present for all companies, but we will attempt to extract them if available.
        "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ],
    "research_and_development": [
        "ResearchAndDevelopmentExpense",
    ],
    "sga": [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
        "SellingAndMarketingExpense",
    ],
    "interest_expense": [
        "InterestExpenseNonOperating",
        "InterestExpense",
        "InterestAndDebtExpense",
    ],
    "income_tax": [
        "IncomeTaxExpenseBenefit",
    ],
    "current_assets": [
        "AssetsCurrent",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "ppe_net": [
        "PropertyPlantAndEquipmentNet",
    ],
    "total_debt": [
        "DebtAndFinanceLeaseObligations",
        "LongTermDebtAndFinanceLeaseObligations",
        "LongTermDebt",
    ],
    "investing_cash_flow": [
        "NetCashProvidedByUsedInInvestingActivities",
    ],
    "financing_cash_flow": [
        "NetCashProvidedByUsedInFinancingActivities",
    ],
    "stock_based_compensation": [
        "ShareBasedCompensation",
    ],
    "share_repurchases": [
        "PaymentsForRepurchaseOfCommonStock",
        "PaymentsForRepurchaseOfEquity",
    ],
}