# 实时监控与纠偏业务流程图

## Mermaid 源码

```mermaid
flowchart TD
    subgraph L0["L0: 物理感知层"]
        A[🏭 熔炼开始] --> B[📡 vCAN采集数据<br/>炉功率/电压/温度<br/>每秒一笔]
    end

    subgraph L1["L1: EDC事实核心"]
        B --> C[(💾 写入RocksDB<br/>时序数据库)]
    end

    subgraph L2["L2: AI分析引擎"]
        C --> D[📊 读取当前实时值]
        E[(🏆 黄金基线库)] --> F[📈 读取基线对应时间点]
        D --> G{🔢 计算偏差率<br/>偏差% = |实际-基线|/基线}
        F --> G
        
        G --> H{📏 偏差判定}
        
        H -->|≤10%| I[🟢 绿灯<br/>正常]
        H -->|10%~15%| J[🟡 黄灯<br/>警告]
        H -->|>15%| K[🔴 红灯<br/>异常]
        
        I --> L[✅ 继续监控]
        J --> M[📝 记录日志<br/>持续观察]
        
        K --> N{⏱️ 是否持续超标?<br/>连续≥10秒}
        
        N -->|否| O[👁️ 继续观察<br/>等待恢复]
        N -->|是| P[📋 生成纠偏任务单]
    end

    subgraph L3["L3: 决策应用层"]
        P --> Q[📊 附加波形对比图<br/>黄金曲线 vs 实际曲线]
        Q --> R[📱 推送通知<br/>现场HMI/手机]
        R --> S[👷 等待人员处置...]
    end

    L --> B
    M --> B
    O --> B
    S -.->|处置完成后| B

    style A fill:#e1f5fe,stroke:#01579b
    style B fill:#e1f5fe,stroke:#01579b
    style C fill:#fff9c4,stroke:#fbc02d
    style E fill:#c8e6c9,stroke:#2e7d32
    style I fill:#c8e6c9,stroke:#2e7d32
    style J fill:#fff9c4,stroke:#fbc02d
    style K fill:#ffcdd2,stroke:#c62828
    style P fill:#ffcdd2,stroke:#c62828
    style R fill:#f3e5f5,stroke:#7b1fa2
    style S fill:#f3e5f5,stroke:#7b1fa2
```

## 流程说明

### 1. 数据采集 (L0)
- vCAN模块每秒采集一笔数据（炉功率、电压、温度）
- 数据格式：{CID, Timestamp, Value}

### 2. 数据存储 (L1)
- 原始数据写入 EDC RocksDB 时序数据库
- 数据不可篡改，毫秒级对齐

### 3. 偏差比对 (L2)
- **实时比对**：每秒采集的数据立即与黄金基线比对
- **偏差计算**：偏差% = |实际值 - 基线值| / 基线值 × 100%
- **三档判定**：
  - 🟢 绿灯（≤10%）：正常，继续监控
  - 🟡 黄灯（10%~15%）：警告，记录日志但不发单
  - 🔴 红灯（>15%）：异常，进入持续超标判定

### 4. 持续超标判定
- **防误报机制**：只有连续超标≥10秒才发纠偏单
- 瞬时波动不会触发发单

### 5. 纠偏任务 (L3)
- 生成纠偏任务单
- 附加波形对比图（黄金曲线 vs 实际曲线）
- 推送通知到现场HMI或手机
