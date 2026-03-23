# InfraHealthProbe

基礎設施健康偵測平台 — 以清單驅動的探測引擎，用於監控各據點的伺服器、網路及服務狀態。

## 功能特色

- **多協定探測** — 支援 ICMP Ping、DNS、TCP、HTTP/HTTPS、SSH 等探測類型
- **清單驅動** — 透過 JSON/CSV 定義監控目標，探測引擎自動載入並標準化
- **健康評分** — 加權計算每個目標的健康分數，搭配 GOOD/FAIR/POOR/SEVERE 判定等級
- **根因提示** — 規則式根因分析引擎（7 條規則），自動產生問題診斷建議
- **多種輸出** — 支援 CSV、JSON Lines、獨立 HTML 報告
- **排程模式** — 可設定間隔重複執行探測，搭配失敗重試機制
- **Profile 設定** — 透過 JSON Profile 定義探測項目、逾時與閾值，CLI 可覆寫
- **WiFi 整合** — 透過 `wifi_adapter.py` 消費 Collect-WiFiMeetingTest 的 JSONL/CSV 輸出

## 系統需求

- Python 3.10+
- 無外部必要相依套件（AI 與 SharePoint 為選用擴充）

## 安裝

```bash
# 安裝（含開發工具）
pip install -e ".[dev]"

# 僅安裝核心
pip install -e .
```

## 快速開始

```bash
# 基本執行 — 指定清單檔與輸出目錄
python -m infra --inventory inventory/targets.json --output-dir ./output

# 篩選特定地點與探測類型
python -m infra -i inventory/targets.json --location Taiwan --probes ping dns

# 使用自訂 Profile
python -m infra -i inventory/targets.json -p profiles/default.json -o ./output

# 排程模式（每 5 分鐘重複執行，Ctrl+C 停止）
python -m infra -i inventory/targets.json --mode scheduled --interval 5
```

## 專案結構

```
InfraHealthProbe/
├── infra/                       # 核心平台 (Python 3.10+)
│   ├── __main__.py              # python -m infra 進入點
│   ├── cli.py                   # CLI 參數解析 (argparse)
│   ├── config.py                # Profile 載入 + CLI 合併
│   ├── runner.py                # 探測調度器 (ThreadPoolExecutor)
│   ├── inventory/               # 目標清單提供者
│   │   ├── core.py              # Target dataclass、驗證、去重、合併、篩選
│   │   ├── local_json.py        # JSON 檔案提供者
│   │   └── local_csv.py         # CSV 檔案提供者
│   ├── probes/                  # 探測引擎
│   │   ├── __init__.py          # 探測註冊表 (PROBE_REGISTRY)
│   │   ├── base.py              # BaseProbe ABC + ProbeResult + ProbeStatus
│   │   ├── ping.py              # ICMP Ping（支援 Linux/Windows）
│   │   ├── dns.py               # DNS 解析計時
│   │   ├── tcp.py               # TCP 埠檢查（多埠）
│   │   ├── http.py              # HTTP/HTTPS 回應 + TLS 計時
│   │   ├── ssh.py               # SSH 可達性 + Banner 偵測
│   │   └── wifi_adapter.py      # WiFi 診斷工具輸出適配器
│   ├── analytics/               # 判定、評分、根因提示
│   │   ├── verdict.py           # 單一指標判定 (GOOD/FAIR/POOR/SEVERE)
│   │   ├── scoring.py           # 加權健康分數計算
│   │   ├── hints.py             # 規則式根因提示（7 條規則）
│   │   └── summary.py           # 摘要報告（管理層 + 技術層）
│   ├── output/                  # 輸出寫入器
│   │   ├── csv_writer.py        # ProbeResult → CSV
│   │   ├── json_writer.py       # ProbeResult → JSON Lines
│   │   ├── html_report.py       # 獨立 HTML 報告（內嵌 CSS）
│   │   └── manifest.py          # 執行元資料 → JSON
│   └── scheduler.py             # 排程模式（重複探測週期）
├── schemas/                     # JSON Schema 定義
├── profiles/                    # 探測 Profile（依目標類型）
├── inventory/                   # 目標清單資料檔
├── tests/                       # pytest 測試套件
└── docs/                        # 架構與規劃文件
```

## 清單格式

目標清單支援 JSON 與 CSV 格式。JSON 範例：

```json
{
  "TargetId": "TW-TPEIP-CACHE-YAMI",
  "Type": "Export",
  "Location": "Taiwan/TPEIP",
  "Function": "Local Cache Server",
  "Hostname": "yami",
  "FQDN": "yami.example.com",
  "IPAddress": "155.161.252.18",
  "OS": "Linux",
  "Ports": [22, 80, 443],
  "ProbeProfile": "cache-server-linux",
  "Enabled": true,
  "Priority": "Normal",
  "OwnerGroup": "ACCS"
}
```

完整範例見 `inventory/targets.example.json`。

## Profile 設定

Profile 定義探測項目、逾時與健康閾值。範例（`profiles/default.json`）：

```json
{
  "ProfileName": "default",
  "Probes": {
    "ping": { "enabled": true, "timeout_ms": 5000, "count": 4 },
    "dns":  { "enabled": true, "timeout_ms": 5000 },
    "tcp":  { "enabled": true, "timeout_ms": 5000 },
    "http": { "enabled": true, "timeout_ms": 10000 }
  },
  "Thresholds": {
    "ping_latency_ms": { "good": 5, "fair": 15, "poor": 30 },
    "dns_latency_ms":  { "good": 150, "fair": 300, "poor": 500 }
  }
}
```

## 測試

```bash
# 執行所有測試（Tier 1 — 無需網路）
pytest tests/

# 執行特定測試檔
pytest tests/test_inventory.py
pytest tests/test_probes.py
pytest tests/test_config.py
```

### 測試分層策略

| 層級 | 範圍 | 成本 | 速度 |
|------|------|------|------|
| Tier 1 | 清單、分析、設定、探測註冊表 | 免費 | 秒級 |
| Tier 2 | 真實網路探測整合測試 | 免費（需網路） | 分鐘級 |
| Tier 3 | AI 分析品質評估 | API 費用 | 分鐘級 |

## 開發里程碑

| 里程碑 | 重點 | 交付項目 |
|--------|------|----------|
| M0 | 基礎架構 | `infra/` 重新命名、探測註冊表、Profile 載入器 |
| M1 | 可執行 | cli.py、runner.py、CSV 輸出、manifest |
| M2 | 具診斷價值 | 評分、根因提示、摘要、JSON 輸出 |
| M3 | 可營運 | 排程模式、HTML 報告、重試邏輯 |
| M4 | 擴充 | AI 分析、ServiceNow、SharePoint、Raspberry Pi |

## 授權

內部專案。
