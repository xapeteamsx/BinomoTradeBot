#!/usr/bin/python3
import asyncio, websockets, ssl
import time
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
import dateutil, calendar
from tapy import Indicators
from DataHistory import Ticker
import ClientConsole as cc
from telethon import TelegramClient
import requests
import logging

class Binongtot(object):
    def __init__(self):
        self._aw_conn = None
        self._depth = 0
        self.df = pd.DataFrame(columns=['Datetime','rate', 'precision', 'repeat', 'ask', 'created_at','bid', 'spread','volume'])
        self.newdf = pd.DataFrame(columns=['Datetime','rate', 'precision', 'repeat', 'ask', 'created_at','bid', 'ric','spread','volume'])
        self.response = {}
        self.counter = 0
        self.loop_socket = 0
        self.assetConf = self.get_asset()
        self.deviceId = self.assetConf["deviceId"]
        self.authToken = self.assetConf["authToken"]
        self.assetRic = self.assetConf["assetRic"]
        self.currency = self.assetConf["currency"]
        self.uagent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"        
        self.bid_price = 10
        self.lowbid = 5
        self.val_support = []
        self.val_resistance = []
        self.state_val_support = []
        self.state_val_resistance = []
        self.ctr_minute = 1
        self.fr_sigbuy = False
        self.fr_sigsel = False
        self.msg_buy = ""
        self.msg_sell = ""        
        self.latest_balance = 0
        self.last_cci_c1 = 0
        self.last_cci_c2 = 0
        self.cci = 0
        self.last_cond_below_support = False
        self.last_cond_below_resistance = False
        self.is_open_position = False
        self.is_macd_crossed = False
        self.last_macd_signal = 0
        self.last_macd_value = 0
        self.is_breakout = False
        self.is_breakdown = False
        self.cci_up = False
        self.cci_down = False
        self.is_fractal_up = False
        self.is_fractal_down = False
        self.is_ema8_up = False
        self.is_ema8_down = False
        self.is_macd_up = False
        self.is_macd_down = False
        self.is_reversal_up = False
        self.is_reversal_down = False
        self.ema8midbb_up = False
        self.ema8midbb_down = False
        self.is_ema8_cross50_up = False
        self.is_ema8_cross50_down = False


        # set time and timezone
        timezone_offset = +7.0 
        self.tzinfo = timezone(timedelta(hours=timezone_offset))
        dtb = datetime.now(self.tzinfo)
        presentDate = dtb + timedelta(minutes=+1)
        self.curr_now = presentDate.strftime('%H:%M')
        self.lasttime = ""
        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        self.curr_utc = utc_present.strftime('%H:%M')

        # setup telegram bot
        self.botToken = '' # your telegram bot token
        self.gchatId = '' # your channel id
        
        self.tempbin = self.getOnlineData()
        self.pollHost = "wss://as.binomo.com/"
        self.cookie = "l=; authtoken="+self.authToken+"; device_id="+self.deviceId+"; device_type=web"
        self.headers = {'User-Agent': self.uagent, 'Cookie': self.cookie}

        self.pb = cc.Placebid()

        '''
        logger = logging.getLogger('websockets')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler())        
        '''

    async def __aenter__(self):
        # create a connection *if not already established*
        if self._aw_conn is None:
            self._aw_conn = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
            self._depth = 0
        self._depth += 1
        return self._aw_conn

    async def __aexit__(self, *exc_info):
        self._depth -= 1
        if self._depth < 1:
            # close the connection
            await self._aw_conn.close()
            self._aw_conn = None
            self._depth = 0

    async def main(self):
        async with self as websocket:
            self.connect()

    async def createDataframe(self, data):
        tempdata = {}
        rates = []
        self.loop_socket+=1
        dtt = datetime.now(self.tzinfo)
        wibtime = dtt.strftime('%H:%M')
        charttime = dtt.strftime('%Y-%m-%d %H:%M:00')

        data.index = pd.to_datetime(data.Datetime)
        df1 = data['rate'].resample('1Min').agg(
                                    {'open': 'first', 
                                     'high': 'max', 
                                     'low': 'min', 
                                     'close': 'last'})
        
        d1 = pd.DataFrame(df1).reset_index()
        d1.columns = ['Datetime','open', 'high','low','close']  

        self.counter = int(data["created_at"][-1].split(":")[-1].split(".")[0])
        print("xctr -> ", self.counter)
        curr_close = 0
        current_price = 0
        curopen = 0

        if self.counter == 0:
            curr_close = df1['close'][-1]        
        elif self.counter == 1:        
            curopen = df1['open'][-1]
        else:
            curr_close = df1['close'][-1]
            curopen = df1['open'][-1]
            current_price = df1['close'][-1]
        
        self.mergeDataWSOnline(self.counter, d1)

    def mergeDataWSOnline(self, ctr, wsdata):        

        counter = ctr
        tempdata = {}
        historydata = []
        pd.set_option('display.float_format', '{:.11f}'.format)        
        wsdata = wsdata.set_index('Datetime')
        curr_open = wsdata['open'][-1]
        cur_digits = str(curr_open).split('.')
        count_lencur = len(cur_digits[1])
        dtb = datetime.now(self.tzinfo)
        present_utc = datetime.now()
        #unix_timestamp = dtb.timestamp(presentDate)*1000
        presentDate = dtb + timedelta(minutes=+1)
        timesx = presentDate.strftime('%H:%M')

        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        timesx_utc = utc_present.strftime('%H:%M')
        temp_dfol = self.tempbin["d1"]

        # merge websocket data with one-day history data
        df_ws = pd.DataFrame(wsdata, columns=['open', 'high', 'low','close'])
        wsdata_copy = df_ws.rename(columns = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close'})
        wsdata_copy['Datetime'] = pd.to_datetime(wsdata_copy.index) + timedelta(minutes=1)
        temp_dfol['Datetime'] = pd.to_datetime(temp_dfol.Datetime)
        wsdata_copy.index = wsdata_copy['Datetime'] 
        temp_dfol['Datetime'] = temp_dfol['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        vol_copy = (wsdata_copy['High'] - wsdata_copy['Low']) - (wsdata_copy['Open'] - wsdata_copy['Close'])
        wsdata_copy['Volume'] = vol_copy

        # dropping last 1 row to avoid duplicate
        temp_dfol = temp_dfol.iloc[:-1]

        merge_ws_dataonline = pd.concat([temp_dfol, wsdata_copy]).drop_duplicates()
        merge_ws_dataonline.index = pd.to_datetime(merge_ws_dataonline.Datetime)
        merge_ws_dataonline["Volume"] = merge_ws_dataonline.Volume * (10 ** count_lencur)
        
        self.my_strategy(ctr, merge_ws_dataonline, count_lencur, wsdata)

    # you can customize your trading strategy
    def my_strategy(self, ctr, merge_ws_dataonline, count_lencur, wsdata):

        dtb = datetime.now(self.tzinfo)
        present_utc = datetime.now()
        presentDate = dtb + timedelta(minutes=+1)
        timesx = presentDate.strftime('%H:%M')

        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        timesx_utc = utc_present.strftime('%H:%M')
        
        curr_high = merge_ws_dataonline['High'][-1]
        curr_low = merge_ws_dataonline['Low'][-1]
        curr_open = merge_ws_dataonline['Open'][-1]
        curr_price = merge_ws_dataonline['Close'][-1]
        op1 = merge_ws_dataonline['Open'].shift(1)[-1]
        cl1 = merge_ws_dataonline['Close'].shift(1)[-1]
        cl2 = merge_ws_dataonline['Close'].shift(2)[-1]
        cl3 = merge_ws_dataonline['Close'].shift(3)[-1]
        cl4 = merge_ws_dataonline['Close'].shift(4)[-1]
        hc1 = merge_ws_dataonline['High'].shift(1)[-1]
        hc2 = merge_ws_dataonline['High'].shift(2)[-1]
        hc3 = merge_ws_dataonline['High'].shift(3)[-1]
        hc4 = merge_ws_dataonline['High'].shift(4)[-1]
        lc1 = merge_ws_dataonline['Low'].shift(1)[-1]
        lc2 = merge_ws_dataonline['Low'].shift(2)[-1]
        lc3 = merge_ws_dataonline['Low'].shift(3)[-1]
        lc4 = merge_ws_dataonline['Low'].shift(4)[-1]

        ind = Indicators(merge_ws_dataonline)
        ind.fractals(column_name_high='fractals_high', column_name_low='fractals_low')
        ind.bollinger_bands()
        ind.ema(period=8, column_name='ema8', apply_to='Close')        
        ind.ema(period=20, column_name='ema20', apply_to='Close')
        ind.ema(period=50, column_name='ema50', apply_to='Close')
        ind.macd(period_fast=12, period_slow=26, period_signal=9, column_name_value='macd_value', column_name_signal='macd_signal')                
        ind.cci()
        
        dof = ind.df

        print("dof -> ", dof.tail(10))        
        macd_value = dof['macd_value'][-1]
        macd_signal = dof['macd_signal'][-1]    

        self.last_macd_value = dof['macd_value'].shift(1)[-1]
        self.last_macd_signal = dof['macd_signal'].shift(1)[-1]

        boltop = dof['bollinger_top'][-1]
        bolmid = dof['bollinger_mid'][-1]
        past_bolmid = dof['bollinger_mid'].shift(1)[-1]
        boltom = dof['bollinger_bottom'][-1]
 
        self.cci = dof['cci'][-1]
        self.last_cci_c1 = dof['cci'].shift(1)[-1]
        self.last_cci_c2 = dof['cci'].shift(2)[-1]

        fhi = dof['fractals_high'].shift(2)[-1]
        flo = dof['fractals_low'].shift(2)[-1]
        
        print("fhi -> ", fhi)
        print("flo -> ", flo)

        if(fhi == True):
            vhi = dof['High'].shift(2)[-1]
            if len(self.val_resistance) > 0:
                if vhi != self.val_resistance[-1]:
                    self.val_resistance.append(vhi)
                    self.state_val_resistance.append(1)
                    self.state_val_support.append(0)                    
            else:
                self.val_resistance.append(vhi)
                self.state_val_resistance.append(1)
                self.state_val_support.append(0)

            self.fr_sigsel = True
            self.fr_sigbuy = False
        else:
            self.state_val_resistance.append(0)
            self.state_val_support.append(0)


        if(flo == True):
            vlo = dof['Low'].shift(2)[-1]
            if len(self.val_support) > 0:
                if vlo != self.val_support[-1]:
                    self.val_support.append(vlo)
                    self.state_val_support.append(1)
                    self.state_val_resistance.append(0)
            else:
                self.val_support.append(vlo)
                self.state_val_support.append(1)
                self.state_val_resistance.append(0)

            self.fr_sigbuy = True
            self.fr_sigsel = False
        else:
            self.state_val_support.append(0)
            self.state_val_resistance.append(0)

        distance_bb_1m_top = (boltop - curr_price) * 10**count_lencur
        distance_bb_1m_bottom = (curr_price - boltom) * 10**count_lencur

        # crossed signal ema8_20 and validation
        ema8 = dof['ema8'][-1]
        ema20 = dof['ema20'][-1]
        ema50 = dof['ema50'][-1]
        ema8_past = dof['ema8'].shift(1)[-1]
        ema20_past = dof['ema20'].shift(1)[-1]
        ema50_past = dof['ema50'].shift(1)[-1]
        bulls_power = dof['bulls_power'][-1]
        bears_power = dof['bears_power'][-1]

        ema820_cross_up = ema8 > ema8_past and ema8_past < ema20_past and ema8 > ema20
        validate_cossed_up_ema820_signal = ema820_cross_up and (curr_price > cl1 or curr_price >= hc1)
        ema820_cross_down = ema8_past > ema8 and ema8_past > ema20_past and ema8 < ema20
        validate_cossed_down_ema820_signal = ema820_cross_down and (curr_price < cl1 or curr_price <= lc1)

        ema8_cross_up_bb = ema8 < past_bolmid and ema8 > bolmid
        validate_cossed_up_bb_ema8_signal = ema8_cross_up_bb and (curr_price > cl1 or curr_price >= hc1)
        ema8_cross_down_bb = ema8 > past_bolmid and ema8 < bolmid
        validate_cossed_down_bb_ema8_signal = ema8_cross_down_bb and (curr_price < cl1 or curr_price <= lc1)
        crossed_macd_up = self.last_macd_signal > self.last_macd_value and macd_value > macd_signal
        crossed_macd_down = self.last_macd_signal < self.last_macd_value and macd_value < macd_signal
        validate_macd_crossed_up = crossed_macd_up and (curr_price > cl1 or curr_price >= hc1)
        validate_macd_crossed_down = crossed_macd_down and (curr_price < cl1 or curr_price <= lc1)
        validate_reversal_up = curr_price > cl1 or curr_price >= hc1
        validate_reversal_down = curr_price < cl1 or curr_price <= lc1
        param_up = (curr_low > lc1 and curr_low > lc2) or (curr_price > cl1 and curr_price > cl2)
        param_down = (curr_low < lc1 and curr_low < lc2) or (curr_price < hc1 and curr_price < hc2)

        ema8crossmidbb_up = ema8_past < past_bolmid and ema8 > bolmid
        ema8crossmidbb_down = ema8_past > past_bolmid and ema8 < bolmid

        ema8cross50_up = ema8_past < ema50_past and ema8 > ema50
        ema8cross50_down = ema8_past > ema50_past and ema8 < ema50

        status_open = self.countOpenPosition()

        set_ctr_exec = 20

        if ctr % 10 == 0:
            # cross signal ema8_20
            # cross up            
            if ema820_cross_up == True and validate_cossed_up_ema820_signal == True and status_open == False and param_up == True:
                print("EMA8_20 crossed, wait for confirmation...")
                self.setEMA8UP(True)

            # cross down
            if ema820_cross_down == True and validate_cossed_down_ema820_signal == True and status_open == False and param_down == True:
                print("EMA8_20 crossed down, wait for confirmation...")
                self.setEMA8Down(True)

            if crossed_macd_up == True and validate_macd_crossed_up == True and status_open == False and param_up == True:
                print("MACD crossed-up, wait for confirmation...")
                self.setMACDUp(True)

            if crossed_macd_down == True and validate_macd_crossed_down == True and status_open == False and param_down == True:
                print("MACD crossed-down, wait for confirmation...")
                self.setMACDdown(True)

            if ema8crossmidbb_up == True and status_open == False and param_up == True:
                print("EMA8 crossed-up mid-BB, wait for confirmation...")
                self.setEMA8BBUp(True)

            if ema8crossmidbb_down == True and status_open == False and param_down == True:
                print("EMA8 crossed-down mid-BB, wait for confirmation...")
                self.setEMA8BBDown(True)


            if ema8cross50_up == True and status_open == False and param_up == True:
                print("EMA8 cross EMA50, wait for confirmation...")
                self.setEMA8BBUp(True)

            if ema8cross50_down == True and status_open == False and param_down == True:
                print("EMA8 cross EMA50, wait for confirmation...")
                self.setEMA8BBDown(True)

            if self.getMACDUp() == True and validate_macd_crossed_up == True and status_open == False and ctr > set_ctr_exec and param_up == True: 
                msg = "⬆️ [[{}]] [[WS]] [[MACD-1m-UP]] potentially BUY [[33011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setMACDUp(False)

            if self.getMACDdown() == True and validate_macd_crossed_down == True and status_open == False and ctr > set_ctr_exec and param_down == True:                
                msg = "⬇️ [[{}]] [[WS]] [[MACD-1m-DOWN]] potentially SELL [[32012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setMACDdown(False)

            if self.getEMA8Up() == True and validate_cossed_up_ema820_signal == True and status_open == False and ctr > set_ctr_exec and param_up == True: 
                msg = "⬆️ [[{}]] [[WS]] [[EMA8-1m]] potentially BUY [[30011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setEMA8UP(False)

            if self.getEMA8Down() == True and validate_cossed_down_ema820_signal == True and status_open == False and ctr > set_ctr_exec and param_down == True:                
                msg = "⬇️ [[{}]] [[WS]] [[EMA8-1m]] potentially SELL [[30012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setEMA8Down(False)

            if self.getEMA8BBUp() == True and status_open == False and ctr > set_ctr_exec and param_up == True: 
                msg = "⬆️ [[{}]] [[WS]] [[EMA8-MIDBB-UP]] potentially BUY [[20011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setEMA8BBUp(False)

            if self.getEMA8BBDown() == True and status_open == False and ctr > set_ctr_exec and param_down == True:                
                msg = "⬇️ [[{}]] [[WS]] [[EMA8-MIDBB-DOWN]] potentially SELL [[20012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setEMA8BBDown(False)

            if self.getEMA8cross50Up() == True and status_open == False and ctr > set_ctr_exec and param_up == True: 
                msg = "⬆️ [[{}]] [[WS]] [[EMA8-50-UP]] potentially BUY [[40011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setEMA8cross50Up(False)

            if self.getEMA8cross50Down() == True and status_open == False and ctr > set_ctr_exec and param_down == True:                
                msg = "⬇️ [[{}]] [[WS]] [[EMA8-50-DOWN]] potentially SELL [[40012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                print("msg -> ",msg)
                print("msg_buy -> ", self.msg_buy)
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, 2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
                    self.setEMA8cross50Down(False)

        print("#------ condition check ------#")
        print("counter -> ", ctr)
        print("status_open position -> ", status_open)
        print("minute -> ", self.ctr_minute)
        print("ema8 cross signal ema20 (UP) -> ", ema820_cross_up)        
        print("ema8 cross signal ema20 (DOWN) -> ", ema820_cross_down)
        print("bulls_power -> ", bulls_power)
        print("bears_power -> ", bears_power)
        print("ema8 -> ", ema8)
        print("ema20 -> ", ema20)
        print("ema50 -> ", ema50)
        print("macd_value -> ", macd_value)     
        print("macd_signal -> ", macd_signal)     
        print("macd_value > macd_signal -> ", macd_value > macd_signal)     
        print("cross macd (UP) -> ", self.last_macd_signal > self.last_macd_value and macd_value > macd_signal)     
        print("cross macd (DOWN) -> ", self.last_macd_signal < self.last_macd_value and macd_value < macd_signal)     
        print("cci -> ", self.cci)
        print("boltop -> ", boltop)
        print("bolmid -> ", bolmid)
        print("boltom -> ", boltom)
        print("curr_price > curr_open : ", curr_price > curr_open)        
        print("curr_price < curr_open : ", curr_price < curr_open)        
        print("curr_price > cl1 : ", curr_price > cl1)
        print("curr_price < cl1 : ", curr_price < cl1)
        print("distance top bb 1m -> ", (boltop - curr_price) * 10**count_lencur)
        print("distance bottom bb 1m -> ", (curr_price - boltom) * 10**count_lencur)        
        print("distance_bb_1m_top > 20 -> ", distance_bb_1m_top > 20)
        print("distance_bb_1m_bottom > 20 -> ", distance_bb_1m_bottom > 20)
        print("cl1 > op1 : ", cl1 > op1)
        print("cl1 < op1 : ", cl1 < op1)
        print("self.cci > 100 or self.last_cci_c1 > 100 : ", self.cci > 100 or self.last_cci_c1 > 100)

        # fractals as support and resistance
        if len(self.val_support) >= 1 and len(self.val_resistance) >= 1:            

            '''
            print("val_support -> ", self.val_support)
            print("val_resistance -> ", self.val_resistance)
            print("cl1 > self.val_support[-1] -> ", cl1 > self.val_support[-1])
            print("cl1 < self.val_support[-1] -> ", cl1 < self.val_support[-1])
            print("cl1 > self.val_resistance[-1] -> ", cl1 > self.val_resistance[-1])
            print("cl1 < self.val_resistance[-1] -> ", cl1 < self.val_resistance[-1])
                       
            cond1 = curr_price < self.val_support[-1]
            cond2 = curr_price < self.val_resistance[-1]
            
            print("last_cond_below_support -> ", self.last_cond_below_support)
            print("last_cond_below_resistance -> ", self.last_cond_below_resistance)

            print("curr_price < val_support[-1] -> ", curr_price < self.val_support[-1])
            print("curr_price > val_support[-1] -> ", curr_price > self.val_support[-1])
            print("curr_price > val_resistance[-1] -> ", curr_price > self.val_resistance[-1])
            print("curr_price < val_resistance[-1] -> ", curr_price < self.val_resistance[-1])            

            print("len(val_support) -> ", len(self.val_support))
            print("len(val_resistance) -> ", len(self.val_resistance))
            '''
                        
            if ctr % 10 == 0:

                print("---- state support & resistance in list ----")        
                # print("self.state_val_support -> ", self.state_val_support)        
                # print("self.state_val_resistance -> ", self.state_val_resistance)  

                #'''     
                if len(self.state_val_support) > 0:
                    curr_state_support = self.state_val_support.pop(-1)
                    past_state_support = self.state_val_support[-1]
                    print("curr_state_support -> ", curr_state_support)
                    print("past_state_support -> ", past_state_support)

                    rev_up = past_state_support < curr_state_support and curr_price > curr_open and curr_price < hc1

                    # reversal kenaikan
                    if rev_up == True and status_open == False:
                        print("Price reversal to long :D but need confirmation...")
                        self.setReversalUp(True)

                if len(self.state_val_resistance) > 0:
                    curr_state_resistance = self.state_val_resistance.pop(-1)
                    past_state_resistance = self.state_val_resistance[-1]
                    print("curr_state_resistance -> ", curr_state_resistance)
                    print("past_state_resistance -> ", past_state_resistance)

                    rev_down = past_state_resistance < curr_state_resistance and curr_price < curr_open and curr_price < lc1

                    if rev_down == True and status_open == False:
                        print("Price reversal to short :D but need confirmation...")
                        self.setReversalDown(True)

                if (self.cci < -100 or self.last_cci_c1 < -100) and curr_price > self.val_support[-1] and curr_price > curr_open and curr_price > hc1 and distance_bb_1m_top > 20 and status_open == False:                    
                    print("Price CCI break closest resistance, wait for confirmation...")
                    self.setCCIUp(True)
                
                if (self.cci > 100 or self.last_cci_c1 > 100) and curr_price < self.val_resistance[-1] and curr_price < curr_open and curr_price < lc1 and distance_bb_1m_bottom > 20 and status_open == False:                    
                    print("Price break down, trying to short in top :D ")
                    self.setCCIDown(True)                    

                if len(self.val_support) > 0:
                    if cl1 > self.val_support[-1] and flo == True and curr_price > self.val_support[-1] and curr_price > curr_open and curr_price > hc1 and curr_price < boltop and distance_bb_1m_top > 20 and status_open == False:
                        self.setFractalsUp(True)

                if len(self.val_resistance) > 0:
                    if cl1 < self.val_resistance[-1] and fhi == True and curr_price < self.val_resistance[-1] and curr_price < lc1 and curr_price < curr_open and curr_price > boltom and distance_bb_1m_bottom > 20 and status_open == False:
                        self.setFractalsDown(True)


                # breakout support and resistance need confirmation to avoid false breakout
                # break resistance
                if len(self.val_resistance) > 0:
                    if cl1 > self.val_resistance[-1] and curr_price > hc1 and curr_price > curr_open and curr_price < boltop and distance_bb_1m_top > 20 and status_open == False:
                        print("Price break closest resistance almost reach breakout, wait for confirmation...")
                        self.setIsBreakout(True)


                # break support
                if len(self.val_support) > 0:
                    if cl1 < self.val_support[-1] and curr_price < lc1 and curr_price < curr_open and curr_price > boltom and distance_bb_1m_bottom > 20 and status_open == False:
                        print("Price breakdown closest resistance, wait for confirmation... ")
                        self.setIsBreakdown(True)


                if self.getReversalUp() == True and validate_reversal_up == True and status_open == False and ctr > set_ctr_exec and param_up == True:
                    msg = "⬆️ [[{}]] [[WS]] [[REVERSAL-UP]] potentially BUY [[20011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                    print("msg -> ",msg)
                    print("msg_buy -> ", self.msg_buy)
                    if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                        self.orderBuySell(4,"call",self.bid_price, 1)
                        self.telegram_bot_sendtext(msg)                    
                        self.msg_buy = msg  
                        self.lasttime = str(timesx)
                        self.state_val_support = []                        
                        self.setReversalUp(False)

                if self.getReversalDown() == True and validate_reversal_down == True and status_open == False and ctr > set_ctr_exec and param_down == True:
                    msg = "⬇️ [[{}]] [[WS]] [[REVERSAL-DOWN]] potentially SELL [[20011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                    print("msg -> ",msg)
                    print("msg_buy -> ", self.msg_buy)
                    if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                        self.orderBuySell(4,"put",self.bid_price, 1)
                        self.telegram_bot_sendtext(msg)                    
                        self.msg_buy = msg  
                        self.lasttime = str(timesx)
                        self.state_val_resistance = []
                        self.setReversalDown(False)


                if self.getCCIUp() == True:                    
                    if(self.cci < -100 or self.last_cci_c1 < -100) and curr_price > self.val_support[-1] and curr_price > curr_open and curr_price > hc1 and ctr > set_ctr_exec and param_up == True:
                        print("CCI-Up confirmed, trying to long...")
                        msg = "⬆️ [[{}]] [[WS]] [[CCI-FAST]] potentially BUY [[51011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                        print("msg -> ",msg)
                        print("msg_buy -> ", self.msg_buy)
                        if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                            self.orderBuySell(4,"call",self.bid_price, 2)
                            self.telegram_bot_sendtext(msg)                    
                            self.msg_buy = msg  
                            self.lasttime = str(timesx)
                            self.setCCIUp(False)

                if self.getCCIDown() == True:
                    if(self.cci > 100 or self.last_cci_c1 > 100) and curr_price < self.val_resistance[-1] and curr_price < curr_open and curr_price < lc1 and ctr > set_ctr_exec and param_down == True:
                        print("CCI-DOwn confirmed, trying to short...")                        
                        msg = "⬇️ [[{}]] [[WS]] [[CCI-FAST]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                        print("msg -> ",msg)
                        print("msg_buy -> ", self.msg_buy)
                        if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                            self.orderBuySell(4,"put",self.bid_price, 2)
                            self.telegram_bot_sendtext(msg)                    
                            self.msg_buy = msg  
                            self.lasttime = str(timesx) 
                            self.setCCIDown(False)   

                if self.getFractalsUp() == True:
                    if cl1 > self.val_support[-1] and flo == True and curr_price > self.val_support[-1] and curr_price > curr_open and curr_price > hc1 and curr_price < boltop and distance_bb_1m_top > 20 and status_open == False and ctr > set_ctr_exec and param_up == True:
                        print("fractals Up confirmed, trying to long...")
                        msg = "⬆️ [[{}]] [[WS]] [[PRICE]] potentially BUY [[51011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                        print("msg -> ",msg)
                        print("msg_buy -> ", self.msg_buy)
                        if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                            self.orderBuySell(4,"call",self.bid_price, 1)
                            self.telegram_bot_sendtext(msg)                    
                            self.msg_buy = msg  
                            self.lasttime = str(timesx)  
                            self.setFractalsUp(False)
                
                if self.getFractalsDown() == True:
                    if cl1 < self.val_resistance[-1] and fhi == True and curr_price < self.val_resistance[-1] and curr_price < lc1 and curr_price < curr_open and curr_price > boltom and distance_bb_1m_bottom > 20 and status_open == False and ctr > set_ctr_exec and param_down == True:
                        print("fractals Down confirmed, trying to short...")
                        msg = "⬇️ [[{}]] [[WS]] [[PRICE]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                        print("msg -> ",msg)
                        print("msg_buy -> ", self.msg_buy)
                        if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                            self.orderBuySell(4,"put",self.bid_price, 1)
                            self.telegram_bot_sendtext(msg)                    
                            self.msg_buy = msg  
                            self.lasttime = str(timesx)   
                            self.setFractalsDown(False)

                if self.getBreakout() == True:
                    if cl1 > self.val_resistance[-1] and curr_price > hc1 and curr_price > curr_open and curr_price < boltop and ctr > set_ctr_exec and param_up == True:
                        print("confirmed breakout, trying to long...")
                        msg = "⬆️ [[{}]] [[WS]] [[FRACTALS-BREAKOUT-UP]] potentially BUY [[51011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                        print("msg -> ",msg)
                        print("msg_buy -> ", self.msg_buy)
                        if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                            self.orderBuySell(4,"call",self.bid_price, 1)
                            self.telegram_bot_sendtext(msg)                    
                            self.msg_buy = msg  
                            self.lasttime = str(timesx)  
                            self.setIsBreakout(False)                  

                if self.getBreakdown() == True:
                    if cl1 < self.val_support[-1] and curr_price < lc1 and curr_price < curr_open and curr_price > boltom and ctr > set_ctr_exec and param_down == True:
                        print("confirmed breakdown, trying to short...")   
                        msg = "⬇️ [[{}]] [[WS]] [[FRACTALS-BREAKDOWN]] potentially SELL [[53011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))
                        print("msg -> ",msg)
                        print("msg_buy -> ", self.msg_buy)
                        if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                            self.orderBuySell(4,"put",self.bid_price, 1)
                            self.telegram_bot_sendtext(msg)                    
                            self.msg_buy = msg  
                            self.lasttime = str(timesx) 
                            self.setIsBreakdown(False)                                        



        is_minute_update = False

        # update data online per one-hour
        if self.ctr_minute == 60:
            self.ctr_minute = 1
            # self.tempbin = self.getOnlineData() 
            self.val_support = []
            self.val_resistance = []

        elif ctr == 0 and is_minute_update == False:
            self.ctr_minute += 1
            is_minute_update = True

    async def toDataframe(self, msg):            
        if msg['data'][0]['assets']:
            timex = int(msg["data"][0]["assets"][0]["created_at"].split(":")[-1].split(".")[0])
            data = msg["data"][0]["assets"][0]
            strdate = data['created_at']
            ctgl = dateutil.parser.parse(strdate)
            utc_time = calendar.timegm(ctgl.utctimetuple())
            udate = datetime.utcfromtimestamp(utc_time).strftime('%Y-%m-%d %H:%M:%S')
            data["Datetime"] = udate        
            data["spread"] = (data["ask"] - data["bid"]) * (10**8)
            djs = pd.DataFrame(data, columns=['Datetime','precision','repeat','rate','ask','bid','created_at', 'spread'], index=[0]).rename_axis(columns='Datetime')        
            if self.df.empty:
                self.df = pd.concat([djs], ignore_index=True)
            else:
                self.df = pd.concat([self.df,djs], ignore_index=True)

            await self.createDataframe(self.df)

    async def connect(self):        
        payload = '{"action":"subscribe","rics":["'+self.assetRic+'"]}'        
        async with self as websocket:        
            await websocket.send(payload)
            while True:                        
                print("> {}".format(payload))
                try:
                    recvv = await asyncio.wait_for(websocket.recv(), timeout=60)
                    # print("> {}".format(recvv))
                    rett = json.loads(recvv)                
                    if rett['data'][0]['action'] == 'assets':
                        await self.toDataframe(rett)
                    else:
                        print("{}".format(rett)) 
                except asyncio.exceptions.CancelledError as e:
                    print(e)
                    websocket = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
                    await websocket.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')        
                    continue
                except websockets.exceptions.ConnectionClosedError as e:
                    websocket = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
                    await websocket.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')        
                    continue
                except asyncio.CancelledError as e:
                    websocket = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
                    await websocket.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')        
                    continue
                    #pass 

    def telegram_bot_sendtext(self,bot_message):    
        send_text = 'https://api.telegram.org/bot' + self.botToken + '/sendMessage?chat_id=' + self.gchatId + '&parse_mode=Markdown&text=' + bot_message
        response = requests.get(send_text)
        return response.json()    

    def get_asset(self):
        with open("asset.json","r") as f:assetList=json.loads(f.read())
        with open("setting.json","r") as f:settings=json.loads(f.read())
        currency = settings["currency"]
        for i in assetList:
            if i["name"] == currency:assetId=i["id"]; assetRic=i["ric"]

        authToken = settings["authToken"]
        walletType = settings["walletType"]
        deviceId = settings["deviceId"]
        tournament_id = settings["tournament_id"]

        return {"assetId": assetId, "assetRic": assetRic, "currency":currency, "authToken": authToken, "deviceId": deviceId, "tournament_id": tournament_id, "walletType": walletType}

    def getOnlineData(self):
        binomodata = Ticker()
        #binomodata = DataHistory()
        data = binomodata.getData()
        if len(data["d1"]) > 0:
            return data
        

    def orderBuySell(self, typeorder, call_put, amnt=15000, duration=1):
        try:
            self.pb.bid(typeorder, call_put, amnt, duration)
        except Exception as e:
            print(e)
        finally:
            pass

        balance = self.pb.getCurrentBalance()
        print("orderBuySell balance -> ", balance)
        self.setBalance(balance)

    def countOpenPosition(self):
        op = self.pb.openPosition()
        if op.empty:            
            return False
        else:
            result = op.query('close_rate == 0')             
            return True if len(result.index) > 0 else False

        #return len(op.index)

    def setBalance(self,lbalance):
        self.latest_balance = lbalance
        
    def getBalance(self):
        return self.latest_balance

    def setIsBreakout(self,is_breakout):
        self.is_breakout = is_breakout
        
    def getBreakout(self):
        return self.is_breakout

    def setIsBreakdown(self,is_breakdown):
        self.is_breakdown = is_breakdown
        
    def getBreakdown(self):
        return self.is_breakdown

    def setCCIUp(self,cci_up):
        self.cci_up = cci_up
        
    def getCCIUp(self):
        return self.cci_up

    def setCCIDown(self,cci_down):
        self.cci_down = cci_down
        
    def getCCIDown(self):
        return self.cci_down

    def setEMA8UP(self,is_ema8_up):
        self.is_ema8_up = is_ema8_up
        
    def getEMA8Up(self):
        return self.is_ema8_up

    def setEMA8Down(self,is_ema8_down):
        self.is_ema8_down = is_ema8_down
        
    def getEMA8Down(self):
        return self.is_ema8_down

    def setFractalsUp(self,is_fractal_up):
        self.is_fractal_up = is_fractal_up
        
    def getFractalsUp(self):
        return self.is_fractal_up

    def setFractalsDown(self,is_fractal_down):
        self.is_fractal_down = is_fractal_down
        
    def getFractalsDown(self):
        return self.is_fractal_down

    def setMACDUp(self,is_macd_up):
        self.is_macd_up = is_macd_up
        
    def getMACDUp(self):
        return self.is_macd_up

    def setMACDdown(self,is_macd_down):
        self.is_macd_down = is_macd_down
        
    def getMACDdown(self):
        return self.is_macd_down

    def setReversalUp(self,is_reversal_up):
        self.is_reversal_up = is_reversal_up
        
    def getReversalUp(self):
        return self.is_reversal_up

    def setReversalDown(self,is_reversal_down):
        self.is_reversal_down = is_reversal_down
        
    def getReversalDown(self):
        return self.is_reversal_down

    def setLastBelowSupport(self, cond):
        self.last_cond_below_support = cond

    def getLastBelowSupport(self):
        return self.last_cond_below_support

    def getLastBelowResistance(self):
        return self.last_cond_below_resistance

    def setLastBelowResistance(self, cond):
        self.last_cond_below_resistance = cond

    def setEMA8BBUp(self, ema8midbb_up):
        self.ema8midbb_up = ema8midbb_up

    def getEMA8BBUp(self):
        return self.ema8midbb_up

    def setEMA8BBDown(self,ema8midbb_down):
        self.ema8midbb_down = ema8midbb_down

    def getEMA8BBDown(self):
        return self.ema8midbb_down

    def setEMA8cross50Up(self, is_ema8_cross50_up):
        self.is_ema8_cross50_up = is_ema8_cross50_up

    def getEMA8cross50Up(self):
        return self.is_ema8_cross50_up

    def setEMA8cross50Down(self, is_ema8_cross50_down):
        self.is_ema8_cross50_down = is_ema8_cross50_down

    def getEMA8cross50Down(self):
        return self.is_ema8_cross50_down


if __name__ == '__main__':
    bit = Binongtot()
    asyncio.run(bit.connect())        
