//+------------------------------------------------------------------+
//|                           GoldTradingEA.mq5                       |
//|                        Telegram-Controlled Gold EA               |
//+------------------------------------------------------------------+
#property copyright "MonkeyCode-AI"
#property version   "1.00"
#property strict

// 输入参数
input string   InpServerURL        = "http://your-domain.com/api";  // 远程控制服务器URL
input int      InpMagicNumber      = 234000;                          // EA幻数
input double   InpLotSize          = 0.01;                           // 交易手数
input int      InpStopLoss         = 2000;                           // 止损 (点数)
input int      InpTakeProfit       = 4000;                           // 止盈 (点数)
input int      InpMaxPositions     = 3;                              // 最大持仓数
input int      InpSlippage         = 20;                             // 滑点
input int      InpTrailingStart    = 500;                            // 移动止损启动点数
input int      InpTrailingStep     = 200;                            // 移动止损步长
input bool     InpEnableAutoTrade  = true;                           // 启用自动交易
input int      InpCheckInterval    = 60;                             // 检查间隔 (秒)

// 全局变量
string   g_serverURL;
datetime g_lastCheckTime;
int      g_httpTimeout = 5000;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    g_serverURL = InpServerURL;
    g_lastCheckTime = 0;

    // 设置EA幻数
    Comment("GoldTradingEA v1.0\n", "Magic: ", InpMagicNumber);

    Print("EA初始化成功 - Magic: ", InpMagicNumber);
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Comment("");
    Print("EA已停止运行");
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
    // 检查是否有新K线
    if(!IsNewBar())
        return;

    // 定期检查远程命令
    if(TimeCurrent() - g_lastCheckTime >= InpCheckInterval)
    {
        CheckRemoteCommands();
        g_lastCheckTime = TimeCurrent();
    }

    // 如果启用自动交易，执行交易逻辑
    if(InpEnableAutoTrade)
    {
        ExecuteAutoTrade();
    }

    // 执行移动止损
    ManageTrailingStop();
}

