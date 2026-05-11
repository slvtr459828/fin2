# VNStock Data — API Reference Toàn Diện

> `vnstock_data` v3.0+ — Unified UI cho dữ liệu chứng khoán, kinh tế, tài sản Việt Nam & quốc tế.
> Kiến trúc 3 lớp: Unified UI → Core Adapter → Module Nguồn cấp.
> Tài liệu gốc: [vnstocks.com/docs](https://vnstocks.com/docs/vnstock-data/kien-truc-thu-vien)

---

## Mục lục

1. [Cài đặt & Import](#1-cài-đặt--import)
2. [Reference Layer — Dữ liệu tham chiếu](#2-reference-layer)
3. [Market Layer — Dữ liệu giao dịch](#3-market-layer)
4. [Fundamental Layer — Dữ liệu cơ bản](#4-fundamental-layer)
5. [Macro Layer — Dữ liệu vĩ mô & hàng hóa](#5-macro-layer)
6. [Insights Layer — Phân tích chuyên sâu](#6-insights-layer)
7. [Analytics Layer — Thống kê & định giá](#7-analytics-layer)
8. [Tiện ích: show_api() & show_doc()](#8-tiện-ích)
9. [Tổng quan nguồn dữ liệu](#9-tổng-quan-nguồn-dữ-liệu)
10. [Bảng tra nhanh theo use case](#10-bảng-tra-nhanh-theo-use-case)

---

## 1. Cài đặt & Import

```python
# Unified UI — khuyên dùng
from vnstock_data import (
    Market,        # Dữ liệu giao dịch (OHLCV, quote, order book...)
    Reference,     # Dữ liệu tham chiếu (danh sách mã, công ty, chỉ số...)
    Fundamental,   # Báo cáo tài chính, chỉ số tài chính
    Macro,         # Vĩ mô, tỷ giá, hàng hóa
    Insights,      # Xếp hạng, bộ lọc chứng khoán
    Analytics,     # Định giá P/E, P/B toàn thị trường
    show_api,      # Hiển thị cây API
    show_doc,      # Đọc docstring
)
```

---

## 2. Reference Layer

**Vai trò**: Tra cứu dữ liệu tham chiếu tĩnh — danh sách mã, thông tin công ty, chỉ số, ngành, ETF, trái phiếu, sự kiện. Dùng cho lookup và master data.

**Khởi tạo**:
```python
from vnstock_data import Reference
ref = Reference()
```

### 2.1 Công ty — `ref.company(symbol)`

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.info()` | Thông tin tổng quan công ty | VCI |
| `.shareholders()` | Danh sách cổ đông chính | VCI |
| `.officers()` | Ban lãnh đạo | VCI |
| `.subsidiaries()` | Công ty con | VCI |
| `.news()` | Tin tức công ty | VCI |
| `.events()` | Sự kiện công ty | VCI |
| `.margin_ratio()` | Tỷ lệ ký quỹ qua các CTCK | KBS |

```python
ref.company("TCB").info()
ref.company("VIC").shareholders()
ref.company("HPG").officers()
ref.company("TCB").margin_ratio()
```

### 2.2 Danh sách cổ phiếu — `ref.equity`

| Hàm | Tham số | Mô tả | Nguồn |
|---|---|---|---|
| `.list()` | — | Toàn bộ 1700+ mã | VCI |
| `.list_by_group(group)` | `"VN30"`, `"VN100"`, `"HOSE"`... | Lọc theo nhóm chỉ số | — |
| `.list_by_exchange()` | — | Phân loại theo sàn | — |
| `.list_by_industry()` | — | Phân loại theo ngành ICB | — |

```python
all_stocks = ref.equity.list()
vn30 = ref.equity.list_by_group("VN30")
vn100 = ref.equity.list_by_group("VN100")
```

### 2.3 Chỉ số — `ref.index`

| Hàm | Tham số | Mô tả | Nguồn |
|---|---|---|---|
| `.list()` | — | Toàn bộ chỉ số | KBS |
| `.groups()` | — | Nhóm chỉ số | KBS |
| `.members(group)` | `"VN30"`... | Thành phần của chỉ số | KBS |
| `.list_by_group(group)` | — | Chỉ số theo nhóm | — |

```python
all_indices = ref.index.list()
vn30_members = ref.index.members("VN30")
vn30_info = ref.index("VN30").info()
```

### 2.4 Ngành — `ref.industry`

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.list()` | Danh sách ngành ICB | VCI |
| `.sectors()` | Cổ phiếu theo ngành | VCI |

### 2.5 Quỹ, ETF, Trái phiếu, Sự kiện

```python
ref.fund.list()                                     # Quỹ đầu tư mở [FMARKET]
ref.etf.list()                                      # ETF [KBS]
ref.bond.list(bond_type="all")                      # Trái phiếu (all/corporate/government)
ref.bond.list(bond_type="corporate")                # Chỉ trái phiếu doanh nghiệp
ref.events.calendar(start="2026-03-01", end="2026-03-31")  # Lịch sự kiện [VCI]
ref.events.calendar(start="2026-03-01", end="2026-03-31", event_type="dividend")
ref.events.market()                                 # Sự kiện đặc biệt thị trường
```

### 2.6 Tìm kiếm — `ref.search`

```python
ref.search.symbol("VNM")                    # Tìm mã chứng khoán [MSN]
ref.search.symbol("Bitcoin", limit=5)       # Tìm crypto quốc tế
ref.search.symbol("Gold", locale="en-us")   # Tìm hàng hóa quốc tế
```

### 2.7 Hợp đồng tương lai & Chứng quyền

```python
ref.futures().list()              # Danh sách HĐTL
ref.futures("VN30F2503").info()   # Chi tiết 1 mã [KBS]
ref.warrant().list()              # Danh sách chứng quyền
ref.warrant("CACB2511").info()    # Chi tiết 1 mã [KBS]
```

---

## 3. Market Layer

**Vai trò**: Dữ liệu giao dịch realtime & lịch sử — OHLCV, bảng giá, order book, dòng tiền, giao dịch thỏa thuận. Dùng cho trading, phân tích kỹ thuật, theo dõi danh mục.

**Khởi tạo**:
```python
from vnstock_data import Market
mkt = Market()
```

### 3.1 Cổ phiếu — `mkt.equity(symbol)`

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.ohlcv(start, end)` | Giá OHLCV lịch sử | KBS |
| `.quote()` | Giá hiện tại | KBS |
| `.trades()` | Lệnh giao dịch chi tiết (Time & Sales) | KBS |
| `.order_book()` | Cấp độ mua/bán (Bid/Ask L2/L3) | KBS |
| `.session_stats()` | Thống kê phiên giao dịch | VCI |
| `.foreign_flow()` | Dòng tiền nước ngoài | VCI |
| `.proprietary_flow()` | Dòng tiền tự doanh | VCI |
| `.block_trades()` | Giao dịch thỏa thuận | KBS |
| `.odd_lot()` | Giao dịch lô lẻ | KBS |
| `.volume_profile()` | Phân bố khối lượng theo giá | KBS |
| `.summary()` | Tổng hợp thông tin cổ phiếu | KBS |
| `.trade_history()` | Thống kê giao dịch lịch sử | KBS |

```python
df = mkt.equity("VCB").ohlcv(start="2025-01-01", end="2026-05-01")
quote = mkt.equity("HPG").quote()
foreign = mkt.equity("VIC").foreign_flow()
trades = mkt.equity("TCB").trades()
```

### 3.2 Bảng giá nhiều mã — `mkt.quote(list)`

```python
# Luôn dùng cách này thay vì lặp từng mã — giảm đáng kể số request
df_quotes = mkt.quote(["VIC", "TCB", "HPG", "VNM", "VCB"])
```

### 3.3 Chỉ số — `mkt.index(symbol)`

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.ohlcv(start, end)` | Điểm chỉ số lịch sử | KBS |
| `.quote()` | Điểm chỉ số hiện tại | KBS |
| `.summary()` | Tổng hợp thông tin chỉ số | KBS |

```python
df = mkt.index("VNINDEX").ohlcv(start="2025-01-01", end="2026-05-01")
quote = mkt.index("VNINDEX").quote()
```

### 3.4 ETF — `mkt.etf(symbol)`

Hỗ trợ đầy đủ như equity: `.ohlcv()`, `.quote()`, `.foreign_flow()`, `.trades()`, `.summary()`...

```python
df = mkt.etf("E1VFVN30").ohlcv(start="2025-01-01", end="2026-05-01")
foreign = mkt.etf("E1VFVN30").foreign_flow()
```

### 3.5 Hợp đồng tương lai — `mkt.futures(symbol)`

`.ohlcv()`, `.quote()`, `.trades()`, `.order_book()`, `.summary()`

```python
df = mkt.futures("VN30F2503").ohlcv(start="2026-02-01", end="2026-03-01")
```

### 3.6 Chứng quyền — `mkt.warrant(symbol)`

`.ohlcv()`, `.quote()`, `.trades()`, `.order_book()`, `.summary()`

```python
df = mkt.warrant("CACB2511").ohlcv(start="2026-02-01", end="2026-03-01")
```

### 3.7 Quỹ mở — `mkt.fund(symbol)`

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.history()` | Lịch sử NAV | FMARKET |
| `.top_holding()` | Top cổ phiếu nắm giữ | FMARKET |
| `.industry_holding()` | Nắm giữ theo ngành | FMARKET |
| `.asset_holding()` | Nắm giữ theo loại tài sản | FMARKET |

### 3.8 Thị trường quốc tế (thử nghiệm) — `mkt.crypto/forex/commodity(symbol)`

Chỉ hỗ trợ `.ohlcv()`, nguồn MSN. Dùng `ref.search.symbol()` để tìm đúng mã.

```python
df_btc = mkt.crypto("BTC").ohlcv(start="2026-01-01", end="2026-03-01")
df_fx = mkt.forex("USDVND").ohlcv(start="2026-01-01", end="2026-03-01")
df_gold = mkt.commodity("GC=F").ohlcv(start="2026-01-01", end="2026-03-01")
```

---

## 4. Fundamental Layer

**Vai trò**: Báo cáo tài chính & chỉ số tài chính doanh nghiệp — phục vụ phân tích cơ bản, định giá cổ phiếu.

**Khởi tạo**:
```python
from vnstock_data import Fundamental
fun = Fundamental()
```

| Hàm | Tham số | Mô tả | Nguồn |
|---|---|---|---|
| `.equity.income_statement(sym, period)` | `period="Q"/"Y"` | Báo cáo KQKD | KBS |
| `.equity.balance_sheet(sym, period)` | `period="Q"/"Y"` | Cân đối kế toán | KBS |
| `.equity.cash_flow(sym, period)` | `period="Q"/"Y"` | Lưu chuyển tiền tệ | KBS |
| `.equity.ratio(sym)` | — | Chỉ số tài chính | KBS |
| `.equity.note(sym)` | — | Thuyết minh BCTC | VCI |

**Cột dữ liệu chính**:

| Báo cáo | Cột |
|---|---|
| `income_statement` | `date, revenue, net_profit, eps, gross_profit...` |
| `balance_sheet` | `date, total_assets, current_assets, total_liabilities, equity...` |
| `cash_flow` | `date, operating_cash_flow, investing_cash_flow, financing_cash_flow, free_cash_flow` |
| `ratio` | `date, pe_ratio, pb_ratio, eps, roa, roe, debt_to_equity, current_ratio, quick_ratio, profit_margin...` |

```python
income = fun.equity.income_statement("TCB", period="Y")
balance = fun.equity.balance_sheet("TCB", period="Q")
cf = fun.equity.cash_flow("VNM", period="Y")
ratio = fun.equity.ratio("HPG")
notes = fun.equity.note("TCB")
```

---

## 5. Macro Layer

**Vai trò**: Dữ liệu kinh tế vĩ mô Việt Nam, tỷ giá, lãi suất, giá hàng hóa trong nước & quốc tế.

**Khởi tạo**:
```python
from vnstock_data import Macro
mac = Macro()
```

### 5.1 Kinh tế Việt Nam — `mac.economy()`

Tham số chung: `start`, `end`, `period` (`"month"/"quarter"/"year"`), `length` (số kỳ gần nhất).

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.gdp()` | Tăng trưởng GDP | MBK |
| `.cpi()` | Chỉ số giá tiêu dùng | MBK |
| `.fdi()` | Đầu tư trực tiếp nước ngoài | MBK |
| `.import_export()` | Xuất nhập khẩu | MBK |
| `.industry_prod()` | Sản xuất công nghiệp | MBK |
| `.retail()` | Doanh thu bán lẻ | MBK |
| `.money_supply()` | Cung tiền | MBK |
| `.population_labor()` | Dân số & lao động | MBK |

```python
gdp = mac.economy().gdp(start="2020-01", end="2026-03", period="quarter")
cpi = mac.economy().cpi(period="month", length=24)
fdi = mac.economy().fdi(period="month")
```

### 5.2 Tiền tệ & Lãi suất — `mac.currency()`

| Hàm | Tham số | Mô tả | Nguồn |
|---|---|---|---|
| `.exchange_rate()` | `period="day"/"month"`, `length` | Tỷ giá liên ngân hàng | MBK |
| `.interest_rate()` | `period`, `format="pivot"/"long"`, `length` | Lãi suất | MBK |

```python
fx = mac.currency().exchange_rate(period="day", length=90)
ir = mac.currency().interest_rate(period="month", format="long")
```

### 5.3 Hàng hóa — `mac.commodity()`

| Hàm | Market | Mô tả | Nguồn |
|---|---|---|---|
| `.gold(market)` | `"VN"`, `"GLOBAL"` | Giá vàng | — |
| `.gas(market)` | `"VN"`, `"GLOBAL"` | Xăng dầu / khí | — |
| `.oil_crude()` | — | Dầu thô WTI & Brent | SPL |
| `.coke()` | — | Than cốc | SPL |
| `.steel(market)` | `"VN"`, `"GLOBAL"` | Thép | — |
| `.iron_ore()` | — | Quặng sắt | SPL |
| `.fertilizer_ure()` | — | Phân URE | SPL |
| `.soybean()` | — | Đậu tương | SPL |
| `.corn()` | — | Ngô | SPL |
| `.sugar()` | — | Đường | SPL |
| `.pork(market)` | `"VN"`, `"CHINA"` | Thịt lợn hơi | — |

```python
gold = mac.commodity().gold(market="VN")
oil = mac.commodity().oil_crude()
steel = mac.commodity().steel(market="GLOBAL")
pork = mac.commodity().pork(market="VN")
```

---

## 6. Insights Layer

**Vai trò**: Xếp hạng top cổ phiếu + bộ lọc chứng khoán toàn thị trường với hàng trăm chỉ tiêu.

**Khởi tạo**:
```python
from vnstock_data import Insights
ins = Insights()
```

### 6.1 Bảng xếp hạng — `ins.ranking()`

| Hàm | Tham số | Mô tả | Nguồn |
|---|---|---|---|
| `.gainer()` | `index`, `limit` | Top tăng giá | VND |
| `.loser()` | `index`, `limit` | Top giảm giá | VND |
| `.value()` | `index`, `limit` | Top giá trị giao dịch | VND |
| `.volume()` | `index`, `limit` | Top khối lượng | VND |
| `.foreign_buy()` | `date`, `limit` | Top nước ngoài mua ròng | VND |
| `.foreign_sell()` | `date`, `limit` | Top nước ngoài bán ròng | VND |
| `.deal()` | `index`, `limit` | Top giao dịch thỏa thuận | VND |

```python
gainers = ins.ranking().gainer(index="VNINDEX", limit=10)
losers = ins.ranking().loser()
foreign_buy = ins.ranking().foreign_buy()
```

### 6.2 Bộ lọc chứng khoán — `ins.screener()`

| Hàm | Mô tả | Nguồn |
|---|---|---|
| `.criteria(lang)` | Danh sách giải nghĩa tên cột (`"vi"/"en"`) | VCI |
| `.filter()` | Dữ liệu screener toàn thị trường | VCI |

```python
criteria = ins.screener().criteria(lang="vi")
df_all = ins.screener().filter()

# Lọc thủ công bằng Pandas
cheap_good = df_all[(df_all['pe'] < 10) & (df_all['roe'] > 15)]
```

---

## 7. Analytics Layer

**Vai trò**: Định giá toàn thị trường — P/E, P/B lịch sử cho các chỉ số. Phục vụ backtest và đánh giá chu kỳ định giá.

**Khởi tạo**:
```python
from vnstock_data import Analytics
ana = Analytics()
```

| Hàm | Tham số | Mô tả | Nguồn |
|---|---|---|---|
| `.valuation(index).pe(duration)` | `duration="1Y"/"2Y"/"3Y"/"5Y"` | P/E lịch sử | VND |
| `.valuation(index).pb(duration)` | `duration` | P/B lịch sử | VND |
| `.valuation(index).evaluation(duration)` | `duration` | Tổng hợp P/E + P/B | VND |

```python
pe = ana.valuation("VNINDEX").pe(duration="5Y")
pb = ana.valuation("HNX").pb(duration="1Y")
eval_df = ana.valuation("VNINDEX").evaluation(duration="5Y")

# So sánh P/E hiện tại vs trung bình 5 năm
pe_current = pe['pe'].iloc[-1]
pe_avg = pe['pe'].mean()
```

---

## 8. Tiện ích

```python
from vnstock_data import show_api, show_doc

# Hiển thị toàn bộ cây API
show_api()

# Hiển thị cây API cho 1 layer cụ thể
show_api(Reference())
show_api(Market())

# Đọc docstring của 1 node
show_doc(Reference().equity)
show_doc(Market().equity("VCB"))
```

---

## 9. Tổng quan nguồn dữ liệu

| Ký hiệu | Nhà cung cấp | Vai trò |
|---|---|---|
| **KBS** | KB Securities | OHLCV, order book, trades, summary, margin ratio, chỉ số, ETF, CW, HĐTL |
| **VCI** | Viet Capital Securities | Báo cáo tài chính, sự kiện, tin tức, cổ đông, lãnh đạo, screener, ngành |
| **VND** | VNDirect | P/E, P/B lịch sử, xếp hạng top cổ phiếu |
| **MAS** | HOSE Market Status | Trạng thái thị trường (OPEN/CLOSED/ATO/ATC) |
| **MSN** | MSN Money | Dữ liệu quốc tế: crypto, forex, commodity, tìm kiếm toàn cầu |
| **MBK** | MacroBack | Vĩ mô: GDP, CPI, FDI, tỷ giá, lãi suất, xuất nhập khẩu... |
| **SPL** | Simplize | Hàng hóa: dầu thô, than, quặng sắt, nông sản quốc tế |
| **FMARKET** | FMarket | Quỹ mở: NAV, danh mục nắm giữ |

---

## 10. Bảng tra nhanh theo use case

| Nhu cầu | Layer | API |
|---|---|---|
| Kéo OHLCV 1 mã | Market | `mkt.equity(sym).ohlcv(start, end)` |
| Kéo OHLCV VN-Index | Market | `mkt.index("VNINDEX").ohlcv(start, end)` |
| Bảng giá nhiều mã cùng lúc | Market | `mkt.quote([sym1, sym2, ...])` |
| Danh sách VN30/VN100 | Reference | `ref.equity.list_by_group("VN100")` |
| Thành phần chỉ số | Reference | `ref.index.members("VN30")` |
| Báo cáo KQKD | Fundamental | `fun.equity.income_statement(sym, period="Y")` |
| Chỉ số P/E, ROE, D/E | Fundamental | `fun.equity.ratio(sym)` |
| Dòng tiền nước ngoài | Market | `mkt.equity(sym).foreign_flow()` |
| Tự doanh | Market | `mkt.equity(sym).proprietary_flow()` |
| Giao dịch thỏa thuận | Market | `mkt.equity(sym).block_trades()` |
| Order book | Market | `mkt.equity(sym).order_book()` |
| Top tăng/giảm giá | Insights | `ins.ranking().gainer()` / `.loser()` |
| Lọc P/E < 10, ROE > 15% | Insights | `ins.screener().filter()` + Pandas |
| P/E, P/B toàn thị trường | Analytics | `ana.valuation("VNINDEX").pe(duration="5Y")` |
| GDP, CPI, FDI | Macro | `mac.economy().gdp(period="quarter")` |
| Tỷ giá, lãi suất | Macro | `mac.currency().exchange_rate()` |
| Giá vàng, dầu, thép, thịt lợn | Macro | `mac.commodity().gold(market="VN")` |
| Thông tin công ty | Reference | `ref.company(sym).info()` |
| Cổ đông, lãnh đạo | Reference | `ref.company(sym).shareholders()` |
| Lịch cổ tức, ĐHCĐ | Reference | `ref.events.calendar(start, end, event_type="dividend")` |
| Tìm mã quốc tế | Reference | `ref.search.symbol("Bitcoin")` |
| NAV quỹ mở, danh mục | Market | `mkt.fund(sym).history()` / `.top_holding()` |
| ETF OHLCV | Market | `mkt.etf("E1VFVN30").ohlcv(start, end)` |
| HĐTL / Chứng quyền | Market | `mkt.futures(sym).ohlcv(start, end)` |
| Trạng thái thị trường | Reference | `ref.market.status()` |
| Khám phá API | — | `show_api()` / `show_doc(node)` |
