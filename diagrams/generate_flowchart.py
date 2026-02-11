#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成实时监控与纠偏业务流程图
使用 mermaid.ink 在线服务渲染
"""

import base64
import urllib.request
import urllib.parse
import zlib
import os

# Mermaid 流程图定义
mermaid_code = """
flowchart TD
    subgraph L0["L0: 物理感知层"]
        A["熔炼开始"]
        B["vCAN采集数据<br/>炉功率/电压/温度<br/>每秒一笔"]
        A --> B
    end

    subgraph L1["L1: EDC事实核心"]
        C[("写入RocksDB<br/>时序数据库")]
    end

    subgraph L2["L2: AI分析引擎"]
        D["读取当前实时值"]
        E[("黄金基线库")]
        F["读取基线对应时间点"]
        G{"计算偏差率<br/>偏差% = |实际-基线|/基线"}
        H{"偏差判定"}
        I["绿灯<br/>正常"]
        J["黄灯<br/>警告"]
        K["红灯<br/>异常"]
        L["继续监控"]
        M["记录日志<br/>持续观察"]
        N{"持续超标?<br/>连续>=10秒"}
        O["继续观察<br/>等待恢复"]
        P["生成纠偏任务单"]
        
        E --> F
        D --> G
        F --> G
        G --> H
        H -->|"<=10%"| I
        H -->|"10%-15%"| J
        H -->|">15%"| K
        I --> L
        J --> M
        K --> N
        N -->|"否"| O
        N -->|"是"| P
    end

    subgraph L3["L3: 决策应用层"]
        Q["附加波形对比图<br/>黄金曲线 vs 实际曲线"]
        R["推送通知<br/>现场HMI/手机"]
        S["等待人员处置"]
        
        Q --> R
        R --> S
    end

    B --> C
    C --> D
    P --> Q
    L --> B
    M --> B
    O --> B
    S -.->|"处置完成后"| B

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
"""


def generate_mermaid_url(code, fmt="svg"):
    """生成 mermaid.ink URL"""
    import json

    json_str = json.dumps({"code": code, "mermaid": {"theme": "default"}})
    compressed = zlib.compress(json_str.encode("utf-8"), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode("utf-8")
    return f"https://mermaid.ink/{fmt}/pako:{encoded}"


def download_image(url, filename):
    """下载图片"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(filename, "wb") as f:
                f.write(response.read())
        print(f"[OK] Saved: {filename}")
        return True
    except Exception as e:
        print(f"[FAIL] Download failed: {e}")
        return False


if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.abspath(__file__))

    # 生成 SVG URL
    svg_url = generate_mermaid_url(mermaid_code, "svg")
    print(f"SVG URL generated (length: {len(svg_url)})")

    # 生成 PNG URL
    png_url = generate_mermaid_url(mermaid_code, "img")
    print(f"PNG URL generated (length: {len(png_url)})")

    # 下载 SVG
    svg_path = os.path.join(output_dir, "realtime_monitor_flowchart.svg")
    download_image(svg_url, svg_path)

    # 下载 PNG
    png_path = os.path.join(output_dir, "realtime_monitor_flowchart.png")
    download_image(png_url, png_path)

    print(f"\nOutput directory: {output_dir}")