//+------------------------------------------------------------------+
//| 检查是否有新K线                                                    |
//+------------------------------------------------------------------+
bool IsNewBar()
{
    static datetime lastBarTime = 0;
    datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
    if(currentBarTime != lastBarTime)
    {
        lastBarTime = currentBarTime;
        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| 检查远程命令                                                        |
//+------------------------------------------------------------------+
void CheckRemoteCommands()
{
    string command = GetRemoteCommand();

    if(command == "")
        return;

    Print("收到远程命令: ", command);

    // 解析命令
    if(StringFind(command, "BUY:") == 0)
    {
        double lot = StringToDouble(StringSubstr(command, 4));
        ExecuteTrade(ORDER_TYPE_BUY, lot);
    }
    else if(StringFind(command, "SELL:") == 0)
    {
        double lot = StringToDouble(StringSubstr(command, 5));
        ExecuteTrade(ORDER_TYPE_SELL, lot);
    }
    else if(command == "CLOSE_ALL")
    {
        CloseAllPositions();
    }
    else if(command == "CLOSE_PROFIT")
    {
        CloseProfitablePositions();
    }
    else if(StringFind(command, "SET_LOT:") == 0)
    {
        InpLotSize = StringToDouble(StringSubstr(command, 8));
        Print("手数已更新: ", InpLotSize);
    }
    else if(StringFind(command, "SET_SL:") == 0)
    {
        InpStopLoss = (int)StringToInteger(StringSubstr(command, 7));
        Print("止损已更新: ", InpStopLoss);
    }
    else if(StringFind(command, "SET_TP:") == 0)
    {
        InpTakeProfit = (int)StringToInteger(StringSubstr(command, 7));
        Print("止盈已更新: ", InpTakeProfit);
    }
    else if(command == "ENABLE_AUTO")
    {
        InpEnableAutoTrade = true;
        Print("自动交易已启用");
    }
    else if(command == "DISABLE_AUTO")
    {
        InpEnableAutoTrade = false;
        Print("自动交易已禁用");
    }
}

//+------------------------------------------------------------------+
//| 从远程服务器获取命令                                                |
//+------------------------------------------------------------------+
string GetRemoteCommand()
{
    char data[];
    char result[];
    string resultStr = "";
    string requestHeaders = "Content-Type: application/json\r\n";

    string url = g_serverURL + "/command?symbol=" + _Symbol + "&magic=" + IntegerToString(InpMagicNumber);

    int timeout = g_httpTimeout;
    int res = WebRequest("GET", url, requestHeaders, timeout, data, result, resultStr);

    if(res == -1)
    {
        int errorCode = GetLastError();
        Print("WebRequest错误: ", errorCode, " - ", ErrorDescription(errorCode));
        return "";
    }

    return resultStr;
}

//+------------------------------------------------------------------+
//| 发送状态到远程服务器                                                |
//+------------------------------------------------------------------+
void SendStatus()
{
    string status = BuildStatusJSON();

    char data[];
    char result[];
    string resultStr;
    string requestHeaders = "Content-Type: application/json\r\n";

    StringToCharArray(status, data, 0, WHOLE_ARRAY, CP_UTF8);
    ArrayResize(data, ArraySize(data) - 1);

    string url = g_serverURL + "/status";
    int timeout = g_httpTimeout;

    WebRequest("POST", url, requestHeaders, timeout, data, result, resultStr);
}

//+------------------------------------------------------------------+
//| 构建状态JSON                                                       |
//+------------------------------------------------------------------+
string BuildStatusJSON()
{
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double margin = AccountInfoDouble(ACCOUNT_MARGIN);
    double profit = AccountInfoDouble(ACCOUNT_PROFIT);

    int totalPositions = PositionsTotal();

    string json = "{";
    json += "\"symbol\":\"" + _Symbol + "\",";
    json += "\"magic\":" + IntegerToString(InpMagicNumber) + ",";
    json += "\"balance\":" + DoubleToString(balance, 2) + ",";
    json += "\"equity\":" + DoubleToString(equity, 2) + ",";
    json += "\"margin\":" + DoubleToString(margin, 2) + ",";
    json += "\"profit\":" + DoubleToString(profit, 2) + ",";
    json += "\"positions\":" + IntegerToString(totalPositions) + ",";
    json += "\"time\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES) + "\"";
    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| 执行交易                                                           |
//+------------------------------------------------------------------+
bool ExecuteTrade(ENUM_ORDER_TYPE orderType, double lotSize = 0)
{
    if(lotSize <= 0)
        lotSize = InpLotSize;

    // 检查持仓数量
    if(CountPositions() >= InpMaxPositions)
    {
        Print("已达到最大持仓数");
        return false;
    }

    // 获取价格
    double price, sl, tp;
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

    if(orderType == ORDER_TYPE_BUY)
    {
        price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        sl = price - InpStopLoss * point;
        tp = price + InpTakeProfit * point;
    }
    else
    {
        price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        sl = price + InpStopLoss * point;
        tp = price - InpTakeProfit * point;
    }

    // 规范化价格
    price = NormalizeDouble(price, _Digits);
    sl = NormalizeDouble(sl, _Digits);
    tp = NormalizeDouble(tp, _Digits);

    // 创建交易请求
    MqlTradeRequest request = {};
    MqlTradeResult result = {};

    request.action = TRADE_ACTION_DEAL;
    request.symbol = _Symbol;
    request.volume = lotSize;
    request.type = orderType;
    request.price = price;
    request.sl = sl;
    request.tp = tp;
    request.deviation = InpSlippage;
    request.magic = InpMagicNumber;
    request.comment = "Telegram EA";

    // 发送订单
    if(!OrderSend(request, result))
    {
        Print("订单失败: ", result.comment);
        return false;
    }

    Print("订单执行成功 - Ticket: ", result.order);
    return true;
}

//+------------------------------------------------------------------+
//| 计算持仓数量                                                       |
//+------------------------------------------------------------------+
int CountPositions()
{
    int count = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionGetSymbol(i) == _Symbol)
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            {
                count++;
            }
        }
    }
    return count;
}

