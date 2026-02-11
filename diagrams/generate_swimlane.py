#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成黄金基线建立流程泳道图
"""

import base64
import urllib.request
import zlib
import json
import os

# Mermaid 泳道图定义
mermaid_code = """
flowchart LR
  subgraph S["系统 (System)"]
    direction TB
    S1["按Header范围<br/>过滤基线列表"]
    S2["拉取历史数据<br/>(数据仓/中心库)"]
    S3["预处理/对齐<br/>/重采样"]
    S4["生成预览叠加图"]
    S5["离线回放验证<br/>偏差%分布/误报率"]
    S6["发布/生效<br/>写入版本与审计日志"]
    S7["运行中引用<br/>Published版本<br/>计算偏差%/归类"]
    S8["支持回滚到旧版本"]
  end

  subgraph M["老师傅 (工艺/操作)"]
    direction TB
    M1["挑选最好的一炉/一天<br/>【选优】"]
    M2["确认曲线是否代表<br/>调功最顺/节拍最稳<br/>【验收】"]
    M3["提出阈值建议<br/>(如 5%关注/15%纠偏)"]
  end

  subgraph E["工艺工程师/数据工程师"]
    direction TB
    E1["确认信号清单<br/>功率/电压/温度等"]
    E2["确认范围<br/>设备/产线/厂区"]
    E3["确认验证样本<br/>最近N天/炉"]
  end

  subgraph A["厂长/负责人 (审批)"]
    direction TB
    A1["审批发布"]
    A2["决定替换/退役/回滚"]
  end

  M1 --> S2
  S2 --> S3
  S3 --> S4
  S4 --> M2
  E1 --> S3
  E2 --> S1
  M3 --> S5
  E3 --> S5
  M2 --> S5
  S5 --> A1
  A1 --> S6
  S6 --> S7
  S7 --> A2
  A2 --> S8

  style S fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
  style M fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
  style E fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
  style A fill:#fce4ec,stroke:#c2185b,stroke-width:2px
  
  style M1 fill:#ffe0b2,stroke:#ef6c00
  style M2 fill:#ffe0b2,stroke:#ef6c00
  style M3 fill:#ffe0b2,stroke:#ef6c00
  style E1 fill:#c8e6c9,stroke:#2e7d32
  style E2 fill:#c8e6c9,stroke:#2e7d32
  style E3 fill:#c8e6c9,stroke:#2e7d32
  style A1 fill:#f8bbd9,stroke:#c2185b
  style A2 fill:#f8bbd9,stroke:#c2185b
  style S1 fill:#bbdefb,stroke:#1565c0
  style S2 fill:#bbdefb,stroke:#1565c0
  style S3 fill:#bbdefb,stroke:#1565c0
  style S4 fill:#bbdefb,stroke:#1565c0
  style S5 fill:#bbdefb,stroke:#1565c0
  style S6 fill:#bbdefb,stroke:#1565c0
  style S7 fill:#bbdefb,stroke:#1565c0
  style S8 fill:#bbdefb,stroke:#1565c0
"""


def generate_mermaid_url(code, fmt="svg"):
    """生成 mermaid.ink URL"""
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
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(filename, "wb") as f:
                f.write(response.read())
        print(f"[OK] Saved: {filename}")
        return True
    except Exception as e:
        print(f"[FAIL] Download failed: {e}")
        return False


if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.abspath(__file__))

    # 生成 SVG
    svg_url = generate_mermaid_url(mermaid_code, "svg")
    svg_path = os.path.join(output_dir, "golden_baseline_swimlane.svg")
    download_image(svg_url, svg_path)

    # 生成 PNG
    png_url = generate_mermaid_url(mermaid_code, "img")
    png_path = os.path.join(output_dir, "golden_baseline_swimlane.png")
    download_image(png_url, png_path)

    print(f"\nOutput directory: {output_dir}")
