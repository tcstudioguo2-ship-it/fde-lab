"""
第 1 周作业：API 跑通验证（智谱 GLM / 通义千问，均走 OpenAI 兼容接口）

用法：
  1. 在虚拟环境里安装依赖：pip install openai
  2. 设置环境变量（PowerShell 当前窗口）：
       $env:ZHIPU_API_KEY="你的智谱key"
       $env:DASHSCOPE_API_KEY="你的通义key"
     注意：key 只放环境变量，不要写进代码——后面代码要进 GitHub，key 进仓库等于公开。
  3. 运行：python api_demo.py zhipu   或   python api_demo.py tongyi

验收标准：普通调用有一句完整回复 + 流式调用逐字输出，即算跑通。
"""

import os
import sys

from openai import OpenAI

PROVIDERS = {
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "key_env": "ZHIPU_API_KEY",
        "model": "glm-4-flash",
    },
    "tongyi": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": "DASHSCOPE_API_KEY",
        "model": "qwen-turbo",
    },
}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "zhipu"
    cfg = PROVIDERS[name]
    api_key = os.environ.get(cfg["key_env"])
    if not api_key:
        print("缺少环境变量 " + cfg["key_env"] + "，先在 PowerShell 里设置它")
        return

    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])

    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": "用一句话介绍你自己"}],
    )
    print("[普通调用]", resp.choices[0].message.content)

    print("[流式调用]", end="", flush=True)
    stream = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": "从1数到5，每个数字一行"}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()
    print("完成：普通调用 + 流式调用都通了")


if __name__ == "__main__":
    main()