//+------------------------------------------------------------------+
//| 平所有仓                                                           |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionGetSymbol(i) == _Symbol)
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            {
                ClosePosition(i);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 平盈利持仓                                                         |
//+------------------------------------------------------------------+
void CloseProfitablePositions()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionGetSymbol(i) == _Symbol)
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            {
                double profit = PositionGetDouble(POSITION_PROFIT);
                if(profit > 0)
                {
                    ClosePosition(i);
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 平指定持仓                                                         |
//+------------------------------------------------------------------+
void ClosePosition(int index)
{
    ulong ticket = PositionGetTicket(index);
    if(ticket == 0)
        return;

    ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
    double volume = PositionGetDouble(POSITION_VOLUME);
    string symbol = PositionGetString(POSITION_SYMBOL);

    MqlTradeRequest request = {};
    MqlTradeResult result = {};

    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.position = ticket;
    request.volume = volume;

    if(posType == POSITION_TYPE_BUY)
    {
        request.type = ORDER_TYPE_SELL;
        request.price = SymbolInfoDouble(symbol, SYMBOL_BID);
    }
    else
    {
        request.type = ORDER_TYPE_BUY;
        request.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
    }

    request.deviation = InpSlippage;
    request.magic = InpMagicNumber;

    if(!OrderSend(request, result))
    {
        Print("平仓失败: ", result.comment);
    }
}

//+------------------------------------------------------------------+
//| 移动止损管理                                                       |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionGetSymbol(i) == _Symbol)
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            {
                TrailingStop(i);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 执行移动止损                                                       |
//+------------------------------------------------------------------+
void TrailingStop(int index)
{
    ulong ticket = PositionGetTicket(index);
    if(ticket == 0)
        return;

    double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
    double currentSL = PositionGetDouble(POSITION_SL);
    double currentTP = PositionGetDouble(POSITION_TP);
    double profit = PositionGetDouble(POSITION_PROFIT);
    ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

    double newSL = 0;
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

    if(posType == POSITION_TYPE_BUY)
    {
        double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        if(currentPrice - openPrice > InpTrailingStart * point)
        {
            newSL = currentPrice - InpTrailingStep * point;
            if(newSL > currentSL + point)
            {
                ModifyPosition(ticket, newSL, currentTP);
            }
        }
    }
    else
    {
        double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        if(openPrice - currentPrice > InpTrailingStart * point)
        {
            newSL = currentPrice + InpTrailingStep * point;
            if(newSL < currentSL - point || currentSL == 0)
            {
                ModifyPosition(ticket, newSL, currentTP);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 修改持仓止损止盈                                                   |
//+------------------------------------------------------------------+
void ModifyPosition(ulong ticket, double sl, double tp)
{
    MqlTradeRequest request = {};
    MqlTradeResult result = {};

    request.action = TRADE_ACTION_SLTP;
    request.position = ticket;
    request.symbol = _Symbol;
    request.sl = NormalizeDouble(sl, _Digits);
    request.tp = NormalizeDouble(tp, _Digits);

    if(!OrderSend(request, result))
    {
        Print("修改止损失败: ", result.comment);
    }
}

//+------------------------------------------------------------------+
//| 自动交易策略                                                       |
//+------------------------------------------------------------------+
void ExecuteAutoTrade()
{
    // 简单策略: 基于RSI和移动平均线
    double rsi = iRSI(_Symbol, PERIOD_CURRENT, 14, PRICE_CLOSE, 1);
    double maFast = iMA(_Symbol, PERIOD_CURRENT, 10, 0, MODE_SMA, PRICE_CLOSE, 1);
    double maSlow = iMA(_Symbol, PERIOD_CURRENT, 20, 0, MODE_SMA, PRICE_CLOSE, 1);
    double atr = iATR(_Symbol, PERIOD_CURRENT, 14, 1);

    // 买入信号
    if(rsi < 30 && maFast > maSlow && CountPositions(POSITION_TYPE_BUY) == 0)
    {
        if(ExecuteTrade(ORDER_TYPE_BUY))
        {
            Print("自动买入信号触发 - RSI: ", rsi);
        }
    }

    // 卖出信号
    if(rsi > 70 && maFast < maSlow && CountPositions(POSITION_TYPE_SELL) == 0)
    {
        if(ExecuteTrade(ORDER_TYPE_SELL))
        {
            Print("自动卖出信号触发 - RSI: ", rsi);
        }
    }
}

//+------------------------------------------------------------------+
//| 计算特定方向的持仓数量                                             |
//+------------------------------------------------------------------+
int CountPositions(ENUM_POSITION_TYPE posType)
{
    int count = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionGetSymbol(i) == _Symbol)
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
               PositionGetInteger(POSITION_TYPE) == posType)
            {
                count++;
            }
        }
    }
    return count;
}

//+------------------------------------------------------------------+
//| 获取错误描述                                                       |
//+------------------------------------------------------------------+
string ErrorDescription(int errorCode)
{
    switch(errorCode)
    {
        case 0:   return "无错误";
        case 1:   return "无错误，但结果未知";
        case 2:   return "常规错误";
        case 3:   return "错误参数";
        case 4:   return "交易服务器繁忙";
        case 5:   return "旧版本终端";
        case 6:   return "没有连接";
        case 7:   return "没有权限";
        case 8:   return "请求太频繁";
        case 9:   return "不允许操作";
        case 64:  return "账户被禁用";
        case 65:  return "账户不正确";
        case 128: return "交易超时";
        case 129: return "错误价格";
        case 130: return "错误止损";
        case 131: return "错误交易量";
        case 132: return "市场已关闭";
        case 133: return "交易被禁止";
        case 134: return "资金不足";
        case 135: return "价格改变";
        case 136: return "没有价格";
        case 137: return "经纪商繁忙";
        case 138: return "重新报价";
        case 139: return "订单被锁定";
        case 140: return "只允许多头";
        case 141: return "请求太多";
        case 145: return "修改被禁止";
        case 146: return "交易子系统忙";
        case 147: return "使用过期";
        case 148: return "打开的订单太多";
        case 149: return "对冲被禁止";
        case 150: return "禁止由FIFO规则";
        default:  return "未知错误";
    }
}
//+------------------------------------------------------------------+
