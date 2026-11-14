# 模型利用率对照

两边使用同一份提示词、同一份工具说明、同一个模型接口，并且各跑两个任务。唯一要算的数是模型利用率：

```text
U = Tbusy / Twall
```

`Tbusy` 是每一次模型请求从开始到返回的时间之和。实验前提是这些请求互不重叠，所以可以直接相加。`Twall` 是两个任务提交之后，到两个任务都完成的墙钟时间。空转时间是 `Twall - Tbusy`。

一次模型请求是一次 API 调用，不是一整道复杂任务。工具等待、读文件和跑命令不计入 `Tbusy`。

## 两组任务

`mechanism` 用可控等待。先测量单次模型请求，再把工具等待设为较高分位数的 1.75 倍。等待要长于一次模型请求，另一份任务才有机会在这段时间里使用模型。

`real` 使用目录列举和一次普通读文件。这些工具可能比模型请求更快。它们照实计算利用率，用来看真实耗时下的结果。

请求时间如果重叠，这一轮不符合「同一时刻最多一个模型请求」，分析时记为无效，不进入平均利用率。

## 运行

在仓库根目录执行。模拟模型不需要密钥，用来检查实验本身：

```text
python example/utilization/calibrate.py --mock --samples 5
python example/utilization/run_linope.py --group mechanism --nonce sample --seconds 0.2 --log example/utilization/runs/linope.jsonl --mock
node example/utilization/run_harness.mjs --group mechanism --nonce sample --seconds 0.2 --log example/utilization/runs/harness.jsonl --mock
python example/utilization/analyze.py example/utilization/runs
```

真实模型把 `--mock` 换成上游地址，并提供密钥：

```text
set UTILIZATION_UPSTREAM=https://api.deepseek.com/v1
set OPENAI_API_KEY=你的密钥
set UTILIZATION_MODEL=deepseek-flash
python example/utilization/calibrate.py --samples 5 --upstream %UTILIZATION_UPSTREAM%
```

把打印出的 `wait_seconds` 传给 `--seconds`。deepseek-harness 的包没有安装在这棵树里，因此 `run_harness.mjs` 按 `agent.ts` 的 `step()` 顺序调用同一个代理：先等模型响应结束，再执行工具，再请求一次。它不额外加锁。

原始 JSONL 写在 `example/utilization/runs/`。
