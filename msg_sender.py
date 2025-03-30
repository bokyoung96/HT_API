import requests
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import io

from event_fetcher import EventFetcher


class MsgSender:
    def __init__(self, config_path: str = 'msg_bot.json'):
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.token = config['TELEGRAM_BOT_TOKEN']
        self.chat_id = config['CHAT_ID']
        self.chat_room_id = config['CHAT_ROOM_ID']

    def send_msg(self, msg: str, to_chat_room: bool = False):
        chat_id = self.chat_room_id if to_chat_room else self.chat_id
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        data = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML"
        }

        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise Exception(
                f"Failed to send telegram message: {response.status_code} | {response.text}")

    def send_file(self, df: pd.DataFrame, filename: str, to_chat_room: bool = False):
        chat_id = self.chat_room_id if to_chat_room else self.chat_id
        url = f"https://api.telegram.org/bot{self.token}/sendDocument"

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        files = {
            'document': (filename, buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        }
        data = {
            'chat_id': chat_id
        }

        response = requests.post(url, data=data, files=files)
        if response.status_code != 200:
            raise Exception(
                f"Failed to send file: {response.status_code} | {response.text}")


class EventNotifier:
    def __init__(self, top_n: int = 5):
        self.fetcher = EventFetcher.get_auth()
        self.sender = MsgSender()
        self.top_n = top_n

    def _format_ipo_message(self, ipo_data: pd.DataFrame) -> str:
        msg = f"🔔 신규 공모주 청약 정보 (최근 {self.top_n}건)\n\n"
        for _, row in ipo_data.iterrows():
            msg += f"📅 청약일: {row['record_date'].strftime('%Y-%m-%d')}\n"
            msg += f"🏢 종목명: {row['isin_name']}\n"
            msg += f"💰 공모가: {int(row['fix_subscr_pri']):,}원\n"
            msg += f"📊 청약일: {row['subscr_dt']}\n"
            msg += f"📝 상장일: {row['list_dt']}\n\n"
        return msg

    def _format_dividend_message(self, div_data: pd.DataFrame) -> str:
        msg = f"💰 배당 정보 (상위 {self.top_n}건)\n\n"
        for _, row in div_data.iterrows():
            msg += f"📅 배당기준일: {row['record_date'].strftime('%Y-%m-%d')}\n"
            msg += f"🏢 종목명: {row['isin_name']}\n"
            msg += f"💵 주당배당금: {int(row['per_sto_divi_amt']):,}원\n\n"
        return msg

    def _format_short_sell_message(self, short_sell_data: pd.DataFrame) -> str:
        msg = f"💰 최근 주식 매도 랭킹 (상위 {self.top_n}건)\n\n"
        for _, row in short_sell_data.iterrows():
            msg += f"🔢 종목코드: {row['mksc_shrn_iscd']}\n"
            msg += f"🏢 종목명: {row['hts_kor_isnm']}\n"
            msg += f"📈 가격등락률: {row['prdy_ctrt']}%\n"
            msg += f"📊 누적거래량: {int(row['acml_vol']):,}주\n"
            msg += f"💰 공매도거래대금: {int(row['ssts_tr_pbmn']):,}원\n"
            msg += f"📊 공매도거래대금비중: {row['ssts_tr_pbmn_rlim']}%\n\n"
        return msg

    def notify_ipo(self, to_chat_room: bool = True):
        f_dt = datetime.now().replace(month=1, day=1).strftime("%Y%m%d")
        t_dt = (datetime.now().replace(day=1) +
                relativedelta(months=2) - timedelta(days=1)).strftime("%Y%m%d")
        ipo_res = pd.DataFrame(self.fetcher.get_ipo_list(None, f_dt, t_dt))

        if not ipo_res.empty:
            ipo_res['record_date'] = pd.to_datetime(
                ipo_res['record_date'], format='%Y%m%d')
            ipo_res = ipo_res.sort_values('record_date', ascending=False)
            ipo_summary = ipo_res.head(self.top_n)

            ipo_msg = self._format_ipo_message(ipo_summary)
            self.sender.send_msg(ipo_msg, to_chat_room=to_chat_room)
            self.sender.send_file(
                ipo_res, f"ipo_list_{datetime.now().strftime('%Y%m%d')}.xlsx", to_chat_room=to_chat_room)

    def notify_dividend(self, to_chat_room: bool = True):
        f_dt = datetime.now().replace(day=1).strftime("%Y%m%d")
        t_dt = (datetime.now().replace(day=1) +
                relativedelta(months=1) - timedelta(days=1)).strftime("%Y%m%d")
        div_res = pd.DataFrame(self.fetcher.get_dividend_rank(
            div_type=2, f_dt=f_dt, t_dt=t_dt))

        if not div_res.empty:
            div_res['record_date'] = pd.to_datetime(
                div_res['record_date'], format='%Y%m%d')
            div_res = div_res.sort_values('record_date', ascending=False)
            div_summary = div_res.head(self.top_n)

            div_msg = self._format_dividend_message(div_summary)
            self.sender.send_msg(div_msg, to_chat_room=to_chat_room)
            self.sender.send_file(
                div_res, f"dividend_list_{datetime.now().strftime('%Y%m%d')}.xlsx", to_chat_room=to_chat_room)

    def notify_short_sell(self, to_chat_room: bool = True):
        short_sell_res = pd.DataFrame(self.fetcher.get_short_sell_rank())

        if not short_sell_res.empty:
            short_sell_res['ssts_tr_pbmn_rlim'] = short_sell_res['ssts_tr_pbmn_rlim'].astype(
                float)
            short_sell_res = short_sell_res.sort_values(
                'ssts_tr_pbmn_rlim', ascending=False)
            short_sell_summary = short_sell_res.head(self.top_n)

            short_sell_msg = self._format_short_sell_message(
                short_sell_summary)
            self.sender.send_msg(short_sell_msg, to_chat_room=to_chat_room)
            self.sender.send_file(
                short_sell_res, f"short_sell_list_{datetime.now().strftime('%Y%m%d')}.xlsx", to_chat_room=to_chat_room)

    def notify_all(self, to_chat_room: bool = True):
        self.notify_ipo(to_chat_room)
        self.notify_dividend(to_chat_room)
        self.notify_short_sell(to_chat_room)


if __name__ == "__main__":
    notifier = EventNotifier(top_n=10)
    notifier.notify_all()
