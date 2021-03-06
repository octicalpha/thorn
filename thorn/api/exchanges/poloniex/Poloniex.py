import time
import datetime
import json

import requests

from thorn.api.exchanges import PublicExchange
from thorn.api.exchanges import Websocket
from thorn.api.exchanges.poloniex import config

class PoloniexPublic(PublicExchange):
    '''Public API class for Poloniex. Extends `PublicExchange`'''

    def __init__(self):
        base = config.API_CONFIG['base']
        super(PoloniexPublic, self).__init__(base=base)

    def send_check(self,payload={}):
        r = self.get(payload=payload)
        if 'error' in r:
            print('Error in send_check: ', r)
            return None
        return r

    def return_ticker(self):
        payload = {'command': 'returnTicker'}
        return self.send_check(payload=payload)

    def return_24_volume(self):
        payload = {'command': 'return24hVolume'}
        return self.send_check(payload=payload)

    def return_order_book(self, pair='BTC_NXT', all_orders=False, depth=10):
        if all_orders:
            payload = {'command': 'returnOrderBook',
                        'currencyPair':'all',
                        'depth': depth}
            return self.send_check(payload=payload)
        elif pair is not None:
            payload = {'command': 'returnOrderBook',
                        'currencyPair':pair,
                        'depth': depth}
            return self.send_check(payload=payload)
        else:
            print('Invalid parameters in return_order_book')

    def return_trade_history(self, start, end, pair='BTC_NXT'):
        start, end = self.check_and_reformat_datetime(start, end)
        if isinstance(start, float) and isinstance(end, float):
            payload = {'command': 'returnTradeHistory',
                        'start': start,
                        'end': end,
                        'currencyPair': pair}
            return self.send_check(payload=payload)
        else:
            raise TypeError('Invalid date structure in return_trade_history')
            return None

    def return_chart_data(self, start, end, period=14400, pair='BTC_NXT'):
        start, end = self.check_and_reformat_datetime(start, end)
        if period not in config.API_CONFIG['valid_periods']:
            raise Exception('Invalid period choice for API')
            return None
        else:
            if isinstance(start, float) and isinstance(end, float):
                payload = {'command': 'returnTradeHistory',
                            'start': start,
                            'end': end,
                            'period': period,
                            'currencyPair': pair}
                return self.send_check(payload=payload)
            else:
                raise TypeError('Invalid date structure in return_trade_history')
                return None

    def return_currencies(self):
        payload={'command': 'returnCurrencies'}
        return self.send_check(payload=payload)

    def return_loan_orders(self, currency='BTC'):
        payload = {'command': 'returnLoanOrders',
                    'currency': currency}
        return self.send_check(payload=payload)


class PoloniexSocket(Websocket):

    def __init__(self, stream, symbol, on_message=None):
        self.valid_streams = config.WEBSOCKET_CONFIG['valid_streams']
        if stream not in self.valid_streams:
            raise AttributeError('stream {} not a valid stream'.format(stream))
        self.base = config.WEBSOCKET_CONFIG['base']
        self.url = self.base
        self.symbol = symbol
        self.wrap_on_message = on_message
        om = self.choose_stream_function(stream)
        super(PoloniexSocket, self).__init__(self.url, on_message = om,
                                            on_error = self.on_error,
                                            on_open = self.on_open,
                                            on_close = self.on_close)

    def on_message_depth(self, ws, message):
        m = json.loads(message)
        if self.wrap_on_message is not None:
            self.wrap_on_message(ws, m)
        else:
            return self.translate_order_book_l2(m)

    def choose_stream_function(self, stream):
        if stream == 'depth':
            return self.on_message_depth

    def translate_depth(self, message):
        ret = []
        header = {}
        header['exchange'] = 'poloniex'
        header['stream'] = 'depth_update'
        try:
            header['pair'] = self.symbol
            header['timestamp'] = self.generate_timestamp()
            data = message['data']
            action = message['action']
        except KeyError:
            print('Unexpected stream format in translate_order_book_l2:', message)
            return ret
        if action == 'update':
            for d in data:
                r = {}
                r['price_id'] = d['id']
                r['quantity'] = d['size']
                r['side'] = d['side'].lower()
                ret.append({**header, **r})
            return ret
        if action == 'insert':
            for d in data:
                r = {}
                r['price_id'] = d['id']
                r['price'] = d['price']
                r['quantity'] = d['size']
                r['side'] = d['side'].lower()
                ret.append({**header, **r})
            return ret
        if action == 'delete':
            for d in data:
                r = {}
                r['price_id'] = d['id']
                r['side'] = d['side'].lower()
                r['quantity'] = 0
                ret.append({**header, **r})
            return ret

    def on_error(self, ws, error):
        print('Error in PoloniexSocket: ', error)

    def on_open(self, ws):
        payload = {'command':'subscribe', 'channel': str(self.symbol)}
        ws.send(json.dumps(payload))
        print('PoloniexSocket: opened')

    def on_close(self, ws):
        print('PoloniexSocket: closed')
