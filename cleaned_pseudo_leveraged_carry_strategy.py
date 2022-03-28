# -*- coding: utf-8 -*-
"""
Created on Mon Mar 28 05:54:26 2022

@author: CZ
"""
def leveragedCarryVault(pair,i):
    """step 1: find the instant carry and moving average of carry (annualized) and take the simple average between 2 figures
    instant carry = (current floating rate - current fixed rate) /30*365
    trailing carry = (30day moving average floating rate - current fixed rate) /30*365"""
    #instant carry if long or short at the current market level 
    vault[pair]['apy_history'][i] = apy_history[pair][i]
    vault[pair]['instant_carry%'][i]= (apy_history[pair][i]-amm[pair]['Quote_initial'][i])/30*365 
    #average carry, if only 1 day, then average carry = instant carry 
    #if 2-30 days, then average carry is the average of all days available 
    #if more than 30 days, then average carry is the average of 30 days 
    vault[pair]['trailing_carry%'][i]=(apy_history_trailing[pair][i]-amm[pair]['Quote_initial'][i])/30*365 #average carry if long or short at the current market level 
    vault[pair]['expected_return'][i]=(vault[pair]['instant_carry%'][i]+vault[pair]['trailing_carry%'][i])/2
    """step 2: decide the side of the trade, whether to long or to short based on the sign of the carry figure
    given the sign of the trade (long or short, the max notinoal that the market AMM allows will differ"""
    #if trader = long, then maxNotional = 0.1* (real TVL+net exposure of AMM + unrealized PnL)
    #if trader = short, then maxNotional = 0.1* (real TVL - net exposure of AMM + unrealized PnL)        
    """doesn't need to calculate ourselves, the maxNotional can be captured from chain"""
    maxNotional=0
    notional=0
    if vault[pair]['expected_return'][i]>0:
        #positive carry, then long
        maxNotional = 0.1*(amm[pair]['Staked_amount'][i]+amm[pair]['net_exposure'][i]+amm[pair]['Unrealized_PnL'][i])
        vault[pair]['side'][i]=1
    else:
        #negative carry, then short 
        maxNotional = 0.1*(amm[pair]['Staked_amount'][i]-amm[pair]['net_exposure'][i]+amm[pair]['Unrealized_PnL'][i])
        vault[pair]['side'][i]=-1
    max = 0
    """step 3: decide the notional of the trade, because for different trade notional, the slippage and trading fee will be different
    in this process, there is an optimization to go through from 1k to min(maxNotional, cashReserves/num. of markets currently available)of the market, and find teh one which yields lowest  net expected return"""
    #decdie the notional because the slippage (expected cost) depends on the notional size of each addtional trade we put on 
    #notional taken from 1k to min(maxNotional, cash reserves of vault / number of markets listed) with increment of 1k
    #check if there is cash reserves avaialble to open more 
    #to ensure that vault doesn't run out of money, then we need to make sure that each market we should not invest more than 20% of the cash reserves 
    #later we can improve the strategy to weighted by the carry itself, but right now we keep it 20% equally weighted over 5 markets
    #that we can make sure we don't "waste" too much money in the market with low carry% 
    if maxNotional > vault_summary['Cash_reserves'][i]/5*10: 
        maxNotional = vault_summary['Cash_reserves'][i]/5*10
    else:
        pass
    for notional in range(1000,int(maxNotional),1000):
        #expected cost 
        trading_fee = notional*amm[pair]['Quote_initial'][i]*0.01*0.01*2 #round trip estimated trading fee
        if vault[pair]['expected_return'][i]>0:
            #slippage = R'/R - 1 (long)
            #slippage = R/R'-1 (short)
            """we don't have to calculate ourselves, we just need to call the value directly from the smart contract of the slippage, then the slippage = notional * slippage%"""
            estimated_slippage = ((amm[pair]['Staked_amount_Long'][i]+notional)/(amm[pair]['Staked_amount_Short'][i])/amm[pair]['Ratio'][i]-1)*notional
        else:
            estimated_slippage = (amm[pair]['Ratio'][i]/(amm[pair]['Staked_amount_Long'][i]/(amm[pair]['Staked_amount_Short'][i]+notional))-1)*notional
    
        #expected USDC income if holding the position for a day (since we rebalance each day )
        """step 4: get the monthly return which is 30day's expected return if put on this trade - expected cost to be net expected cost. 
        we pick the notional that has the highst next expected return"""
        expected_return = vault[pair]['side'][i]*notional*vault[pair]['expected_return'][i]/100 #percentage%
        #expected USDC cost per carry trade 
        expected_cost = trading_fee+estimated_slippage #round trip cost based on notional
        #find the notional amount that maximize the (expected return - expected cost)
        if (expected_return - expected_cost)>max:
            max = expected_return - expected_cost
            vault[pair]['expected_net_return'][i] = expected_return - expected_cost
            vault[pair]['notional'][i] = notional
            vault[pair]['position'][i] = notional
            vault[pair]['collateral'][i] =vault[pair]['notional'][i] /10 #always take the maximum leverag
            vault[pair]['trading_fee_in'][i] = trading_fee/2 #trading fee calcualted as round trip 
            vault[pair]['estimated_slippage'][i] = estimated_slippage
            vault[pair]['expected_cost'][i] = trading_fee+estimated_slippage
            vault[pair]['expected_net_return'][i] = expected_return - expected_cost
        else:               
            pass 
    """step 5 (if i don't have open position), then if expected return > 36.5% annualized a year
    note that we calcualte expected return in annualized way, which is (floating rate - fixed rate)/30 * 365 (without %), so the daily expected return % / 365 again 
    """
    if i == 0:       
        #then 50%/30*365 = 608% a year, a day = 1.6%, which is higher than 0.1% a day = 36.5% a year --> long
        #then if -50%/30*365 = -608% a year, a day = -1.6% --> short 
        #in between: do nothing 
        if vault[pair]['expected_return'][i]/100/365>0.001:  
            vault[pair]['side'][i]=1
        elif vault[pair]['expected_return'][i]/30/vault[pair]['collateral'][i]<-0.001: 
            vault[pair]['side'][i]=-1
        else:
            #do nothing if carry is not high enough (to leave some buffer)
            vault[pair]['side'][i]=0 
    """step 6: every 24 hours, check positions to decide if
    add collateral
    close partially
    close all
    hold /do nothing
    add more
    for each market """
    elif i>0:
    """step 6a: check if any existing open position, if no existing open position, repeat the step 5 """ 
        if vault[pair]['position'][i-1] == 0.0: 
        #open new (same as day 0)
            if vault[pair]['expected_return'][i]/100/365>0.001: 
                vault[pair]['side'][i]=1
            elif vault[pair]['expected_return'][i]/100/365<-0.001: 
                vault[pair]['side'][i]=-1
            else:
                #do nothing if carry is not high enough (to leave some buffer)
                vault[pair]['side'][i]=0 
                
    """step 6b: if there is some exiting open position, then ALWAYS first check if we need to add collateral""" 
        elif vault[pair]['position'][i-1] != 0.0:
            # no need to calculate margin ourselves, can just call from smart contract on the margin% level which more accurate 
            """calculate the amount in order to bring the margin back to 10%, which is roughly: notional * 0.1 - unrealized PnL of the position, for which each of the value can be retrieved from smart contract"""
            if (vault[pair]['collateral'][i]+vault[pair]['Unrealized_PnL'][i])/vault[pair]['position'][i]<0.1:
                vault_summary['Cash_reserves'][i]-= (-vault[pair]['Unrealized_PnL'][i])
                vault_summary['USDC_Balance'][i] -= (-vault[pair]['Unrealized_PnL'][i])
                vault[pair]['collateral'][i] = (vault[pair]['position'][i]*0.1-vault[pair]['Unrealized_PnL'][i]) #if unrealized is negative, then need to add a negative number
                # if the vault runs out of cash balance to add collateral, then transaction reverted, do nothing, because 10% is "generous" level, it doesn't mean if <10%, we will be liquidated immediately 
                if vault_summary['Cash_reserves'][i] <0:
                    #means the position is closed to be liquidated and we don't even have enough cash to add reserves, we need to close the position to 
                    print('alert: not enough cash balance for the trading vault to top up collateral!!!')        
        
    """step 7c: after checking margin% level for existing position then check if we want to close to take profit or cut loss
    unrealized pnl can be retrieved from smart contract
    expected return next 30days = annualized expected return ~simple average of (instant carry and moving average carry) *exisitng open position /365*30 
    expected return next 1 day = annuzlied expected return ~simple average of (instant carry and moving average carry) *existing open position /365*1
    (1) cut loss level = if unrealized pnl + expected return over next 30 days < 0
    this means, i already lost 100 U, but I only expect to receive less than 100U over next 30 days so let's stop this trade, it will take me more than 30 days to break even 
    (2a) take profit level = 50%, if ( unrealized pnl / days since inception of the position + expected return next 1 day ) / collatearl level > 50% 
    *(3) if we cannot find number of days since inception of the position, then we can do the following 
    (2b) take profit levl = 50%, if (unrealized pnl + expeced return next 1 day) / collateral > 50%
    """
            #close to cut loss (if my unrealized loss already overpasses my 30days of expected returns) to avoid being liquidated OR
            #close to take profit if my daily return (over period of holding) > 70%  
            (vault[pair]['Unrealized_PnL'][i]+vault[pair]['side'][i-1]*vault[pair]['expected_return'][i]/100/365*30*vault[pair]['position'][i]) <0 or\
                (vault[pair]['Unrealized_PnL'][i]/vault[pair]['days_elapsed'][i]+vault[pair]['expected_return'][i]/100/365*vault[pair]['position'][i])/vault[pair]['collateral'][i]>50:
                #make sure I would not close the full position that slippage would be too large
                """step 7d: if position > 20k, then close only 50%, otherwise the impact  from slippage is too large. If the position < 10k, then close all"""
                if vault[pair]['position'][i]>10000:
                    partial = 0.5 
                    vault[pair]['days_elapsed'][i] = vault[pair]['days_elapsed'][i-1] 
                else:
                    partial = 1
                    vault[pair]['days_elapsed'][i] = 0
                #default for closing to cut loss or take profit 
    """step 7e: if we don't need to close or partially close position to take profit/cut loss, then judge if we want to hold position or add more position
    below 2 conditions are met: 
    (1) if unrealized pnl + expected return over next 30 days > 0 (no need to close)
    (2) (unrealized pnl / number of days since inception of position + expected return next 1 day) / collateral <  50% (no need to take profit)
    while
    (3) expected return today and yesterday sign changed--> HOLD
    (4) if we cannot obtain the sign of the expected return, then we can just use current (floating rate - fixed rate) > 0 but current position is short, then HOLD the current short position 
    """
            #otherwise hold if the sign of the trade changes 
            #if nothing exciting, then hold the position to the next day, sometimes the withdrawal will help us to close some positions to lock in 
            elif (vault[pair]['Unrealized_PnL'][i]+vault[pair]['side'][i-1]*vault[pair]['expected_return'][i]/100/365*30*vault[pair]['position'][i])>0 and np.sign(vault[pair]['expected_return'][i])!= np.sign(vault[pair]['expected_return'][i-1]):
              
    """step 7f: if we don't need to close or partially close position to take profit/cut loss, then judge if we want to hold position or add more position
    below 2 conditions are not 
    (1) if unrealized pnl + expected return over next 30 days > 0 (no need to close)
    (2) (unrealized pnl / number of days since inception of position + expected return next 1 day) / collateral <  50% (no need to take profit)
    while
    (3) expected return today and yesterday sign doesn't change --> ADD MORE 
    (4) repeat step 5 (it is possible that we eventually did't add more after checking step 5)
    """
            elif (vault[pair]['Unrealized_PnL'][i]+vault[pair]['side'][i-1]*vault[pair]['expected_return'][i]/100/365*30*vault[pair]['position'][i])>0 and np.sign(vault[pair]['expected_return'][i]) == np.sign(vault[pair]['expected_return'][i-1]):
                #notional is already decided at the for_loop for pairs before
                if vault[pair]['expected_return'][i]/365/100>0.001:
                    vault[pair]['side'][i]=1
                elif vault[pair]['expected_return'][i]/365/100<-0.001: 
                    vault[pair]['side'][i]=-1
                else: #no need to add more positions if < buffer (which means carry is not that attractive right now )
                    vault[pair]['side'][i]=0
                   